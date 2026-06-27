"""Discovery API — public tree search, access requests, merge requests."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.api.deps import CurrentUserDep, UoWDep
from src.domain.collaboration.entities import (
    Action, AuditEntityType, AuditEntry, AppRole, TreeRole,
)
from src.infrastructure.repositories.collaboration import AuditLogRepository

router = APIRouter(tags=["discovery"])


def _sql(s: str) -> text:
    return text(s)


def _actor_name(user) -> str:
    return f"{user.given_name or ''} {user.family_name or ''}".strip() or user.email


# ── Toggle searchable ─────────────────────────────────────────────────────────

class UpdateSearchableRequest(BaseModel):
    is_searchable: bool


@router.patch("/trees/{tree_id}/searchable", summary="Toggle whether a tree is discoverable by other users")
async def update_searchable(
    tree_id: uuid.UUID,
    body: UpdateSearchableRequest,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    member_row = (await uow._session.execute(
        _sql("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this tree")
    if member_row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owner or admin can change searchability")

    await uow._session.execute(
        _sql("UPDATE family_trees SET is_searchable = :val, updated_at = NOW() WHERE id = :tid"),
        {"val": body.is_searchable, "tid": tree_id},
    )
    await uow._session.commit()
    return {"is_searchable": body.is_searchable}


# ── Discovery search ──────────────────────────────────────────────────────────

class MatchingPerson(BaseModel):
    person_id: str
    given_name: Optional[str]
    surname: Optional[str]
    birth_year: Optional[int]


class DiscoveryTreeResult(BaseModel):
    tree_id: str
    tree_name: str
    tree_description: Optional[str] = None
    owner_name: str
    owner_id: str
    person_count: int
    matching_persons: list[MatchingPerson]
    is_member: bool
    matched_on: str  # "person", "tree_name", "tree_description", or comma-separated combo


class DiscoverySearchResponse(BaseModel):
    total: int
    results: list[DiscoveryTreeResult]
    took_ms: int


@router.get("/discover/search", response_model=DiscoverySearchResponse, summary="Search across all searchable trees by tree name, description, or person name")
async def discovery_search(
    q: str = Query(..., min_length=2, max_length=200, description="Search query"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUserDep = ...,
    uow: UoWDep = ...,
) -> DiscoverySearchResponse:
    import time
    t0 = time.monotonic()

    raw = q.strip()
    if len(raw) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Query must be at least 2 characters")

    like_pattern = f"%{raw}%"

    words = raw.split()
    last_word_prefix = words[-1] + ":*" if words else raw + ":*"

    if not raw.endswith(" "):
        tsq_cte = "SELECT plainto_tsquery('simple', unaccent(:raw)) || to_tsquery('simple', unaccent(:prefix_raw)) AS v"
    else:
        tsq_cte = "SELECT plainto_tsquery('simple', unaccent(:raw)) AS v"

    # 1. Find trees matching by name or description (ILIKE for flexible matching)
    tree_match_sql = _sql("""
        SELECT
            ft.id AS tree_id,
            ft.name AS tree_name,
            ft.description AS tree_description,
            COALESCE(u.given_name || ' ' || u.family_name, u.email) AS owner_name,
            u.id AS owner_id,
            (SELECT COUNT(*) FROM persons pp WHERE pp.tree_id = ft.id AND pp.is_deleted = false) AS person_count,
            CASE WHEN tm.user_id IS NOT NULL THEN true ELSE false END AS is_member,
            CASE
                WHEN ft.name ILIKE :like_pattern THEN 'tree_name'
                ELSE 'tree_description'
            END AS match_source
        FROM family_trees ft
        JOIN tree_members own ON own.tree_id = ft.id AND own.role = 'OWNER'
        JOIN users u ON u.id = own.user_id
        LEFT JOIN tree_members tm ON tm.tree_id = ft.id AND tm.user_id = :current_user_id
        WHERE ft.is_searchable = true
          AND ft.is_deleted = false
          AND (ft.name ILIKE :like_pattern OR ft.description ILIKE :like_pattern)
        ORDER BY
            CASE WHEN ft.name ILIKE :like_pattern THEN 0 ELSE 1 END,
            ft.name
        LIMIT 100
    """)

    tree_rows = (await uow._session.execute(tree_match_sql, {
        "like_pattern": like_pattern,
        "current_user_id": current_user.id,
    })).fetchall()

    # 2. Find persons matching by name (FTS on search_vector)
    person_match_sql = _sql(f"""
        WITH _tsq AS ({tsq_cte})
        SELECT
            p.id AS person_id,
            p.tree_id,
            p.display_given_name,
            p.display_surname,
            p.birth_year,
            ft.name AS tree_name,
            ft.description AS tree_description,
            COALESCE(u.given_name || ' ' || u.family_name, u.email) AS owner_name,
            u.id AS owner_id,
            (SELECT COUNT(*) FROM persons pp WHERE pp.tree_id = ft.id AND pp.is_deleted = false) AS person_count,
            ts_rank_cd(p.search_vector, _tsq.v, 32) AS score,
            CASE WHEN tm.user_id IS NOT NULL THEN true ELSE false END AS is_member
        FROM persons p
        CROSS JOIN _tsq
        JOIN family_trees ft ON ft.id = p.tree_id
        JOIN tree_members own ON own.tree_id = ft.id AND own.role = 'OWNER'
        JOIN users u ON u.id = own.user_id
        LEFT JOIN tree_members tm ON tm.tree_id = ft.id AND tm.user_id = :current_user_id
        WHERE ft.is_searchable = true
          AND ft.is_deleted = false
          AND p.is_deleted = false
          AND p.search_vector @@ _tsq.v
        ORDER BY score DESC
        LIMIT 500
    """)

    person_rows = (await uow._session.execute(person_match_sql, {
        "raw": raw,
        "prefix_raw": last_word_prefix,
        "current_user_id": current_user.id,
    })).fetchall()

    # 2b. Fuzzy fallback (pg_trgm) when FTS returns no person matches and query >= 3 chars
    if not person_rows and len(raw) >= 3:
        fuzzy_sql = _sql("""
            SELECT
                p.id AS person_id,
                p.tree_id,
                p.display_given_name,
                p.display_surname,
                p.birth_year,
                ft.name AS tree_name,
                ft.description AS tree_description,
                COALESCE(u.given_name || ' ' || u.family_name, u.email) AS owner_name,
                u.id AS owner_id,
                (SELECT COUNT(*) FROM persons pp WHERE pp.tree_id = ft.id AND pp.is_deleted = false) AS person_count,
                greatest(
                    similarity(coalesce(p.display_given_name,'') || ' ' || coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_given_name,''), :raw)
                ) AS score,
                CASE WHEN tm.user_id IS NOT NULL THEN true ELSE false END AS is_member
            FROM persons p
            JOIN family_trees ft ON ft.id = p.tree_id
            JOIN tree_members own ON own.tree_id = ft.id AND own.role = 'OWNER'
            JOIN users u ON u.id = own.user_id
            LEFT JOIN tree_members tm ON tm.tree_id = ft.id AND tm.user_id = :current_user_id
            WHERE ft.is_searchable = true
              AND ft.is_deleted = false
              AND p.is_deleted = false
              AND greatest(
                    similarity(coalesce(p.display_given_name,'') || ' ' || coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_given_name,''), :raw)
                  ) > 0.25
            ORDER BY score DESC
            LIMIT 200
        """)
        person_rows = (await uow._session.execute(fuzzy_sql, {
            "raw": raw,
            "current_user_id": current_user.id,
        })).fetchall()

    # 3. Merge: build a unified tree map
    tree_map: dict[str, DiscoveryTreeResult] = {}
    match_sources: dict[str, set[str]] = {}

    # Add tree-level matches first (no matching persons for these yet)
    for r in tree_rows:
        tid = str(r.tree_id)
        if tid not in tree_map:
            tree_map[tid] = DiscoveryTreeResult(
                tree_id=tid,
                tree_name=r.tree_name,
                tree_description=r.tree_description,
                owner_name=r.owner_name,
                owner_id=str(r.owner_id),
                person_count=r.person_count,
                matching_persons=[],
                is_member=r.is_member,
                matched_on="",
            )
            match_sources[tid] = set()
        match_sources[tid].add(r.match_source)

    # Add person-level matches
    for r in person_rows:
        tid = str(r.tree_id)
        if tid not in tree_map:
            tree_map[tid] = DiscoveryTreeResult(
                tree_id=tid,
                tree_name=r.tree_name,
                tree_description=r.tree_description,
                owner_name=r.owner_name,
                owner_id=str(r.owner_id),
                person_count=r.person_count,
                matching_persons=[],
                is_member=r.is_member,
                matched_on="",
            )
            match_sources[tid] = set()
        match_sources.setdefault(tid, set()).add("person")
        if len(tree_map[tid].matching_persons) < 3:
            tree_map[tid].matching_persons.append(MatchingPerson(
                person_id=str(r.person_id),
                given_name=r.display_given_name,
                surname=r.display_surname,
                birth_year=r.birth_year,
            ))

    # Set matched_on for each tree
    for tid, result in tree_map.items():
        result.matched_on = ", ".join(sorted(match_sources.get(tid, set())))

    # Sort: person matches first (more specific), then tree-name, then description
    def _sort_key(r: DiscoveryTreeResult) -> tuple:
        has_person = "person" in r.matched_on
        has_name = "tree_name" in r.matched_on
        return (not has_person, not has_name, r.tree_name.lower())

    results = sorted(tree_map.values(), key=_sort_key)
    total = len(results)
    results = results[offset:offset + limit]

    took_ms = int((time.monotonic() - t0) * 1000)
    return DiscoverySearchResponse(total=total, results=results, took_ms=took_ms)


# ── Discovery tree graph ──────────────────────────────────────────────────────

@router.get("/discover/trees/{tree_id}/graph", summary="View a searchable tree graph (read-only for non-members)")
async def get_discovery_tree_graph(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    tree_row = (await uow._session.execute(
        _sql("SELECT id, name, description, is_searchable FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()

    if tree_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if not tree_row.is_searchable:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This tree is not searchable")

    # Check if user is already a member
    member_row = (await uow._session.execute(
        _sql("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    user_role = member_row.role if member_row else "VIEWER"

    persons_q = _sql("""
        SELECT id, tree_id, display_given_name, display_surname,
               sex, is_living, is_deceased, photo_url,
               birth_date, death_date, birth_year, death_year,
               born_city, born_country, died_city, died_country,
               notes
        FROM persons
        WHERE tree_id = :tid AND is_deleted = false
        ORDER BY display_surname, display_given_name
    """)
    person_rows = (await uow._session.execute(persons_q, {"tid": tree_id})).fetchall()

    from src.api.v1._s3 import presign_photo as _presign_photo
    persons = [
        {
            "id": str(r.id),
            "treeId": str(r.tree_id),
            "displayGivenName": r.display_given_name,
            "displaySurname": r.display_surname,
            "sex": r.sex,
            "isLiving": r.is_living,
            "isDeceased": r.is_deceased,
            **({"photoUrl": _presign_photo(r.photo_url)} if r.photo_url else {}),
            **({"birthDate": r.birth_date.isoformat()} if r.birth_date else {}),
            **({"deathDate": r.death_date.isoformat()} if r.death_date else {}),
            **({"birthYear": r.birth_year} if r.birth_year is not None else {}),
            **({"deathYear": r.death_year} if r.death_year is not None else {}),
            **({"bornCity": r.born_city} if r.born_city else {}),
            **({"bornCountry": r.born_country} if r.born_country else {}),
            **({"diedCity": r.died_city} if r.died_city else {}),
            **({"diedCountry": r.died_country} if r.died_country else {}),
            **({"notes": r.notes} if r.notes else {}),
        }
        for r in person_rows
    ]

    fg_q = _sql("""
        SELECT fg.id, fg.tree_id, fg.union_type, fg.custom_label, fg.is_divorced,
               fg.union_date, fg.union_date_year, fg.union_end_date, fg.union_end_date_year,
               fgm.person_id, fgm.role, fgm.parentage_type
        FROM family_groups fg
        LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
        LEFT JOIN persons p ON p.id = fgm.person_id
        WHERE fg.tree_id = :tid
          AND (fgm.person_id IS NULL OR p.is_deleted = false)
        ORDER BY fg.id
    """)
    fg_rows = (await uow._session.execute(fg_q, {"tid": tree_id})).fetchall()

    groups: dict[str, dict] = {}
    for r in fg_rows:
        gid = str(r.id)
        if gid not in groups:
            groups[gid] = {
                "id": gid,
                "treeId": str(r.tree_id),
                "unionType": r.union_type,
                **({"customLabel": r.custom_label} if r.custom_label else {}),
                **({"isDivorced": True} if r.is_divorced else {}),
                **({"unionDate": r.union_date.isoformat()} if r.union_date else {}),
                **({"unionDateYear": r.union_date_year} if r.union_date_year is not None else {}),
                **({"unionEndDate": r.union_end_date.isoformat()} if r.union_end_date else {}),
                **({"unionEndDateYear": r.union_end_date_year} if r.union_end_date_year is not None else {}),
                "parentIds": [],
                "children": {},
            }
        if r.person_id is None:
            continue
        pid = str(r.person_id)
        if r.role == "PARENT":
            if pid not in groups[gid]["parentIds"]:
                groups[gid]["parentIds"].append(pid)
        elif r.role == "CHILD":
            groups[gid]["children"][pid] = r.parentage_type or "BIOLOGICAL"

    return {
        "treeId":          str(tree_id),
        "treeName":        tree_row.name,
        "treeDescription": tree_row.description,
        "userRole":        user_role,
        "isMember":        member_row is not None,
        "persons":         persons,
        "familyGroups":    list(groups.values()),
    }


# ── Access requests ───────────────────────────────────────────────────────────

class SubmitAccessRequestBody(BaseModel):
    requested_role: str = Field(..., pattern="^(EDITOR|ADMIN)$")
    message: Optional[str] = Field(None, max_length=500)


class AccessRequestResponse(BaseModel):
    id: str
    tree_id: str
    requester_id: str
    requester_name: str
    requester_email: str
    requested_role: str
    message: Optional[str]
    status: str
    created_at: str


@router.post("/discover/trees/{tree_id}/access-requests", status_code=status.HTTP_201_CREATED, summary="Request access to a searchable tree")
async def submit_access_request(
    tree_id: uuid.UUID,
    body: SubmitAccessRequestBody,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    # Verify tree is searchable
    tree_row = (await uow._session.execute(
        _sql("SELECT id, name, is_searchable, tenant_id FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()
    if tree_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if not tree_row.is_searchable:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This tree is not searchable")

    # Verify user is not already a member
    member_row = (await uow._session.execute(
        _sql("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row:
        raise HTTPException(status.HTTP_409_CONFLICT, "You are already a member of this tree")

    # Check for existing pending request
    existing = (await uow._session.execute(
        _sql("SELECT 1 FROM access_requests WHERE tree_id = :tid AND requester_id = :uid AND status = 'PENDING' LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a pending access request for this tree")

    request_id = uuid.uuid4()
    await uow._session.execute(
        _sql("""
            INSERT INTO access_requests (id, tree_id, requester_id, tenant_id, requested_role, message)
            VALUES (:id, :tid, :uid, :tenant_id, :role, :msg)
        """),
        {
            "id": request_id, "tid": tree_id, "uid": current_user.id,
            "tenant_id": tree_row.tenant_id, "role": body.requested_role,
            "msg": body.message,
        },
    )

    # Notify tree owner(s)
    owners = (await uow._session.execute(
        _sql("SELECT user_id FROM tree_members WHERE tree_id = :tid AND role = 'OWNER'"),
        {"tid": tree_id},
    )).fetchall()

    requester_name = _actor_name(current_user)
    notif_data = json.dumps({
        "tree_id": str(tree_id),
        "request_id": str(request_id),
        "requester_id": str(current_user.id),
        "requested_role": body.requested_role,
    })
    for owner in owners:
        await uow._session.execute(
            _sql("""
                INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
                VALUES (:user_id, :tenant_id, 'ACCESS_REQUEST', :title, :nbody, CAST(:data AS jsonb))
            """),
            {
                "user_id": owner.user_id,
                "tenant_id": tree_row.tenant_id,
                "title": f"Access request for {tree_row.name}",
                "nbody": f"{requester_name} wants {body.requested_role} access",
                "data": notif_data,
            },
        )

    await uow._session.commit()
    return {"id": str(request_id), "status": "PENDING"}


@router.get("/trees/{tree_id}/access-requests", response_model=list[AccessRequestResponse], summary="List access requests for a tree")
async def list_access_requests(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
    req_status: Optional[str] = Query(None, alias="status", pattern="^(PENDING|APPROVED|DENIED)$"),
) -> list[AccessRequestResponse]:
    # Must be owner or admin
    member_row = (await uow._session.execute(
        _sql("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None or member_row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owner or admin can view access requests")

    status_filter = "AND ar.status = :status" if req_status else ""
    params: dict = {"tid": tree_id}
    if req_status:
        params["status"] = req_status

    rows = (await uow._session.execute(
        _sql(f"""
            SELECT ar.id, ar.tree_id, ar.requester_id, ar.requested_role, ar.message, ar.status, ar.created_at,
                   COALESCE(u.given_name || ' ' || u.family_name, u.email) AS requester_name,
                   u.email AS requester_email
            FROM access_requests ar
            JOIN users u ON u.id = ar.requester_id
            WHERE ar.tree_id = :tid {status_filter}
            ORDER BY ar.created_at DESC
        """),
        params,
    )).fetchall()

    return [
        AccessRequestResponse(
            id=str(r.id), tree_id=str(r.tree_id), requester_id=str(r.requester_id),
            requester_name=r.requester_name, requester_email=r.requester_email,
            requested_role=r.requested_role, message=r.message, status=r.status,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


class ResolveRequestBody(BaseModel):
    action: str = Field(..., pattern="^(approve|deny)$")


@router.patch("/trees/{tree_id}/access-requests/{request_id}", summary="Approve or deny an access request")
async def resolve_access_request(
    tree_id: uuid.UUID,
    request_id: uuid.UUID,
    body: ResolveRequestBody,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    # Must be owner
    member_row = (await uow._session.execute(
        _sql("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None or member_row.role != "OWNER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the tree owner can resolve access requests")

    req_row = (await uow._session.execute(
        _sql("SELECT id, requester_id, requested_role, status, tenant_id FROM access_requests WHERE id = :rid AND tree_id = :tid LIMIT 1"),
        {"rid": request_id, "tid": tree_id},
    )).first()
    if req_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Access request not found")
    if req_row.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Request already {req_row.status.lower()}")

    new_status = "APPROVED" if body.action == "approve" else "DENIED"

    await uow._session.execute(
        _sql("UPDATE access_requests SET status = :status, resolved_by_id = :uid, resolved_at = NOW(), updated_at = NOW() WHERE id = :rid"),
        {"status": new_status, "uid": current_user.id, "rid": request_id},
    )

    tree_row = (await uow._session.execute(
        _sql("SELECT name, tenant_id FROM family_trees WHERE id = :tid LIMIT 1"),
        {"tid": tree_id},
    )).first()

    if body.action == "approve":
        # Add requester as member
        await uow._session.execute(
            _sql("""
                INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
                VALUES (gen_random_uuid(), :tid, :uid, :tenant, :role, NOW())
                ON CONFLICT (tree_id, user_id) DO NOTHING
            """),
            {"tid": tree_id, "uid": req_row.requester_id, "tenant": tree_row.tenant_id, "role": req_row.requested_role},
        )
        notif_type = "ACCESS_APPROVED"
        notif_title = f"Access granted to {tree_row.name}"
        notif_body_text = f"You now have {req_row.requested_role} access"
    else:
        notif_type = "ACCESS_DENIED"
        notif_title = f"Access request for {tree_row.name} was denied"
        notif_body_text = None

    # Notify requester
    await uow._session.execute(
        _sql("""
            INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
            VALUES (:user_id, :tenant_id, :type, :title, :nbody, CAST(:data AS jsonb))
        """),
        {
            "user_id": req_row.requester_id,
            "tenant_id": tree_row.tenant_id,
            "type": notif_type,
            "title": notif_title,
            "nbody": notif_body_text,
            "data": json.dumps({"tree_id": str(tree_id), "request_id": str(request_id)}),
        },
    )

    # Audit
    audit_action = Action.APPROVE_ACCESS if body.action == "approve" else Action.DENY_ACCESS
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=tree_row.tenant_id,
            actor_id=current_user.id,
            actor_display_name=_actor_name(current_user),
            action=audit_action,
            entity_type=AuditEntityType.ACCESS_REQUEST,
            entity_id=request_id,
            after={"requester_id": str(req_row.requester_id), "requested_role": req_row.requested_role, "resolution": new_status},
        )
    )

    await uow._session.commit()
    return {"id": str(request_id), "status": new_status}


# ── Merge requests ────────────────────────────────────────────────────────────

class SubmitMergeRequestBody(BaseModel):
    source_tree_id: uuid.UUID
    source_pivot_person_id: uuid.UUID
    target_pivot_person_id: uuid.UUID
    new_tree_name: str = Field(..., min_length=1, max_length=255)
    message: Optional[str] = Field(None, max_length=1000)


class MergeRequestResponse(BaseModel):
    id: str
    target_tree_id: str
    source_tree_id: str
    source_tree_name: str
    requester_id: str
    requester_name: str
    requester_email: str
    target_pivot_person_id: str
    source_pivot_person_id: str
    target_pivot_name: Optional[str]
    source_pivot_name: Optional[str]
    new_tree_name: str
    message: Optional[str]
    status: str
    created_at: str


@router.post("/discover/trees/{tree_id}/merge-requests", status_code=status.HTTP_201_CREATED, summary="Request to merge your tree with a searchable tree")
async def submit_merge_request(
    tree_id: uuid.UUID,
    body: SubmitMergeRequestBody,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    # Verify target tree is searchable
    target_tree = (await uow._session.execute(
        _sql("SELECT id, name, is_searchable, tenant_id FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()
    if target_tree is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target tree not found")
    if not target_tree.is_searchable:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Target tree is not searchable")

    # Verify user owns the source tree
    source_member = (await uow._session.execute(
        _sql("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": body.source_tree_id, "uid": current_user.id},
    )).first()
    if source_member is None or source_member.role != "OWNER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You must be the owner of the source tree")

    source_tree = (await uow._session.execute(
        _sql("SELECT id, name FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": body.source_tree_id},
    )).first()
    if source_tree is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source tree not found")

    # Verify pivot persons exist
    target_pivot = (await uow._session.execute(
        _sql("SELECT id FROM persons WHERE id = :pid AND tree_id = :tid AND is_deleted = false LIMIT 1"),
        {"pid": body.target_pivot_person_id, "tid": tree_id},
    )).first()
    if target_pivot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target pivot person not found in the target tree")

    source_pivot = (await uow._session.execute(
        _sql("SELECT id FROM persons WHERE id = :pid AND tree_id = :tid AND is_deleted = false LIMIT 1"),
        {"pid": body.source_pivot_person_id, "tid": body.source_tree_id},
    )).first()
    if source_pivot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source pivot person not found in your tree")

    # Check for existing pending merge request
    existing = (await uow._session.execute(
        _sql("SELECT 1 FROM merge_requests WHERE target_tree_id = :ttid AND source_tree_id = :stid AND status = 'PENDING' LIMIT 1"),
        {"ttid": tree_id, "stid": body.source_tree_id},
    )).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A pending merge request already exists for these trees")

    request_id = uuid.uuid4()
    await uow._session.execute(
        _sql("""
            INSERT INTO merge_requests (id, target_tree_id, source_tree_id, requester_id, tenant_id,
                                        target_pivot_person_id, source_pivot_person_id, new_tree_name, message)
            VALUES (:id, :ttid, :stid, :uid, :tenant_id, :tpid, :spid, :name, :msg)
        """),
        {
            "id": request_id, "ttid": tree_id, "stid": body.source_tree_id,
            "uid": current_user.id, "tenant_id": target_tree.tenant_id,
            "tpid": body.target_pivot_person_id, "spid": body.source_pivot_person_id,
            "name": body.new_tree_name, "msg": body.message,
        },
    )

    # Notify target tree owner(s)
    owners = (await uow._session.execute(
        _sql("SELECT user_id FROM tree_members WHERE tree_id = :tid AND role = 'OWNER'"),
        {"tid": tree_id},
    )).fetchall()

    requester_name = _actor_name(current_user)
    notif_data = json.dumps({
        "tree_id": str(tree_id),
        "request_id": str(request_id),
        "requester_id": str(current_user.id),
        "source_tree_name": source_tree.name,
    })
    for owner in owners:
        await uow._session.execute(
            _sql("""
                INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
                VALUES (:user_id, :tenant_id, 'MERGE_REQUEST', :title, :nbody, CAST(:data AS jsonb))
            """),
            {
                "user_id": owner.user_id,
                "tenant_id": target_tree.tenant_id,
                "title": f"Merge request for {target_tree.name}",
                "nbody": f"{requester_name} wants to merge \"{source_tree.name}\" with your tree",
                "data": notif_data,
            },
        )

    await uow._session.commit()
    return {"id": str(request_id), "status": "PENDING"}


@router.get("/trees/{tree_id}/merge-requests", response_model=list[MergeRequestResponse], summary="List merge requests for a tree")
async def list_merge_requests(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
    req_status: Optional[str] = Query(None, alias="status", pattern="^(PENDING|APPROVED|DENIED)$"),
) -> list[MergeRequestResponse]:
    member_row = (await uow._session.execute(
        _sql("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None or member_row.role != "OWNER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the tree owner can view merge requests")

    status_filter = "AND mr.status = :status" if req_status else ""
    params: dict = {"tid": tree_id}
    if req_status:
        params["status"] = req_status

    rows = (await uow._session.execute(
        _sql(f"""
            SELECT mr.id, mr.target_tree_id, mr.source_tree_id, mr.requester_id,
                   mr.target_pivot_person_id, mr.source_pivot_person_id,
                   mr.new_tree_name, mr.message, mr.status, mr.created_at,
                   COALESCE(u.given_name || ' ' || u.family_name, u.email) AS requester_name,
                   u.email AS requester_email,
                   sft.name AS source_tree_name,
                   COALESCE(tp.display_given_name || ' ' || tp.display_surname, '') AS target_pivot_name,
                   COALESCE(sp.display_given_name || ' ' || sp.display_surname, '') AS source_pivot_name
            FROM merge_requests mr
            JOIN users u ON u.id = mr.requester_id
            LEFT JOIN family_trees sft ON sft.id = mr.source_tree_id
            LEFT JOIN persons tp ON tp.id = mr.target_pivot_person_id
            LEFT JOIN persons sp ON sp.id = mr.source_pivot_person_id
            WHERE mr.target_tree_id = :tid {status_filter}
            ORDER BY mr.created_at DESC
        """),
        params,
    )).fetchall()

    return [
        MergeRequestResponse(
            id=str(r.id), target_tree_id=str(r.target_tree_id),
            source_tree_id=str(r.source_tree_id), source_tree_name=r.source_tree_name or "",
            requester_id=str(r.requester_id), requester_name=r.requester_name,
            requester_email=r.requester_email,
            target_pivot_person_id=str(r.target_pivot_person_id),
            source_pivot_person_id=str(r.source_pivot_person_id),
            target_pivot_name=r.target_pivot_name or None,
            source_pivot_name=r.source_pivot_name or None,
            new_tree_name=r.new_tree_name, message=r.message,
            status=r.status, created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.patch("/trees/{tree_id}/merge-requests/{request_id}", summary="Approve or deny a merge request")
async def resolve_merge_request(
    tree_id: uuid.UUID,
    request_id: uuid.UUID,
    body: ResolveRequestBody,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    # Must be owner of target tree
    member_row = (await uow._session.execute(
        _sql("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None or member_row.role != "OWNER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the tree owner can resolve merge requests")

    req_row = (await uow._session.execute(
        _sql("""
            SELECT id, target_tree_id, source_tree_id, requester_id,
                   target_pivot_person_id, source_pivot_person_id,
                   new_tree_name, status, tenant_id
            FROM merge_requests WHERE id = :rid AND target_tree_id = :tid LIMIT 1
        """),
        {"rid": request_id, "tid": tree_id},
    )).first()
    if req_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merge request not found")
    if req_row.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Request already {req_row.status.lower()}")

    tree_row = (await uow._session.execute(
        _sql("SELECT name, tenant_id FROM family_trees WHERE id = :tid LIMIT 1"),
        {"tid": tree_id},
    )).first()

    new_status = "APPROVED" if body.action == "approve" else "DENIED"
    merged_tree_id = None

    if body.action == "approve":
        from src.api.v1.collaboration import _execute_merge
        merged_tree_id = await _execute_merge(
            session=uow._session,
            sources=[
                {"tree_id": req_row.target_tree_id, "pivot_person_id": req_row.target_pivot_person_id},
                {"tree_id": req_row.source_tree_id, "pivot_person_id": req_row.source_pivot_person_id},
            ],
            new_tree_name=req_row.new_tree_name,
            tenant_id=tree_row.tenant_id,
            owner_user_ids=[current_user.id, req_row.requester_id],
            merge_identical=False,
        )

    await uow._session.execute(
        _sql("""
            UPDATE merge_requests
            SET status = :status, resolved_by_id = :uid, resolved_at = NOW(), updated_at = NOW(),
                merged_tree_id = :mtid
            WHERE id = :rid
        """),
        {"status": new_status, "uid": current_user.id, "rid": request_id, "mtid": merged_tree_id},
    )

    # Notify requester
    if body.action == "approve":
        notif_type = "MERGE_APPROVED"
        notif_title = f"Merge request for {tree_row.name} was approved"
        notif_body_text = f"The merged tree \"{req_row.new_tree_name}\" has been created"
    else:
        notif_type = "MERGE_DENIED"
        notif_title = f"Merge request for {tree_row.name} was denied"
        notif_body_text = None

    await uow._session.execute(
        _sql("""
            INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
            VALUES (:user_id, :tenant_id, :type, :title, :nbody, CAST(:data AS jsonb))
        """),
        {
            "user_id": req_row.requester_id,
            "tenant_id": tree_row.tenant_id,
            "type": notif_type,
            "title": notif_title,
            "nbody": notif_body_text,
            "data": json.dumps({
                "tree_id": str(tree_id),
                "request_id": str(request_id),
                **({"merged_tree_id": str(merged_tree_id)} if merged_tree_id else {}),
            }),
        },
    )

    # Audit
    audit_action = Action.APPROVE_MERGE if body.action == "approve" else Action.DENY_MERGE
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=tree_row.tenant_id,
            actor_id=current_user.id,
            actor_display_name=_actor_name(current_user),
            action=audit_action,
            entity_type=AuditEntityType.MERGE_REQUEST,
            entity_id=request_id,
            after={
                "requester_id": str(req_row.requester_id),
                "source_tree_id": str(req_row.source_tree_id),
                "resolution": new_status,
                **({"merged_tree_id": str(merged_tree_id)} if merged_tree_id else {}),
            },
        )
    )

    await uow._session.commit()
    return {"id": str(request_id), "status": new_status, **({"merged_tree_id": str(merged_tree_id)} if merged_tree_id else {})}


# ── Diagnostic: inspect family groups of a tree ──────────────────────────────

@router.get("/trees/{tree_id}/debug-family-groups", summary="Debug: show raw family groups and members for a tree")
async def debug_family_groups(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    rows = (await uow._session.execute(
        _sql("""
            SELECT fg.id AS fg_id, fg.union_type, fg.custom_label,
                   fg.parent1_id, fg.parent2_id,
                   fgm.person_id, fgm.role, fgm.parentage_type,
                   p.display_given_name, p.display_surname
            FROM family_groups fg
            LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
            LEFT JOIN persons p ON p.id = fgm.person_id
            WHERE fg.tree_id = :tid
            ORDER BY fg.id, fgm.role, p.display_surname
        """),
        {"tid": tree_id},
    )).fetchall()

    groups: dict[str, dict] = {}
    for r in rows:
        gid = str(r.fg_id)
        if gid not in groups:
            groups[gid] = {
                "fg_id": gid,
                "union_type": r.union_type,
                "custom_label": r.custom_label,
                "parent1_id": str(r.parent1_id) if r.parent1_id else None,
                "parent2_id": str(r.parent2_id) if r.parent2_id else None,
                "members": [],
            }
        if r.person_id:
            groups[gid]["members"].append({
                "person_id": str(r.person_id),
                "name": f"{r.display_given_name or ''} {r.display_surname or ''}".strip(),
                "role": r.role,
                "parentage_type": r.parentage_type,
            })

    return {"tree_id": str(tree_id), "family_groups": list(groups.values())}
