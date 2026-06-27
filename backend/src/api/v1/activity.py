"""Activity feed — tenant-wide audit log + login events.

Accessible only to ADMIN and AUDITOR app roles.
"""
from __future__ import annotations

import csv
import io
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from src.api.deps import SessionDep, VerifiedUserDep
from src.api.v1._admin_log import LOGIN_EVENT_TYPES
from src.domain.collaboration.entities import AppRole

router = APIRouter(tags=["Activity"])

_PAGE_LIMIT = 25


def _require_elevated(user) -> None:
    if user.app_role not in (AppRole.SUPER_ADMIN, AppRole.ADMIN, AppRole.AUDITOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Activity log is restricted to Admin and Auditor roles")


# ── Response schema ────────────────────────────────────────────────────────────

class ActivityItem(BaseModel):
    id: uuid.UUID
    event_source: str           # "audit" | "login"
    actor_id: Optional[uuid.UUID]
    actor_display_name: str
    action: str
    entity_type: Optional[str]
    entity_id: Optional[uuid.UUID]
    entity_display_name: Optional[str]
    tree_id: Optional[uuid.UUID]
    tree_name: Optional[str]
    ip_address: Optional[str]
    occurred_at: str            # ISO string


class ActivityResponse(BaseModel):
    total: int
    items: list[ActivityItem]
    page: int
    page_size: int
    total_pages: int


# ── SQL helpers ────────────────────────────────────────────────────────────────

_AUDIT_SELECT = """
    SELECT
        'audit'                          AS event_source,
        al.id,
        al.actor_id,
        al.actor_display_name,
        al.action::text                  AS action,
        al.entity_type::text             AS entity_type,
        al.entity_id,
        al.entity_display_name,
        al.tree_id,
        ft.name                          AS tree_name,
        al.ip_address,
        al.occurred_at
    FROM audit_logs al
    LEFT JOIN family_trees ft ON ft.id = al.tree_id
    WHERE al.tenant_id = :tenant_id
"""

_LOGIN_SELECT = """
    SELECT
        'login'                                                    AS event_source,
        le.id,
        le.user_id                                                 AS actor_id,
        le.user_display_name                                       AS actor_display_name,
        le.event_type                                              AS action,
        'USER'                                                     AS entity_type,
        le.user_id                                                 AS entity_id,
        le.user_email                                              AS entity_display_name,
        NULL::uuid                                                 AS tree_id,
        NULL::text                                                 AS tree_name,
        le.ip_address,
        le.occurred_at
    FROM login_events le
    WHERE le.tenant_id = :tenant_id
"""


def _build_query(
    search: Optional[str],
    action_filter: Optional[str],
    entity_type_filter: Optional[str],
    sort_dir: str,
    limit: int,
    offset: int,
    count_only: bool = False,
) -> tuple[str, dict]:
    params: dict = {}

    audit_where = ""
    login_where = ""

    if search:
        params["search"] = f"%{search}%"
        audit_where += """
          AND (al.actor_display_name ILIKE :search
               OR al.entity_display_name ILIKE :search
               OR al.action::text ILIKE :search)
        """
        login_where += """
          AND (le.user_display_name ILIKE :search
               OR le.user_email ILIKE :search)
        """

    if action_filter:
        params["action_filter"] = action_filter
        if action_filter in LOGIN_EVENT_TYPES:
            audit_where += " AND false"
            login_where += " AND le.event_type = :action_filter"
        else:
            audit_where += " AND al.action::text = :action_filter"
            login_where += " AND false"

    if entity_type_filter and entity_type_filter != "LOGIN":
        params["entity_type_filter"] = entity_type_filter
        audit_where += " AND al.entity_type::text = :entity_type_filter"
        login_where += " AND false"
    elif entity_type_filter == "LOGIN":
        audit_where += " AND false"

    audit_sql = _AUDIT_SELECT + audit_where
    login_sql = _LOGIN_SELECT + login_where

    if count_only:
        sql = f"""
            SELECT COUNT(*) AS total
            FROM (
                {audit_sql}
                UNION ALL
                {login_sql}
            ) combined
        """
    else:
        order = "DESC" if sort_dir == "desc" else "ASC"
        params["limit"] = limit
        params["offset"] = offset
        sql = f"""
            SELECT * FROM (
                {audit_sql}
                UNION ALL
                {login_sql}
            ) combined
            ORDER BY occurred_at {order}
            LIMIT :limit OFFSET :offset
        """

    return sql, params


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/activity", response_model=ActivityResponse, summary="Tenant-wide activity feed (admin/auditor only)")
async def list_activity(
    current_user: VerifiedUserDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(_PAGE_LIMIT, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=200),
    action: Optional[str] = Query(None, description="Filter by action, e.g. CREATE_PERSON, LOGIN"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type, e.g. PERSON, TREE, LOGIN"),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
) -> ActivityResponse:
    _require_elevated(current_user)

    offset = (page - 1) * page_size
    params = {"tenant_id": current_user.tenant_id}

    count_sql, count_params = _build_query(search, action, entity_type, sort, page_size, offset, count_only=True)
    count_params["tenant_id"] = current_user.tenant_id
    total_row = (await session.execute(text(count_sql), count_params)).first()
    total = int(total_row.total) if total_row else 0

    data_sql, data_params = _build_query(search, action, entity_type, sort, page_size, offset)
    data_params["tenant_id"] = current_user.tenant_id
    rows = (await session.execute(text(data_sql), data_params)).fetchall()

    items = [
        ActivityItem(
            id=r.id,
            event_source=r.event_source,
            actor_id=r.actor_id,
            actor_display_name=r.actor_display_name or "",
            action=r.action or "",
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            entity_display_name=r.entity_display_name,
            tree_id=r.tree_id,
            tree_name=r.tree_name,
            ip_address=r.ip_address,
            occurred_at=r.occurred_at.isoformat() if r.occurred_at else "",
        )
        for r in rows
    ]

    import math
    return ActivityResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/activity/export", summary="Export activity feed as CSV (admin/auditor only)")
async def export_activity(
    current_user: VerifiedUserDep,
    session: SessionDep,
    search: Optional[str] = Query(None, max_length=200),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
) -> StreamingResponse:
    _require_elevated(current_user)

    data_sql, data_params = _build_query(search, action, entity_type, sort, limit=10000, offset=0)
    data_params["tenant_id"] = current_user.tenant_id
    rows = (await session.execute(text(data_sql), data_params)).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Occurred At", "Type", "Actor", "Action",
        "Entity Type", "Entity", "Tree", "IP Address",
    ])
    for r in rows:
        writer.writerow([
            r.occurred_at.isoformat() if r.occurred_at else "",
            r.event_source.upper(),
            r.actor_display_name or "",
            r.action or "",
            r.entity_type or "",
            r.entity_display_name or "",
            r.tree_name or "",
            r.ip_address or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity.csv"},
    )
