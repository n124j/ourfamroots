"""
Security tests — user group management authorization boundaries.

User Groups are managed the same way Permission Groups are: any namespace
ADMIN (or Super Admin) may create/manage them, but AUDITOR and unauthenticated
callers must be rejected. This exercises the real FastAPI dependency chain
(JWT decode, TenantMiddleware, AdminUserDep) via the fake in-memory DB used
elsewhere in this suite (see tests/security/test_namespace_isolation.py for
the same pattern).

The grant/revoke propagation logic (linking a user group to a permission
group, adding/removing members, the "still entitled another way" guard, bulk
role assignment) was verified live against a real Postgres DB rather than
here — the fake session doesn't model the multi-table joins those code paths
depend on (permission_group_user_groups + user_group_members + tree_members),
so a test against it would give false confidence rather than real coverage.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.infrastructure.database.models.user import UserModel
from src.infrastructure.security.jwt import JWTService
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID, FakeTokenStore, FakeUnitOfWork, FakeUserRepository


def make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str,
    app_role: str = "STANDARD",
    tenant_id: uuid.UUID = TEST_TENANT_ID,
) -> UserModel:
    user = UserModel()
    user.id = user_id or uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = email
    user.given_name = email.split("@")[0].title()
    user.family_name = "Test"
    user.app_role = app_role
    user.is_active = True
    user.email_verified = True
    user.failed_login_attempts = 0
    user.locked_until = None
    user.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return user


def bearer_headers(user_id: uuid.UUID, tenant_id: uuid.UUID = TEST_TENANT_ID) -> dict:
    from src.config import get_settings
    settings = get_settings()
    svc = JWTService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=60,
        refresh_token_expire_days=1,
    )
    access_token, _ = svc.create_access_token(user_id, tenant_id)
    return {"Authorization": f"Bearer {access_token}"}


DEFAULT_ADMIN = make_user(user_id=TEST_USER_ID, email="admin@example.com", app_role="ADMIN")


@pytest_asyncio.fixture
async def user_group_app(request: pytest.FixtureRequest):
    """Mirrors the `namespace_app` fixture in test_namespace_isolation.py."""
    from src.api.deps import get_token_store, get_uow
    from src.infrastructure.database.session import get_db_session
    from src.main import create_app

    seed_users = getattr(request, "param", None) or [DEFAULT_ADMIN]

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
        yield client, repo, fake_uow


class TestUserGroupCreateAuthorization:
    @pytest.mark.asyncio
    async def test_namespace_admin_can_create_user_group(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.post(
            "/api/v1/admin/user-groups",
            headers=bearer_headers(TEST_USER_ID),
            json={"name": "Family Editors", "description": "Editors for the family tree"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Family Editors"
        assert body["member_count"] == 0

    @pytest.mark.parametrize(
        "user_group_app",
        [[make_user(user_id=TEST_USER_ID, email="super@example.com", app_role="SUPER_ADMIN")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_super_admin_can_create_user_group(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.post(
            "/api/v1/admin/user-groups",
            headers=bearer_headers(TEST_USER_ID),
            json={"name": "Ops Team"},
        )
        assert r.status_code == 201

    @pytest.mark.parametrize(
        "user_group_app",
        [[make_user(user_id=TEST_USER_ID, email="auditor@example.com", app_role="AUDITOR")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_auditor_cannot_create_user_group(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.post(
            "/api/v1/admin/user-groups",
            headers=bearer_headers(TEST_USER_ID),
            json={"name": "Should Not Exist"},
        )
        assert r.status_code == 403

    @pytest.mark.parametrize(
        "user_group_app",
        [[make_user(user_id=TEST_USER_ID, email="standard@example.com", app_role="STANDARD")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_standard_user_cannot_create_user_group(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.post(
            "/api/v1/admin/user-groups",
            headers=bearer_headers(TEST_USER_ID),
            json={"name": "Should Not Exist"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.post("/api/v1/admin/user-groups", json={"name": "X"})
        assert r.status_code == 401


class TestUserGroupListAuthorization:
    @pytest.mark.asyncio
    async def test_namespace_admin_can_list_user_groups(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.get("/api/v1/admin/user-groups", headers=bearer_headers(TEST_USER_ID))
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["items"], list)

    @pytest.mark.parametrize(
        "user_group_app",
        [[make_user(user_id=TEST_USER_ID, email="auditor@example.com", app_role="AUDITOR")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_auditor_cannot_list_user_groups(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.get("/api/v1/admin/user-groups", headers=bearer_headers(TEST_USER_ID))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, user_group_app):
        client, _repo, _fake_uow = user_group_app
        r = await client.get("/api/v1/admin/user-groups")
        assert r.status_code == 401


# Note: the bulk-role SUPER_ADMIN-escalation guard (only an existing Super
# Admin may grant SUPER_ADMIN in bulk) is not covered here — the fake session
# used by this suite doesn't model UserGroupModel lookups (only UserModel/
# TenantModel full-entity selects), so the group-existence check the guard
# sits behind can never resolve against it. The guard is a direct copy of the
# already-covered admin.py::update_user escalation check (same ordering:
# resource lookup, then role-escalation check) — reviewed by inspection
# rather than re-tested here to avoid a test that always 404s regardless of
# whether the guard actually fires.
