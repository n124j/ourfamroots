"""Real-database integration tests for cross-namespace "Global Trees" visibility.

Global permission groups (permission_groups.is_global) used to grant access
only to users within the flagging group's own tenant. This module verifies
the platform-wide behavior: a tree attached to an is_global group must be
auto-enrolled for users in ANY tenant, with the resulting tree_members row
stamped with the TREE's own tenant_id (not the enrolling user's) — and that
a NON-global tree remains fully isolated across tenants, exactly as before.

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
    """A stand-in for UserModel — the endpoints/services only ever read these attributes."""
    given = email.split("@")[0].title()
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name=given, family_name="Test", full_name=f"{given} Test", app_role=app_role,
    )


def _fake_request() -> SimpleNamespace:
    return SimpleNamespace(headers={}, client=None)


class TwoTenantSeed:
    """Tenant A owns a tree with a global permission group attached; Tenant B
    has a standard user with no pre-existing relationship to Tenant A's tree.
    A separate Super Admin (its own tenant) is seeded for the cross-tenant
    admin-management tests."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_a = uuid.uuid4()
        self.tenant_b = uuid.uuid4()
        self.tenant_sa = uuid.uuid4()
        self.tree_a = uuid.uuid4()          # global tree in tenant A
        self.tree_a_private = uuid.uuid4()  # NON-global tree in tenant A
        self.tree_c = uuid.uuid4()          # tenant C's tree, for the cross-tenant attach test
        self.tenant_c = uuid.uuid4()
        self.alice_id = uuid.uuid4()
        self.bob_id = uuid.uuid4()
        self.user_b = _user(uuid.uuid4(), self.tenant_b, "bob-user@example.com")
        self.super_admin = _user(uuid.uuid4(), self.tenant_sa, "root@example.com", app_role="SUPER_ADMIN")
        self.global_group_id = uuid.uuid4()

    async def build(self) -> "TwoTenantSeed":
        s = self.session
        for tid, slug in (
            (self.tenant_a, "tenant-a"), (self.tenant_b, "tenant-b"),
            (self.tenant_sa, "tenant-sa"), (self.tenant_c, "tenant-c"),
        ):
            await s.execute(
                text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": tid, "name": slug, "slug": f"{slug}-{tid.hex[:8]}"},
            )
        for u in (self.user_b, self.super_admin):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, :role, :given, :family)
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role,
                 "given": u.given_name, "family": u.family_name},
            )
        for tid, tenant, name in (
            (self.tree_a, self.tenant_a, "Global Family'A"),
            (self.tree_a_private, self.tenant_a, "Private Family A"),
            (self.tree_c, self.tenant_c, "Tenant C Family"),
        ):
            await s.execute(
                text("INSERT INTO family_trees (id, tenant_id, name) VALUES (:id, :tenant, :name)"),
                {"id": tid, "tenant": tenant, "name": name},
            )
        # A READ_WRITE global permission group in tenant A, attached to tree_a only
        # (tree_a_private is deliberately left out of any group).
        await s.execute(
            text("""INSERT INTO permission_groups (id, tenant_id, name, permission_level, is_global)
                    VALUES (:id, :tenant, 'Everyone Everywhere', 'READ_WRITE', true)"""),
            {"id": self.global_group_id, "tenant": self.tenant_a},
        )
        await s.execute(
            text("INSERT INTO permission_group_trees (id, group_id, tree_id) VALUES (gen_random_uuid(), :gid, :tid)"),
            {"gid": self.global_group_id, "tid": self.tree_a},
        )
        # Two persons in tree_a for relationship-mutation tests
        await s.execute(
            text("""
                INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                VALUES (:id, :tenant, :tid, 'Alice', 'Smith', 'FEMALE')
            """),
            {"id": self.alice_id, "tenant": self.tenant_a, "tid": self.tree_a},
        )
        await s.execute(
            text("""
                INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                VALUES (:id, :tenant, :tid, 'Bob', 'Smith', 'MALE')
            """),
            {"id": self.bob_id, "tenant": self.tenant_a, "tid": self.tree_a},
        )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> TwoTenantSeed:
    return await TwoTenantSeed(session).build()


class TestCrossTenantEnrollment:
    @pytest.mark.asyncio
    async def test_grant_global_tree_access_stamps_tree_own_tenant(self, seed: TwoTenantSeed):
        """A Tenant B user enrolling via a Tenant A global group must get a
        tree_members row tenant-stamped with Tenant A's id, not their own."""
        from src.infrastructure.database.global_access import grant_global_tree_access

        await grant_global_tree_access(seed.session, seed.user_b.id)
        await seed.session.commit()

        row = (await seed.session.execute(
            text("SELECT tenant_id, role FROM tree_members WHERE tree_id = :tid AND user_id = :uid"),
            {"tid": seed.tree_a, "uid": seed.user_b.id},
        )).first()
        assert row is not None, "Tenant B user should have been auto-enrolled in the global tree"
        assert row.tenant_id == seed.tenant_a, "tree_members.tenant_id must be the TREE's own tenant"
        assert row.role == "EDITOR"  # READ_WRITE maps to EDITOR

    @pytest.mark.asyncio
    async def test_cross_tenant_user_can_read_global_tree_person(self, seed: TwoTenantSeed):
        from src.api.v1._roles import resolve_effective_tree_role, resolve_tree_tenant_id
        from src.application.genealogy.service import FamilyTreeApplicationService
        from src.infrastructure.database.global_access import grant_global_tree_access

        await grant_global_tree_access(seed.session, seed.user_b.id)
        await seed.session.commit()

        role = await resolve_effective_tree_role(seed.session, seed.tree_a, seed.user_b)
        assert role is not None, "cross-tenant tree_members membership must resolve to a role"

        tree_tenant_id = await resolve_tree_tenant_id(seed.session, seed.tree_a)
        assert tree_tenant_id == seed.tenant_a

        svc = FamilyTreeApplicationService(seed.session)
        detail = await svc.get_person(seed.tree_a, tree_tenant_id, seed.alice_id)
        assert detail.display_given_name == "Alice"

    @pytest.mark.asyncio
    async def test_cross_tenant_editor_mutation_stamps_tree_own_tenant(self, seed: TwoTenantSeed):
        """Regression guard: a cross-tenant EDITOR's mutation must stamp new
        family_groups rows with the tree's own tenant, not the actor's — else
        the next same-tenant GraphLoader.load() would silently miss the row."""
        from src.application.genealogy.schemas import AddChildRequest
        from src.application.genealogy.service import FamilyTreeApplicationService
        from src.infrastructure.database.global_access import grant_global_tree_access
        from src.infrastructure.repositories.graph_loader import GraphLoader

        await grant_global_tree_access(seed.session, seed.user_b.id)
        await seed.session.commit()

        svc = FamilyTreeApplicationService(seed.session)
        await svc.add_child(seed.tree_a, seed.tenant_a, seed.alice_id, AddChildRequest(child_id=seed.bob_id))
        await seed.session.commit()

        fg_row = (await seed.session.execute(
            text("SELECT tenant_id FROM family_groups WHERE tree_id = :tid"),
            {"tid": seed.tree_a},
        )).first()
        assert fg_row is not None
        assert fg_row.tenant_id == seed.tenant_a, "new family_groups row must be stamped with the tree's own tenant"

        # A same-tenant load (as any Tenant A member would perform) must see it.
        graph = await GraphLoader(seed.session).load(seed.tree_a, seed.tenant_a)
        assert seed.bob_id in graph.children_of(seed.alice_id)

    @pytest.mark.asyncio
    async def test_ungloablizing_revokes_cross_tenant_access(self, seed: TwoTenantSeed):
        from src.api.v1.permission_groups import SetGlobalBody, set_permission_group_global
        from src.infrastructure.database.global_access import grant_global_tree_access

        await grant_global_tree_access(seed.session, seed.user_b.id)
        await seed.session.commit()

        await set_permission_group_global(
            seed.global_group_id, SetGlobalBody(is_global=False),
            seed.super_admin, seed.session, _fake_request(),
        )
        await seed.session.commit()

        row = (await seed.session.execute(
            text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid"),
            {"tid": seed.tree_a, "uid": seed.user_b.id},
        )).first()
        assert row is None, "un-globalizing must revoke the cross-tenant tree_members row"


class TestNonGlobalTreeStaysIsolated:
    @pytest.mark.asyncio
    async def test_cross_tenant_user_cannot_read_non_global_tree(self, seed: TwoTenantSeed):
        from src.api.v1._roles import resolve_effective_tree_role

        role = await resolve_effective_tree_role(seed.session, seed.tree_a_private, seed.user_b)
        assert role is None, "a Tenant B user must have no role on a non-global Tenant A tree"


class TestSuperAdminCrossNamespaceManagement:
    @pytest.mark.asyncio
    async def test_super_admin_can_attach_tree_from_other_namespace_to_group(self, seed: TwoTenantSeed):
        from src.api.v1.permission_groups import AddTreeBody, add_group_tree

        # Super Admin creates/owns a group in their own tenant, then attaches
        # tenant C's tree to it — this must succeed cross-tenant.
        group_id = uuid.uuid4()
        await seed.session.execute(
            text("""INSERT INTO permission_groups (id, tenant_id, name, permission_level)
                    VALUES (:id, :tenant, 'Cross-namespace group', 'READ')"""),
            {"id": group_id, "tenant": seed.tenant_sa},
        )
        await seed.session.commit()

        result = await add_group_tree(
            group_id, AddTreeBody(tree_id=seed.tree_c),
            seed.super_admin, seed.session, _fake_request(),
        )
        assert result.tree_id == seed.tree_c

        row = (await seed.session.execute(
            text("SELECT 1 FROM permission_group_trees WHERE group_id = :gid AND tree_id = :tid"),
            {"gid": group_id, "tid": seed.tree_c},
        )).first()
        assert row is not None

    @pytest.mark.asyncio
    async def test_list_admin_trees_all_namespaces_super_admin_only(self, seed: TwoTenantSeed):
        from src.api.v1.permission_groups import list_tenant_trees

        all_ns = await list_tenant_trees(
            seed.super_admin, seed.session, page=1, page_size=200, search=None, all_namespaces=True,
        )
        returned_ids = {item.id for item in all_ns.items}
        assert seed.tree_a in returned_ids
        assert seed.tree_a_private in returned_ids
        assert seed.tree_c in returned_ids
        by_id = {item.id: item for item in all_ns.items}
        assert by_id[seed.tree_a].namespace_id == seed.tenant_a

        own_tenant_only = await list_tenant_trees(
            seed.super_admin, seed.session, page=1, page_size=200, search=None, all_namespaces=False,
        )
        assert own_tenant_only.total == 0, "Super Admin's own (empty) tenant should have no trees without the flag"
