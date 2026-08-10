"""Real-database integration tests for POST/DELETE /trees/{tree_id}/hide.

`hide_tree` used to reject any tree that wasn't attached to a global
permission group (400 "Only a globally-shared tree can be hidden"). That
restriction was removed so any tree a user is a member of can be hidden
from their own Dashboard — this module locks that in and guards against a
regression back to the old global-only behavior.

Follows the same real-Postgres pattern as test_change_request_revert.py (see
that module's docstring for local setup instructions). Requires
TEST_DATABASE_URL; the whole module is skipped if it isn't set.
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
        "database (see test_change_request_revert.py for local setup). Skipping.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


def _user(uid: uuid.UUID, tenant_id: uuid.UUID, email: str, app_role: str = "STANDARD") -> SimpleNamespace:
    """A stand-in for UserModel — the endpoint only ever reads these attributes."""
    given = email.split("@")[0].title()
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name=given, family_name="Test", full_name=f"{given} Test", app_role=app_role,
    )


class Seed:
    """One regular (non-global) tree and one globally-shared tree, both in the
    same tenant, with a single member on each — plus an outsider with no
    tree_members row on either, and an Auditor (who bypasses the membership
    check entirely, per hide_tree's own logic)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.tree_regular = uuid.uuid4()
        self.tree_global = uuid.uuid4()
        self.member = _user(uuid.uuid4(), self.tenant_id, "member@example.com")
        self.outsider = _user(uuid.uuid4(), self.tenant_id, "outsider@example.com")
        self.auditor = _user(uuid.uuid4(), self.tenant_id, "auditor@example.com", app_role="AUDITOR")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.member, self.outsider, self.auditor):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, :role, :given, :family)
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role,
                 "given": u.given_name, "family": u.family_name},
            )
        for tid, name in ((self.tree_regular, "Regular Family"), (self.tree_global, "Global Family")):
            await s.execute(
                text("INSERT INTO family_trees (id, tenant_id, name) VALUES (:id, :tenant, :name)"),
                {"id": tid, "tenant": self.tenant_id, "name": name},
            )
        for tid in (self.tree_regular, self.tree_global):
            await s.execute(
                text("""INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
                        VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER', NOW())"""),
                {"tid": tid, "uid": self.member.id, "tenant": self.tenant_id},
            )
        group_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO permission_groups (id, tenant_id, name, permission_level, is_global)
                    VALUES (:id, :tenant, 'Everyone', 'READ_WRITE', true)"""),
            {"id": group_id, "tenant": self.tenant_id},
        )
        await s.execute(
            text("INSERT INTO permission_group_trees (id, group_id, tree_id) VALUES (gen_random_uuid(), :gid, :tid)"),
            {"gid": group_id, "tid": self.tree_global},
        )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


def _uow(session: AsyncSession):
    from src.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
    return SqlAlchemyUnitOfWork(session)


async def _hidden_tree_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = (await session.execute(
        text("SELECT tree_id FROM tree_hides WHERE user_id = :uid"), {"uid": user_id},
    )).all()
    return {r.tree_id for r in rows}


class TestHideTree:
    @pytest.mark.asyncio
    async def test_member_can_hide_a_regular_non_global_tree(self, seed: Seed):
        """Regression guard: hide_tree must NOT reject non-global trees anymore."""
        from src.api.v1.collaboration import hide_tree

        await hide_tree(seed.tree_regular, seed.member, _uow(seed.session))

        assert seed.tree_regular in await _hidden_tree_ids(seed.session, seed.member.id)

    @pytest.mark.asyncio
    async def test_member_can_hide_a_globally_shared_tree(self, seed: Seed):
        """Unchanged behavior: hiding a global tree still works."""
        from src.api.v1.collaboration import hide_tree

        await hide_tree(seed.tree_global, seed.member, _uow(seed.session))

        assert seed.tree_global in await _hidden_tree_ids(seed.session, seed.member.id)

    @pytest.mark.asyncio
    async def test_non_member_cannot_hide_a_tree(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.collaboration import hide_tree

        with pytest.raises(HTTPException) as exc_info:
            await hide_tree(seed.tree_regular, seed.outsider, _uow(seed.session))
        assert exc_info.value.status_code == 403

        assert seed.tree_regular not in await _hidden_tree_ids(seed.session, seed.outsider.id)

    @pytest.mark.asyncio
    async def test_auditor_can_hide_any_tree_without_membership(self, seed: Seed):
        """hide_tree explicitly skips the membership check for AUDITOR."""
        from src.api.v1.collaboration import hide_tree

        await hide_tree(seed.tree_regular, seed.auditor, _uow(seed.session))

        assert seed.tree_regular in await _hidden_tree_ids(seed.session, seed.auditor.id)

    @pytest.mark.asyncio
    async def test_hide_then_unhide_removes_the_row(self, seed: Seed):
        from src.api.v1.collaboration import hide_tree, unhide_tree

        await hide_tree(seed.tree_regular, seed.member, _uow(seed.session))
        assert seed.tree_regular in await _hidden_tree_ids(seed.session, seed.member.id)

        await unhide_tree(seed.tree_regular, seed.member, _uow(seed.session))
        assert seed.tree_regular not in await _hidden_tree_ids(seed.session, seed.member.id)

    @pytest.mark.asyncio
    async def test_hiding_twice_is_idempotent(self, seed: Seed):
        """The endpoint upserts with ON CONFLICT DO NOTHING — calling it twice
        must not raise a unique-constraint error."""
        from src.api.v1.collaboration import hide_tree

        await hide_tree(seed.tree_regular, seed.member, _uow(seed.session))
        await hide_tree(seed.tree_regular, seed.member, _uow(seed.session))

        assert seed.tree_regular in await _hidden_tree_ids(seed.session, seed.member.id)
