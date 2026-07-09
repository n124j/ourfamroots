"""Change Requests API — propose edits to a globally-shared tree.

Flow: an Editor-level member of a globally-shared tree starts a private draft
copy (clone of the tree, visible only to them), edits it using the normal
person/relationship endpoints (which work unchanged since the draft is just a
regular tree they own), then Posts it. The original tree's owner reviews a
side-by-side diff — either the list/JSON modal, or the draft itself on the
real tree canvas with added/modified persons highlighted (GET .../draft-diff
powers both) — and approves (the draft's changes are applied onto the live
tree) or denies (the draft is discarded). Both sides get an email + in-app
notification, and the resolution is written to the tree's audit log/History.

Revert: approving a change request first snapshots the tree's full persons +
family-group state, stored on the APPROVE_CHANGE audit entry. A Super Admin
(only) can later call POST .../revert to restore that exact snapshot, undoing
the approval — and any edits made since, since it's a full point-in-time
restore rather than a surgical undo of just that one change.
"""
from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.api.deps import CurrentUserDep, NotAuditorDep, SuperAdminDep, UoWDep
from src.domain.collaboration.entities import Action, AppRole, AuditEntityType, AuditEntry
from src.infrastructure.repositories.collaboration import AuditLogRepository

router = APIRouter(tags=["Change Requests"])

_PERSON_FIELDS = [
    "display_given_name", "display_surname", "sex",
    "is_living", "is_deceased", "photo_url",
    "birth_date", "death_date", "birth_year", "death_year",
    "born_city", "born_country", "died_city", "died_country",
    "notes",
]


def _actor_name(user) -> str:
    return f"{user.given_name or ''} {user.family_name or ''}".strip() or user.email


def _jsonable(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _full_name(r) -> str:
    return f"{r.display_given_name or ''} {r.display_surname or ''}".strip() or "Unnamed"


# ── Draft creation ───────────────────────────────────────────────────────────

@router.post(
    "/trees/{tree_id}/change-requests/draft",
    status_code=status.HTTP_201_CREATED,
    summary="Create (or resume) a private draft copy of a globally-shared tree to propose changes",
)
async def create_draft(
    tree_id: uuid.UUID,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> dict:
    session = uow._session

    member_row = (await session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None or member_row.role != "EDITOR":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only Editor-level members can propose changes")

    is_global = (await session.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM permission_group_trees pgt
                JOIN permission_groups pg ON pg.id = pgt.group_id
                WHERE pgt.tree_id = :tid AND pg.is_global = true
            )
        """),
        {"tid": tree_id},
    )).scalar()
    if not is_global:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This tree is not globally shared")

    # Reuse an existing unposted draft, if any
    existing = (await session.execute(
        text("""
            SELECT ft.id FROM family_trees ft
            WHERE ft.draft_of_tree_id = :tid AND ft.draft_owner_user_id = :uid AND ft.is_deleted = false
              AND NOT EXISTS (SELECT 1 FROM tree_change_requests tcr WHERE tcr.draft_tree_id = ft.id)
            LIMIT 1
        """),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if existing:
        return {"draft_tree_id": str(existing.id)}

    pending = (await session.execute(
        text("SELECT 1 FROM tree_change_requests WHERE tree_id = :tid AND requester_id = :uid AND status = 'PENDING' LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a proposal pending review for this tree")

    original = (await session.execute(
        text("SELECT name, description, tenant_id FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()
    if original is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")

    draft_tree_id = uuid.uuid4()
    await session.execute(
        text("""
            INSERT INTO family_trees (id, tenant_id, name, description, draft_of_tree_id, draft_owner_user_id, is_searchable, link_sharing)
            VALUES (:id, :tenant, :name, :desc, :orig, :uid, false, 'RESTRICTED')
        """),
        {"id": draft_tree_id, "tenant": original.tenant_id, "name": original.name,
         "desc": original.description, "orig": tree_id, "uid": current_user.id},
    )
    await session.execute(
        text("""
            INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
            VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER', NOW())
        """),
        {"tid": draft_tree_id, "uid": current_user.id, "tenant": original.tenant_id},
    )

    # Clone persons, remembering old→new id map
    id_map: dict[uuid.UUID, uuid.UUID] = {}
    person_rows = (await session.execute(
        text(f"SELECT id, {', '.join(_PERSON_FIELDS)} FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": tree_id},
    )).fetchall()
    insert_person_sql = text(f"""
        INSERT INTO persons (id, tenant_id, tree_id, origin_person_id, {', '.join(_PERSON_FIELDS)})
        VALUES (:id, :tenant, :tid, :origin, {', '.join(':' + f for f in _PERSON_FIELDS)})
    """)
    for r in person_rows:
        new_id = uuid.uuid4()
        id_map[r.id] = new_id
        params = {f: getattr(r, f) for f in _PERSON_FIELDS}
        params.update({"id": new_id, "tenant": original.tenant_id, "tid": draft_tree_id, "origin": r.id})
        await session.execute(insert_person_sql, params)

    # Clone family groups + members, remapped through id_map
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
    await _clone_family_groups(session, fg_rows, id_map, original.tenant_id, draft_tree_id)

    await session.commit()
    return {"draft_tree_id": str(draft_tree_id)}


async def _clone_family_groups(session, fg_rows, id_map: dict, tenant_id: uuid.UUID, target_tree_id: uuid.UUID) -> None:
    """Shared by draft creation and approval: rebuild family_groups/members for
    target_tree_id from *fg_rows*, remapping person ids through *id_map*
    (falling back to the original person_id when it isn't in the map)."""
    fg_map: dict[uuid.UUID, dict] = {}
    for r in fg_rows:
        if r.fg_id not in fg_map:
            fg_map[r.fg_id] = {
                "union_type": r.union_type, "custom_label": r.custom_label, "is_divorced": r.is_divorced,
                "union_date": r.union_date, "union_date_year": r.union_date_year,
                "union_end_date": r.union_end_date, "union_end_date_year": r.union_end_date_year,
                "parent_ids": [], "children": {},
            }
        if r.person_id is None:
            continue
        new_pid = id_map.get(r.person_id, r.person_id)
        if r.role == "PARENT":
            if new_pid not in fg_map[r.fg_id]["parent_ids"]:
                fg_map[r.fg_id]["parent_ids"].append(new_pid)
        else:
            fg_map[r.fg_id]["children"][new_pid] = r.parentage_type or "BIOLOGICAL"

    for fg_data in fg_map.values():
        parent_ids = fg_data["parent_ids"]
        if not parent_ids and not fg_data["children"]:
            continue
        new_fg_id = uuid.uuid4()
        await session.execute(
            text("""
                INSERT INTO family_groups (id, tenant_id, tree_id, union_type, custom_label, is_divorced,
                                            union_date, union_date_year, union_end_date, union_end_date_year,
                                            parent1_id, parent2_id)
                VALUES (:id, :tenant, :tid, :utype, :clabel, :divorced, :udate, :udyear, :uedate, :uedyear, :p1, :p2)
            """),
            {"id": new_fg_id, "tenant": tenant_id, "tid": target_tree_id,
             "utype": fg_data["union_type"] or "UNKNOWN", "clabel": fg_data["custom_label"],
             "divorced": fg_data["is_divorced"], "udate": fg_data["union_date"], "udyear": fg_data["union_date_year"],
             "uedate": fg_data["union_end_date"], "uedyear": fg_data["union_end_date_year"],
             "p1": parent_ids[0] if len(parent_ids) > 0 else None,
             "p2": parent_ids[1] if len(parent_ids) > 1 else None},
        )
        for pid in parent_ids:
            await session.execute(
                text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
                        VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')"""),
                {"tenant": tenant_id, "tid": target_tree_id, "fgid": new_fg_id, "pid": pid},
            )
        for child_pid, parentage in fg_data["children"].items():
            await session.execute(
                text("""INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                        VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', :pt)"""),
                {"tenant": tenant_id, "tid": target_tree_id, "fgid": new_fg_id, "pid": child_pid, "pt": parentage},
            )


# ── Status ───────────────────────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/change-requests/mine",
    summary="The current user's change-request state for this tree",
)
async def my_change_request_state(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    session = uow._session
    req_row = (await session.execute(
        text("""
            SELECT id, draft_tree_id, status FROM tree_change_requests
            WHERE tree_id = :tid AND requester_id = :uid
            ORDER BY created_at DESC LIMIT 1
        """),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if req_row and req_row.status == "PENDING":
        return {"state": "pending", "request_id": str(req_row.id),
                "draft_tree_id": str(req_row.draft_tree_id) if req_row.draft_tree_id else None}

    draft_row = (await session.execute(
        text("""
            SELECT id FROM family_trees ft
            WHERE ft.draft_of_tree_id = :tid AND ft.draft_owner_user_id = :uid AND ft.is_deleted = false
              AND NOT EXISTS (SELECT 1 FROM tree_change_requests tcr WHERE tcr.draft_tree_id = ft.id)
            LIMIT 1
        """),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if draft_row:
        return {"state": "drafting", "draft_tree_id": str(draft_row.id)}

    if req_row:
        return {"state": req_row.status.lower(), "request_id": str(req_row.id)}

    return {"state": "none"}


# ── Submit ───────────────────────────────────────────────────────────────────

class SubmitChangeRequestBody(BaseModel):
    message: Optional[str] = Field(None, max_length=1000)


@router.post(
    "/trees/{draft_tree_id}/change-requests/submit",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a draft's proposed changes to the original tree's owner for review",
)
async def submit_change_request(
    draft_tree_id: uuid.UUID,
    body: SubmitChangeRequestBody,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> dict:
    session = uow._session

    draft = (await session.execute(
        text("SELECT id, draft_of_tree_id, draft_owner_user_id, tenant_id FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": draft_tree_id},
    )).first()
    if draft is None or draft.draft_of_tree_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    if draft.draft_owner_user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This isn't your draft")

    existing = (await session.execute(
        text("SELECT 1 FROM tree_change_requests WHERE draft_tree_id = :did LIMIT 1"),
        {"did": draft_tree_id},
    )).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "This draft has already been submitted")

    original_tree_id = draft.draft_of_tree_id
    request_id = uuid.uuid4()
    await session.execute(
        text("""
            INSERT INTO tree_change_requests (id, tree_id, draft_tree_id, requester_id, tenant_id, message)
            VALUES (:id, :tid, :did, :uid, :tenant, :msg)
        """),
        {"id": request_id, "tid": original_tree_id, "did": draft_tree_id,
         "uid": current_user.id, "tenant": draft.tenant_id, "msg": body.message},
    )

    original = (await session.execute(
        text("SELECT name FROM family_trees WHERE id = :tid LIMIT 1"), {"tid": original_tree_id}
    )).first()
    tree_name = original.name if original else "your tree"
    requester_name = _actor_name(current_user)

    owners = (await session.execute(
        text("""
            SELECT u.id, u.email, u.given_name, u.family_name
            FROM tree_members tm JOIN users u ON u.id = tm.user_id
            WHERE tm.tree_id = :tid AND tm.role = 'OWNER'
        """),
        {"tid": original_tree_id},
    )).fetchall()

    from src.config import get_settings
    settings = get_settings()
    review_url = f"{settings.frontend_base_url}/trees/{original_tree_id}?changeRequest={request_id}"

    notif_data = json.dumps({"tree_id": str(original_tree_id), "request_id": str(request_id)})
    for owner in owners:
        await session.execute(
            text("""
                INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
                VALUES (:uid, :tenant, 'CHANGE_REQUEST', :title, :nbody, CAST(:data AS jsonb))
            """),
            {"uid": owner.id, "tenant": draft.tenant_id,
             "title": f"Proposed changes to {tree_name}",
             "nbody": f"{requester_name} submitted changes for your review",
             "data": notif_data},
        )

    await AuditLogRepository(session).append(
        AuditEntry.create(
            tree_id=original_tree_id, tenant_id=draft.tenant_id,
            actor_id=current_user.id, actor_display_name=requester_name,
            action=Action.REQUEST_CHANGE, entity_type=AuditEntityType.CHANGE_REQUEST,
            entity_id=request_id, entity_display_name=f"Proposal from {requester_name}",
        )
    )
    await session.commit()

    import asyncio
    from src.infrastructure.email.service import send_email, change_request_submitted_email
    for owner in owners:
        owner_name = f"{owner.given_name or ''} {owner.family_name or ''}".strip() or owner.email
        html, text_body = change_request_submitted_email(
            owner_name=owner_name, requester_name=requester_name,
            tree_name=tree_name, review_url=review_url, message=body.message,
        )
        asyncio.create_task(send_email(
            to=owner.email, subject=f"{requester_name} proposed changes to {tree_name}",
            html_body=html, text_body=text_body,
        ))

    return {"id": str(request_id), "status": "PENDING"}


# ── List (owner inbox) ────────────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/change-requests",
    summary="List change requests for a tree (owner inbox)",
)
async def list_change_requests(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
    req_status: Optional[str] = Query(None, alias="status", pattern="^(PENDING|APPROVED|DENIED)$"),
) -> list[dict]:
    session = uow._session
    member_row = (await session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None or member_row.role != "OWNER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the tree owner can view change requests")

    status_filter = "AND tcr.status = :status" if req_status else ""
    params: dict = {"tid": tree_id}
    if req_status:
        params["status"] = req_status

    rows = (await session.execute(
        text(f"""
            SELECT tcr.id, tcr.draft_tree_id, tcr.requester_id, tcr.message, tcr.status,
                   tcr.decision_note, tcr.created_at, tcr.resolved_at,
                   COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS requester_name,
                   u.email AS requester_email
            FROM tree_change_requests tcr
            JOIN users u ON u.id = tcr.requester_id
            WHERE tcr.tree_id = :tid {status_filter}
            ORDER BY tcr.created_at DESC
        """),
        params,
    )).fetchall()

    return [
        {
            "id": str(r.id), "draft_tree_id": str(r.draft_tree_id) if r.draft_tree_id else None,
            "requester_id": str(r.requester_id), "requester_name": r.requester_name,
            "requester_email": r.requester_email, "message": r.message, "status": r.status,
            "decision_note": r.decision_note, "created_at": r.created_at.isoformat(),
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in rows
    ]


# ── Diff ─────────────────────────────────────────────────────────────────────

async def _compute_diff(session, original_tree_id: uuid.UUID, draft_tree_id: uuid.UUID) -> dict:
    orig_rows = (await session.execute(
        text(f"SELECT id, {', '.join(_PERSON_FIELDS)} FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": original_tree_id},
    )).fetchall()
    draft_rows = (await session.execute(
        text(f"SELECT id, origin_person_id, {', '.join(_PERSON_FIELDS)} FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": draft_tree_id},
    )).fetchall()

    orig_by_id = {r.id: r for r in orig_rows}
    draft_origin_ids = {r.origin_person_id for r in draft_rows if r.origin_person_id is not None}

    def _row_to_dict(r):
        d = {f: _jsonable(getattr(r, f)) for f in _PERSON_FIELDS}
        d["id"] = str(r.id)
        return d

    added_persons: list[dict] = []
    modified_persons: list[dict] = []
    for r in draft_rows:
        orig = orig_by_id.get(r.origin_person_id) if r.origin_person_id else None
        if orig is None:
            added_persons.append(_row_to_dict(r))
            continue
        changes = {}
        for f in _PERSON_FIELDS:
            ov, dv = _jsonable(getattr(orig, f)), _jsonable(getattr(r, f))
            if ov != dv:
                changes[f] = {"before": ov, "after": dv}
        if changes:
            modified_persons.append({
                "id": str(orig.id),
                "draft_id": str(r.id),
                "display_given_name": orig.display_given_name,
                "display_surname": orig.display_surname,
                "changes": changes,
            })

    removed_persons = [_row_to_dict(r) for r in orig_rows if r.id not in draft_origin_ids]

    # canon_map translates a draft-local person id to the id it will carry once
    # merged onto the live tree (the matched original's id, or its own id if new)
    canon_map = {r.id: (r.origin_person_id or r.id) for r in draft_rows}

    name_by_id: dict[str, str] = {str(r.id): _full_name(r) for r in orig_rows}
    for r in draft_rows:
        name_by_id[str(canon_map[r.id])] = _full_name(r)

    added_ids = {str(r.id) for r in draft_rows if r.origin_person_id is None}
    relationship_summary, relationship_changes, connections_by_person = await _diff_relationships(
        session, original_tree_id, draft_tree_id, canon_map, name_by_id, added_ids,
    )

    for entry in added_persons:
        entry["connections"] = connections_by_person.get(entry["id"], [])

    return {
        "added_persons": added_persons,
        "removed_persons": removed_persons,
        "modified_persons": modified_persons,
        "relationship_summary": relationship_summary,
        "relationship_changes": relationship_changes,
    }


async def _fetch_groups(session, tree_id: uuid.UUID) -> list[dict]:
    """Family groups for *tree_id* as {parents: {person_id}, children: {person_id}}."""
    rows = (await session.execute(
        text("""
            SELECT fg.id AS fg_id, fgm.person_id, fgm.role
            FROM family_groups fg
            LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
            WHERE fg.tree_id = :tid
        """),
        {"tid": tree_id},
    )).fetchall()
    groups: dict[uuid.UUID, dict] = {}
    for r in rows:
        g = groups.setdefault(r.fg_id, {"parents": set(), "children": set()})
        if r.person_id is None:
            continue
        (g["parents"] if r.role == "PARENT" else g["children"]).add(r.person_id)
    return list(groups.values())


def _group_edges(groups: list[dict]):
    unions, links = set(), set()
    for g in groups:
        pkey = tuple(sorted(str(p) for p in g["parents"]))
        unions.add(pkey)
        for cid in g["children"]:
            links.add((pkey, str(cid)))
    return unions, links


async def _diff_relationships(
    session, original_tree_id: uuid.UUID, draft_tree_id: uuid.UUID,
    canon_map: dict, name_by_id: dict[str, str], added_ids: set[str],
) -> tuple[dict, dict, dict]:
    """Computes relationship counts, named before/after details, and — for each
    newly-added person — the existing/new family members they connect to (the
    "connecting member"), so a reviewer can see exactly what's being proposed."""
    orig_groups = await _fetch_groups(session, original_tree_id)
    draft_groups_raw = await _fetch_groups(session, draft_tree_id)
    draft_groups = [
        {
            "parents": {str(canon_map.get(p, p)) for p in g["parents"]},
            "children": {str(canon_map.get(c, c)) for c in g["children"]},
        }
        for g in draft_groups_raw
    ]

    orig_unions, orig_links = _group_edges(orig_groups)
    draft_unions, draft_links = _group_edges(draft_groups)

    def _names(ids) -> list[str]:
        return [name_by_id.get(i, "Unknown") for i in ids if i]

    relationship_changes = {
        "unions_added": [{"parents": _names(pkey)} for pkey in sorted(draft_unions - orig_unions) if pkey],
        "unions_removed": [{"parents": _names(pkey)} for pkey in sorted(orig_unions - draft_unions) if pkey],
        "links_added": [
            {"parents": _names(pkey), "child": name_by_id.get(cid, "Unknown")}
            for pkey, cid in sorted(draft_links - orig_links)
        ],
        "links_removed": [
            {"parents": _names(pkey), "child": name_by_id.get(cid, "Unknown")}
            for pkey, cid in sorted(orig_links - draft_links)
        ],
    }
    relationship_summary = {
        "unions_added": len(relationship_changes["unions_added"]),
        "unions_removed": len(relationship_changes["unions_removed"]),
        "parent_child_links_added": len(relationship_changes["links_added"]),
        "parent_child_links_removed": len(relationship_changes["links_removed"]),
    }

    connections_by_person: dict[str, list[dict]] = {aid: [] for aid in added_ids}
    for g in draft_groups:
        parent_ids, child_ids = g["parents"], g["children"]
        for aid in parent_ids & added_ids:
            for other in parent_ids - {aid}:
                connections_by_person[aid].append({"relation": "spouse_of", "with": name_by_id.get(other, "Unknown")})
            for cid in child_ids:
                connections_by_person[aid].append({"relation": "parent_of", "with": name_by_id.get(cid, "Unknown")})
        for aid in child_ids & added_ids:
            for pid in parent_ids:
                connections_by_person[aid].append({"relation": "child_of", "with": name_by_id.get(pid, "Unknown")})

    return relationship_summary, relationship_changes, connections_by_person


@router.get(
    "/trees/{tree_id}/change-requests/{request_id}/diff",
    summary="Compute the side-by-side diff for a change request",
)
async def get_change_request_diff(
    tree_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    session = uow._session

    req_row = (await session.execute(
        text("""
            SELECT tcr.id, tcr.draft_tree_id, tcr.requester_id, tcr.status, tcr.message,
                   COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS requester_name
            FROM tree_change_requests tcr
            JOIN users u ON u.id = tcr.requester_id
            WHERE tcr.id = :rid AND tcr.tree_id = :tid LIMIT 1
        """),
        {"rid": request_id, "tid": tree_id},
    )).first()
    if req_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change request not found")

    member_row = (await session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    is_owner = member_row is not None and member_row.role == "OWNER"
    if not is_owner and req_row.requester_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to view this proposal")

    if req_row.draft_tree_id is None:
        raise HTTPException(status.HTTP_410_GONE, "The draft for this proposal is no longer available")

    diff = await _compute_diff(session, tree_id, req_row.draft_tree_id)
    diff["draft_tree_id"] = str(req_row.draft_tree_id)
    diff["requester_name"] = req_row.requester_name
    diff["message"] = req_row.message
    return diff


@router.get(
    "/trees/{draft_tree_id}/draft-diff",
    summary="Compute the diff between a draft tree and the original tree it was cloned from",
)
async def get_draft_diff(
    draft_tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    """Lets the diff (and its added/modified coloring in the tree canvas) show
    up for the draft's own owner while they're still editing — not just for
    the original tree's owner during formal review after Post."""
    session = uow._session

    tree_row = (await session.execute(
        text("SELECT draft_of_tree_id, draft_owner_user_id FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": draft_tree_id},
    )).first()
    if tree_row is None or tree_row.draft_of_tree_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This tree is not a draft")

    original_tree_id = tree_row.draft_of_tree_id

    if current_user.app_role not in (AppRole.AUDITOR, AppRole.SUPER_ADMIN):
        is_draft_owner = tree_row.draft_owner_user_id == current_user.id
        if not is_draft_owner:
            owner_row = (await session.execute(
                text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid AND role = 'OWNER' LIMIT 1"),
                {"tid": original_tree_id, "uid": current_user.id},
            )).first()
            if owner_row is None:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to view this draft's changes")

    diff = await _compute_diff(session, original_tree_id, draft_tree_id)

    # If this draft has been submitted, surface who's asking and why — used
    # by the review banner when an owner opens the draft to approve/deny.
    cr_row = (await session.execute(
        text("""
            SELECT tcr.id, tcr.message,
                   COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS requester_name
            FROM tree_change_requests tcr
            JOIN users u ON u.id = tcr.requester_id
            WHERE tcr.draft_tree_id = :did AND tcr.status = 'PENDING'
            ORDER BY tcr.created_at DESC LIMIT 1
        """),
        {"did": draft_tree_id},
    )).first()

    diff["draft_tree_id"] = str(draft_tree_id)
    diff["change_request_id"] = str(cr_row.id) if cr_row else None
    diff["requester_name"] = cr_row.requester_name if cr_row else None
    diff["message"] = cr_row.message if cr_row else None
    return diff


# ── Resolve (approve / deny) ──────────────────────────────────────────────────

async def _apply_change_request(session, original_tree_id: uuid.UUID, draft_tree_id: uuid.UUID) -> dict:
    """Apply a draft tree's persons/relationships onto the live original tree.

    Matched persons (origin_person_id set) get their editable fields copied
    onto the original row, keeping its id stable. Newly-added draft persons
    are adopted directly into the original tree. Original persons with no
    corresponding draft row are soft-deleted. Family groups/members are fully
    regenerated from the draft (matching them 1:1 isn't tracked), remapped
    through the same id space.
    """
    draft_rows = (await session.execute(
        text(f"SELECT id, origin_person_id, {', '.join(_PERSON_FIELDS)} FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": draft_tree_id},
    )).fetchall()

    matched_ids = {r.origin_person_id for r in draft_rows if r.origin_person_id is not None}
    # Ids that must survive the soft-delete-removed pass below: matched originals
    # (kept via UPDATE) plus newly-adopted persons (repointed to this tree — their
    # own id becomes their identity in the original tree from here on).
    keep_ids = set(matched_ids)

    added_count = 0
    modified_count = 0
    for r in draft_rows:
        if r.origin_person_id is None:
            await session.execute(
                text("UPDATE persons SET tree_id = :tid, origin_person_id = NULL WHERE id = :pid"),
                {"tid": original_tree_id, "pid": r.id},
            )
            keep_ids.add(r.id)
            added_count += 1
        else:
            set_clause = ", ".join(f"{f} = :{f}" for f in _PERSON_FIELDS)
            params = {f: getattr(r, f) for f in _PERSON_FIELDS}
            params.update({"pid": r.origin_person_id, "tid": original_tree_id})
            await session.execute(text(f"UPDATE persons SET {set_clause} WHERE id = :pid AND tree_id = :tid"), params)
            modified_count += 1

    removed = (await session.execute(
        text("""
            UPDATE persons SET is_deleted = true, deleted_at = NOW()
            WHERE tree_id = :tid AND is_deleted = false AND id != ALL(:keep)
            RETURNING id
        """),
        {"tid": original_tree_id, "keep": list(keep_ids) or [uuid.uuid4()]},
    )).fetchall()

    id_map = {r.id: (r.origin_person_id or r.id) for r in draft_rows}

    await session.execute(text("DELETE FROM family_group_members WHERE tree_id = :tid"), {"tid": original_tree_id})
    await session.execute(text("DELETE FROM family_groups WHERE tree_id = :tid"), {"tid": original_tree_id})

    tenant_row = (await session.execute(text("SELECT tenant_id FROM family_trees WHERE id = :tid"), {"tid": original_tree_id})).first()

    fg_rows = (await session.execute(
        text("""
            SELECT fg.id AS fg_id, fg.union_type, fg.custom_label, fg.is_divorced,
                   fg.union_date, fg.union_date_year, fg.union_end_date, fg.union_end_date_year,
                   fgm.person_id, fgm.role, fgm.parentage_type
            FROM family_groups fg
            LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
            WHERE fg.tree_id = :tid
        """),
        {"tid": draft_tree_id},
    )).fetchall()
    await _clone_family_groups(session, fg_rows, id_map, tenant_row.tenant_id, original_tree_id)

    # Discard the draft tree — cascades away its remaining (matched-clone) persons,
    # its own family_groups/members, and any gallery photos.
    await session.execute(text("DELETE FROM family_trees WHERE id = :did"), {"did": draft_tree_id})

    return {"added": added_count, "modified": modified_count, "removed": len(removed)}


async def _snapshot_tree(session, tree_id: uuid.UUID) -> dict:
    """Full point-in-time snapshot of a tree's persons + family structure,
    JSON-serialisable. Captured right before an approval is applied so a
    Super Admin can later revert it back to exactly this state."""
    person_rows = (await session.execute(
        text(f"SELECT id, {', '.join(_PERSON_FIELDS)} FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": tree_id},
    )).fetchall()
    persons = [
        {"id": str(r.id), **{f: _jsonable(getattr(r, f)) for f in _PERSON_FIELDS}}
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
                "union_date": _jsonable(r.union_date), "union_date_year": r.union_date_year,
                "union_end_date": _jsonable(r.union_end_date), "union_end_date_year": r.union_end_date_year,
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


def _to_date(v):
    return date.fromisoformat(v) if isinstance(v, str) else v


_PERSON_DATE_FIELDS = {"birth_date", "death_date"}


async def _apply_revert(session, tree_id: uuid.UUID, snapshot: dict) -> dict:
    """Restore *tree_id*'s persons + family groups to exactly the state
    captured in *snapshot* (an APPROVE_CHANGE audit entry's `before`).

    This undoes the approval — and, necessarily, any edits made to the tree
    since then too, since it resets to a full point-in-time snapshot rather
    than replaying just that one change.
    """
    current_rows = (await session.execute(
        text("SELECT id FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": tree_id},
    )).fetchall()
    current_ids = {str(r.id) for r in current_rows}
    snap_persons = {p["id"]: p for p in snapshot["persons"]}
    snap_ids = set(snap_persons.keys())

    # Adopted/created by the approval (or since) — not in the pre-approval snapshot.
    added_since = current_ids - snap_ids
    if added_since:
        await session.execute(
            text("UPDATE persons SET is_deleted = true, deleted_at = NOW() WHERE tree_id = :tid AND id = ANY(:ids)"),
            {"tid": tree_id, "ids": [uuid.UUID(i) for i in added_since]},
        )

    # Restore every snapshot person's fields — covers both persons that were
    # modified in place and persons that were soft-deleted by the approval.
    set_clause = ", ".join(f"{f} = :{f}" for f in _PERSON_FIELDS)
    for pid, p in snap_persons.items():
        params = {}
        for f in _PERSON_FIELDS:
            v = p.get(f)
            params[f] = _to_date(v) if f in _PERSON_DATE_FIELDS else v
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
             "udate": _to_date(fg["union_date"]), "udyear": fg["union_date_year"],
             "uedate": _to_date(fg["union_end_date"]), "uedyear": fg["union_end_date_year"],
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


class ResolveChangeRequestBody(BaseModel):
    action: str = Field(..., pattern="^(approve|deny)$")
    decision_note: Optional[str] = Field(None, max_length=1000)


@router.patch(
    "/trees/{tree_id}/change-requests/{request_id}",
    summary="Approve or deny a proposed change request",
)
async def resolve_change_request(
    tree_id: uuid.UUID,
    request_id: uuid.UUID,
    body: ResolveChangeRequestBody,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> dict:
    session = uow._session

    member_row = (await session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None or member_row.role != "OWNER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the tree owner can resolve change requests")

    req_row = (await session.execute(
        text("SELECT id, draft_tree_id, requester_id, status, tenant_id FROM tree_change_requests WHERE id = :rid AND tree_id = :tid LIMIT 1"),
        {"rid": request_id, "tid": tree_id},
    )).first()
    if req_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change request not found")
    if req_row.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Request already {req_row.status.lower()}")

    diff_summary = None
    before_snapshot = None
    if body.action == "approve" and req_row.draft_tree_id:
        before_snapshot = await _snapshot_tree(session, tree_id)
        diff_summary = await _apply_change_request(session, tree_id, req_row.draft_tree_id)
    elif req_row.draft_tree_id:
        await session.execute(text("DELETE FROM family_trees WHERE id = :did"), {"did": req_row.draft_tree_id})

    new_status = "APPROVED" if body.action == "approve" else "DENIED"
    await session.execute(
        text("""
            UPDATE tree_change_requests
            SET status = :status, resolved_by_id = :uid, resolved_at = NOW(),
                decision_note = :note, draft_tree_id = NULL, updated_at = NOW()
            WHERE id = :rid
        """),
        {"status": new_status, "uid": current_user.id, "note": body.decision_note, "rid": request_id},
    )

    tree_row = (await session.execute(text("SELECT name FROM family_trees WHERE id = :tid LIMIT 1"), {"tid": tree_id})).first()
    tree_name = tree_row.name if tree_row else "the tree"
    resolver_name = _actor_name(current_user)

    notif_type = "CHANGE_REQUEST_APPROVED" if body.action == "approve" else "CHANGE_REQUEST_DENIED"
    await session.execute(
        text("""
            INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
            VALUES (:uid, :tenant, :type, :title, :nbody, CAST(:data AS jsonb))
        """),
        {
            "uid": req_row.requester_id, "tenant": req_row.tenant_id, "type": notif_type,
            "title": f"Your proposal for {tree_name} was {new_status.lower()}",
            "nbody": body.decision_note,
            "data": json.dumps({"tree_id": str(tree_id), "request_id": str(request_id)}),
        },
    )

    await AuditLogRepository(session).append(
        AuditEntry.create(
            tree_id=tree_id, tenant_id=req_row.tenant_id,
            actor_id=current_user.id, actor_display_name=resolver_name,
            action=Action.APPROVE_CHANGE if body.action == "approve" else Action.DENY_CHANGE,
            entity_type=AuditEntityType.CHANGE_REQUEST, entity_id=request_id,
            before=before_snapshot,
            after=diff_summary,
        )
    )
    await session.commit()

    requester = (await session.execute(
        text("SELECT email, given_name, family_name FROM users WHERE id = :uid LIMIT 1"),
        {"uid": req_row.requester_id},
    )).first()
    if requester:
        import asyncio
        from src.config import get_settings
        from src.infrastructure.email.service import send_email, change_request_resolved_email
        requester_name = f"{requester.given_name or ''} {requester.family_name or ''}".strip() or requester.email
        settings = get_settings()
        tree_url = f"{settings.frontend_base_url}/trees/{tree_id}"
        html, text_body = change_request_resolved_email(
            requester_name=requester_name, tree_name=tree_name,
            approved=(body.action == "approve"), decision_note=body.decision_note, tree_url=tree_url,
        )
        asyncio.create_task(send_email(
            to=requester.email,
            subject=f"Your proposal for {tree_name} was {new_status.lower()}",
            html_body=html, text_body=text_body,
        ))

    return {"id": str(request_id), "status": new_status}


# ── Revert (Super Admin only) ──────────────────────────────────────────────────

@router.post(
    "/trees/{tree_id}/change-requests/{request_id}/revert",
    summary="Revert an approved change request back to its pre-approval state (Super Admin only)",
)
async def revert_change_request(
    tree_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: SuperAdminDep,
    uow: UoWDep,
) -> dict:
    session = uow._session

    req_row = (await session.execute(
        text("""
            SELECT id, status, tenant_id, requester_id, reverted_at
            FROM tree_change_requests WHERE id = :rid AND tree_id = :tid LIMIT 1
        """),
        {"rid": request_id, "tid": tree_id},
    )).first()
    if req_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change request not found")
    if req_row.status != "APPROVED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an approved change request can be reverted")
    if req_row.reverted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This change request has already been reverted")

    approve_entries = await AuditLogRepository(session).list_by_tree(
        tree_id, entity_type=AuditEntityType.CHANGE_REQUEST, entity_id=request_id, limit=50,
    )
    approve_entry = next((e for e in approve_entries if e.action == Action.APPROVE_CHANGE), None)
    if approve_entry is None or not approve_entry.before:
        raise HTTPException(status.HTTP_409_CONFLICT, "No snapshot is available to revert this approval")

    summary = await _apply_revert(session, tree_id, approve_entry.before)

    await session.execute(
        text("UPDATE tree_change_requests SET reverted_by_id = :uid, reverted_at = NOW(), updated_at = NOW() WHERE id = :rid"),
        {"uid": current_user.id, "rid": request_id},
    )

    tree_row = (await session.execute(text("SELECT name FROM family_trees WHERE id = :tid LIMIT 1"), {"tid": tree_id})).first()
    tree_name = tree_row.name if tree_row else "the tree"
    actor_name = _actor_name(current_user)

    await AuditLogRepository(session).append(
        AuditEntry.create(
            tree_id=tree_id, tenant_id=req_row.tenant_id,
            actor_id=current_user.id, actor_display_name=actor_name,
            action=Action.REVERT_CHANGE, entity_type=AuditEntityType.CHANGE_REQUEST, entity_id=request_id,
            after=summary,
        )
    )

    notify_ids = {req_row.requester_id}
    owners = (await session.execute(
        text("SELECT user_id FROM tree_members WHERE tree_id = :tid AND role = 'OWNER'"), {"tid": tree_id},
    )).fetchall()
    notify_ids.update(o.user_id for o in owners)
    notif_data = json.dumps({"tree_id": str(tree_id), "request_id": str(request_id)})
    for uid in notify_ids:
        await session.execute(
            text("""
                INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
                VALUES (:uid, :tenant, 'CHANGE_REQUEST_REVERTED', :title, :nbody, CAST(:data AS jsonb))
            """),
            {
                "uid": uid, "tenant": req_row.tenant_id,
                "title": f"A change to {tree_name} was reverted by an administrator",
                "nbody": f"{actor_name} reverted a previously approved proposal.",
                "data": notif_data,
            },
        )

    await session.commit()
    return {"id": str(request_id), "status": "APPROVED", "reverted": True, **summary}
