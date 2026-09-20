"""Real-database integration tests for AdminPaidFeatureDep (admin-only AND
paid-tier-only gating). Same real-Postgres, direct-function-call pattern as
test_broadcast.py (requires TEST_DATABASE_URL; skipped otherwise)."""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — this module needs a real, migrated Postgres "
        "database (see test_broadcast.py for local setup). Skipping.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


def _user(uid: uuid.UUID, tenant_id: uuid.UUID, email: str, app_role: str = "STANDARD") -> SimpleNamespace:
    return SimpleNamespace(id=uid, tenant_id=tenant_id, email=email, app_role=app_role)


class Seed:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.free_admin = _user(uuid.uuid4(), self.tenant_id, "free-admin@example.com", "ADMIN")
        self.paid_standard = _user(uuid.uuid4(), self.tenant_id, "paid-standard@example.com", "STANDARD")
        self.paid_admin = _user(uuid.uuid4(), self.tenant_id, "paid-admin@example.com", "ADMIN")
        self.super_admin = _user(uuid.uuid4(), self.tenant_id, "root@example.com", "SUPER_ADMIN")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.free_admin, self.paid_standard, self.paid_admin, self.super_admin):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, :role, 'Test', 'User')
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role},
            )
        sub_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO subscriptions (id, tenant_id, name, tier)
                    VALUES (:id, :tenant, 'Premium', 'PREMIUM_INDIVIDUAL')"""),
            {"id": sub_id, "tenant": self.tenant_id},
        )
        for u in (self.paid_standard, self.paid_admin):
            await s.execute(
                text("""INSERT INTO subscription_members (id, subscription_id, user_id)
                        VALUES (gen_random_uuid(), :sid, :uid)"""),
                {"sid": sub_id, "uid": u.id},
            )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


class TestAdminPaidFeatureDep:
    @pytest.mark.asyncio
    async def test_free_tier_admin_is_blocked(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        with pytest.raises(HTTPException) as exc:
            await require_admin_paid_feature(user=seed.free_admin, session=seed.session)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_paid_non_admin_is_blocked(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        with pytest.raises(HTTPException) as exc:
            await require_admin_paid_feature(user=seed.paid_standard, session=seed.session)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_paid_admin_is_allowed(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        result = await require_admin_paid_feature(user=seed.paid_admin, session=seed.session)
        assert result.id == seed.paid_admin.id

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_paid_check(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        result = await require_admin_paid_feature(user=seed.super_admin, session=seed.session)
        assert result.id == seed.super_admin.id
