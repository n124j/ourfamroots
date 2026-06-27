"""Shared pytest fixtures.

Layers:
  - unit tests   — use mock UoW; no DB required
  - integration  — use real async test DB (postgres) + async test client
"""

from __future__ import annotations

import os
import uuid

# Ensure get_settings() can initialise in unit-test workers that never go
# through the auth_headers fixture.  setdefault is a no-op if the var is
# already injected by the CI environment.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-that-is-long-enough-for-hs256",
)
# Botocore needs non-None credentials to generate presigned URLs (pure local
# HMAC computation — no network).  setdefault is a no-op in environments that
# already have real or localstack credentials configured.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-access-key-id")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret-access-key")
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.application.auth.service import AuthService
from src.domain.interfaces.repositories import (
    AbstractRefreshTokenRepository,
    AbstractUserRepository,
)
from src.domain.interfaces.unit_of_work import AbstractUnitOfWork
from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.security.jwt import JWTService
from src.infrastructure.security.password import PasswordHasher


# ── Constants ─────────────────────────────────────────────────────

TEST_TENANT_ID   = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_ID     = uuid.UUID("00000000-0000-0000-0000-000000000002")
TEST_SECRET      = "test-secret-key-that-is-long-enough-for-hs256"
TEST_TENANT_SLUG = "ourfamroots-system"

# Mirrors the constant in AuthService so tests can reference it without
# importing a private name from the production module.
_MAX_FAILED_ATTEMPTS = 5


# ── Domain fakes ──────────────────────────────────────────────────

class FakeUserRepository(AbstractUserRepository):
    def __init__(self, users: list[UserModel] | None = None) -> None:
        self._users: list[UserModel] = users or []

    async def get_by_id(self, entity_id: uuid.UUID) -> UserModel | None:
        return next((u for u in self._users if u.id == entity_id), None)

    async def add(self, entity: UserModel) -> UserModel:
        if not entity.id:
            entity.id = uuid.uuid4()
        self._users.append(entity)
        return entity

    async def update(self, entity: UserModel) -> UserModel:
        return entity

    async def delete(self, entity_id: uuid.UUID) -> None:
        self._users = [u for u in self._users if u.id != entity_id]

    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> UserModel | None:
        return next(
            (u for u in self._users if u.tenant_id == tenant_id and u.email == email.lower()),
            None,
        )

    async def get_by_id_and_tenant(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> UserModel | None:
        return next(
            (u for u in self._users if u.id == user_id and u.tenant_id == tenant_id),
            None,
        )

    async def exists_by_email(self, tenant_id: uuid.UUID, email: str) -> bool:
        return any(u.tenant_id == tenant_id and u.email == email.lower() for u in self._users)

    async def get_by_password_reset_token(self, token: str) -> UserModel | None:
        return next((u for u in self._users if u.password_reset_token == token), None)

    async def get_by_verification_token(self, token: str) -> UserModel | None:
        return next((u for u in self._users if u.email_verification_token == token), None)

    async def get_by_login_verification_token(self, token: str) -> UserModel | None:
        return next((u for u in self._users if u.login_verification_token == token), None)


class FakeTenantRepository:
    def __init__(self) -> None:
        self._tenants: list[Any] = []

    async def get_by_id(self, entity_id: uuid.UUID) -> Any:
        return next((t for t in self._tenants if t.id == entity_id), None)

    async def add(self, entity: Any) -> Any:
        if not getattr(entity, "id", None):
            entity.id = uuid.uuid4()
        self._tenants.append(entity)
        return entity

    async def update(self, entity: Any) -> Any:
        return entity

    async def delete(self, entity_id: uuid.UUID) -> None:
        pass

    async def get_by_slug(self, slug: str) -> Any | None:
        return next((t for t in self._tenants if t.slug == slug), None)

    async def exists_by_slug(self, slug: str) -> bool:
        return any(t.slug == slug for t in self._tenants)


class FakeUnitOfWork(AbstractUnitOfWork):
    def __init__(self, users: FakeUserRepository | None = None) -> None:
        self._users = users or FakeUserRepository()
        self._tenants = FakeTenantRepository()
        self.committed = False
        # Pre-seed the default tenant so AuthService.register() resolves
        # the same TEST_TENANT_ID regardless of which slug it looks up.
        _default_tenant = TenantModel()
        _default_tenant.id = TEST_TENANT_ID
        _default_tenant.slug = TEST_TENANT_SLUG
        _default_tenant.name = "OurFamRoots System"
        _default_tenant.is_active = True
        self._tenants._tenants = [_default_tenant]

        # Pre-seed a default authenticated user so get_current_user() resolves
        # TEST_USER_ID to a valid active user in integration tests.
        # Only added when the repo is empty (i.e. not the verified_user fixture path).
        if not self._users._users:
            _default_user = UserModel()
            _default_user.id = TEST_USER_ID
            _default_user.tenant_id = TEST_TENANT_ID
            _default_user.email = "alice@example.com"
            _default_user.email_verified = True
            _default_user.is_active = True
            _default_user.app_role = "ADMIN"
            _default_user.failed_login_attempts = 0
            _default_user.locked_until = None
            # Required by UserProfileResponse serialisation
            _default_user.locale = "en"
            _default_user.timezone = "UTC"
            _default_user.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            _default_user.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            self._users._users.append(_default_user)

    @property
    def users(self) -> FakeUserRepository:
        return self._users

    @property
    def tenants(self) -> FakeTenantRepository:
        return self._tenants

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    # Expose internal session stub for AuthService._find_user_by_email
    class _FakeSession:
        def __init__(self, users: list[UserModel], tenants: list[Any] | None = None) -> None:
            self._users = users
            self._tenants = tenants if tenants is not None else []
            self._pending: list[Any] = []

        async def execute(self, stmt: Any, params: Any = None) -> Any:
            from src.infrastructure.database.models.user import UserModel as _UM
            from src.infrastructure.database.models.tenant import TenantModel as _TM

            items: list = []
            try:
                col_descs = getattr(stmt, 'column_descriptions', None)
                is_user_query = bool(col_descs and col_descs[0].get('entity') is _UM)
                is_tenant_query = bool(col_descs and col_descs[0].get('entity') is _TM)
            except Exception:
                is_user_query = False
                is_tenant_query = False

            source = (
                self._users if is_user_query
                else self._tenants if is_tenant_query
                else []
            )
            items = list(source)

            if is_user_query or is_tenant_query:
                try:
                    wc = getattr(stmt, 'whereclause', None)
                    if wc is not None:
                        clauses = list(getattr(wc, 'clauses', None) or [wc])
                        for clause in clauses:
                            key = getattr(getattr(clause, 'left', None), 'key', None)
                            val = getattr(getattr(clause, 'right', None), 'value', None)
                            if key == 'email' and val is not None:
                                items = [u for u in items if u.email == val.lower()]
                            elif key == 'id' and val is not None:
                                items = [u for u in items if str(u.id) == str(val)]
                except Exception:
                    pass

            class _Result:
                def __init__(self, data: list) -> None:
                    self._items = data
                def scalars(self) -> "_Result":
                    return self
                def first(self) -> Any:
                    return self._items[0] if self._items else None
                def all(self) -> list:
                    return self._items
                def fetchall(self) -> list:
                    return self._items
                def scalar(self) -> Any:
                    return self._items[0] if self._items else None
                def scalar_one(self) -> Any:
                    return self._items[0] if self._items else None
                def scalar_one_or_none(self) -> Any:
                    return self._items[0] if self._items else None
            return _Result(items)

        async def get(self, model: Any, pk: Any) -> Any:
            return next((u for u in self._users if str(u.id) == str(pk)), None)

        def add(self, entity: Any) -> None:
            self._pending.append(entity)

        async def flush(self) -> None:
            from src.infrastructure.database.models.tenant import TenantModel as _TM
            for entity in self._pending:
                if isinstance(entity, _TM):
                    self._tenants.append(entity)
                elif isinstance(entity, UserModel):
                    self._users.append(entity)
            self._pending.clear()

    @property
    def _session(self) -> Any:
        return self._FakeSession(self._users._users, self._tenants._tenants)


class FakeTokenStore(AbstractRefreshTokenRepository):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._pending_logins: dict[str, dict] = {}

    async def store(self, jti: str, user_id: uuid.UUID, expires_in_seconds: int) -> None:
        self._store[jti] = str(user_id)

    async def exists(self, jti: str) -> bool:
        return jti in self._store

    async def revoke(self, jti: str) -> None:
        self._store.pop(jti, None)

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        self._store = {k: v for k, v in self._store.items() if v != str(user_id)}

    async def has_active_sessions(self, user_id: uuid.UUID) -> bool:
        return any(v == str(user_id) for v in self._store.values())

    async def store_pending_login(
        self, token: str, user_id: uuid.UUID, ip_address: str | None, expires_in_seconds: int,
    ) -> None:
        self._pending_logins[token] = {"user_id": str(user_id), "ip_address": ip_address}

    async def get_pending_login(self, token: str) -> dict | None:
        return self._pending_logins.get(token)

    async def delete_pending_login(self, token: str) -> None:
        self._pending_logins.pop(token, None)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def jwt_service() -> JWTService:
    return JWTService(secret_key=TEST_SECRET, access_token_expire_minutes=15, refresh_token_expire_days=30)


@pytest.fixture
def hasher() -> PasswordHasher:
    return PasswordHasher()


@pytest.fixture
def fake_token_store() -> FakeTokenStore:
    return FakeTokenStore()


@pytest.fixture
def verified_user(hasher: PasswordHasher) -> UserModel:
    user = UserModel()
    user.id = TEST_USER_ID
    user.tenant_id = TEST_TENANT_ID
    user.email = "alice@example.com"
    user.password_hash = hasher.hash("Password1")
    user.email_verified = True
    user.email_verified_at = datetime.now(tz=timezone.utc)
    user.is_active = True
    user.failed_login_attempts = 0
    user.locked_until = None
    return user


@pytest.fixture
def fake_uow(verified_user: UserModel) -> FakeUnitOfWork:
    repo = FakeUserRepository(users=[verified_user])
    return FakeUnitOfWork(users=repo)


@pytest.fixture
def auth_service(
    fake_uow: FakeUnitOfWork,
    fake_token_store: FakeTokenStore,
    jwt_service: JWTService,
    hasher: PasswordHasher,
) -> AuthService:
    return AuthService(uow=fake_uow, token_store=fake_token_store, jwt=jwt_service, hasher=hasher)


# ── Integration: async test client ────────────────────────────────

@pytest_asyncio.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client against the FastAPI app with overridden dependencies.
    No real DB or Redis needed — uses fake implementations.
    """
    from src.main import create_app
    from src.api.deps import get_uow, get_token_store
    from src.infrastructure.database.session import get_db_session

    app = create_app()

    fake_uow = FakeUnitOfWork()
    fake_store = FakeTokenStore()

    # Override UoW and Redis store as before
    app.dependency_overrides[get_uow] = lambda: fake_uow
    app.dependency_overrides[get_token_store] = lambda: fake_store

    # Also override the raw DB session so get_current_user (SessionDep) doesn't
    # attempt a real PostgreSQL connection in unit/integration tests.
    async def _fake_db_session():
        yield fake_uow._session

    app.dependency_overrides[get_db_session] = _fake_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers() -> dict:
    """
    Authorization header with a valid Bearer token for integration tests.

    The token is signed with settings.jwt_secret_key (the same secret the
    TenantMiddleware uses) and carries TEST_USER_ID / TEST_TENANT_ID claims
    so that get_current_user resolves to the pre-seeded verified_user.
    """
    from src.config import get_settings
    settings = get_settings()
    svc = JWTService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=60,
        refresh_token_expire_days=1,
    )
    access_token, _ = svc.create_access_token(TEST_USER_ID, TEST_TENANT_ID)
    return {"Authorization": f"Bearer {access_token}"}
