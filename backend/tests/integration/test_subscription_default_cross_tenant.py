"""Real-database integration test: a subscription's "default for all users"
flag must entitle every user on the platform, across every namespace — not
just users in the subscription's own (creating) tenant. Mirrors
test_global_tree_cross_tenant.py's rationale and setup pattern; see that
module's docstring for local test-DB setup instructions. Requires
TEST_DATABASE_URL; skipped if it isn't set.
"""
from __future__ import annotations

import os
import uuid
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
        "database (see test_global_tree_cross_tenant.py for local setup). Skipping.",
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
    """Tenant A creates a default subscription with one filter; Tenant B has
    a standard user with no membership in that subscription."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_a = uuid.uuid4()
        self.tenant_b = uuid.uuid4()
        self.sub_id = uuid.uuid4()
        self.user_b = _user(uuid.uuid4(), self.tenant_b, "bob@example.com")

    async def build(self) -> "Seed":
        s = self.session
        for tid, slug in ((self.tenant_a, "sub-tenant-a"), (self.tenant_b, "sub-tenant-b")):
            await s.execute(
                text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": tid, "name": slug, "slug": f"{slug}-{tid.hex[:8]}"},
            )
        await s.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                VALUES (:id, :tenant, :email, true, true, 'STANDARD', 'Bob', 'Test')
            """),
            {"id": self.user_b.id, "tenant": self.tenant_b, "email": self.user_b.email},
        )
        await s.execute(
            text("""INSERT INTO subscriptions (id, tenant_id, name, tier, is_default)
                    VALUES (:id, :tenant, 'Everyone Everywhere Free', 'FREE', true)"""),
            {"id": self.sub_id, "tenant": self.tenant_a},
        )
        await s.execute(
            text("""INSERT INTO subscription_filters (id, subscription_id, filter_key)
                    VALUES (gen_random_uuid(), :sid, 'timeline')"""),
            {"sid": self.sub_id},
        )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


class TestDefaultSubscriptionIsPlatformWide:
    @pytest.mark.asyncio
    async def test_cross_tenant_user_gets_default_subscription_filters(self, seed: Seed):
        from src.api.v1.subscriptions import get_my_filters

        result = await get_my_filters(seed.user_b, seed.session)
        assert "timeline" in result.filterKeys, (
            "a Tenant A default subscription must entitle a Tenant B user's filters"
        )
