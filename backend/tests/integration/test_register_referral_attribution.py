"""Real-database integration tests for referral attribution on registration
(`RegisterRequest.ref`) and on tree-invitation acceptance.

register() resolves `ref` (a shared tree's share_token) to that tree's OWNER
via a raw SQL join (tree_members JOIN family_trees), and accept_invitation()
credits the inviter directly from the already-loaded Invitation — neither
path is exercised by the fake-UoW unit/integration suites (see
test_auth_service.py's `test_register_without_ref_leaves_referral_unset` /
`test_register_with_malformed_ref_does_not_crash` for the fake-backed cases),
so both need a real Postgres to prove the SQL and the "set once, never
overwrite" guard actually work.

Follows the same real-Postgres pattern as test_change_request_revert.py (see
that module's docstring for local setup instructions). Requires
TEST_DATABASE_URL; the whole module is skipped if it isn't set.
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — this module needs a real, migrated Postgres "
        "database (see test_change_request_revert.py for local setup). Skipping.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


class Seed:
    """One tenant, one tree owned by `owner`, its share_token, and a second
    unrelated tenant+tree (owned by `other_owner`) used to prove a bad/
    mismatched ref doesn't cross-attribute."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.tree_id = uuid.uuid4()
        self.share_token = uuid.uuid4()
        self.owner_id = uuid.uuid4()
        self.other_tenant_id = uuid.uuid4()
        self.other_tree_id = uuid.uuid4()
        self.other_owner_id = uuid.uuid4()

    async def build(self) -> "Seed":
        s = self.session
        for tid, slug in ((self.tenant_id, "referral-a"), (self.other_tenant_id, "referral-b")):
            await s.execute(
                text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
                {"id": tid, "slug": f"{slug}-{tid.hex[:8]}"},
            )
        for uid, tenant, email in (
            (self.owner_id, self.tenant_id, "owner@example.com"),
            (self.other_owner_id, self.other_tenant_id, "other-owner@example.com"),
        ):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, 'STANDARD', 'Test', 'Owner')
                """),
                {"id": uid, "tenant": tenant, "email": email},
            )
        await s.execute(
            text("""INSERT INTO family_trees (id, tenant_id, name, link_sharing, share_token)
                    VALUES (:id, :tenant, 'Owner Family', 'ANYONE', :token)"""),
            {"id": self.tree_id, "tenant": self.tenant_id, "token": self.share_token},
        )
        await s.execute(
            text("INSERT INTO family_trees (id, tenant_id, name) VALUES (:id, :tenant, 'Other Family')"),
            {"id": self.other_tree_id, "tenant": self.other_tenant_id},
        )
        for tid, tenant, uid in (
            (self.tree_id, self.tenant_id, self.owner_id),
            (self.other_tree_id, self.other_tenant_id, self.other_owner_id),
        ):
            await s.execute(
                text("""INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
                        VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER', NOW())"""),
                {"tid": tid, "uid": uid, "tenant": tenant},
            )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


def _auth_service(session: AsyncSession):
    from src.application.auth.service import AuthService
    from src.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
    from src.infrastructure.security.password import PasswordHasher

    return AuthService(
        uow=SqlAlchemyUnitOfWork(session),
        token_store=None,  # not touched by register()
        jwt=None,  # not touched by register()
        hasher=PasswordHasher(),
    )


async def _user_referral(session: AsyncSession, email: str):
    row = (await session.execute(
        text("SELECT referred_by_user_id, referral_channel FROM users WHERE email = :email"),
        {"email": email},
    )).first()
    assert row is not None, f"user {email} was not created"
    return row.referred_by_user_id, row.referral_channel


class TestRegisterShareLinkAttribution:
    @pytest.mark.asyncio
    async def test_register_with_valid_share_token_credits_the_tree_owner(self, seed: Seed, session: AsyncSession):
        from src.application.auth.schemas import RegisterRequest

        req = RegisterRequest(
            email="visitor@example.com", password="Password1",
            given_name="Visitor", family_name="Test", ref=str(seed.share_token),
        )
        await _auth_service(session).register(req)

        referred_by, channel = await _user_referral(session, "visitor@example.com")
        assert referred_by == seed.owner_id
        assert channel == "share_link"

    @pytest.mark.asyncio
    async def test_register_with_unknown_share_token_leaves_referral_unset(self, seed: Seed, session: AsyncSession):
        from src.application.auth.schemas import RegisterRequest

        req = RegisterRequest(
            email="stranger@example.com", password="Password1",
            given_name="Stranger", family_name="Test", ref=str(uuid.uuid4()),  # not any tree's share_token
        )
        await _auth_service(session).register(req)

        referred_by, channel = await _user_referral(session, "stranger@example.com")
        assert referred_by is None
        assert channel is None

    @pytest.mark.asyncio
    async def test_register_without_ref_leaves_referral_unset(self, seed: Seed, session: AsyncSession):
        from src.application.auth.schemas import RegisterRequest

        req = RegisterRequest(
            email="noref@example.com", password="Password1", given_name="No", family_name="Ref",
        )
        await _auth_service(session).register(req)

        referred_by, channel = await _user_referral(session, "noref@example.com")
        assert referred_by is None
        assert channel is None
