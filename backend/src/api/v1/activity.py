"""Activity feed — audit log + login events.

Accessible only to ADMIN, AUDITOR, and SUPER_ADMIN app roles. ADMIN sees only
their own namespace; AUDITOR and SUPER_ADMIN see activity across every
namespace by default, optionally narrowed with `namespace_id`.
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
from src.application.common.namespace import NamespaceSummary
from src.domain.collaboration.entities import AppRole, SUPER_ADMIN_DISPLAY_LABEL

router = APIRouter(tags=["Activity"])

_PAGE_LIMIT = 25


def _require_elevated(user) -> None:
    if user.app_role not in (AppRole.SUPER_ADMIN, AppRole.ADMIN, AppRole.AUDITOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Activity log is restricted to Admin and Auditor roles")


def _is_global(user) -> bool:
    """Super Admin and Auditor see activity across every namespace; a plain Admin stays tenant-scoped."""
    return user.app_role in (AppRole.SUPER_ADMIN, AppRole.AUDITOR)


# Action types where the login-events row is self-referential (the actor is acting
# on their own account), so entity_display_name (the row's `user_email` column)
# also identifies the actor and must be masked alongside actor_display_name. Other
# login-sourced actions (ADMIN_CREATE, PG_*, ...) reuse that same column to describe
# a different target, which isn't the actor's own identity and stays untouched.
_AUTH_EVENT_TYPES = {"LOGIN", "LOGOUT", "FAILED_LOGIN"}


def _display_names(row, viewer_is_super_admin: bool) -> tuple[str, Optional[str]]:
    if viewer_is_super_admin or row.actor_app_role != AppRole.SUPER_ADMIN.value:
        return row.actor_display_name or "", row.entity_display_name
    entity = None if row.action in _AUTH_EVENT_TYPES else row.entity_display_name
    return SUPER_ADMIN_DISPLAY_LABEL, entity


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
    tenant_id: Optional[uuid.UUID] = None
    namespace: Optional[NamespaceSummary] = None


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
        al.occurred_at,
        al.tenant_id,
        t.name                           AS tenant_name,
        t.slug                           AS tenant_slug,
        au.app_role                      AS actor_app_role
    FROM audit_logs al
    LEFT JOIN family_trees ft ON ft.id = al.tree_id
    LEFT JOIN tenants t ON t.id = al.tenant_id
    LEFT JOIN users au ON au.id = al.actor_id
    WHERE 1=1
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
        le.user_email                                               AS entity_display_name,
        NULL::uuid                                                 AS tree_id,
        NULL::text                                                 AS tree_name,
        le.ip_address,
        le.occurred_at,
        le.tenant_id,
        t.name                                                     AS tenant_name,
        t.slug                                                     AS tenant_slug,
        au.app_role                                                AS actor_app_role
    FROM login_events le
    LEFT JOIN tenants t ON t.id = le.tenant_id
    LEFT JOIN users au ON au.id = le.user_id
    WHERE 1=1
"""


def _build_query(
    tenant_id: Optional[uuid.UUID],
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

    if tenant_id is not None:
        params["tenant_id"] = tenant_id
        audit_where += " AND al.tenant_id = :tenant_id"
        login_where += " AND le.tenant_id = :tenant_id"

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

@router.get("/activity", response_model=ActivityResponse, summary="Activity feed (admin/auditor only)")
async def list_activity(
    current_user: VerifiedUserDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(_PAGE_LIMIT, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=200),
    action: Optional[str] = Query(None, description="Filter by action, e.g. CREATE_PERSON, LOGIN"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type, e.g. PERSON, TREE, LOGIN"),
    namespace_id: Optional[uuid.UUID] = Query(None, description="Super Admin/Auditor only: filter to one namespace"),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
) -> ActivityResponse:
    _require_elevated(current_user)

    is_global = _is_global(current_user)
    tenant_filter = (namespace_id if is_global else current_user.tenant_id)
    viewer_is_super_admin = current_user.app_role == AppRole.SUPER_ADMIN

    offset = (page - 1) * page_size

    count_sql, count_params = _build_query(tenant_filter, search, action, entity_type, sort, page_size, offset, count_only=True)
    total_row = (await session.execute(text(count_sql), count_params)).first()
    total = int(total_row.total) if total_row else 0

    data_sql, data_params = _build_query(tenant_filter, search, action, entity_type, sort, page_size, offset)
    rows = (await session.execute(text(data_sql), data_params)).fetchall()

    items = []
    for r in rows:
        actor_name, entity_name = _display_names(r, viewer_is_super_admin)
        items.append(ActivityItem(
            id=r.id,
            event_source=r.event_source,
            actor_id=r.actor_id,
            actor_display_name=actor_name,
            action=r.action or "",
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            entity_display_name=entity_name,
            tree_id=r.tree_id,
            tree_name=r.tree_name,
            ip_address=r.ip_address,
            occurred_at=r.occurred_at.isoformat() if r.occurred_at else "",
            tenant_id=r.tenant_id,
            namespace=NamespaceSummary(id=r.tenant_id, name=r.tenant_name, slug=r.tenant_slug) if r.tenant_id and r.tenant_name else None,
        ))

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
    namespace_id: Optional[uuid.UUID] = Query(None, description="Super Admin/Auditor only: filter to one namespace"),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
) -> StreamingResponse:
    _require_elevated(current_user)

    is_global = _is_global(current_user)
    tenant_filter = (namespace_id if is_global else current_user.tenant_id)
    viewer_is_super_admin = current_user.app_role == AppRole.SUPER_ADMIN

    data_sql, data_params = _build_query(tenant_filter, search, action, entity_type, sort, limit=10000, offset=0)
    rows = (await session.execute(text(data_sql), data_params)).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Occurred At", "Type", "Actor", "Action",
        "Entity Type", "Entity", "Tree", "Namespace", "IP Address",
    ])
    for r in rows:
        actor_name, entity_name = _display_names(r, viewer_is_super_admin)
        writer.writerow([
            r.occurred_at.isoformat() if r.occurred_at else "",
            r.event_source.upper(),
            actor_name,
            r.action or "",
            r.entity_type or "",
            entity_name or "",
            r.tree_name or "",
            r.tenant_name or "",
            r.ip_address or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity.csv"},
    )
