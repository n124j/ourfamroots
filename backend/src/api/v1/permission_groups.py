"""Admin — Permission Group management.

Permission groups are reusable access templates that admins assign to
users for specific trees. Three levels are supported:
  VISIBLE    — user can see the tree (maps to TreeRole.VIEWER)
  READ       — read-only access (maps to TreeRole.VIEWER)
  READ_WRITE — full edit access (maps to TreeRole.EDITOR)

Design: a group has a list of trees and a list of members.
Adding a member grants them the group's permission level on every tree in
the group. Adding a tree grants all current members access to that tree.
Removing either side revokes the corresponding tree_members rows (unless
the user has OWNER or ADMIN role, which is never granted via groups).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status

def _ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else request.client.host if request.client else None
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from fastapi import Request as _Request

from src.api.deps import AdminUserDep, SessionDep
from src.api.v1._admin_log import log_admin_action
from src.domain.collaboration.entities import AppRole
from src.infrastructure.database.models.permission_group import (
    PermissionGroupAssignmentModel,
    PermissionGroupMemberModel,
    PermissionGroupModel,
    PermissionGroupTreeModel,
)
from src.infrastructure.database.models.user import UserModel

router = APIRouter(prefix="/admin", tags=["Admin", "Permission Groups"])

VALID_LEVELS = {"VISIBLE", "READ", "READ_WRITE"}

_LEVEL_TO_TREE_ROLE = {
    "VISIBLE":    "VIEWER",
    "READ":       "VIEWER",
    "READ_WRITE": "EDITOR",
}

# Role ranks — PG never grants ADMIN or OWNER
_ROLE_RANK = {"VIEWER": 1, "EDITOR": 2, "ADMIN": 3, "OWNER": 4}

# ── Schemas ─────────────────────────────────────────────────────────────────────

class PermissionGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permission_level: str = Field(..., pattern="^(VISIBLE|READ|READ_WRITE)$")


class PermissionGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permission_level: Optional[str] = Field(None, pattern="^(VISIBLE|READ|READ_WRITE)$")


class PermissionGroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    permission_level: str
    tree_count: int
    member_count: int
    created_by: Optional[uuid.UUID]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class GroupTreeResponse(BaseModel):
    id: uuid.UUID
    tree_id: uuid.UUID
    tree_name: str
    added_by: Optional[uuid.UUID]
    added_at: str


class GroupMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_display_name: str
    added_by: Optional[uuid.UUID]
    added_at: str


class AddTreeBody(BaseModel):
    tree_id: uuid.UUID


class AddMemberBody(BaseModel):
    user_id: uuid.UUID


class TenantTreeResponse(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


# ── Helpers ─────────────────────────────────────────────────────────────────────

async def _grant_tree_access(
    session,
    tree_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    granted_by: uuid.UUID,
) -> None:
    """Upsert a tree_members row without downgrading existing higher roles."""
    existing = (await session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": user_id},
    )).first()

    if existing:
        if _ROLE_RANK.get(existing.role, 0) >= _ROLE_RANK.get(role, 0):
            return  # never downgrade
        await session.execute(
            text("UPDATE tree_members SET role = :role WHERE tree_id = :tid AND user_id = :uid"),
            {"role": role, "tid": tree_id, "uid": user_id},
        )
    else:
        await session.execute(
            text("""
                INSERT INTO tree_members (tree_id, user_id, tenant_id, role, invited_by_id, joined_at)
                VALUES (:tid, :uid, :tenant, :role, :by, now())
                ON CONFLICT (tree_id, user_id) DO NOTHING
            """),
            {"tid": tree_id, "uid": user_id, "tenant": tenant_id, "role": role, "by": granted_by},
        )


async def _revoke_tree_access(session, tree_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Remove a tree_members row, but only if it was granted via a permission group.
    OWNER and ADMIN roles are never touched — they're always directly granted."""
    await session.execute(
        text("""
            DELETE FROM tree_members
            WHERE tree_id = :tid AND user_id = :uid AND role IN ('VIEWER', 'EDITOR')
        """),
        {"tid": tree_id, "uid": user_id},
    )


async def _get_group_tree_ids(session, group_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (await session.execute(
        select(PermissionGroupTreeModel.tree_id).where(
            PermissionGroupTreeModel.group_id == group_id
        )
    )).scalars().all()
    return list(rows)


async def _get_group_user_ids(session, group_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (await session.execute(
        select(PermissionGroupMemberModel.user_id).where(
            PermissionGroupMemberModel.group_id == group_id
        )
    )).scalars().all()
    return list(rows)


async def _get_tenant_id(session, group_id: uuid.UUID) -> uuid.UUID:
    row = (await session.execute(
        select(PermissionGroupModel.tenant_id).where(PermissionGroupModel.id == group_id)
    )).scalar_one()
    return row


# ── Endpoints — Groups ──────────────────────────────────────────────────────────

@router.get("/permission-groups", response_model=list[PermissionGroupResponse],
            summary="List all permission groups in the tenant")
async def list_permission_groups(
    current_user: AdminUserDep,
    session: SessionDep,
) -> list[PermissionGroupResponse]:
    rows = (await session.execute(
        text("""
            SELECT
                pg.id,
                pg.name,
                pg.description,
                pg.permission_level,
                pg.created_by,
                pg.created_at,
                pg.updated_at,
                COUNT(DISTINCT pgt.id) AS tree_count,
                COUNT(DISTINCT pgm.id) AS member_count
            FROM permission_groups pg
            LEFT JOIN permission_group_trees pgt ON pgt.group_id = pg.id
            LEFT JOIN permission_group_members pgm ON pgm.group_id = pg.id
            WHERE pg.tenant_id = :tid
            GROUP BY pg.id
            ORDER BY pg.name
        """),
        {"tid": current_user.tenant_id},
    )).fetchall()

    return [
        PermissionGroupResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            permission_level=r.permission_level,
            tree_count=r.tree_count,
            member_count=r.member_count,
            created_by=r.created_by,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/permission-groups", response_model=PermissionGroupResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Create a permission group")
async def create_permission_group(
    body: PermissionGroupCreate,
    current_user: AdminUserDep,
    session: SessionDep,
    request: Request,
) -> PermissionGroupResponse:
    existing = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.tenant_id == current_user.tenant_id,
            PermissionGroupModel.name == body.name,
        )
    )).scalars().first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"A permission group named '{body.name}' already exists")

    group = PermissionGroupModel(
        tenant_id=current_user.tenant_id,
        name=body.name,
        description=body.description,
        permission_level=body.permission_level,
        created_by=current_user.id,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "PG_CREATE", group.name, _ip(request))
    await session.commit()
    return PermissionGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        permission_level=group.permission_level,
        tree_count=0,
        member_count=0,
        created_by=group.created_by,
        created_at=group.created_at.isoformat(),
        updated_at=group.updated_at.isoformat(),
    )


@router.patch("/permission-groups/{group_id}", response_model=PermissionGroupResponse,
              summary="Update a permission group")
async def update_permission_group(
    group_id: uuid.UUID,
    body: PermissionGroupUpdate,
    current_user: AdminUserDep,
    session: SessionDep,
    request: Request,
) -> PermissionGroupResponse:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description

    if body.permission_level is not None and body.permission_level != group.permission_level:
        new_role = _LEVEL_TO_TREE_ROLE.get(body.permission_level)
        if new_role:
            # Propagate role change to all existing (member, tree) pairs in this group
            await session.execute(
                text("""
                    UPDATE tree_members tm
                    SET role = :role
                    FROM permission_group_members pgm
                    JOIN permission_group_trees pgt ON pgt.group_id = pgm.group_id
                    WHERE pgm.group_id = :gid
                      AND tm.tree_id = pgt.tree_id
                      AND tm.user_id = pgm.user_id
                      AND tm.role NOT IN ('OWNER', 'ADMIN')
                """),
                {"role": new_role, "gid": group_id},
            )
        group.permission_level = body.permission_level

    await session.commit()
    await session.refresh(group)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "PG_UPDATE", group.name, _ip(request))
    await session.commit()

    tree_count = (await session.execute(
        select(func.count()).where(PermissionGroupTreeModel.group_id == group_id)
    )).scalar_one()
    member_count = (await session.execute(
        select(func.count()).where(PermissionGroupMemberModel.group_id == group_id)
    )).scalar_one()

    return PermissionGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        permission_level=group.permission_level,
        tree_count=tree_count,
        member_count=member_count,
        created_by=group.created_by,
        created_at=group.created_at.isoformat(),
        updated_at=group.updated_at.isoformat(),
    )


@router.delete("/permission-groups/{group_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               response_model=None,
               summary="Delete a permission group and revoke all its access grants")
async def delete_permission_group(
    group_id: uuid.UUID,
    current_user: AdminUserDep,
    session: SessionDep,
    request: Request,
) -> None:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    group_name = group.name

    # Revoke all tree access for all (member, tree) pairs before deleting
    tree_role = _LEVEL_TO_TREE_ROLE.get(group.permission_level)
    if tree_role:
        await session.execute(
            text("""
                DELETE FROM tree_members tm
                USING permission_group_members pgm, permission_group_trees pgt
                WHERE pgm.group_id = :gid
                  AND pgt.group_id = :gid
                  AND tm.tree_id = pgt.tree_id
                  AND tm.user_id = pgm.user_id
                  AND tm.role IN ('VIEWER', 'EDITOR')
            """),
            {"gid": group_id},
        )

    await session.delete(group)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "PG_DELETE", group_name, _ip(request))
    await session.commit()


# ── Endpoints — Group Trees ─────────────────────────────────────────────────────

@router.get("/permission-groups/{group_id}/trees",
            response_model=list[GroupTreeResponse],
            summary="List trees in a permission group")
async def list_group_trees(
    group_id: uuid.UUID,
    current_user: AdminUserDep,
    session: SessionDep,
) -> list[GroupTreeResponse]:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    rows = (await session.execute(
        text("""
            SELECT pgt.id, pgt.tree_id, ft.name AS tree_name, pgt.added_by, pgt.added_at
            FROM permission_group_trees pgt
            JOIN family_trees ft ON ft.id = pgt.tree_id
            WHERE pgt.group_id = :gid
            ORDER BY ft.name
        """),
        {"gid": group_id},
    )).fetchall()

    return [
        GroupTreeResponse(
            id=r.id,
            tree_id=r.tree_id,
            tree_name=r.tree_name,
            added_by=r.added_by,
            added_at=r.added_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/permission-groups/{group_id}/trees",
             response_model=GroupTreeResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Add a tree to a permission group")
async def add_group_tree(
    group_id: uuid.UUID,
    body: AddTreeBody,
    current_user: AdminUserDep,
    session: SessionDep,
    request: Request,
) -> GroupTreeResponse:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    # Verify tree exists and admin has access to it
    tree_row = (await session.execute(
        text("SELECT id, name FROM family_trees WHERE id = :tid AND tenant_id = :tenant AND is_deleted = false LIMIT 1"),
        {"tid": body.tree_id, "tenant": current_user.tenant_id},
    )).first()
    if tree_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if current_user.app_role != AppRole.AUDITOR:
        member_check = (await session.execute(
            text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
            {"tid": body.tree_id, "uid": current_user.id},
        )).first()
        if not member_check:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of this tree")

    # Duplicate check
    dup = (await session.execute(
        select(PermissionGroupTreeModel).where(
            PermissionGroupTreeModel.group_id == group_id,
            PermissionGroupTreeModel.tree_id == body.tree_id,
        )
    )).scalars().first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "This tree is already in the group")

    entry = PermissionGroupTreeModel(
        group_id=group_id,
        tree_id=body.tree_id,
        added_by=current_user.id,
    )
    session.add(entry)

    # Grant access to all existing group members
    tree_role = _LEVEL_TO_TREE_ROLE.get(group.permission_level)
    if tree_role:
        user_ids = await _get_group_user_ids(session, group_id)
        for uid in user_ids:
            await _grant_tree_access(
                session,
                tree_id=body.tree_id,
                user_id=uid,
                tenant_id=current_user.tenant_id,
                role=tree_role,
                granted_by=current_user.id,
            )

    await session.commit()
    await session.refresh(entry)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "PG_ADD_TREE",
                           f"{group.name} → {tree_row.name}", _ip(request))
    await session.commit()

    return GroupTreeResponse(
        id=entry.id,
        tree_id=entry.tree_id,
        tree_name=tree_row.name,
        added_by=entry.added_by,
        added_at=entry.added_at.isoformat(),
    )


@router.delete("/permission-groups/{group_id}/trees/{tree_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               response_model=None,
               summary="Remove a tree from a permission group")
async def remove_group_tree(
    group_id: uuid.UUID,
    tree_id: uuid.UUID,
    current_user: AdminUserDep,
    session: SessionDep,
    request: Request,
) -> None:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    entry = (await session.execute(
        select(PermissionGroupTreeModel).where(
            PermissionGroupTreeModel.group_id == group_id,
            PermissionGroupTreeModel.tree_id == tree_id,
        )
    )).scalars().first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not in this group")

    tree_name_row = (await session.execute(
        text("SELECT name FROM family_trees WHERE id = :tid LIMIT 1"), {"tid": tree_id}
    )).first()
    tree_name = tree_name_row.name if tree_name_row else str(tree_id)

    await session.delete(entry)

    # Revoke access for all group members on this tree
    user_ids = await _get_group_user_ids(session, group_id)
    for uid in user_ids:
        await _revoke_tree_access(session, tree_id=tree_id, user_id=uid)

    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "PG_REMOVE_TREE",
                           f"{group.name} → {tree_name}", _ip(request))
    await session.commit()


# ── Endpoints — Group Members ───────────────────────────────────────────────────

@router.get("/permission-groups/{group_id}/members",
            response_model=list[GroupMemberResponse],
            summary="List members of a permission group")
async def list_group_members(
    group_id: uuid.UUID,
    current_user: AdminUserDep,
    session: SessionDep,
) -> list[GroupMemberResponse]:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    rows = (await session.execute(
        text("""
            SELECT
                pgm.id, pgm.user_id,
                u.email AS user_email,
                COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS user_display_name,
                pgm.added_by, pgm.added_at
            FROM permission_group_members pgm
            JOIN users u ON u.id = pgm.user_id
            WHERE pgm.group_id = :gid
            ORDER BY user_display_name
        """),
        {"gid": group_id},
    )).fetchall()

    return [
        GroupMemberResponse(
            id=r.id,
            user_id=r.user_id,
            user_email=r.user_email,
            user_display_name=r.user_display_name,
            added_by=r.added_by,
            added_at=r.added_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/permission-groups/{group_id}/members",
             response_model=GroupMemberResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Add a user to a permission group")
async def add_group_member(
    group_id: uuid.UUID,
    body: AddMemberBody,
    current_user: AdminUserDep,
    session: SessionDep,
    request: Request,
) -> GroupMemberResponse:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    user = (await session.execute(
        select(UserModel).where(
            UserModel.id == body.user_id,
            UserModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in this tenant")

    dup = (await session.execute(
        select(PermissionGroupMemberModel).where(
            PermissionGroupMemberModel.group_id == group_id,
            PermissionGroupMemberModel.user_id == body.user_id,
        )
    )).scalars().first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already in this group")

    entry = PermissionGroupMemberModel(
        group_id=group_id,
        user_id=body.user_id,
        added_by=current_user.id,
    )
    session.add(entry)

    # Grant access to all trees in this group
    tree_role = _LEVEL_TO_TREE_ROLE.get(group.permission_level)
    if tree_role:
        tree_ids = await _get_group_tree_ids(session, group_id)
        for tid in tree_ids:
            await _grant_tree_access(
                session,
                tree_id=tid,
                user_id=body.user_id,
                tenant_id=current_user.tenant_id,
                role=tree_role,
                granted_by=current_user.id,
            )

    await session.commit()
    await session.refresh(entry)

    user_display = f"{user.given_name or ''} {user.family_name or ''}".strip() or user.email
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "PG_ADD_MEMBER",
                           f"{group.name} → {user_display}", _ip(request))
    await session.commit()

    return GroupMemberResponse(
        id=entry.id,
        user_id=entry.user_id,
        user_email=user.email,
        user_display_name=user_display,
        added_by=entry.added_by,
        added_at=entry.added_at.isoformat(),
    )


@router.delete("/permission-groups/{group_id}/members/{member_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               response_model=None,
               summary="Remove a user from a permission group")
async def remove_group_member(
    group_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: AdminUserDep,
    session: SessionDep,
    request: Request,
) -> None:
    group = (await session.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.id == group_id,
            PermissionGroupModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission group not found")

    entry = (await session.execute(
        select(PermissionGroupMemberModel).where(
            PermissionGroupMemberModel.id == member_id,
            PermissionGroupMemberModel.group_id == group_id,
        )
    )).scalars().first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not in this group")

    user_id = entry.user_id

    # Fetch user display name before deleting
    user_row = (await session.execute(
        text("""SELECT email, given_name, family_name FROM users WHERE id = :uid LIMIT 1"""),
        {"uid": user_id},
    )).first()
    user_display = (
        f"{user_row.given_name or ''} {user_row.family_name or ''}".strip() or user_row.email
        if user_row else str(user_id)
    )

    await session.delete(entry)

    # Revoke access to all trees in this group
    tree_ids = await _get_group_tree_ids(session, group_id)
    for tid in tree_ids:
        await _revoke_tree_access(session, tree_id=tid, user_id=user_id)

    await log_admin_action(session, current_user.tenant_id, current_user.id,
                           current_user.full_name, "PG_REMOVE_MEMBER",
                           f"{group.name} → {user_display}", _ip(request))
    await session.commit()


# ── Helper endpoint — list trees in tenant (for assignment modal) ──────────────

@router.get("/trees", response_model=list[TenantTreeResponse],
            summary="List all trees in the tenant (for assignment dropdowns)")
async def list_tenant_trees(
    current_user: AdminUserDep,
    session: SessionDep,
) -> list[TenantTreeResponse]:
    if current_user.app_role == AppRole.AUDITOR:
        rows = (await session.execute(
            text("SELECT id, name FROM family_trees WHERE tenant_id = :tid AND is_deleted = false ORDER BY name"),
            {"tid": current_user.tenant_id},
        )).fetchall()
    else:
        # ADMIN sees only trees they are a member of
        rows = (await session.execute(
            text("""
                SELECT ft.id, ft.name FROM family_trees ft
                JOIN tree_members tm ON tm.tree_id = ft.id AND tm.user_id = :user_id
                WHERE ft.tenant_id = :tid AND ft.is_deleted = false
                ORDER BY ft.name
            """),
            {"tid": current_user.tenant_id, "user_id": current_user.id},
        )).fetchall()
    return [TenantTreeResponse(id=r.id, name=r.name) for r in rows]
