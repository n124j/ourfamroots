"""Grants tree_members access for a user based on the tenant's global permission groups.

Shared by user registration (AuthService) and admin-created users (POST /admin/users)
so a newly created user immediately sees every tree attached to a group with
is_global=true, at that group's permission level.
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
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    rows = (await session.execute(
        text("""
            SELECT pgt.tree_id, pg.permission_level
            FROM permission_groups pg
            JOIN permission_group_trees pgt ON pgt.group_id = pg.id
            WHERE pg.tenant_id = :tid AND pg.is_global = true
        """),
        {"tid": tenant_id},
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
            {"tid": row.tree_id, "uid": user_id, "tenant": tenant_id, "role": role},
        )
