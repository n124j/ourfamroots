"""Real-database integration tests for the non-family-group relationships
endpoints (src/api/v1/relationships.py) — Godparent/Guardian/Mentor/Custom
links between two people, independent of the exclusive parent-child/spouse
family-group graph.

Follows the same real-Postgres pattern as test_dashboard_hide_tree.py (see
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
    """A stand-in for UserModel — the endpoints only ever read these attributes."""
    given = email.split("@")[0].title()
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name=given, family_name="Test", full_name=f"{given} Test", app_role=app_role,
    )


class Seed:
    """One tree with three persons (Alice, Bob, Carol) and four users:
    an OWNER, an EDITOR, a VIEWER, and an outsider with no tree_members row."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.tree_id = uuid.uuid4()
        self.alice_id = uuid.uuid4()
        self.bob_id = uuid.uuid4()
        self.carol_id = uuid.uuid4()
        self.owner = _user(uuid.uuid4(), self.tenant_id, "owner@example.com")
        self.editor = _user(uuid.uuid4(), self.tenant_id, "editor@example.com")
        self.viewer = _user(uuid.uuid4(), self.tenant_id, "viewer@example.com")
        self.outsider = _user(uuid.uuid4(), self.tenant_id, "outsider@example.com")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.owner, self.editor, self.viewer, self.outsider):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, :role, :given, :family)
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role,
                 "given": u.given_name, "family": u.family_name},
            )
        await s.execute(
            text("INSERT INTO family_trees (id, tenant_id, name) VALUES (:id, :tenant, 'The Test Family')"),
            {"id": self.tree_id, "tenant": self.tenant_id},
        )
        for u, role in ((self.owner, "OWNER"), (self.editor, "EDITOR"), (self.viewer, "VIEWER")):
            await s.execute(
                text("""INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
                        VALUES (gen_random_uuid(), :tid, :uid, :tenant, :role, NOW())"""),
                {"tid": self.tree_id, "uid": u.id, "tenant": self.tenant_id, "role": role},
            )
        for pid, given in ((self.alice_id, "Alice"), (self.bob_id, "Bob"), (self.carol_id, "Carol")):
            await s.execute(
                text("""
                    INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                    VALUES (:id, :tenant, :tid, :given, 'Smith', 'UNKNOWN')
                """),
                {"id": pid, "tenant": self.tenant_id, "tid": self.tree_id, "given": given},
            )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


async def _relationship_rows(session: AsyncSession, tree_id: uuid.UUID) -> list:
    return (await session.execute(
        text("SELECT id, person1_id, person2_id, relationship_type, custom_label FROM relationships WHERE tree_id = :tid"),
        {"tid": tree_id},
    )).all()


class TestCreateRelationship:
    @pytest.mark.asyncio
    async def test_editor_can_create_a_godparent_relationship(self, seed: Seed):
        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="GODPARENT")
        result = await create_relationship(seed.tree_id, req, seed.editor, seed.session)

        assert result.relationship_type == "GODPARENT"
        assert result.person1_id == seed.alice_id
        assert result.person2_id == seed.bob_id
        rows = await _relationship_rows(seed.session, seed.tree_id)
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_owner_can_create_each_relationship_type(self, seed: Seed):
        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        for rtype in ("GODPARENT", "GUARDIAN", "MENTOR"):
            req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type=rtype)
            result = await create_relationship(seed.tree_id, req, seed.owner, seed.session)
            assert result.relationship_type == rtype

        rows = await _relationship_rows(seed.session, seed.tree_id)
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_custom_relationship_requires_a_label(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="CUSTOM")
        with pytest.raises(HTTPException) as exc_info:
            await create_relationship(seed.tree_id, req, seed.editor, seed.session)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_custom_relationship_with_a_label_succeeds(self, seed: Seed):
        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(
            person1_id=seed.alice_id, person2_id=seed.bob_id,
            relationship_type="CUSTOM", custom_label="Business Partner",
        )
        result = await create_relationship(seed.tree_id, req, seed.editor, seed.session)
        assert result.custom_label == "Business Partner"

    @pytest.mark.asyncio
    async def test_self_relationship_rejected(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.alice_id, relationship_type="GUARDIAN")
        with pytest.raises(HTTPException) as exc_info:
            await create_relationship(seed.tree_id, req, seed.editor, seed.session)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_pair_and_type_rejected(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="MENTOR")
        await create_relationship(seed.tree_id, req, seed.editor, seed.session)

        with pytest.raises(HTTPException) as exc_info:
            await create_relationship(seed.tree_id, req, seed.editor, seed.session)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_same_pair_different_type_is_allowed(self, seed: Seed):
        """A person can hold multiple different relationship roles with the same other person."""
        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="GUARDIAN"),
            seed.editor, seed.session,
        )
        await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="MENTOR"),
            seed.editor, seed.session,
        )
        rows = await _relationship_rows(seed.session, seed.tree_id)
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_person_not_in_tree_rejected(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=uuid.uuid4(), relationship_type="MENTOR")
        with pytest.raises(HTTPException) as exc_info:
            await create_relationship(seed.tree_id, req, seed.editor, seed.session)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_a_relationship(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="GODPARENT")
        with pytest.raises(HTTPException) as exc_info:
            await create_relationship(seed.tree_id, req, seed.viewer, seed.session)
        assert exc_info.value.status_code == 403

        rows = await _relationship_rows(seed.session, seed.tree_id)
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_non_member_cannot_create_a_relationship(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship

        req = CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="GODPARENT")
        with pytest.raises(HTTPException) as exc_info:
            await create_relationship(seed.tree_id, req, seed.outsider, seed.session)
        assert exc_info.value.status_code == 403


class TestListRelationships:
    @pytest.mark.asyncio
    async def test_member_can_list_all_relationships(self, seed: Seed):
        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship, list_relationships

        await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="GODPARENT"),
            seed.editor, seed.session,
        )
        await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.carol_id, person2_id=seed.bob_id, relationship_type="GUARDIAN"),
            seed.editor, seed.session,
        )

        results = await list_relationships(seed.tree_id, seed.viewer, seed.session, person_id=None)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_filters_by_person_id_on_either_side(self, seed: Seed):
        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship, list_relationships

        await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="GODPARENT"),
            seed.editor, seed.session,
        )
        await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.carol_id, person2_id=seed.bob_id, relationship_type="GUARDIAN"),
            seed.editor, seed.session,
        )

        # Bob is person2 in both relationships.
        bob_results = await list_relationships(seed.tree_id, seed.viewer, seed.session, person_id=seed.bob_id)
        assert len(bob_results) == 2

        # Alice is only in the first.
        alice_results = await list_relationships(seed.tree_id, seed.viewer, seed.session, person_id=seed.alice_id)
        assert len(alice_results) == 1
        assert alice_results[0].relationship_type == "GODPARENT"

    @pytest.mark.asyncio
    async def test_non_member_cannot_list_relationships(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import list_relationships

        with pytest.raises(HTTPException) as exc_info:
            await list_relationships(seed.tree_id, seed.outsider, seed.session, person_id=None)
        assert exc_info.value.status_code == 403


class TestDeleteRelationship:
    @pytest.mark.asyncio
    async def test_editor_can_delete_a_relationship(self, seed: Seed):
        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship, delete_relationship

        created = await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="MENTOR"),
            seed.editor, seed.session,
        )

        await delete_relationship(seed.tree_id, created.id, seed.editor, seed.session)

        rows = await _relationship_rows(seed.session, seed.tree_id)
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_deleting_unknown_relationship_404s(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import delete_relationship

        with pytest.raises(HTTPException) as exc_info:
            await delete_relationship(seed.tree_id, uuid.uuid4(), seed.editor, seed.session)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_viewer_cannot_delete_a_relationship(self, seed: Seed):
        from fastapi import HTTPException

        from src.api.v1.relationships import CreateRelationshipRequest, create_relationship, delete_relationship

        created = await create_relationship(
            seed.tree_id,
            CreateRelationshipRequest(person1_id=seed.alice_id, person2_id=seed.bob_id, relationship_type="MENTOR"),
            seed.editor, seed.session,
        )

        with pytest.raises(HTTPException) as exc_info:
            await delete_relationship(seed.tree_id, created.id, seed.viewer, seed.session)
        assert exc_info.value.status_code == 403

        rows = await _relationship_rows(seed.session, seed.tree_id)
        assert len(rows) == 1
