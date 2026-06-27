"""Unit tests for OAuth flow — _find_or_create_user and callback helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.security.oauth import OAuthUserInfo
from src.api.v1.oauth import _find_or_create_user, _safe_next_path

TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
TEST_TENANT_SLUG = "ourfamroots-system"


# ── Fake session that supports both UserModel and TenantModel ────────────────

class FakeOAuthSession:
    def __init__(
        self,
        users: list[UserModel] | None = None,
        tenants: list[TenantModel] | None = None,
    ) -> None:
        self._users = users or []
        self._tenants = tenants or []
        self._added: list[Any] = []

    async def execute(self, stmt: Any, params: Any = None) -> Any:
        items: list = []
        try:
            col_descs = getattr(stmt, "column_descriptions", None)
            entity = col_descs[0].get("entity") if col_descs else None
        except Exception:
            entity = None

        if entity is UserModel:
            items = list(self._users)
        elif entity is TenantModel:
            items = list(self._tenants)

        try:
            wc = getattr(stmt, "whereclause", None)
            if wc is not None:
                clauses = list(getattr(wc, "clauses", None) or [wc])
                for clause in clauses:
                    key = getattr(getattr(clause, "left", None), "key", None)
                    val = getattr(getattr(clause, "right", None), "value", None)
                    if key == "email" and val is not None:
                        items = [i for i in items if getattr(i, "email", None) == val.lower()]
                    elif key == "id" and val is not None:
                        items = [i for i in items if str(i.id) == str(val)]
                    elif key == "slug" and val is not None:
                        items = [i for i in items if getattr(i, "slug", None) == val]
        except Exception:
            pass

        class _Result:
            def __init__(self, data: list) -> None:
                self._items = data
            def scalars(self) -> "_Result":
                return self
            def first(self) -> Any:
                return self._items[0] if self._items else None
            def scalar_one_or_none(self) -> Any:
                return self._items[0] if self._items else None

        return _Result(items)

    def add(self, entity: Any) -> None:
        self._added.append(entity)
        if isinstance(entity, TenantModel):
            if entity.id is None:
                entity.id = uuid.uuid4()
            self._tenants.append(entity)
        elif isinstance(entity, UserModel):
            self._users.append(entity)

    async def flush(self) -> None:
        pass


class FakeOAuthUoW:
    def __init__(self, session: FakeOAuthSession) -> None:
        self._session_obj = session

    @property
    def _session(self) -> FakeOAuthSession:
        return self._session_obj


def _make_settings(default_tenant_slug: str = "") -> MagicMock:
    s = MagicMock()
    s.default_tenant_slug = default_tenant_slug
    return s


def _make_user_info(
    email: str = "alice@example.com",
    name: str = "Alice Smith",
    given_name: str = "Alice",
    family_name: str = "Smith",
) -> OAuthUserInfo:
    return OAuthUserInfo(
        provider="google",
        provider_user_id="google-123",
        email=email,
        display_name=name,
        given_name=given_name,
        family_name=family_name,
        avatar_url="https://example.com/avatar.png",
        email_verified=True,
    )


# ── _find_or_create_user tests ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestFindOrCreateUser:
    async def test_returns_existing_user(self):
        """If a user with this email already exists, return them."""
        existing = UserModel()
        existing.id = uuid.uuid4()
        existing.tenant_id = TEST_TENANT_ID
        existing.email = "alice@example.com"
        existing.given_name = "Alice"
        existing.family_name = "Smith"

        session = FakeOAuthSession(users=[existing])
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)

        result = await _find_or_create_user(uow, _make_user_info(), settings)

        assert result is existing
        assert len(session._added) == 0

    async def test_backfills_names_on_existing_user(self):
        """If an existing user has no names, backfill from provider."""
        existing = UserModel()
        existing.id = uuid.uuid4()
        existing.tenant_id = TEST_TENANT_ID
        existing.email = "alice@example.com"
        existing.given_name = ""
        existing.family_name = ""
        existing.avatar_url = None

        session = FakeOAuthSession(users=[existing])
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)

        result = await _find_or_create_user(uow, _make_user_info(), settings)

        assert result.given_name == "Alice"
        assert result.family_name == "Smith"
        assert result.avatar_url == "https://example.com/avatar.png"

    async def test_updates_avatar_on_every_login(self):
        """Avatar is always refreshed from provider, even if user already has one."""
        existing = UserModel()
        existing.id = uuid.uuid4()
        existing.tenant_id = TEST_TENANT_ID
        existing.email = "alice@example.com"
        existing.given_name = "Alice"
        existing.family_name = "Smith"
        existing.avatar_url = "https://example.com/old-avatar.png"

        session = FakeOAuthSession(users=[existing])
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)

        result = await _find_or_create_user(uow, _make_user_info(), settings)

        assert result.avatar_url == "https://example.com/avatar.png"

    async def test_returns_none_when_no_default_tenant_slug(self):
        """If default_tenant_slug is empty, returns None (provisioning disabled)."""
        session = FakeOAuthSession()
        uow = FakeOAuthUoW(session)
        settings = _make_settings("")

        result = await _find_or_create_user(uow, _make_user_info(), settings)

        assert result is None

    async def test_creates_tenant_when_missing(self):
        """If the default tenant doesn't exist in DB, auto-create it."""
        session = FakeOAuthSession(users=[], tenants=[])
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)

        result = await _find_or_create_user(uow, _make_user_info(), settings)

        assert result is not None
        # Tenant was auto-created with slug from settings
        tenant_adds = [e for e in session._added if isinstance(e, TenantModel)]
        assert len(tenant_adds) == 1
        assert tenant_adds[0].slug == TEST_TENANT_SLUG
        assert result.tenant_id == tenant_adds[0].id

    async def test_skips_tenant_creation_when_exists(self):
        """If the default tenant already exists, don't duplicate it."""
        existing_tenant = TenantModel()
        existing_tenant.id = TEST_TENANT_ID
        existing_tenant.name = "OurFamRoots System"
        existing_tenant.slug = TEST_TENANT_SLUG

        session = FakeOAuthSession(users=[], tenants=[existing_tenant])
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)

        result = await _find_or_create_user(uow, _make_user_info(), settings)

        assert result is not None
        assert result.tenant_id == TEST_TENANT_ID
        tenant_adds = [e for e in session._added if isinstance(e, TenantModel)]
        assert len(tenant_adds) == 0

    async def test_new_user_fields_populated(self):
        """New user gets correct email, name, avatar, and verification status."""
        session = FakeOAuthSession()
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)
        info = _make_user_info(email="Bob.Jones@Example.COM", name="Bob Jones", given_name="Bob", family_name="Jones")

        result = await _find_or_create_user(uow, info, settings)

        assert result is not None
        assert result.email == "bob.jones@example.com"
        assert result.given_name == "Bob"
        assert result.family_name == "Jones"
        assert result.avatar_url == "https://example.com/avatar.png"
        assert result.email_verified is True
        assert result.email_verified_at is not None
        assert result.is_active is True
        assert result.failed_login_attempts == 0

    async def test_unverified_email_sets_no_verified_at(self):
        """If provider says email is not verified, email_verified_at stays None."""
        session = FakeOAuthSession()
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)
        info = OAuthUserInfo(
            provider="google",
            provider_user_id="g-456",
            email="unverified@example.com",
            display_name="Unverified User",
            given_name="Unverified",
            family_name="User",
            avatar_url=None,
            email_verified=False,
        )

        result = await _find_or_create_user(uow, info, settings)

        assert result is not None
        assert result.email_verified is False
        assert result.email_verified_at is None

    async def test_single_name_goes_to_given_name(self):
        """A single-word display name goes to given_name, family_name is empty."""
        session = FakeOAuthSession()
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)
        info = _make_user_info(name="Madonna", given_name="Madonna", family_name="")

        result = await _find_or_create_user(uow, info, settings)

        assert result.given_name == "Madonna"
        assert result.family_name == ""

    async def test_no_display_name_gives_empty_names(self):
        """If provider gives no display_name, both name fields are empty."""
        session = FakeOAuthSession()
        uow = FakeOAuthUoW(session)
        settings = _make_settings(TEST_TENANT_SLUG)
        info = OAuthUserInfo(
            provider="google",
            provider_user_id="g-789",
            email="noname@example.com",
            display_name=None,
            given_name=None,
            family_name=None,
            avatar_url=None,
            email_verified=True,
        )

        result = await _find_or_create_user(uow, info, settings)

        assert result.given_name == ""
        assert result.family_name == ""


# ── _safe_next_path tests ───────────────────────────────────────────────────


class TestSafeNextPath:
    def test_valid_relative_path(self):
        assert _safe_next_path("/dashboard") == "/dashboard"

    def test_path_with_query(self):
        assert _safe_next_path("/?auth=login") == "/?auth=login"

    def test_rejects_double_slash(self):
        assert _safe_next_path("//evil.com") == "/login"

    def test_rejects_absolute_url(self):
        assert _safe_next_path("https://evil.com") == "/login"

    def test_none_returns_login(self):
        assert _safe_next_path(None) == "/login"

    def test_empty_string_returns_login(self):
        assert _safe_next_path("") == "/login"
