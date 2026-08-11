"""Real-database integration tests for the site-wide announcement banner
(src/api/v1/site_settings.py's banner endpoints) — independent of
maintenance mode, non-blocking, and time-bounded.

Follows the same real-Postgres pattern as test_dashboard_hide_tree.py (see
that module's docstring for local setup instructions). Requires
TEST_DATABASE_URL; the whole module is skipped if it isn't set.

Permission-gate wiring (SuperAdminDep / require_super_admin) is proven
generically by tests/unit/test_super_admin_dependency.py and is reused here
verbatim (same type alias as update_maintenance, already in production) —
this module focuses on the banner-specific business logic: the
enabled+time-window "is it active right now" computation, and the
read/write round-trip.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — this module needs a real, migrated Postgres "
        "database (see test_dashboard_hide_tree.py for local setup). Skipping.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


def _user(uid: uuid.UUID, tenant_id: uuid.UUID, email: str, app_role: str = "STANDARD") -> SimpleNamespace:
    given = email.split("@")[0].title()
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name=given, family_name="Test", full_name=f"{given} Test", app_role=app_role,
    )


class Seed:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.super_admin = _user(uuid.uuid4(), self.tenant_id, "root@example.com", app_role="SUPER_ADMIN")
        self.standard_user = _user(uuid.uuid4(), self.tenant_id, "user@example.com")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.super_admin, self.standard_user):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, :role, :given, :family)
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role,
                 "given": u.given_name, "family": u.family_name},
            )
        # Reset the site_settings singleton to a known, banner-disabled state
        # before every test — this table has exactly one row shared across
        # the whole database, so tests must not leak state between each other.
        await s.execute(text("DELETE FROM site_settings"))
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


class TestBannerActiveComputation:
    """_is_banner_active via the public GET — disabled/unbounded/before/within/after/one-sided."""

    @pytest.mark.asyncio
    async def test_disabled_is_never_active_even_within_a_valid_window(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        await update_banner(
            UpdateBannerRequest(banner_enabled=False, banner_message="Hi",
                                 banner_starts_at=now - timedelta(hours=1), banner_ends_at=now + timedelta(hours=1)),
            seed.super_admin, seed.session,
        )
        result = await get_banner_status(seed.session)
        assert result.active is False
        assert result.message is None

    @pytest.mark.asyncio
    async def test_enabled_with_no_bounds_is_active(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="We'll be down soon"),
            seed.super_admin, seed.session,
        )
        result = await get_banner_status(seed.session)
        assert result.active is True
        assert result.message == "We'll be down soon"

    @pytest.mark.asyncio
    async def test_enabled_before_start_time_is_not_active(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Later", banner_starts_at=now + timedelta(hours=1)),
            seed.super_admin, seed.session,
        )
        result = await get_banner_status(seed.session)
        assert result.active is False
        assert result.message is None

    @pytest.mark.asyncio
    async def test_enabled_within_window_is_active(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        await update_banner(
            UpdateBannerRequest(
                banner_enabled=True, banner_message="Now",
                banner_starts_at=now - timedelta(hours=1), banner_ends_at=now + timedelta(hours=1),
            ),
            seed.super_admin, seed.session,
        )
        result = await get_banner_status(seed.session)
        assert result.active is True
        assert result.message == "Now"

    @pytest.mark.asyncio
    async def test_enabled_after_end_time_is_not_active(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Expired", banner_ends_at=now - timedelta(hours=1)),
            seed.super_admin, seed.session,
        )
        result = await get_banner_status(seed.session)
        assert result.active is False
        assert result.message is None

    @pytest.mark.asyncio
    async def test_enabled_with_only_a_start_time_is_active_indefinitely_after_it(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Started", banner_starts_at=now - timedelta(minutes=1)),
            seed.super_admin, seed.session,
        )
        result = await get_banner_status(seed.session)
        assert result.active is True

    @pytest.mark.asyncio
    async def test_enabled_with_only_an_end_time_is_active_until_it(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Ends soon", banner_ends_at=now + timedelta(minutes=1)),
            seed.super_admin, seed.session,
        )
        result = await get_banner_status(seed.session)
        assert result.active is True


class TestBannerConfigAndUpdate:
    @pytest.mark.asyncio
    async def test_config_returns_raw_fields_including_when_inactive(self, seed: Seed):
        """Unlike the public status endpoint, /banner/config must expose the
        raw enabled flag and schedule even when not currently active, so the
        admin form can be populated correctly."""
        from src.api.v1.site_settings import get_banner_config, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        starts = now + timedelta(days=1)
        ends = now + timedelta(days=2)
        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Future", banner_starts_at=starts, banner_ends_at=ends),
            seed.super_admin, seed.session,
        )
        config = await get_banner_config(seed.super_admin, seed.session)
        assert config.banner_enabled is True
        assert config.banner_message == "Future"
        assert config.banner_starts_at is not None
        assert config.banner_ends_at is not None

    @pytest.mark.asyncio
    async def test_partial_update_leaves_other_fields_untouched(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_config, update_banner, UpdateBannerRequest

        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Original"),
            seed.super_admin, seed.session,
        )
        await update_banner(
            UpdateBannerRequest(banner_message="Updated"),
            seed.super_admin, seed.session,
        )
        config = await get_banner_config(seed.super_admin, seed.session)
        assert config.banner_enabled is True
        assert config.banner_message == "Updated"

    @pytest.mark.asyncio
    async def test_clear_schedule_resets_both_bounds(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_config, update_banner, UpdateBannerRequest

        now = datetime.now(timezone.utc)
        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_starts_at=now, banner_ends_at=now + timedelta(hours=1)),
            seed.super_admin, seed.session,
        )
        await update_banner(
            UpdateBannerRequest(clear_schedule=True),
            seed.super_admin, seed.session,
        )
        config = await get_banner_config(seed.super_admin, seed.session)
        assert config.banner_starts_at is None
        assert config.banner_ends_at is None
        assert config.banner_enabled is True  # unrelated field untouched

    @pytest.mark.asyncio
    async def test_updated_by_id_is_stamped_on_save(self, seed: Seed):
        from sqlalchemy import text as sa_text

        from src.api.v1.site_settings import update_banner, UpdateBannerRequest

        await update_banner(
            UpdateBannerRequest(banner_enabled=True),
            seed.super_admin, seed.session,
        )
        row = (await seed.session.execute(sa_text("SELECT updated_by_id FROM site_settings LIMIT 1"))).first()
        assert row.updated_by_id == seed.super_admin.id

    @pytest.mark.asyncio
    async def test_maintenance_fields_are_unaffected_by_banner_updates(self, seed: Seed):
        """The banner and maintenance mode share one settings row but must
        stay fully independent of each other."""
        from src.api.v1.site_settings import get_maintenance_status, update_banner, UpdateBannerRequest

        before = await get_maintenance_status(seed.session)
        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Announcement"),
            seed.super_admin, seed.session,
        )
        after = await get_maintenance_status(seed.session)
        assert after.maintenance_mode == before.maintenance_mode
        assert after.maintenance_message == before.maintenance_message


class TestBannerColors:
    @pytest.mark.asyncio
    async def test_colors_default_to_null(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_config

        config = await get_banner_config(seed.super_admin, seed.session)
        assert config.banner_bg_color is None
        assert config.banner_text_color is None

    @pytest.mark.asyncio
    async def test_setting_valid_hex_colors_persists(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_config, update_banner, UpdateBannerRequest

        await update_banner(
            UpdateBannerRequest(banner_bg_color="#112233", banner_text_color="#ffffff"),
            seed.super_admin, seed.session,
        )
        config = await get_banner_config(seed.super_admin, seed.session)
        assert config.banner_bg_color == "#112233"
        assert config.banner_text_color == "#ffffff"

    @pytest.mark.asyncio
    async def test_invalid_hex_color_is_rejected(self, seed: Seed):
        from pydantic import ValidationError

        from src.api.v1.site_settings import UpdateBannerRequest

        for bad in ("red", "#fff", "112233", "#gggggg", "#1122334"):
            with pytest.raises(ValidationError):
                UpdateBannerRequest(banner_bg_color=bad)

    @pytest.mark.asyncio
    async def test_reset_colors_clears_both_regardless_of_other_fields(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_config, update_banner, UpdateBannerRequest

        await update_banner(
            UpdateBannerRequest(banner_bg_color="#112233", banner_text_color="#445566"),
            seed.super_admin, seed.session,
        )
        await update_banner(
            UpdateBannerRequest(reset_colors=True),
            seed.super_admin, seed.session,
        )
        config = await get_banner_config(seed.super_admin, seed.session)
        assert config.banner_bg_color is None
        assert config.banner_text_color is None

    @pytest.mark.asyncio
    async def test_public_status_includes_colors_only_when_active(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_status, update_banner, UpdateBannerRequest

        await update_banner(
            UpdateBannerRequest(banner_enabled=False, banner_bg_color="#112233", banner_text_color="#ffffff"),
            seed.super_admin, seed.session,
        )
        inactive_status = await get_banner_status(seed.session)
        assert inactive_status.active is False
        assert inactive_status.bg_color is None
        assert inactive_status.text_color is None

        await update_banner(
            UpdateBannerRequest(banner_enabled=True, banner_message="Hi"),
            seed.super_admin, seed.session,
        )
        active_status = await get_banner_status(seed.session)
        assert active_status.active is True
        assert active_status.bg_color == "#112233"
        assert active_status.text_color == "#ffffff"

    @pytest.mark.asyncio
    async def test_colors_are_independent_of_message_and_schedule_updates(self, seed: Seed):
        from src.api.v1.site_settings import get_banner_config, update_banner, UpdateBannerRequest

        await update_banner(
            UpdateBannerRequest(banner_bg_color="#112233", banner_text_color="#445566"),
            seed.super_admin, seed.session,
        )
        await update_banner(
            UpdateBannerRequest(banner_message="Just the message changed"),
            seed.super_admin, seed.session,
        )
        config = await get_banner_config(seed.super_admin, seed.session)
        assert config.banner_bg_color == "#112233"
        assert config.banner_text_color == "#445566"
