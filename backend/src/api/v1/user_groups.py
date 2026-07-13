"""Admin — User Group management.

A user group is a named, reusable collection of users within a tenant.
Linking a user group to a Permission Group (see permission_groups.py) grants
every current member of the user group that permission group's access —
live: adding/removing someone from the user group immediately grants/revokes
access implied by every permission group the user group is linked to.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from src.api.deps import AdminUserDep, SessionDep
from src.api.v1._admin_log import log_admin_action
from src.api.v1.permission_groups import _LEVEL_TO_TREE_ROLE, _grant_tree_access, _revoke_tree_access, _user_still_entitled
from src.domain.collaboration.entities import AppRole
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.database.models.user_group import UserGroupMemberModel, UserGroupModel

router = APIRouter(prefix="/admin/user-groups", tags=["Admin", "User Groups"])

PREVIEW_LIMIT = 3


# ── Schemas ──────────────────────────────────────────────────────────────────

class UserGroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    member_count: int
    member_preview: list[str] = []
    created_by: Optional[uuid.UUID]
    created_at: str
    updated_at: str


class UserGroupsResponse(BaseModel):
    total: int
    items: list[UserGroupResponse]
    page: int
    page_size: int
    total_pages: int


class CreateUserGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class UpdateUserGroupRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class UserGroupMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_display_name: str
    added_by: Optional[uuid.UUID]
    added_at: str


class AddUserGroupMemberRequest(BaseModel):
    user_id: uuid.UUID


class BulkRoleRequest(BaseModel):
    app_role: str = Field(..., pattern="^(ADMIN|STANDARD|AUDITOR|SUPER_ADMIN)$")


class BulkRoleResponse(BaseModel):
    updated_count: int


def _ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else request.client.host if request.client else None


async def _get_linked_permission_group_trees(session, user_group_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    """(tree_id, tree_role) pairs across every permission group linked to this user group."""
    rows = (await session.execute(
        text("""
            SELECT DISTINCT pgt.tree_id, pg.permission_level
            FROM permission_group_user_groups pgug
            JOIN permission_groups pg ON pg.id = pgug.permission_group_id
            JOIN permission_group_trees pgt ON pgt.group_id = pg.id
            WHERE pgug.user_group_id = :ugid
        """),
        {"ugid": user_group_id},
    )).fetchall()
    pairs = [(r.tree_id, _LEVEL_TO_TREE_ROLE.get(r.permission_level)) for r in rows]
    return [(tid, role) for tid, role in pairs if role]


async def _member_previews(session, group_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    """First PREVIEW_LIMIT members per user group, for an inline table preview."""
    if not group_ids:
        return {}
    rows = (await session.execute(
        text("""
            SELECT group_id, display_name FROM (
                SELECT
                    ugm.group_id,
                    COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS display_name,
                    ROW_NUMBER() OVER (PARTITION BY ugm.group_id ORDER BY ugm.added_at) AS rn
                FROM user_group_members ugm
                JOIN users u ON u.id = ugm.user_id
                WHERE ugm.group_id = ANY(:gids)
            ) ranked
            WHERE rn <= :limit
        """),
        {"gids": group_ids, "limit": PREVIEW_LIMIT},
    )).all()
    previews: dict[uuid.UUID, list[str]] = {}
    for gid, name in rows:
        previews.setdefault(gid, []).append(name)
    return previews


def _serialize(g: UserGroupModel, member_count: int, member_preview: list[str] | None = None) -> UserGroupResponse:
    return UserGroupResponse(
        id=g.id, name=g.name, description=g.description, member_count=member_count,
        member_preview=member_preview or [],
        created_by=g.created_by, created_at=g.created_at.isoformat(), updated_at=g.updated_at.isoformat(),
    )


# ── Endpoints — Groups ───────────────────────────────────────────────────────

@router.post("", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED,
             summary="Create a user group")
async def create_user_group(
    body: CreateUserGroupRequest,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> UserGroupResponse:
    dup = (await session.execute(
        select(UserGroupModel).where(
            UserGroupModel.tenant_id == current_user.tenant_id,
            UserGroupModel.name == body.name,
        )
    )).scalars().first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A user group named '{body.name}' already exists")

    group = UserGroupModel(
        tenant_id=current_user.tenant_id, name=body.name, description=body.description,
        created_by=current_user.id,
    )
    session.add(group)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "UG_CREATE", body.name, _ip(request))
    await session.commit()
    await session.refresh(group)
    return _serialize(group, 0)


@router.get("", response_model=UserGroupsResponse,
            summary="List user groups in the tenant, paginated and searchable")
async def list_user_groups(
    current_user: AdminUserDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=200),
) -> UserGroupsResponse:
    base = select(UserGroupModel).where(UserGroupModel.tenant_id == current_user.tenant_id)
    if search:
        base = base.where(UserGroupModel.name.ilike(f"%{search}%"))

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    groups = (await session.execute(
        base.order_by(UserGroupModel.name).offset(offset).limit(page_size)
    )).scalars().all()

    counts: dict[uuid.UUID, int] = {}
    previews: dict[uuid.UUID, list[str]] = {}
    if groups:
        group_ids = [g.id for g in groups]
        rows = (await session.execute(
            select(UserGroupMemberModel.group_id, func.count())
            .where(UserGroupMemberModel.group_id.in_(group_ids))
            .group_by(UserGroupMemberModel.group_id)
        )).all()
        counts = dict(rows)
        previews = await _member_previews(session, group_ids)

    import math
    return UserGroupsResponse(
        total=total,
        items=[_serialize(g, counts.get(g.id, 0), previews.get(g.id, [])) for g in groups],
        page=page, page_size=page_size, total_pages=max(1, math.ceil(total / page_size)),
    )


@router.patch("/{group_id}", response_model=UserGroupResponse, summary="Rename or redescribe a user group")
async def update_user_group(
    group_id: uuid.UUID,
    body: UpdateUserGroupRequest,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> UserGroupResponse:
    group = (await session.execute(
        select(UserGroupModel).where(
            UserGroupModel.id == group_id, UserGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User group not found")

    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description

    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "UG_UPDATE", group.name, _ip(request))
    await session.commit()
    await session.refresh(group)

    member_count = (await session.execute(
        select(func.count()).where(UserGroupMemberModel.group_id == group_id)
    )).scalar_one()
    return _serialize(group, member_count)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None,
               summary="Delete a user group and revoke any access it was granting")
async def delete_user_group(
    group_id: uuid.UUID,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> None:
    group = (await session.execute(
        select(UserGroupModel).where(
            UserGroupModel.id == group_id, UserGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User group not found")

    group_name = group.name
    member_ids = (await session.execute(
        select(UserGroupMemberModel.user_id).where(UserGroupMemberModel.group_id == group_id)
    )).scalars().all()
    tree_pairs = await _get_linked_permission_group_trees(session, group_id)
    tree_ids = {tid for tid, _role in tree_pairs}

    await session.delete(group)  # cascades user_group_members + permission_group_user_groups
    await session.flush()

    for uid in member_ids:
        for tid in tree_ids:
            if not await _user_still_entitled(session, current_user.tenant_id, uid, tid):
                await _revoke_tree_access(session, tree_id=tid, user_id=uid)

    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "UG_DELETE", group_name, _ip(request))
    await session.commit()


# ── Endpoints — Members ──────────────────────────────────────────────────────

@router.get("/{group_id}/members", response_model=list[UserGroupMemberResponse],
            summary="List members of a user group")
async def list_user_group_members(
    group_id: uuid.UUID,
    current_user: AdminUserDep,
    session: SessionDep,
) -> list[UserGroupMemberResponse]:
    group = (await session.execute(
        select(UserGroupModel).where(
            UserGroupModel.id == group_id, UserGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User group not found")

    rows = (await session.execute(
        text("""
            SELECT
                ugm.id, ugm.user_id, u.email AS user_email,
                COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS user_display_name,
                ugm.added_by, ugm.added_at
            FROM user_group_members ugm
            JOIN users u ON u.id = ugm.user_id
            WHERE ugm.group_id = :gid
            ORDER BY user_display_name
        """),
        {"gid": group_id},
    )).fetchall()

    return [
        UserGroupMemberResponse(
            id=r.id, user_id=r.user_id, user_email=r.user_email, user_display_name=r.user_display_name,
            added_by=r.added_by, added_at=r.added_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/{group_id}/members", response_model=UserGroupMemberResponse, status_code=status.HTTP_201_CREATED,
             summary="Add a user to a user group")
async def add_user_group_member(
    group_id: uuid.UUID,
    body: AddUserGroupMemberRequest,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> UserGroupMemberResponse:
    group = (await session.execute(
        select(UserGroupModel).where(
            UserGroupModel.id == group_id, UserGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User group not found")

    user = (await session.execute(
        select(UserModel).where(
            UserModel.id == body.user_id, UserModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in this tenant")

    dup = (await session.execute(
        select(UserGroupMemberModel).where(
            UserGroupMemberModel.group_id == group_id, UserGroupMemberModel.user_id == body.user_id,
        )
    )).scalars().first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already in this group")

    entry = UserGroupMemberModel(group_id=group_id, user_id=body.user_id, added_by=current_user.id)
    session.add(entry)

    # Grant access implied by every permission group this user group is linked to
    tree_pairs = await _get_linked_permission_group_trees(session, group_id)
    for tid, role in tree_pairs:
        await _grant_tree_access(
            session, tree_id=tid, user_id=body.user_id,
            tenant_id=current_user.tenant_id, role=role, granted_by=current_user.id,
        )

    await session.commit()
    await session.refresh(entry)

    user_display = f"{user.given_name or ''} {user.family_name or ''}".strip() or user.email
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "UG_ADD_MEMBER",
                           f"{group.name} → {user_display}", _ip(request))
    await session.commit()

    return UserGroupMemberResponse(
        id=entry.id, user_id=entry.user_id, user_email=user.email, user_display_name=user_display,
        added_by=entry.added_by, added_at=entry.added_at.isoformat(),
    )


@router.delete("/{group_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None,
               summary="Remove a user from a user group")
async def remove_user_group_member(
    group_id: uuid.UUID,
    member_id: uuid.UUID,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> None:
    group = (await session.execute(
        select(UserGroupModel).where(
            UserGroupModel.id == group_id, UserGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User group not found")

    entry = (await session.execute(
        select(UserGroupMemberModel).where(
            UserGroupMemberModel.id == member_id, UserGroupMemberModel.group_id == group_id,
        )
    )).scalars().first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not in this group")

    user_id = entry.user_id
    user_row = (await session.execute(
        text("SELECT email, given_name, family_name FROM users WHERE id = :uid LIMIT 1"), {"uid": user_id},
    )).first()
    user_display = (
        f"{user_row.given_name or ''} {user_row.family_name or ''}".strip() or user_row.email
        if user_row else str(user_id)
    )

    tree_pairs = await _get_linked_permission_group_trees(session, group_id)
    tree_ids = {tid for tid, _role in tree_pairs}

    await session.delete(entry)
    await session.flush()

    for tid in tree_ids:
        if not await _user_still_entitled(session, current_user.tenant_id, user_id, tid):
            await _revoke_tree_access(session, tree_id=tid, user_id=user_id)

    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "UG_REMOVE_MEMBER",
                           f"{group.name} → {user_display}", _ip(request))
    await session.commit()


# ── Bulk role assignment ─────────────────────────────────────────────────────

@router.post("/{group_id}/bulk-role", response_model=BulkRoleResponse,
             summary="Set the app role for every member of a user group at once")
async def bulk_assign_role(
    group_id: uuid.UUID,
    body: BulkRoleRequest,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> BulkRoleResponse:
    group = (await session.execute(
        select(UserGroupModel).where(
            UserGroupModel.id == group_id, UserGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User group not found")

    # SUPER_ADMIN is a single site-wide role — only an existing Super Admin
    # may grant it, same guard as the single-user admin.py::update_user.
    if body.app_role == "SUPER_ADMIN" and current_user.app_role != AppRole.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a Super Administrator can grant Super Admin access")

    member_ids = (await session.execute(
        select(UserGroupMemberModel.user_id).where(UserGroupMemberModel.group_id == group_id)
    )).scalars().all()
    # Never change the caller's own role via a bulk action, same self-protection as the single-user endpoint.
    target_ids = [uid for uid in member_ids if uid != current_user.id]
    if not target_ids:
        return BulkRoleResponse(updated_count=0)

    result = await session.execute(
        select(UserModel).where(
            UserModel.id.in_(target_ids), UserModel.tenant_id == current_user.tenant_id,
        )
    )
    users = result.scalars().all()
    for u in users:
        u.app_role = body.app_role

    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "UG_BULK_ROLE",
                           f"{group.name} → {body.app_role} ({len(users)} users)", _ip(request))
    await session.commit()

    return BulkRoleResponse(updated_count=len(users))
