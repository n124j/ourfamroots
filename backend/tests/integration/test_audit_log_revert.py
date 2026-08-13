"""Real-database integration tests for the generalized Super-Admin revert.

Covers both revert strategies dispatched by `revert_audit_entry`:
- Full-tree-snapshot revert: DELETE_PERSON, REMOVE_RELATIONSHIP, ADD_RELATIONSHIP.
- Surgical single-row revert: CREATE_PERSON, UPDATE_PERSON, UPDATE_RELATIONSHIP
  (on both `family_groups` and `family_group_members`).

Shares the same real-Postgres fixture setup as test_change_request_revert.py
(see that module's docstring for local setup — TEST_DATABASE_URL etc.); the
whole module is skipped if it isn't set.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.test_change_request_revert import Seed, seed, session  # noqa: F401

pytestmark = pytest.mark.integration


class TestDeletePersonRevert:
    @pytest.mark.asyncio
    async def test_revert_restores_the_deleted_person(self, seed: Seed):
        from src.api.v1.collaboration import revert_audit_log_entry
        from src.api.v1.persons import delete_person

        s = seed.session

        await delete_person(seed.tree_id, seed.alice_id, seed.editor, s)

        deleted_row = (await s.execute(
            text("SELECT is_deleted FROM persons WHERE id = :id"), {"id": seed.alice_id},
        )).first()
        assert deleted_row.is_deleted is True

        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :pid AND action = 'DELETE_PERSON'"),
            {"pid": seed.alice_id},
        )).first()
        assert entry is not None, "delete_person must record a revertible audit entry"

        result = await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert result["reverted"] is True

        restored_row = (await s.execute(
            text("SELECT is_deleted, display_given_name FROM persons WHERE id = :id"), {"id": seed.alice_id},
        )).first()
        assert restored_row.is_deleted is False
        assert restored_row.display_given_name == "Alice"

    @pytest.mark.asyncio
    async def test_double_revert_is_rejected(self, seed: Seed):
        from fastapi import HTTPException
        from src.api.v1.collaboration import revert_audit_log_entry
        from src.api.v1.persons import delete_person

        s = seed.session
        await delete_person(seed.tree_id, seed.alice_id, seed.editor, s)
        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :pid AND action = 'DELETE_PERSON'"),
            {"pid": seed.alice_id},
        )).first()

        await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)

        with pytest.raises(HTTPException) as exc_info:
            await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_non_revertible_entry_is_rejected(self, seed: Seed):
        """A plain UPDATE_PERSON-style entry with no full-tree snapshot
        attached can't be reverted through the generic endpoint."""
        from fastapi import HTTPException
        from src.api.v1.collaboration import revert_audit_log_entry

        s = seed.session
        entry_id = uuid.uuid4()
        await s.execute(
            text("""
                INSERT INTO audit_logs (id, tree_id, tenant_id, actor_id, actor_display_name, action, entity_type, entity_id)
                VALUES (:id, :tid, :tenant, :actor, 'Editor Test', 'UPDATE_PERSON', 'PERSON', :pid)
            """),
            {"id": entry_id, "tid": seed.tree_id, "tenant": seed.tenant_id, "actor": seed.editor.id, "pid": seed.alice_id},
        )
        await s.commit()

        with pytest.raises(HTTPException) as exc_info:
            await revert_audit_log_entry(seed.tree_id, entry_id, seed.super_admin, seed.uow)
        assert exc_info.value.status_code == 409


class TestRemoveRelationshipRevert:
    @pytest.mark.asyncio
    async def test_revert_restores_a_hard_deleted_family_group(self, seed: Seed):
        """family_groups/family_group_members are hard-deleted, so this is
        the only way to recover a removed union — no soft-delete flag to
        flip back, unlike persons."""
        from src.api.v1.collaboration import delete_family_group, revert_audit_log_entry

        s = seed.session
        child_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                    VALUES (:id, :tenant, :tid, 'Charlie', 'Smith', 'MALE')"""),
            {"id": child_id, "tenant": seed.tenant_id, "tid": seed.tree_id},
        )
        fg_id = uuid.uuid4()
        await s.execute(
            text("INSERT INTO family_groups (id, tenant_id, tree_id, union_type) VALUES (:id, :tenant, :tid, 'UNKNOWN')"),
            {"id": fg_id, "tenant": seed.tenant_id, "tid": seed.tree_id},
        )
        await s.execute(
            text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
                    VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')"""),
            {"tenant": seed.tenant_id, "tid": seed.tree_id, "fgid": fg_id, "pid": seed.alice_id},
        )
        await s.execute(
            text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                    VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', 'BIOLOGICAL')"""),
            {"tenant": seed.tenant_id, "tid": seed.tree_id, "fgid": fg_id, "pid": child_id},
        )
        await s.commit()

        await delete_family_group(seed.tree_id, fg_id, seed.editor, seed.uow)

        links_after_delete = (await s.execute(
            text("SELECT COUNT(*) FROM family_group_members WHERE tree_id = :tid"), {"tid": seed.tree_id},
        )).scalar()
        assert links_after_delete == 0

        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :fgid AND action = 'REMOVE_RELATIONSHIP'"),
            {"fgid": fg_id},
        )).first()
        assert entry is not None

        result = await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert result["reverted"] is True

        links_after_revert = (await s.execute(
            text("SELECT COUNT(*) FROM family_group_members WHERE tree_id = :tid"), {"tid": seed.tree_id},
        )).scalar()
        assert links_after_revert == 2, "revert must recreate the parent+child rows"


class TestCreatePersonRevert:
    @pytest.mark.asyncio
    async def test_revert_soft_deletes_the_created_person(self, seed: Seed):
        from src.api.v1.collaboration import revert_audit_log_entry
        from src.api.v1.persons import create_person
        from src.application.genealogy.schemas import CreatePersonRequest
        from src.domain.genealogy.entities import Sex

        s = seed.session
        created = await create_person(
            seed.tree_id, CreatePersonRequest(given_name="Dana", surname="Lee", sex=Sex.FEMALE),
            seed.editor, s,
        )

        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :pid AND action = 'CREATE_PERSON'"),
            {"pid": created.id},
        )).first()
        assert entry is not None

        result = await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert result["reverted"] is True

        row = (await s.execute(text("SELECT is_deleted FROM persons WHERE id = :id"), {"id": created.id})).first()
        assert row.is_deleted is True


class TestUpdatePersonRevert:
    @pytest.mark.asyncio
    async def test_revert_restores_every_edited_field(self, seed: Seed):
        """Regression check: the old before-snapshot only captured
        name/sex/is_living — this must restore ALL editable fields,
        including ones like birth_date that weren't captured before."""
        from src.api.v1.collaboration import revert_audit_log_entry
        from src.api.v1.persons import update_person
        from src.application.genealogy.schemas import UpdatePersonRequest
        from src.domain.genealogy.entities import Sex

        s = seed.session
        await update_person(
            seed.tree_id, seed.alice_id,
            UpdatePersonRequest(given_name="Alicia", surname="Jones", sex=Sex.FEMALE,
                                 birth_date=date(1999, 12, 31), notes="edited"),
            seed.editor, s,
        )

        row_after_edit = (await s.execute(
            text("SELECT display_given_name, birth_date FROM persons WHERE id = :id"), {"id": seed.alice_id},
        )).first()
        assert row_after_edit.display_given_name == "Alicia"
        assert row_after_edit.birth_date == date(1999, 12, 31)

        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :pid AND action = 'UPDATE_PERSON'"),
            {"pid": seed.alice_id},
        )).first()

        result = await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert result["reverted"] is True

        restored = (await s.execute(
            text("SELECT display_given_name, display_surname, birth_date, notes FROM persons WHERE id = :id"),
            {"id": seed.alice_id},
        )).first()
        assert restored.display_given_name == "Alice"
        assert restored.display_surname == "Smith"
        assert restored.birth_date == date(1955, 3, 2)
        assert restored.notes is None


class TestRelationshipFieldRevert:
    @pytest.mark.asyncio
    async def test_revert_restores_family_group_fields(self, seed: Seed):
        from src.api.v1.collaboration import UpdateFamilyGroupRequest, revert_audit_log_entry, update_family_group

        s = seed.session
        fg_id = uuid.uuid4()
        spouse_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                    VALUES (:id, :tenant, :tid, 'Bob', 'Smith', 'MALE')"""),
            {"id": spouse_id, "tenant": seed.tenant_id, "tid": seed.tree_id},
        )
        await s.execute(
            text("""INSERT INTO family_groups (id, tenant_id, tree_id, union_type, custom_label)
                    VALUES (:id, :tenant, :tid, 'MARRIAGE', 'Original label')"""),
            {"id": fg_id, "tenant": seed.tenant_id, "tid": seed.tree_id},
        )
        await s.commit()

        await update_family_group(
            seed.tree_id, fg_id, UpdateFamilyGroupRequest(custom_label="Renamed", union_type="PARTNERSHIP"),
            seed.editor, seed.uow,
        )
        row_after = (await s.execute(
            text("SELECT custom_label, union_type FROM family_groups WHERE id = :id"), {"id": fg_id},
        )).first()
        assert row_after.custom_label == "Renamed"
        assert row_after.union_type == "PARTNERSHIP"

        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :fgid AND action = 'UPDATE_RELATIONSHIP'"),
            {"fgid": fg_id},
        )).first()

        result = await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert result["reverted"] is True

        restored = (await s.execute(
            text("SELECT custom_label, union_type FROM family_groups WHERE id = :id"), {"id": fg_id},
        )).first()
        assert restored.custom_label == "Original label"
        assert restored.union_type == "MARRIAGE"

    @pytest.mark.asyncio
    async def test_revert_restores_member_parentage_type(self, seed: Seed):
        from src.api.v1.collaboration import UpdateMemberParentageRequest, revert_audit_log_entry, update_family_group_member

        s = seed.session
        fg_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                    VALUES (:id, :tenant, :tid, 'Pat', 'Smith', 'FEMALE')"""),
            {"id": parent_id, "tenant": seed.tenant_id, "tid": seed.tree_id},
        )
        await s.execute(
            text("INSERT INTO family_groups (id, tenant_id, tree_id, union_type) VALUES (:id, :tenant, :tid, 'UNKNOWN')"),
            {"id": fg_id, "tenant": seed.tenant_id, "tid": seed.tree_id},
        )
        await s.execute(
            text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
                    VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')"""),
            {"tenant": seed.tenant_id, "tid": seed.tree_id, "fgid": fg_id, "pid": parent_id},
        )
        await s.execute(
            text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                    VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', 'BIOLOGICAL')"""),
            {"tenant": seed.tenant_id, "tid": seed.tree_id, "fgid": fg_id, "pid": seed.alice_id},
        )
        await s.commit()

        await update_family_group_member(
            seed.tree_id, fg_id, seed.alice_id, UpdateMemberParentageRequest(parentage_type="ADOPTIVE"),
            seed.editor, seed.uow,
        )
        row_after = (await s.execute(
            text("SELECT parentage_type FROM family_group_members WHERE family_group_id = :fgid AND person_id = :pid"),
            {"fgid": fg_id, "pid": seed.alice_id},
        )).first()
        assert row_after.parentage_type == "ADOPTIVE"

        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :fgid AND action = 'UPDATE_RELATIONSHIP' ORDER BY occurred_at DESC LIMIT 1"),
            {"fgid": fg_id},
        )).first()

        result = await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert result["reverted"] is True

        restored = (await s.execute(
            text("SELECT parentage_type FROM family_group_members WHERE family_group_id = :fgid AND person_id = :pid"),
            {"fgid": fg_id, "pid": seed.alice_id},
        )).first()
        assert restored.parentage_type == "BIOLOGICAL"


class TestAddRelationshipRevert:
    @pytest.mark.asyncio
    async def test_revert_removes_the_added_child(self, seed: Seed):
        """Uses the full-tree-snapshot path (same engine as DELETE_PERSON),
        since add_child delegates to the genealogy graph service."""
        from src.api.v1.collaboration import revert_audit_log_entry
        from src.api.v1.persons import add_child
        from src.application.genealogy.schemas import AddChildRequest

        s = seed.session
        child_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname, sex)
                    VALUES (:id, :tenant, :tid, 'Ella', 'Smith', 'FEMALE')"""),
            {"id": child_id, "tenant": seed.tenant_id, "tid": seed.tree_id},
        )
        await s.commit()

        await add_child(seed.tree_id, seed.alice_id, AddChildRequest(child_id=child_id), seed.editor, s, force=False)

        links_after_add = (await s.execute(
            text("SELECT COUNT(*) FROM family_group_members WHERE tree_id = :tid"), {"tid": seed.tree_id},
        )).scalar()
        assert links_after_add > 0

        entry = (await s.execute(
            text("SELECT id FROM audit_logs WHERE entity_id = :pid AND action = 'ADD_RELATIONSHIP'"),
            {"pid": seed.alice_id},
        )).first()
        assert entry is not None

        result = await revert_audit_log_entry(seed.tree_id, entry.id, seed.super_admin, seed.uow)
        assert result["reverted"] is True

        links_after_revert = (await s.execute(
            text("SELECT COUNT(*) FROM family_group_members WHERE tree_id = :tid"), {"tid": seed.tree_id},
        )).scalar()
        assert links_after_revert == 0, "revert must remove the union created by add_child"
