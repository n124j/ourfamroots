"""Namespace API — Super Admin-only namespace (tenant) management.

A "namespace" is the product-facing name for the existing `tenants` table/
`tenant_id` column (kept as-is internally — see the namespace feature plan).
Only the Super Administrator can create or list namespaces, and only the
Super Administrator can list users across more than one namespace at a time.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text

from src.api.deps import NamespaceOwnerDep, SessionDep, SuperAdminDep, TokenStoreDep
from src.api.v1._admin_log import log_admin_action
from src.domain.collaboration.entities import AppRole
from src.infrastructure.database.global_access import get_global_tenant_id, grant_global_tree_access
from src.infrastructure.database.models.collaboration import TreeMemberModel
from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel

router = APIRouter(prefix="/admin/namespaces", tags=["Admin", "Namespaces"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class NamespaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_global: bool
    user_count: int
    user_preview: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateNamespaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class UpdateNamespaceRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class NamespacesResponse(BaseModel):
    total: int
    items: list[NamespaceResponse]
    page: int
    page_size: int
    total_pages: int


PREVIEW_LIMIT = 3


def _admin_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _user_counts(session: SessionDep, tenant_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not tenant_ids:
        return {}
    rows = (await session.execute(
        select(UserModel.tenant_id, func.count())
        .where(UserModel.tenant_id.in_(tenant_ids))
        .group_by(UserModel.tenant_id)
    )).all()
    return {tid: count for tid, count in rows}


async def _user_previews(session: SessionDep, tenant_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    """First PREVIEW_LIMIT users per namespace, for an inline "who's in here" preview."""
    if not tenant_ids:
        return {}
    rows = (await session.execute(
        text("""
            SELECT tenant_id, display_name FROM (
                SELECT
                    tenant_id,
                    COALESCE(NULLIF(TRIM(CONCAT(given_name, ' ', family_name)), ''), email) AS display_name,
                    ROW_NUMBER() OVER (PARTITION BY tenant_id ORDER BY created_at) AS rn
                FROM users
                WHERE tenant_id = ANY(:tids)
            ) ranked
            WHERE rn <= :limit
        """),
        {"tids": tenant_ids, "limit": PREVIEW_LIMIT},
    )).all()
    previews: dict[uuid.UUID, list[str]] = {}
    for tid, name in rows:
        previews.setdefault(tid, []).append(name)
    return previews


def _serialize(t: TenantModel, user_count: int, user_preview: list[str] | None = None) -> NamespaceResponse:
    return NamespaceResponse(
        id=t.id, name=t.name, slug=t.slug, is_active=t.is_active,
        is_global=t.is_global, user_count=user_count, user_preview=user_preview or [],
        created_at=t.created_at,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", response_model=NamespaceResponse, status_code=status.HTTP_201_CREATED,
             summary="Create a new namespace (Super Admin only)")
async def create_namespace(
    body: CreateNamespaceRequest,
    request: Request,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> NamespaceResponse:
    existing = (await session.execute(
        select(TenantModel).where(TenantModel.slug == body.slug)
    )).scalars().first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A namespace with slug '{body.slug}' already exists")

    tenant = TenantModel(name=body.name, slug=body.slug, is_active=True, is_global=False)
    session.add(tenant)
    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        current_user.full_name, "NS_CREATE", f"{body.name} ({body.slug})", _admin_ip(request),
    )
    await session.commit()
    await session.refresh(tenant)
    return _serialize(tenant, 0)


@router.get("", response_model=NamespacesResponse,
            summary="List namespaces, paginated and searchable (Super Admin only)")
async def list_namespaces(
    current_user: SuperAdminDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=200),
    is_active: Optional[bool] = Query(None),
) -> NamespacesResponse:
    base = select(TenantModel)
    if search:
        pattern = f"%{search}%"
        base = base.where(TenantModel.name.ilike(pattern) | TenantModel.slug.ilike(pattern))
    if is_active is not None:
        base = base.where(TenantModel.is_active == is_active)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    offset = (page - 1) * page_size
    tenants = (await session.execute(
        base.order_by(TenantModel.created_at.desc()).offset(offset).limit(page_size)
    )).scalars().all()

    tenant_ids = [t.id for t in tenants]
    counts = await _user_counts(session, tenant_ids)
    previews = await _user_previews(session, tenant_ids)
    return NamespacesResponse(
        total=total,
        items=[_serialize(t, counts.get(t.id, 0), previews.get(t.id, [])) for t in tenants],
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


async def _notify_namespace_members(session: SessionDep, tenant: TenantModel, activated: bool) -> None:
    """Email every member of a namespace when it's activated or deactivated.

    Best-effort and run after the status change is already committed — an
    email failure must never roll back or block the activate/deactivate
    action itself (mirrors the try/except-and-move-on pattern used for every
    other admin-triggered email in this codebase).
    """
    import asyncio

    from src.config import get_settings
    from src.infrastructure.email.service import (
        namespace_activated_email,
        namespace_deactivated_email,
        send_email,
    )

    members = (await session.execute(
        select(UserModel).where(UserModel.tenant_id == tenant.id)
    )).scalars().all()
    if not members:
        return

    settings = get_settings()
    login_url = f"{settings.frontend_base_url}/login"

    async def _send_one(member: UserModel) -> None:
        try:
            if activated:
                html, text = namespace_activated_email(member.full_name, tenant.name, login_url)
                subject = f"'{tenant.name}' is active again on OurFamRoots"
            else:
                html, text = namespace_deactivated_email(member.full_name, tenant.name)
                subject = f"'{tenant.name}' has been deactivated on OurFamRoots"
            await send_email(to=member.email, subject=subject, html_body=html, text_body=text)
        except Exception:
            pass

    await asyncio.gather(*[_send_one(m) for m in members])


@router.patch("/{namespace_id}", response_model=NamespaceResponse,
              summary="Rename or activate/deactivate a namespace (Super Admin only)")
async def update_namespace(
    namespace_id: uuid.UUID,
    body: UpdateNamespaceRequest,
    request: Request,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> NamespaceResponse:
    tenant = await session.get(TenantModel, namespace_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Namespace not found")

    if tenant.is_global and body.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The Global namespace cannot be deactivated")

    was_active = tenant.is_active

    if body.name is not None:
        tenant.name = body.name
    if body.is_active is not None:
        tenant.is_active = body.is_active

    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        current_user.full_name, "NS_UPDATE", f"{tenant.name} ({tenant.slug})", _admin_ip(request),
    )
    await session.commit()
    await session.refresh(tenant)

    if body.is_active is not None and body.is_active != was_active:
        await _notify_namespace_members(session, tenant, activated=body.is_active)
    counts = await _user_counts(session, [tenant.id])
    return _serialize(tenant, counts.get(tenant.id, 0))


@router.delete("/{namespace_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a namespace (Super Admin only)")
async def delete_namespace(
    namespace_id: uuid.UUID,
    request: Request,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> Response:
    tenant = await session.get(TenantModel, namespace_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Namespace not found")

    if tenant.is_global:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The Global namespace cannot be deleted")

    counts = await _user_counts(session, [tenant.id])
    if counts.get(tenant.id, 0) > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This namespace still has users assigned to it. Move or remove them before deleting it.",
        )

    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        current_user.full_name, "NS_DELETE", f"{tenant.name} ({tenant.slug})", _admin_ip(request),
    )
    await session.delete(tenant)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{namespace_id}/users", summary="List users in any namespace (Super Admin only)")
async def list_namespace_users(
    namespace_id: uuid.UUID,
    current_user: SuperAdminDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=200),
) -> dict:
    tenant = await session.get(TenantModel, namespace_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Namespace not found")

    base = select(UserModel).where(UserModel.tenant_id == namespace_id)
    if search:
        pattern = f"%{search}%"
        base = base.where(
            (UserModel.email.ilike(pattern))
            | (UserModel.given_name.ilike(pattern))
            | (UserModel.family_name.ilike(pattern))
        )

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    rows = (await session.execute(
        base.order_by(UserModel.created_at.desc()).offset(offset).limit(page_size)
    )).scalars().all()

    from src.application.common.namespace import NamespaceSummary
    from src.api.v1.admin import _serialize as _serialize_user  # reuse existing user DTO shape

    namespace_summary = NamespaceSummary(id=tenant.id, name=tenant.name, slug=tenant.slug)
    return {
        "total": total,
        "items": [_serialize_user(u, namespace_summary) for u in rows],
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


@router.delete(
    "/{namespace_id}/users/{user_id}",
    summary="Remove a user from this namespace — moves them back to the Global namespace",
)
async def remove_namespace_user(
    namespace_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    current_user: NamespaceOwnerDep,
    session: SessionDep,
    token_store: TokenStoreDep,
) -> dict:
    namespace = await session.get(TenantModel, namespace_id)
    if namespace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Namespace not found")
    if namespace.is_global:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove users from the Global namespace")

    user = (await session.execute(
        select(UserModel).where(UserModel.id == user_id, UserModel.tenant_id == namespace_id)
    )).scalars().first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in this namespace")
    if user.id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove your own account from the namespace")

    global_tenant_id = await get_global_tenant_id(session)
    if global_tenant_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No Global namespace is configured")

    user_email = user.email
    user_name = user.full_name
    namespace_name = namespace.name

    # Mirrors accept_namespace_invitation's transfer, in reverse: drop this
    # namespace's tree access and role, restore the plain Global-user shape.
    user.tenant_id = global_tenant_id
    user.app_role = AppRole.STANDARD.value

    await session.execute(
        delete(TreeMemberModel).where(
            TreeMemberModel.user_id == user.id,
            TreeMemberModel.tenant_id == namespace_id,
        )
    )
    await grant_global_tree_access(session, user.id)

    await log_admin_action(
        session, namespace_id, current_user.id, current_user.full_name,
        "NS_REMOVE_USER", user.email, _admin_ip(request),
    )
    await session.commit()

    # The JWT's 'tid'/'role' claims are now stale — force re-login everywhere.
    await token_store.revoke_all_for_user(user.id)

    try:
        from src.infrastructure.email.service import namespace_removed_email, send_email
        html, text = namespace_removed_email(user_name, namespace_name)
        await send_email(
            to=user_email,
            subject=f"You've been removed from {namespace_name} on OurFamRoots",
            html_body=html,
            text_body=text,
        )
    except Exception:
        pass  # email failure must never roll back the removal

    return {"id": str(user.id), "email": user_email, "tenant_id": str(global_tenant_id)}
