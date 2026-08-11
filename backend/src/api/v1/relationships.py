"""Non-family-group relationships router — /api/v1/trees/{tree_id}/relationships/*

Models a social role between two people — Godparent, Guardian, Mentor, or a
Custom label — independent of the parent-child/spouse family-group graph
(src/domain/genealogy/validators.py), which stays exclusive/singular: a
person can only ever be a CHILD in one family group, of any parentage_type.
A relationship recorded here coexists freely with that graph (or with
nothing at all) since it's a completely separate table.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from src.api.deps import EditableTreeDep, SessionDep, VerifiedUserDep

router = APIRouter(
    prefix="/trees/{tree_id}/relationships",
    tags=["Relationships"],
)

RELATIONSHIP_TYPES = ("GODPARENT", "GUARDIAN", "MENTOR", "CUSTOM")


# ── Schemas ──────────────────────────────────────────────────────────

class RelationshipResponse(BaseModel):
    id: uuid.UUID
    person1_id: uuid.UUID
    person2_id: uuid.UUID
    relationship_type: str
    custom_label: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


class CreateRelationshipRequest(BaseModel):
    person1_id: uuid.UUID
    person2_id: uuid.UUID
    relationship_type: str
    custom_label: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)


# ── Helpers ──────────────────────────────────────────────────────────

async def _require_editor(session, tree_id: uuid.UUID, user) -> None:
    """Verify *user* holds at least EDITOR on *tree_id*.

    ACTION_MIN_ROLE/is_permitted() (src/domain/collaboration/entities.py)
    already map ADD_RELATIONSHIP/REMOVE_RELATIONSHIP to EDITOR but aren't
    wired into any endpoint yet elsewhere in this codebase — used here
    directly since this is a new resource, rather than replicating every
    other write endpoint's looser EditableTreeDep-only gate (which doesn't
    itself verify tree membership or role floor).
    """
    from src.api.v1._roles import resolve_effective_tree_role
    from src.domain.collaboration.entities import Action, is_permitted

    role = await resolve_effective_tree_role(session, tree_id, user)
    if role is None or not is_permitted(role, Action.ADD_RELATIONSHIP):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Editor role or higher required")


async def _audit(session, tree_id: uuid.UUID, user, action, entity_id=None, after: dict | None = None) -> None:
    from src.domain.collaboration.entities import AuditEntityType, AuditEntry
    from src.infrastructure.repositories.collaboration import AuditLogRepository

    actor_name = f"{user.given_name or ''} {user.family_name or ''}".strip() or user.email
    await AuditLogRepository(session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=user.tenant_id,
            actor_id=user.id,
            actor_display_name=actor_name,
            action=action,
            entity_type=AuditEntityType.RELATIONSHIP,
            entity_id=entity_id,
            after=after,
        )
    )


def _row_to_response(row) -> RelationshipResponse:
    return RelationshipResponse(
        id=row.id,
        person1_id=row.person1_id,
        person2_id=row.person2_id,
        relationship_type=row.relationship_type,
        custom_label=row.custom_label,
        notes=row.notes,
        created_at=row.created_at.isoformat(),
    )


# ── List ─────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[RelationshipResponse],
    summary="List non-family-group relationships in a tree",
)
async def list_relationships(
    tree_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
    person_id: Optional[uuid.UUID] = Query(None, description="Filter to relationships involving this person"),
) -> list[RelationshipResponse]:
    from sqlalchemy import text

    from src.api.v1._roles import resolve_effective_tree_role

    role = await resolve_effective_tree_role(session, tree_id, user)
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this tree")

    query = """
        SELECT id, person1_id, person2_id, relationship_type, custom_label, notes, created_at
        FROM relationships
        WHERE tree_id = :tid
    """
    params: dict = {"tid": tree_id}
    if person_id is not None:
        query += " AND (person1_id = :pid OR person2_id = :pid)"
        params["pid"] = person_id
    query += " ORDER BY created_at"

    rows = (await session.execute(text(query), params)).all()
    return [_row_to_response(r) for r in rows]


# ── Create ───────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a non-family-group relationship",
)
async def create_relationship(
    tree_id: uuid.UUID,
    req: CreateRelationshipRequest,
    user: EditableTreeDep,
    session: SessionDep,
) -> RelationshipResponse:
    from sqlalchemy import text

    from src.api.v1._roles import resolve_tree_tenant_id
    from src.domain.collaboration.entities import Action

    await _require_editor(session, tree_id, user)

    if req.relationship_type not in RELATIONSHIP_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"relationship_type must be one of {RELATIONSHIP_TYPES}")
    if req.person1_id == req.person2_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A person cannot have a relationship with themself")
    custom_label = req.custom_label.strip() if req.custom_label else None
    if req.relationship_type == "CUSTOM" and not custom_label:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "custom_label is required for a CUSTOM relationship")

    tenant_id = await resolve_tree_tenant_id(session, tree_id)

    persons = (await session.execute(
        text("SELECT id FROM persons WHERE tree_id = :tid AND id IN (:p1, :p2) AND is_deleted = false"),
        {"tid": tree_id, "p1": req.person1_id, "p2": req.person2_id},
    )).all()
    if len(persons) != 2:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or both persons were not found in this tree")

    relationship_id = uuid.uuid4()
    try:
        await session.execute(
            text("""
                INSERT INTO relationships
                    (id, tenant_id, tree_id, person1_id, person2_id, relationship_type, custom_label, notes, created_by)
                VALUES
                    (:id, :tenant, :tid, :p1, :p2, :rtype, :label, :notes, :uid)
            """),
            {
                "id": relationship_id, "tenant": tenant_id, "tid": tree_id,
                "p1": req.person1_id, "p2": req.person2_id, "rtype": req.relationship_type,
                "label": custom_label, "notes": req.notes, "uid": user.id,
            },
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This relationship already exists") from None

    await _audit(
        session, tree_id, user, Action.ADD_RELATIONSHIP, entity_id=relationship_id,
        after={"person1_id": str(req.person1_id), "person2_id": str(req.person2_id),
               "relationship_type": req.relationship_type},
    )
    await session.commit()

    row = (await session.execute(
        text("""
            SELECT id, person1_id, person2_id, relationship_type, custom_label, notes, created_at
            FROM relationships WHERE id = :id
        """),
        {"id": relationship_id},
    )).one()
    return _row_to_response(row)


# ── Delete ───────────────────────────────────────────────────────────

@router.delete(
    "/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Delete a relationship",
)
async def delete_relationship(
    tree_id: uuid.UUID,
    relationship_id: uuid.UUID,
    user: EditableTreeDep,
    session: SessionDep,
) -> Response:
    from sqlalchemy import text

    from src.domain.collaboration.entities import Action

    await _require_editor(session, tree_id, user)

    row = (await session.execute(
        text("SELECT id FROM relationships WHERE id = :id AND tree_id = :tid"),
        {"id": relationship_id, "tid": tree_id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found")

    await session.execute(text("DELETE FROM relationships WHERE id = :id"), {"id": relationship_id})
    await _audit(session, tree_id, user, Action.REMOVE_RELATIONSHIP, entity_id=relationship_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
