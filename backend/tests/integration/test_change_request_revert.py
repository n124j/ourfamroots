"""Real-database integration tests for the change-request review/approve/revert
flow (docs/... "Propose changes" feature).

This module is deliberately different from the rest of tests/integration/:
every other file in that directory runs against the in-memory FakeUnitOfWork
(see tests/conftest.py) and never touches Postgres. The endpoints under test
here (src/api/v1/change_requests.py) are written as raw multi-table SQL
directly against persons/family_groups/family_group_members/tree_members/
tree_change_requests — there is no repository layer to fake convincingly, and
a mocked session would only prove the mocks were wired correctly, not that
the SQL is. So this module talks to a real Postgres instance instead.

Requires TEST_DATABASE_URL (see .github/workflows/ci.yml, which provisions
and migrates a throwaway `ourfamroots_test` database for exactly this). The
whole module is skipped if it isn't set — never run this against a real dev
or prod database.

Run locally:
    docker compose exec db psql -U postgres -c "CREATE DATABASE ourfamroots_test;"
    docker compose exec db psql -U postgres -d ourfamroots_test \
        -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; CREATE EXTENSION IF NOT EXISTS "pg_trgm";'
    docker compose run --rm \
        -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/ourfamroots_test \
        -e SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/ourfamroots_test \
        migrate
    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:7000/ourfamroots_test \
        pytest tests/integration/test_change_request_revert.py -v
"""
from __future__ import annotations

import os
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — this module needs a real, migrated Postgres "
        "database (see module docstring for local setup). Skipping.",
        allow_module_level=True,
    )


# ── DB fixture ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def _no_real_email():
    """Every resolve/submit call fires a fire-and-forget email send — stub it
    out so tests never attempt real SMTP and never leave dangling tasks."""
    with patch(
        "src.infrastructure.email.service.send_email", new=AsyncMock(return_value=None)
    ):
        yield


def _user(uid: uuid.UUID, tenant_id: uuid.UUID, email: str, app_role: str = "STANDARD") -> SimpleNamespace:
    """A stand-in for UserModel — the endpoints only ever read these attributes."""
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name=email.split("@")[0].title(), family_name="Test", app_role=app_role,
    )


class Seed:
    """Everything a test needs to call the change_requests endpoints directly,
    bypassing FastAPI/HTTP — `uow._session` is all these handlers ever touch.
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.uow = SimpleNamespace(_session=session)
        self.tenant_id = uuid.uuid4()
        self.tree_id = uuid.uuid4()
        self.owner = _user(uuid.uuid4(), self.tenant_id, "owner@example.com")
        self.editor = _user(uuid.uuid4(), self.tenant_id, "editor@example.com")
        self.super_admin = _user(uuid.uuid4(), self.tenant_id, "root@example.com", app_role="SUPER_ADMIN")
        self.alice_id = uuid.uuid4()

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.owner, self.editor, self.super_admin):
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
        await s.execute(
            text("""INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
                    VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER', NOW())"""),
            {"tid": self.tree_id, "uid": self.owner.id, "tenant": self.tenant_id},
        )
        await s.execute(
            text("""INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
                    VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'EDITOR', NOW())"""),
            {"tid": self.tree_id, "uid": self.editor.id, "tenant": self.tenant_id},
        )
        # Make the tree globally shared — required by POST .../change-requests/draft
        group_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO permission_groups (id, tenant_id, name, permission_level, is_global)
                    VALUES (:id, :tenant, 'Everyone', 'EDITOR', true)"""),
            {"id": group_id, "tenant": self.tenant_id},
        )
        await s.execute(
            text("INSERT INTO permission_group_trees (id, group_id, tree_id) VALUES (gen_random_uuid(), :gid, :tid)"),
            {"gid": group_id, "tid": self.tree_id},
        )
        # One original person: Alice, born 1955-03-02
        await s.execute(
            text("""
                INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex, birth_date)
                VALUES (:id, :tenant, :tid, 'Alice', 'Smith', 'FEMALE', :bdate)
            """),
            {"id": self.alice_id, "tenant": self.tenant_id, "tid": self.tree_id, "bdate": date(1955, 3, 2)},
        )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


# ── The full propose → approve → revert lifecycle ───────────────────────────

class TestProposeApproveRevertLifecycle:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self, seed: Seed):
        from src.api.v1.change_requests import (
            create_draft, get_change_request_diff, get_draft_diff,
            resolve_change_request, revert_change_request,
            ResolveChangeRequestBody, SubmitChangeRequestBody, submit_change_request,
        )

        s = seed.session

        # ── 1. Editor starts a draft ────────────────────────────────────────
        draft = await create_draft(seed.tree_id, seed.editor, seed.uow)
        draft_tree_id = uuid.UUID(draft["draft_tree_id"])

        alice_draft_row = (await s.execute(
            text("SELECT id FROM persons WHERE tree_id = :tid AND origin_person_id = :orig"),
            {"tid": draft_tree_id, "orig": seed.alice_id},
        )).first()
        assert alice_draft_row is not None, "draft must contain a clone of Alice"

        # Editor changes Alice's surname in the draft, and adds a new person.
        await s.execute(
            text("UPDATE persons SET display_surname = 'Jones' WHERE id = :id"),
            {"id": alice_draft_row.id},
        )
        bob_draft_id = uuid.uuid4()
        await s.execute(
            text("""
                INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                VALUES (:id, :tenant, :tid, 'Bob', 'Jones', 'MALE')
            """),
            {"id": bob_draft_id, "tenant": seed.tenant_id, "tid": draft_tree_id},
        )
        await s.commit()

        # ── 2. Diff before submission is visible to the draft's own owner ──
        pre_submit_diff = await get_draft_diff(draft_tree_id, seed.editor, seed.uow)
        assert {p["display_given_name"] for p in pre_submit_diff["added_persons"]} == {"Bob"}
        assert len(pre_submit_diff["modified_persons"]) == 1
        assert pre_submit_diff["modified_persons"][0]["changes"]["display_surname"] == {
            "before": "Smith", "after": "Jones",
        }

        # ── 3. Editor posts it for review ───────────────────────────────────
        submitted = await submit_change_request(
            draft_tree_id, SubmitChangeRequestBody(message="Please review"), seed.editor, seed.uow,
        )
        request_id = uuid.UUID(submitted["id"])
        assert submitted["status"] == "PENDING"

        # ── 4. Owner reviews the diff (connecting-member / added/modified) ─
        diff = await get_change_request_diff(seed.tree_id, request_id, seed.owner, seed.uow)
        assert diff["requester_name"] == "Editor Test"
        assert len(diff["added_persons"]) == 1
        assert diff["added_persons"][0]["display_given_name"] == "Bob"
        assert len(diff["modified_persons"]) == 1

        # ── 5. Owner approves — merges onto the live tree ───────────────────
        resolved = await resolve_change_request(
            seed.tree_id, request_id, ResolveChangeRequestBody(action="approve"), seed.owner, seed.uow,
        )
        assert resolved["status"] == "APPROVED"

        live_rows = (await s.execute(
            text("SELECT id, display_given_name, display_surname FROM persons WHERE tree_id = :tid AND is_deleted = false"),
            {"tid": seed.tree_id},
        )).fetchall()
        by_name = {r.display_given_name: r for r in live_rows}
        assert "Bob" in by_name, "approval must adopt the new person into the live tree"
        assert by_name["Alice"].display_surname == "Jones", "approval must apply the field edit"
        assert by_name["Alice"].id == seed.alice_id, "matched person keeps its original id"

        approve_entry = (await s.execute(
            text("SELECT before, after FROM audit_logs WHERE entity_id = :rid AND action = 'APPROVE_CHANGE'"),
            {"rid": request_id},
        )).first()
        assert approve_entry is not None
        assert approve_entry.after == {"added": 1, "modified": 1, "removed": 0}
        snapshot_names = {p["id"]: p["display_surname"] for p in approve_entry.before["persons"]}
        assert snapshot_names[str(seed.alice_id)] == "Smith", "snapshot must hold the PRE-approval value"

        # (Who's *allowed* to call revert_change_request at all is enforced by
        # FastAPI's SuperAdminDep before the handler body ever runs — see
        # tests/unit/test_super_admin_dependency.py. Calling the handler
        # directly here, as the rest of this module does, bypasses that
        # dependency chain, so it isn't meaningful to assert a 403 for a
        # non-admin caller at this layer.)

        # ── 6. Super Admin reverts ──────────────────────────────────────────
        from fastapi import HTTPException
        reverted = await revert_change_request(seed.tree_id, request_id, seed.super_admin, seed.uow)
        assert reverted["reverted"] is True

        live_rows_after = (await s.execute(
            text("SELECT display_given_name, display_surname, is_deleted FROM persons WHERE tree_id = :tid"),
            {"tid": seed.tree_id},
        )).fetchall()
        by_name_after = {r.display_given_name: r for r in live_rows_after}
        assert by_name_after["Alice"].display_surname == "Smith", "revert must restore the pre-approval field value"
        assert by_name_after["Bob"].is_deleted is True, "revert must undo the adoption of the newly added person"

        # ── 7. Reverting twice is rejected ──────────────────────────────────
        with pytest.raises(HTTPException) as exc_info:
            await revert_change_request(seed.tree_id, request_id, seed.super_admin, seed.uow)
        assert exc_info.value.status_code == 409

        request_row = (await s.execute(
            text("SELECT reverted_by_id, reverted_at, status FROM tree_change_requests WHERE id = :rid"),
            {"rid": request_id},
        )).first()
        assert request_row.reverted_by_id == seed.super_admin.id
        assert request_row.reverted_at is not None
        assert request_row.status == "APPROVED", "status stays APPROVED — revert is tracked separately"

        revert_entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :rid AND action = 'REVERT_CHANGE'"),
            {"rid": request_id},
        )).first()
        assert revert_entry is not None


class TestRevertRelationships:
    @pytest.mark.asyncio
    async def test_revert_restores_family_group_structure(self, seed: Seed):
        """Alice gets a new child added in the draft; approving creates the
        union+parent-child link, reverting must remove it again."""
        from src.api.v1.change_requests import (
            create_draft, resolve_change_request, revert_change_request,
            ResolveChangeRequestBody, SubmitChangeRequestBody, submit_change_request,
        )

        s = seed.session
        draft = await create_draft(seed.tree_id, seed.editor, seed.uow)
        draft_tree_id = uuid.UUID(draft["draft_tree_id"])

        alice_draft_row = (await s.execute(
            text("SELECT id FROM persons WHERE tree_id = :tid AND origin_person_id = :orig"),
            {"tid": draft_tree_id, "orig": seed.alice_id},
        )).first()

        child_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                    VALUES (:id, :tenant, :tid, 'Charlie', 'Jones', 'MALE')"""),
            {"id": child_id, "tenant": seed.tenant_id, "tid": draft_tree_id},
        )
        fg_id = uuid.uuid4()
        await s.execute(
            text("INSERT INTO family_groups (id, tenant_id, tree_id, union_type) VALUES (:id, :tenant, :tid, 'UNKNOWN')"),
            {"id": fg_id, "tenant": seed.tenant_id, "tid": draft_tree_id},
        )
        await s.execute(
            text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
                    VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')"""),
            {"tenant": seed.tenant_id, "tid": draft_tree_id, "fgid": fg_id, "pid": alice_draft_row.id},
        )
        await s.execute(
            text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                    VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', 'BIOLOGICAL')"""),
            {"tenant": seed.tenant_id, "tid": draft_tree_id, "fgid": fg_id, "pid": child_id},
        )
        await s.commit()

        submitted = await submit_change_request(
            draft_tree_id, SubmitChangeRequestBody(message=None), seed.editor, seed.uow,
        )
        request_id = uuid.UUID(submitted["id"])
        await resolve_change_request(
            seed.tree_id, request_id, ResolveChangeRequestBody(action="approve"), seed.owner, seed.uow,
        )

        links_after_approve = (await s.execute(
            text("SELECT COUNT(*) FROM family_group_members WHERE tree_id = :tid"), {"tid": seed.tree_id},
        )).scalar()
        assert links_after_approve == 2, "parent + child rows for the new union"

        await revert_change_request(seed.tree_id, request_id, seed.super_admin, seed.uow)

        links_after_revert = (await s.execute(
            text("SELECT COUNT(*) FROM family_group_members WHERE tree_id = :tid"), {"tid": seed.tree_id},
        )).scalar()
        assert links_after_revert == 0, "the union added by the approval must be gone after revert"


class TestDenyDoesNotSnapshotOrAllowRevert:
    @pytest.mark.asyncio
    async def test_denied_request_cannot_be_reverted(self, seed: Seed):
        from src.api.v1.change_requests import (
            create_draft, resolve_change_request, revert_change_request,
            ResolveChangeRequestBody, SubmitChangeRequestBody, submit_change_request,
        )
        from fastapi import HTTPException

        draft = await create_draft(seed.tree_id, seed.editor, seed.uow)
        draft_tree_id = uuid.UUID(draft["draft_tree_id"])
        submitted = await submit_change_request(
            draft_tree_id, SubmitChangeRequestBody(message=None), seed.editor, seed.uow,
        )
        request_id = uuid.UUID(submitted["id"])

        resolved = await resolve_change_request(
            seed.tree_id, request_id, ResolveChangeRequestBody(action="deny"), seed.owner, seed.uow,
        )
        assert resolved["status"] == "DENIED"

        with pytest.raises(HTTPException) as exc_info:
            await revert_change_request(seed.tree_id, request_id, seed.super_admin, seed.uow)
        assert exc_info.value.status_code == 409
