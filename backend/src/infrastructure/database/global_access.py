"""Grants tree_members access for a user based on platform-wide global permission groups.

Shared by user registration (AuthService), admin-created users (POST /admin/users),
OAuth auto-provisioning, and namespace-invitation acceptance, so a user immediately
sees every tree attached to a group with is_global=true, at that group's permission
level — regardless of which tenant (namespace) the user or the tree belongs to.
The resulting tree_members row is stamped with the TREE's own tenant_id, not the
user's, so a user's own tenant_id and their tree_members.tenant_id can legitimately
differ for global trees (see the discovery.py access-request flow for the existing
precedent of this pattern).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

_LEVEL_TO_TREE_ROLE = {
    "VISIBLE":    "VIEWER",
    "READ":       "VIEWER",
    "READ_WRITE": "EDITOR",
}


async def get_global_tenant_id(session: AsyncSession) -> uuid.UUID | None:
    """Return the id of the single Global namespace (tenants.is_global = true), if any."""
    from src.infrastructure.database.models.tenant import TenantModel

    result = await session.execute(
        select(TenantModel.id).where(TenantModel.is_global.is_(True))
    )
    return result.scalar_one_or_none()


async def grant_global_tree_access(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    rows = (await session.execute(
        text("""
            SELECT pgt.tree_id, pg.permission_level, ft.tenant_id AS tree_tenant_id
            FROM permission_groups pg
            JOIN permission_group_trees pgt ON pgt.group_id = pg.id
            JOIN family_trees ft ON ft.id = pgt.tree_id
            WHERE pg.is_global = true AND ft.is_deleted = false
        """),
    )).fetchall()

    for row in rows:
        role = _LEVEL_TO_TREE_ROLE.get(row.permission_level)
        if not role:
            continue
        await session.execute(
            text("""
                INSERT INTO tree_members (tree_id, user_id, tenant_id, role, invited_by_id, joined_at)
                VALUES (:tid, :uid, :tenant, :role, NULL, now())
                ON CONFLICT (tree_id, user_id) DO NOTHING
            """),
            {"tid": row.tree_id, "uid": user_id, "tenant": row.tree_tenant_id, "role": role},
        )
