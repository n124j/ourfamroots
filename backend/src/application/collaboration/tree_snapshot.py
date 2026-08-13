"""Shared point-in-time revert engine behind the Super-Admin "revert" safety
net in the tree's Audit Log.

Every revertible audit entry is tagged with a `metadata.snapshot_kind`:

- `"full_tree"` — a full JSON snapshot of the tree's persons + family
  structure, captured before a mutation whose blast radius isn't cheaply
  knowable at the API layer (change-request approval, DELETE_PERSON,
  REMOVE_RELATIONSHIP, ADD_RELATIONSHIP via the genealogy graph service).
  Restoring it resets the *entire tree* to that point in time — simple and
  proven, but blunt: it also undoes anything else changed since.
- `"person_created"` / `"person_updated"` / `"relationship_field"` — cheap,
  surgical single-row snapshots for the plain single-row mutations
  (CREATE_PERSON, UPDATE_PERSON, UPDATE_RELATIONSHIP), restoring just that
  one row without touching the rest of the tree.

Every capture site goes through `record_revertible_action` so the
`snapshot_kind` marker is only ever set in one place. `revert_audit_entry` is
the shared guard+restore+log orchestration used by both the generic revert
endpoint and the change-request-specific one, dispatching to the right
restore function by kind.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.collaboration.entities import Action, AuditEntityType, AuditEntry
from src.infrastructure.repositories.collaboration import AuditLogRepository

PERSON_SNAPSHOT_FIELDS = [
    "display_given_name", "display_surname", "sex",
    "is_living", "is_deceased", "photo_url",
    "birth_date", "death_date", "birth_year", "death_year",
    "born_city", "born_country", "died_city", "died_country",
    "notes",
]

PERSON_DATE_FIELDS = {"birth_date", "death_date"}

FAMILY_GROUP_FIELDS = [
    "custom_label", "is_divorced", "union_type",
    "union_date", "union_date_year", "union_end_date", "union_end_date_year",
]

FAMILY_GROUP_DATE_FIELDS = {"union_date", "union_end_date"}

#: Snapshot kinds the generic revert endpoint knows how to restore.
#: "full_tree" resets the whole tree to a point in time; the rest are
#: surgical single-row restores that never touch anything else.
REVERTIBLE_SNAPSHOT_KINDS = {"full_tree", "person_created", "person_updated", "relationship_field"}

#: Which of the two revert UX treatments each kind gets on the frontend —
#: the broad "this resets the entire tree" warning for "full_tree", or a
#: lighter "just this row" warning for everything else.
FULL_TREE_KINDS = {"full_tree"}


def jsonable(v: Any) -> Any:
    return v.isoformat() if hasattr(v, "isoformat") else v


def to_date(v: Any) -> Any:
    return date.fromisoformat(v) if isinstance(v, str) else v


def is_revertible(entry: AuditEntry) -> bool:
    """True if *entry* carries a snapshot the generic revert endpoint can
    restore and hasn't already been reverted."""
    if entry.reverted_at is not None:
        return False
    kind = entry.metadata.get("snapshot_kind")
    if kind not in REVERTIBLE_SNAPSHOT_KINDS:
        return False
    return kind == "person_created" or entry.before is not None


def revert_kind_for(entry: AuditEntry) -> str:
    """"full_tree" or "field" — which revert-warning treatment applies."""
    kind = entry.metadata.get("snapshot_kind")
    return "full_tree" if kind in FULL_TREE_KINDS else "field"


async def snapshot_tree(session: AsyncSession, tree_id: uuid.UUID) -> dict:
    """Full point-in-time snapshot of a tree's persons + family structure,
    JSON-serialisable. Captured right before a destructive mutation so a
    Super Admin can later revert it back to exactly this state."""
    person_rows = (await session.execute(
        text(f"SELECT id, {', '.join(PERSON_SNAPSHOT_FIELDS)} FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": tree_id},
    )).fetchall()
    persons = [
        {"id": str(r.id), **{f: jsonable(getattr(r, f)) for f in PERSON_SNAPSHOT_FIELDS}}
        for r in person_rows
    ]

    fg_rows = (await session.execute(
        text("""
            SELECT fg.id AS fg_id, fg.union_type, fg.custom_label, fg.is_divorced,
                   fg.union_date, fg.union_date_year, fg.union_end_date, fg.union_end_date_year,
                   fgm.person_id, fgm.role, fgm.parentage_type
            FROM family_groups fg
            LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
            WHERE fg.tree_id = :tid
        """),
        {"tid": tree_id},
    )).fetchall()

    fg_map: dict[str, dict] = {}
    for r in fg_rows:
        gid = str(r.fg_id)
        if gid not in fg_map:
            fg_map[gid] = {
                "union_type": r.union_type, "custom_label": r.custom_label, "is_divorced": r.is_divorced,
                "union_date": jsonable(r.union_date), "union_date_year": r.union_date_year,
                "union_end_date": jsonable(r.union_end_date), "union_end_date_year": r.union_end_date_year,
                "parent_ids": [], "children": {},
            }
        if r.person_id is None:
            continue
        pid = str(r.person_id)
        if r.role == "PARENT":
            if pid not in fg_map[gid]["parent_ids"]:
                fg_map[gid]["parent_ids"].append(pid)
        else:
            fg_map[gid]["children"][pid] = r.parentage_type or "BIOLOGICAL"

    return {"persons": persons, "family_groups": list(fg_map.values())}


async def apply_revert(session: AsyncSession, tree_id: uuid.UUID, snapshot: dict) -> dict:
    """Restore *tree_id*'s persons + family groups to exactly the state
    captured in *snapshot* (a revertible audit entry's `before`).

    This undoes the mutation that triggered the snapshot — and, necessarily,
    any edits made to the tree since then too, since it resets to a full
    point-in-time snapshot rather than replaying just that one change.
    """
    current_rows = (await session.execute(
        text("SELECT id FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": tree_id},
    )).fetchall()
    current_ids = {str(r.id) for r in current_rows}
    snap_persons = {p["id"]: p for p in snapshot["persons"]}
    snap_ids = set(snap_persons.keys())

    # Adopted/created since the snapshot — not in the pre-snapshot state.
    added_since = current_ids - snap_ids
    if added_since:
        await session.execute(
            text("UPDATE persons SET is_deleted = true, deleted_at = NOW() WHERE tree_id = :tid AND id = ANY(:ids)"),
            {"tid": tree_id, "ids": [uuid.UUID(i) for i in added_since]},
        )

    # Restore every snapshot person's fields — covers both persons that were
    # modified in place and persons that were soft-deleted since the snapshot.
    set_clause = ", ".join(f"{f} = :{f}" for f in PERSON_SNAPSHOT_FIELDS)
    for pid, p in snap_persons.items():
        params = {}
        for f in PERSON_SNAPSHOT_FIELDS:
            v = p.get(f)
            params[f] = to_date(v) if f in PERSON_DATE_FIELDS else v
        params.update({"pid": uuid.UUID(pid), "tid": tree_id})
        await session.execute(
            text(f"UPDATE persons SET {set_clause}, is_deleted = false, deleted_at = NULL WHERE id = :pid AND tree_id = :tid"),
            params,
        )

    await session.execute(text("DELETE FROM family_group_members WHERE tree_id = :tid"), {"tid": tree_id})
    await session.execute(text("DELETE FROM family_groups WHERE tree_id = :tid"), {"tid": tree_id})

    tenant_row = (await session.execute(text("SELECT tenant_id FROM family_trees WHERE id = :tid"), {"tid": tree_id})).first()

    for fg in snapshot["family_groups"]:
        parent_ids = [uuid.UUID(p) for p in fg["parent_ids"]]
        children = {uuid.UUID(cid): pt for cid, pt in fg["children"].items()}
        if not parent_ids and not children:
            continue
        new_fg_id = uuid.uuid4()
        await session.execute(
            text("""
                INSERT INTO family_groups (id, tenant_id, tree_id, union_type, custom_label, is_divorced,
                                            union_date, union_date_year, union_end_date, union_end_date_year,
                                            parent1_id, parent2_id)
                VALUES (:id, :tenant, :tid, :utype, :clabel, :divorced, :udate, :udyear, :uedate, :uedyear, :p1, :p2)
            """),
            {"id": new_fg_id, "tenant": tenant_row.tenant_id, "tid": tree_id,
             "utype": fg["union_type"] or "UNKNOWN", "clabel": fg["custom_label"], "divorced": fg["is_divorced"],
             "udate": to_date(fg["union_date"]), "udyear": fg["union_date_year"],
             "uedate": to_date(fg["union_end_date"]), "uedyear": fg["union_end_date_year"],
             "p1": parent_ids[0] if len(parent_ids) > 0 else None,
             "p2": parent_ids[1] if len(parent_ids) > 1 else None},
        )
        for pid in parent_ids:
            await session.execute(
                text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
                        VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')"""),
                {"tenant": tenant_row.tenant_id, "tid": tree_id, "fgid": new_fg_id, "pid": pid},
            )
        for child_pid, parentage in children.items():
            await session.execute(
                text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                        VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', :pt)"""),
                {"tenant": tenant_row.tenant_id, "tid": tree_id, "fgid": new_fg_id, "pid": child_pid, "pt": parentage},
            )

    return {"restored_persons": len(snap_persons), "removed_persons": len(added_since)}


# ── Surgical single-row snapshots ───────────────────────────────────────────

async def snapshot_person_fields(session: AsyncSession, person_id: uuid.UUID) -> Optional[dict]:
    """One person's editable fields, for a surgical UPDATE_PERSON revert."""
    row = (await session.execute(
        text(f"SELECT {', '.join(PERSON_SNAPSHOT_FIELDS)} FROM persons WHERE id = :pid"),
        {"pid": person_id},
    )).first()
    if row is None:
        return None
    return {f: jsonable(getattr(row, f)) for f in PERSON_SNAPSHOT_FIELDS}


async def apply_person_field_revert(session: AsyncSession, person_id: uuid.UUID, before: dict) -> dict:
    set_clause = ", ".join(f"{f} = :{f}" for f in PERSON_SNAPSHOT_FIELDS)
    params: dict = {}
    for f in PERSON_SNAPSHOT_FIELDS:
        v = before.get(f)
        params[f] = to_date(v) if f in PERSON_DATE_FIELDS else v
    params["pid"] = person_id
    await session.execute(text(f"UPDATE persons SET {set_clause} WHERE id = :pid"), params)
    return {"restored_person_id": str(person_id)}


async def apply_person_created_revert(session: AsyncSession, person_id: uuid.UUID) -> dict:
    """Undo a CREATE_PERSON — no `before` state exists, the person simply
    didn't exist yet, so revert is just soft-deleting it."""
    await session.execute(
        text("UPDATE persons SET is_deleted = true, deleted_at = NOW() WHERE id = :pid"),
        {"pid": person_id},
    )
    return {"removed_person_id": str(person_id)}


async def snapshot_family_group_fields(session: AsyncSession, family_group_id: uuid.UUID) -> Optional[dict]:
    """One family group's editable fields, for a surgical UPDATE_RELATIONSHIP
    revert of `update_family_group`."""
    row = (await session.execute(
        text(f"SELECT {', '.join(FAMILY_GROUP_FIELDS)} FROM family_groups WHERE id = :fgid"),
        {"fgid": family_group_id},
    )).first()
    if row is None:
        return None
    return {f: jsonable(getattr(row, f)) for f in FAMILY_GROUP_FIELDS}


async def apply_relationship_field_revert(session: AsyncSession, before: dict) -> dict:
    """Restore fields on a single `family_groups` or `family_group_members`
    row, per *before*'s self-describing `table` key (see the two shapes
    built by `update_family_group`/`update_family_group_member`)."""
    table = before["table"]
    if table == "family_groups":
        fg_id = uuid.UUID(before["id"])
        fields = before["fields"]
        set_clause = ", ".join(f"{f} = :{f}" for f in FAMILY_GROUP_FIELDS)
        params: dict = {}
        for f in FAMILY_GROUP_FIELDS:
            v = fields.get(f)
            params[f] = to_date(v) if f in FAMILY_GROUP_DATE_FIELDS else v
        params["fgid"] = fg_id
        await session.execute(text(f"UPDATE family_groups SET {set_clause} WHERE id = :fgid"), params)
        return {"restored_family_group_id": str(fg_id)}

    if table == "family_group_members":
        fg_id = uuid.UUID(before["family_group_id"])
        person_id = uuid.UUID(before["person_id"])
        parentage_type = before["fields"]["parentage_type"]
        await session.execute(
            text("""
                UPDATE family_group_members SET parentage_type = :pt
                WHERE family_group_id = :fgid AND person_id = :pid
            """),
            {"pt": parentage_type, "fgid": fg_id, "pid": person_id},
        )
        return {"restored_family_group_id": str(fg_id), "restored_person_id": str(person_id)}

    raise ValueError(f"Unknown relationship_field table: {table!r}")


# ── Capture + revert orchestration ──────────────────────────────────────────

async def record_revertible_action(
    session: AsyncSession,
    *,
    tree_id: uuid.UUID,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_display_name: str,
    action: Action,
    entity_type: AuditEntityType,
    entity_id: Optional[uuid.UUID] = None,
    entity_display_name: Optional[str] = None,
    snapshot: Optional[dict] = None,
    snapshot_kind: str = "full_tree",
    after: Optional[dict] = None,
) -> AuditEntry:
    """Write an audit entry carrying a revert snapshot, tagged with
    *snapshot_kind* so the generic revert endpoint recognizes it as
    revertible and knows how to restore it."""
    entry = AuditEntry.create(
        tree_id=tree_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_display_name=actor_display_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_display_name=entity_display_name,
        before=snapshot,
        after=after,
        snapshot_kind=snapshot_kind,
    )
    await AuditLogRepository(session).append(entry)
    return entry


async def revert_audit_entry(
    session: AsyncSession,
    tree_id: uuid.UUID,
    entry: AuditEntry,
    *,
    actor_id: uuid.UUID,
    actor_display_name: str,
    revert_action: Action = Action.REVERT_SNAPSHOT,
) -> dict:
    """Revert *entry* (must carry a full-tree snapshot) back to its `before`
    state: restores the tree, marks the entry reverted, and records a new
    audit entry (*revert_action* — defaults to the generic REVERT_SNAPSHOT;
    callers reverting a specific known action type, e.g. change-request
    approvals, may pass their own existing action value, such as
    REVERT_CHANGE, to keep prior labeling/i18n unchanged). Does not commit —
    the caller owns the transaction. Raises HTTPException(409) if the entry
    isn't revertible or was already reverted, HTTPException(404) if it
    doesn't belong to *tree_id*.
    """
    if entry.tree_id != tree_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit entry not found")
    if not is_revertible(entry):
        raise HTTPException(status.HTTP_409_CONFLICT, "No snapshot is available to revert this entry")

    # Atomic conditional claim — guards against two admins reverting the same
    # entry concurrently (a plain SELECT-then-UPDATE would race).
    claimed = (await session.execute(
        text("""
            UPDATE audit_logs SET reverted_at = NOW(), reverted_by_id = :uid
            WHERE id = :id AND reverted_at IS NULL
            RETURNING id
        """),
        {"id": entry.id, "uid": actor_id},
    )).first()
    if claimed is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This entry has already been reverted")

    kind = entry.metadata.get("snapshot_kind")
    if kind == "full_tree":
        summary = await apply_revert(session, tree_id, entry.before)
    elif kind == "person_created":
        summary = await apply_person_created_revert(session, entry.entity_id)
    elif kind == "person_updated":
        summary = await apply_person_field_revert(session, entry.entity_id, entry.before)
    elif kind == "relationship_field":
        summary = await apply_relationship_field_revert(session, entry.before)
    else:
        raise HTTPException(status.HTTP_409_CONFLICT, "No snapshot is available to revert this entry")

    await AuditLogRepository(session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=entry.tenant_id,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
            action=revert_action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            entity_display_name=entry.entity_display_name,
            after=summary,
            reverted_entry_id=str(entry.id),
        )
    )

    return {
        "reverted_entry_id": str(entry.id),
        "original_action": entry.action.value,
        "original_actor_id": str(entry.actor_id) if entry.actor_id else None,
        **summary,
    }
