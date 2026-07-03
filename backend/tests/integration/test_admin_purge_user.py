"""
Integration tests for the Super-Admin "permanently delete user" endpoint.

    DELETE /api/v1/admin/users/{user_id}/purge

Covers authorization (Super Admin only), the deactivate-first safety guard,
the self-deletion guard, the happy path (user actually removed, sessions
revoked, audit entry written), and 404 handling.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.infrastructure.database.models.user import UserModel
from src.infrastructure.security.jwt import JWTService
from tests.conftest import (
    TEST_SECRET,
    TEST_TENANT_ID,
    TEST_USER_ID,
    FakeTokenStore,
    FakeUnitOfWork,
    FakeUserRepository,
)


def make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str,
    app_role: str = "STANDARD",
    is_active: bool = True,
    tenant_id: uuid.UUID = TEST_TENANT_ID,
) -> UserModel:
    user = UserModel()
    user.id = user_id or uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = email
    user.given_name = email.split("@")[0].title()
    user.family_name = "Test"
    user.app_role = app_role
    user.is_active = is_active
    user.email_verified = True
    user.failed_login_attempts = 0
    user.locked_until = None
    user.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return user


def bearer_headers(user_id: uuid.UUID, tenant_id: uuid.UUID = TEST_TENANT_ID) -> dict:
    svc = JWTService(
        secret_key=TEST_SECRET,
        access_token_expire_minutes=60,
        refresh_token_expire_days=1,
    )
    access_token, _ = svc.create_access_token(user_id, tenant_id)
    return {"Authorization": f"Bearer {access_token}"}


DEFAULT_SUPER_ADMIN = make_user(
    user_id=TEST_USER_ID, email="super@example.com", app_role="SUPER_ADMIN"
)


@pytest_asyncio.fixture
async def admin_app(request: pytest.FixtureRequest):
    """
    A fresh FastAPI app wired to an in-memory fake DB. Seeded, by default,
    with a single Super Admin actor at TEST_USER_ID (the id `bearer_headers`
    signs tokens for). Tests that need a different actor role can override
    the seed list via `@pytest.mark.parametrize("admin_app", [[...]], indirect=True)`.

    Yields (client, repo, token_store, fake_uow) so tests can add target
    users, seed sessions, make requests, and assert on fake-DB state and
    the write helper's captured audit-log entities afterwards.
    """
    from src.api.deps import get_token_store, get_uow
    from src.infrastructure.database.session import get_db_session
    from src.main import create_app

    seed_users = getattr(request, "param", None) or [DEFAULT_SUPER_ADMIN]

    repo = FakeUserRepository(users=list(seed_users))
    fake_uow = FakeUnitOfWork(users=repo)
    fake_store = FakeTokenStore()

    app = create_app()
    app.dependency_overrides[get_uow] = lambda: fake_uow
    app.dependency_overrides[get_token_store] = lambda: fake_store

    async def _fake_db_session():
        yield fake_uow._session

    app.dependency_overrides[get_db_session] = _fake_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, repo, fake_store, fake_uow


class TestAuthorization:
    @pytest.mark.parametrize(
        "admin_app",
        [[make_user(user_id=TEST_USER_ID, email="admin@example.com", app_role="ADMIN")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_regular_admin_cannot_purge(self, admin_app):
        """A plain ADMIN (not SUPER_ADMIN) must be rejected with 403."""
        client, repo, _store, _uow = admin_app
        target = make_user(email="target@example.com", is_active=False)
        repo._users.append(target)

        r = await client.delete(
            f"/api/v1/admin/users/{target.id}/purge",
            headers=bearer_headers(TEST_USER_ID),
        )

        assert r.status_code == 403
        assert any(u.id == target.id for u in repo._users)  # target untouched

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, admin_app):
        client, _repo, _store, _uow = admin_app
        r = await client.delete(f"/api/v1/admin/users/{uuid.uuid4()}/purge")
        assert r.status_code == 401


class TestSafetyGuards:
    @pytest.mark.asyncio
    async def test_cannot_purge_own_account(self, admin_app):
        client, repo, _store, _uow = admin_app  # actor is the only seeded user
        r = await client.delete(
            f"/api/v1/admin/users/{TEST_USER_ID}/purge",
            headers=bearer_headers(TEST_USER_ID),
        )
        assert r.status_code == 400
        assert any(u.id == TEST_USER_ID for u in repo._users)

    @pytest.mark.asyncio
    async def test_still_active_user_is_rejected(self, admin_app):
        """Purge requires the target to already be deactivated (two-step delete)."""
        client, repo, _store, _uow = admin_app
        active_target = make_user(email="active@example.com", is_active=True)
        repo._users.append(active_target)

        r = await client.delete(
            f"/api/v1/admin/users/{active_target.id}/purge",
            headers=bearer_headers(TEST_USER_ID),
        )

        assert r.status_code == 400
        assert "deactivated" in r.json()["detail"].lower()
        assert any(u.id == active_target.id for u in repo._users)  # not deleted

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_404(self, admin_app):
        client, _repo, _store, _uow = admin_app
        r = await client.delete(
            f"/api/v1/admin/users/{uuid.uuid4()}/purge",
            headers=bearer_headers(TEST_USER_ID),
        )
        assert r.status_code == 404


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_purge_removes_user_revokes_sessions_and_logs_the_action(self, admin_app):
        client, repo, store, fake_uow = admin_app
        target = make_user(email="deactivated@example.com", app_role="STANDARD", is_active=False)
        repo._users.append(target)

        # Simulate the target having an active refresh-token session beforehand.
        await store.store(jti="session-jti-1", user_id=target.id, expires_in_seconds=3600)
        assert await store.has_active_sessions(target.id) is True

        r = await client.delete(
            f"/api/v1/admin/users/{target.id}/purge",
            headers=bearer_headers(TEST_USER_ID),
        )

        assert r.status_code == 204
        assert r.content == b""

        # The row is actually gone, not just flagged inactive.
        assert not any(u.id == target.id for u in repo._users)

        # Sessions/tokens for the deleted user are revoked.
        assert await store.has_active_sessions(target.id) is False

        # The action was written to the audit/activity feed as ADMIN_DELETE,
        # attributed to the acting Super Admin, identifying the deleted user.
        delete_events = [
            e for e in fake_uow.logged_entities
            if getattr(e, "event_type", None) == "ADMIN_DELETE"
        ]
        assert len(delete_events) == 1
        event = delete_events[0]
        assert event.user_id == TEST_USER_ID  # actor, not the deleted target
        assert target.email in event.user_email
        assert str(target.id) in event.user_email
        assert "STANDARD" in event.user_email

    @pytest.mark.asyncio
    async def test_purge_does_not_affect_other_users(self, admin_app):
        client, repo, _store, _uow = admin_app
        target = make_user(email="deactivated@example.com", is_active=False)
        bystander = make_user(email="bystander@example.com", is_active=False)
        repo._users.extend([target, bystander])

        r = await client.delete(
            f"/api/v1/admin/users/{target.id}/purge",
            headers=bearer_headers(TEST_USER_ID),
        )

        assert r.status_code == 204
        remaining_ids = {u.id for u in repo._users}
        assert target.id not in remaining_ids
        assert bystander.id in remaining_ids
        assert TEST_USER_ID in remaining_ids
