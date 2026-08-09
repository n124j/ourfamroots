"""Shared tree-role resolution + section-visibility helpers.

resolve_effective_tree_role() folds AppRole overrides (Super Admin => OWNER,
Auditor => VIEWER) into the caller's tree_members role, the same way
GET /trees/{tree_id}/graph does — any endpoint that needs "my role on this
tree" should use this instead of re-deriving it ad hoc.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import SessionDep, VerifiedUserDep
from src.domain.collaboration.entities import AppRole, TreeRole
from src.infrastructure.database.models.user import UserModel

# Registry of sections with a visibility-rule dimension. Only one exists
# today; a future section (Relationships, Gallery, ...) just needs a new
# key here and a check at its call site — no schema change required.
PERSON_MORE_DETAILS_SECTION = "person_more_details"

AVAILABLE_SECTIONS: list[dict[str, str]] = [
    {"key": PERSON_MORE_DETAILS_SECTION, "label": "Person profile — More details (dates & location; Notes is always visible)"},
]


async def resolve_effective_tree_role(
    session: AsyncSession, tree_id: uuid.UUID, user: UserModel
) -> TreeRole | None:
    """Resolve *user*'s effective TreeRole for *tree_id*. Returns None if the
    user isn't a member and holds no AppRole override."""
    from sqlalchemy import text

    if user.app_role == AppRole.AUDITOR:
        return TreeRole.VIEWER
    if user.app_role == AppRole.SUPER_ADMIN:
        return TreeRole.OWNER

    row = (await session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": user.id},
    )).first()
    return TreeRole(row.role) if row is not None else None


async def is_section_visible(
    session: AsyncSession,
    tree_id: uuid.UUID,
    user: UserModel,
    role: TreeRole,
    section_key: str,
) -> bool:
    """Default: OWNER, ADMIN, and EDITOR see the section — only VIEWER is
    hidden by default and needs an explicit visibility override. A direct
    per-user rule takes precedence; otherwise any user-group rule granting
    access applies."""
    if role in (TreeRole.OWNER, TreeRole.ADMIN, TreeRole.EDITOR):
        return True

    from sqlalchemy import text

    user_rule = (await session.execute(
        text("""
            SELECT is_visible FROM section_visibility_rules
            WHERE tree_id = :tid AND section_key = :sk
              AND subject_type = 'USER' AND subject_id = :uid
        """),
        {"tid": tree_id, "sk": section_key, "uid": user.id},
    )).first()
    if user_rule is not None:
        return bool(user_rule.is_visible)

    group_rule = (await session.execute(
        text("""
            SELECT 1
            FROM section_visibility_rules v
            JOIN user_group_members ugm ON ugm.group_id = v.subject_id
            WHERE v.tree_id = :tid AND v.section_key = :sk
              AND v.subject_type = 'USER_GROUP' AND v.is_visible = true
              AND ugm.user_id = :uid
            LIMIT 1
        """),
        {"tid": tree_id, "sk": section_key, "uid": user.id},
    )).first()
    return group_rule is not None


async def require_tree_admin(
    tree_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
) -> UserModel:
    """Restrict endpoint to the tree's ADMIN/OWNER (Super Admin is folded
    into OWNER by resolve_effective_tree_role above)."""
    role = await resolve_effective_tree_role(session, tree_id, user)
    if role is None or role not in (TreeRole.ADMIN, TreeRole.OWNER):
        raise HTTPException(status_code=403, detail="Tree administrator access required")
    return user


TreeAdminDep = Annotated[UserModel, Depends(require_tree_admin)]
