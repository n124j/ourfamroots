"""Real-database integration tests for living-member privacy masking on the
canvas graph endpoints (src/api/v1/collaboration.py get_tree_graph and
get_shared_tree_graph).

Same rule as test_person_privacy_masking.py, applied to the graph payload
that actually feeds the tree canvas: a *living* person's dates, locations,
and Notes are stripped for view-only viewers (authenticated VIEWER role,
and anonymous public share-link visitors); a deceased person's full details
are visible to both.

Follows the same real-Postgres pattern as test_change_request_revert.py (see
that module's docstring for local setup instructions). Requires
TEST_DATABASE_URL; the whole module is skipped if it isn't set.
"""
from __future__ import annotations

import os
import uuid
from datetime import date
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
    given = email.split("@")[0].title()
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name=given, family_name="Test", app_role=app_role,
    )


class Seed:
    """One tree with an OWNER, a VIEWER, a living person (Alice) and a
    deceased person (Bob), both with full "more details" + notes set, plus a
    share_token so the tree is publicly link-shared."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.uow = SimpleNamespace(_session=session)
        self.tenant_id = uuid.uuid4()
        self.tree_id = uuid.uuid4()
        self.share_token = uuid.uuid4()
        self.alice_id = uuid.uuid4()  # living
        self.bob_id = uuid.uuid4()    # deceased
        self.owner = _user(uuid.uuid4(), self.tenant_id, "owner@example.com")
        self.viewer = _user(uuid.uuid4(), self.tenant_id, "viewer@example.com")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.owner, self.viewer):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, :role, :given, :family)
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role,
                 "given": u.given_name, "family": u.family_name},
            )
        await s.execute(
            text("""INSERT INTO family_trees (id, tenant_id, name, share_token, link_sharing)
                    VALUES (:id, :tenant, 'The Test Family', :token, 'ANYONE')"""),
            {"id": self.tree_id, "tenant": self.tenant_id, "token": self.share_token},
        )
        for u, role in ((self.owner, "OWNER"), (self.viewer, "VIEWER")):
            await s.execute(
                text("""INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
                        VALUES (gen_random_uuid(), :tid, :uid, :tenant, :role, NOW())"""),
                {"tid": self.tree_id, "uid": u.id, "tenant": self.tenant_id, "role": role},
            )
        await s.execute(
            text("""
                INSERT INTO persons (
                    id, tenant_id, tree_id, display_given_name, display_surname, sex,
                    is_living, is_deceased, birth_date, birth_year, born_city, born_country, notes
                ) VALUES (
                    :id, :tenant, :tid, 'Alice', 'Smith', 'FEMALE',
                    true, false, :bdate, 1990, 'Springfield', 'USA', 'Loves gardening'
                )
            """),
            {"id": self.alice_id, "tenant": self.tenant_id, "tid": self.tree_id, "bdate": date(1990, 5, 1)},
        )
        await s.execute(
            text("""
                INSERT INTO persons (
                    id, tenant_id, tree_id, display_given_name, display_surname, sex,
                    is_living, is_deceased, birth_date, death_date, birth_year, death_year,
                    born_city, born_country, died_city, died_country, notes
                ) VALUES (
                    :id, :tenant, :tid, 'Bob', 'Smith', 'MALE',
                    false, true, :bdate, :ddate, 1920, 1990,
                    'Metropolis', 'USA', 'Gotham', 'USA', 'War veteran'
                )
            """),
            {"id": self.bob_id, "tenant": self.tenant_id, "tid": self.tree_id,
             "bdate": date(1920, 3, 1), "ddate": date(1990, 12, 1)},
        )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


def _person(persons: list[dict], person_id: uuid.UUID) -> dict:
    return next(p for p in persons if p["id"] == str(person_id))


class TestGetTreeGraphMasksLivingMembersForViewers:
    @pytest.mark.asyncio
    async def test_viewer_does_not_see_living_persons_dates_or_notes(self, seed: Seed):
        from src.api.v1.collaboration import get_tree_graph

        result = await get_tree_graph(seed.tree_id, seed.viewer, seed.uow)
        alice = _person(result["persons"], seed.alice_id)

        assert alice["displayGivenName"] == "Alice"
        assert alice["sex"] == "FEMALE"
        assert alice["isLiving"] is True
        assert "birthDate" not in alice
        assert "birthYear" not in alice
        assert "bornCity" not in alice
        assert "notes" not in alice

    @pytest.mark.asyncio
    async def test_viewer_sees_deceased_persons_full_details(self, seed: Seed):
        from src.api.v1.collaboration import get_tree_graph

        result = await get_tree_graph(seed.tree_id, seed.viewer, seed.uow)
        bob = _person(result["persons"], seed.bob_id)

        assert bob["isLiving"] is False
        assert bob["birthDate"] == "1920-03-01"
        assert bob["diedCity"] == "Gotham"
        assert bob["notes"] == "War veteran"

    @pytest.mark.asyncio
    async def test_owner_sees_living_persons_full_details(self, seed: Seed):
        from src.api.v1.collaboration import get_tree_graph

        result = await get_tree_graph(seed.tree_id, seed.owner, seed.uow)
        alice = _person(result["persons"], seed.alice_id)

        assert alice["birthDate"] == "1990-05-01"
        assert alice["bornCity"] == "Springfield"
        assert alice["notes"] == "Loves gardening"


class TestGetSharedTreeGraphMasksLivingMembersForAnonymousVisitors:
    @pytest.mark.asyncio
    async def test_anonymous_visitor_does_not_see_living_persons_dates_or_notes(self, seed: Seed):
        from src.api.v1.collaboration import get_shared_tree_graph

        result = await get_shared_tree_graph(seed.share_token, seed.uow)
        alice = _person(result["persons"], seed.alice_id)

        assert alice["displayGivenName"] == "Alice"
        assert alice["isLiving"] is True
        assert "birthDate" not in alice
        assert "bornCity" not in alice
        assert "notes" not in alice

    @pytest.mark.asyncio
    async def test_anonymous_visitor_sees_deceased_persons_full_details(self, seed: Seed):
        from src.api.v1.collaboration import get_shared_tree_graph

        result = await get_shared_tree_graph(seed.share_token, seed.uow)
        bob = _person(result["persons"], seed.bob_id)

        assert bob["isLiving"] is False
        assert bob["birthDate"] == "1920-03-01"
        assert bob["diedCity"] == "Gotham"
        assert bob["notes"] == "War veteran"
