"""
Security tests — namespace management authorization boundaries.

Namespace CRUD (POST/GET/PATCH /admin/namespaces) must be Super-Admin-only:
a plain namespace ADMIN must never be able to create, list, or rename
namespaces, even though they administer users within their own namespace.

These exercise the real FastAPI dependency chain (JWT decode, TenantMiddleware,
require_super_admin) end-to-end via the fake in-memory DB used elsewhere in
this suite (see tests/integration/test_admin_purge_user.py for the same
pattern) — deeper namespace-invitation flows (invite/accept, cross-namespace
transfer) are covered by manual verification against a real Postgres DB, since
the fake session here doesn't model NamespaceInvitationModel's joined queries.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.infrastructure.database.models.tenant import TenantModel
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
    # Sign with the app's actual configured secret (like the shared `auth_headers`
    # fixture does) rather than a hardcoded test constant — a hardcoded secret
    # only works when JWT_SECRET_KEY is unset in the environment, which isn't
    # true everywhere this suite runs (e.g. a dev container with a real secret
    # already exported).
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


DEFAULT_SUPER_ADMIN = make_user(user_id=TEST_USER_ID, email="super@example.com", app_role="SUPER_ADMIN")


@pytest_asyncio.fixture
async def namespace_app(request: pytest.FixtureRequest):
    """Mirrors the `admin_app` fixture in test_admin_purge_user.py."""
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
        yield client, repo, fake_uow


class TestNamespaceCreateAuthorization:
    @pytest.mark.asyncio
    async def test_super_admin_can_create_namespace(self, namespace_app):
        client, _repo, fake_uow = namespace_app
        r = await client.post(
            "/api/v1/admin/namespaces",
            headers=bearer_headers(TEST_USER_ID),
            json={"name": "Smith Family", "slug": "smith-family"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["slug"] == "smith-family"
        assert body["is_global"] is False
        assert any(t.slug == "smith-family" for t in fake_uow._tenants._tenants)

    @pytest.mark.parametrize(
        "namespace_app",
        [[make_user(user_id=TEST_USER_ID, email="admin@example.com", app_role="ADMIN")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_regular_admin_cannot_create_namespace(self, namespace_app):
        client, _repo, fake_uow = namespace_app
        r = await client.post(
            "/api/v1/admin/namespaces",
            headers=bearer_headers(TEST_USER_ID),
            json={"name": "Hacker Namespace", "slug": "hacker-ns"},
        )
        assert r.status_code == 403
        assert not any(t.slug == "hacker-ns" for t in fake_uow._tenants._tenants)

    @pytest.mark.parametrize(
        "namespace_app",
        [[make_user(user_id=TEST_USER_ID, email="auditor@example.com", app_role="AUDITOR")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_auditor_cannot_create_namespace(self, namespace_app):
        client, _repo, _fake_uow = namespace_app
        r = await client.post(
            "/api/v1/admin/namespaces",
            headers=bearer_headers(TEST_USER_ID),
            json={"name": "Hacker Namespace", "slug": "hacker-ns-2"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, namespace_app):
        client, _repo, _fake_uow = namespace_app
        r = await client.post(
            "/api/v1/admin/namespaces", json={"name": "X", "slug": "x"},
        )
        assert r.status_code == 401


class TestNamespaceListAuthorization:
    @pytest.mark.asyncio
    async def test_super_admin_can_list_namespaces(self, namespace_app):
        client, _repo, _fake_uow = namespace_app
        r = await client.get("/api/v1/admin/namespaces", headers=bearer_headers(TEST_USER_ID))
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["items"], list)
        assert body["total"] >= 1

    @pytest.mark.parametrize(
        "namespace_app",
        [[make_user(user_id=TEST_USER_ID, email="admin@example.com", app_role="ADMIN")]],
        indirect=True,
    )
    @pytest.mark.asyncio
    async def test_regular_admin_cannot_list_namespaces(self, namespace_app):
        """Only a Super Admin can see across all namespaces."""
        client, _repo, _fake_uow = namespace_app
        r = await client.get("/api/v1/admin/namespaces", headers=bearer_headers(TEST_USER_ID))
        assert r.status_code == 403
