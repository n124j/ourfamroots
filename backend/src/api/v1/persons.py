"""Persons + genealogy relationship router — /api/v1/trees/{tree_id}/persons/*"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from src.api.deps import EditableTreeDep, SessionDep, VerifiedUserDep
from src.application.genealogy.schemas import (
    AddBothParentsRequest,
    AddChildRequest,
    AddParentRequest,
    AddSiblingRequest,
    AddSpouseRequest,
    AncestorsByGenerationResponse,
    CreatePersonRequest,
    KinshipResponse,
    LineagePathResponse,
    PersonDetailResponse,
    PersonResponse,
    UpdatePersonRequest,
)
from src.application.genealogy.service import FamilyTreeApplicationService

router = APIRouter(
    prefix="/trees/{tree_id}/persons",
    tags=["Persons & Relationships"],
)


def _svc(session: SessionDep) -> FamilyTreeApplicationService:
    return FamilyTreeApplicationService(session)


# ── Audit helper ──────────────────────────────────────────────────

async def _audit(
    session,
    tree_id: uuid.UUID,
    user,
    action,
    entity_type,
    entity_id=None,
    entity_name: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    from src.domain.collaboration.entities import Action, AuditEntry, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{user.given_name or ''} {user.family_name or ''}".strip() or user.email
    await AuditLogRepository(session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=user.tenant_id,
            actor_id=user.id,
            actor_display_name=actor_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_display_name=entity_name,
            before=before,
            after=after,
        )
    )


# ── Create person ─────────────────────────────────────────────────

@router.post(
    "",
    response_model=PersonResponse,
    status_code=201,
    summary="Add a new person to the tree",
)
async def create_person(
    tree_id: uuid.UUID,
    req: CreatePersonRequest,
    user: EditableTreeDep,
    session: SessionDep,
) -> PersonResponse:
    from sqlalchemy import text as sa_text
    import uuid as _uuid
    person_id = _uuid.uuid4()
    await session.execute(
        sa_text("""
            INSERT INTO persons (
                id, tenant_id, tree_id, sex, display_given_name, display_surname,
                is_living, is_deceased,
                birth_date, death_date, birth_year, death_year,
                born_city, born_country, died_city, died_country,
                notes
            ) VALUES (
                :id, :tenant_id, :tree_id, :sex, :given, :surname,
                :living, :deceased,
                :birth_date, :death_date, :birth_year, :death_year,
                :born_city, :born_country, :died_city, :died_country,
                :notes
            )
        """),
        {
            "id": person_id,
            "tenant_id": user.tenant_id,
            "tree_id": tree_id,
            "sex": req.sex.value,
            "given": req.given_name,
            "surname": req.surname,
            "living": req.is_living,
            "deceased": req.is_deceased,
            "birth_date": req.birth_date,
            "death_date": req.death_date,
            "birth_year": req.birth_year,
            "death_year": req.death_year,
            "born_city": req.born_city,
            "born_country": req.born_country,
            "died_city": req.died_city,
            "died_country": req.died_country,
            "notes": req.notes,
        },
    )
    from src.domain.collaboration.entities import Action, AuditEntityType
    await _audit(session, tree_id, user, Action.CREATE_PERSON, AuditEntityType.PERSON,
                 entity_id=person_id,
                 entity_name=f"{req.given_name} {req.surname}".strip(),
                 after={"sex": req.sex.value, "is_living": req.is_living})
    await session.commit()
    return PersonResponse(
        id=person_id,
        tree_id=tree_id,
        display_given_name=req.given_name,
        display_surname=req.surname,
        sex=req.sex.value,
        is_living=req.is_living,
        is_deceased=req.is_deceased,
        birth_date=req.birth_date,
        death_date=req.death_date,
        birth_year=req.birth_year,
        death_year=req.death_year,
        born_city=req.born_city,
        born_country=req.born_country,
        died_city=req.died_city,
        died_country=req.died_country,
        notes=req.notes,
    )


# ── Person detail ─────────────────────────────────────────────────

@router.get(
    "/{person_id}",
    response_model=PersonDetailResponse,
    summary="Get a person with their immediate relatives",
)
async def get_person(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
) -> PersonDetailResponse:
    svc = _svc(session)
    return await svc.get_person(tree_id, user.tenant_id, person_id)


# ── Update person ────────────────────────────────────────────────

@router.patch(
    "/{person_id}",
    response_model=PersonResponse,
    summary="Update a person's details",
)
async def update_person(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    req: UpdatePersonRequest,
    user: EditableTreeDep,
    session: SessionDep,
) -> PersonResponse:
    from sqlalchemy import text as sa_text
    from fastapi import HTTPException
    from src.domain.collaboration.entities import Action, AuditEntityType

    # Capture before state
    before_row = (await session.execute(
        sa_text("SELECT display_given_name, display_surname, sex, is_living, is_deceased FROM persons WHERE id=:pid AND is_deleted=false"),
        {"pid": person_id},
    )).first()
    before_snap = {"name": f"{before_row.display_given_name} {before_row.display_surname}".strip(),
                   "sex": before_row.sex, "is_living": before_row.is_living} if before_row else None

    result = await session.execute(
        sa_text("""
            UPDATE persons
            SET display_given_name = :given,
                display_surname    = :surname,
                sex                = :sex,
                is_living          = :living,
                is_deceased        = :deceased,
                photo_url          = COALESCE(:photo_url, photo_url),
                birth_date         = :birth_date,
                death_date         = :death_date,
                birth_year         = :birth_year,
                death_year         = :death_year,
                born_city          = :born_city,
                born_country       = :born_country,
                died_city          = :died_city,
                died_country       = :died_country,
                notes              = :notes
            WHERE id = :pid AND tree_id = :tid AND tenant_id = :tenant AND is_deleted = false
            RETURNING id, tree_id, display_given_name, display_surname, sex,
                      is_living, is_deceased, photo_url,
                      birth_date, death_date, birth_year, death_year,
                      born_city, born_country, died_city, died_country,
                      notes
        """),
        {
            "given":           req.given_name,
            "surname":         req.surname,
            "sex":             req.sex.value,
            "living":          req.is_living,
            "deceased":        req.is_deceased,
            "photo_url":       req.photo_url,
            "birth_date":      req.birth_date,
            "death_date":      req.death_date,
            "birth_year":      req.birth_year,
            "death_year":      req.death_year,
            "born_city":       req.born_city,
            "born_country":    req.born_country,
            "died_city":       req.died_city,
            "died_country":    req.died_country,
            "notes":           req.notes,
            "pid":             person_id,
            "tid":             tree_id,
            "tenant":          user.tenant_id,
        },
    )
    row = result.first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    full_name = f"{row.display_given_name} {row.display_surname}".strip()
    await _audit(session, tree_id, user, Action.UPDATE_PERSON, AuditEntityType.PERSON,
                 entity_id=person_id, entity_name=full_name,
                 before=before_snap,
                 after={"name": full_name, "sex": row.sex, "is_living": row.is_living})
    await session.commit()
    from src.api.v1._s3 import presign_photo
    return PersonResponse(
        id=row.id,
        tree_id=row.tree_id,
        display_given_name=row.display_given_name,
        display_surname=row.display_surname,
        sex=row.sex,
        is_living=row.is_living,
        is_deceased=row.is_deceased,
        photo_url=presign_photo(row.photo_url),
        birth_date=row.birth_date,
        death_date=row.death_date,
        birth_year=row.birth_year,
        death_year=row.death_year,
        born_city=row.born_city,
        born_country=row.born_country,
        died_city=row.died_city,
        died_country=row.died_country,
        notes=row.notes,
    )


# ── Upload profile photo ─────────────────────────────────────────

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/{person_id}/photo",
    summary="Upload a profile photo (server-side S3 upload — no CORS required)",
)
async def upload_person_photo(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    file: UploadFile = File(...),
    user: EditableTreeDep = None,
    session: SessionDep = None,
):
    import boto3
    from botocore.config import Config as BotoCfg
    from sqlalchemy import text as sa_text
    from src.config import get_settings

    settings = get_settings()

    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPEG, PNG, WEBP or GIF images are allowed")

    data = await file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 10 MB limit")

    ext = (file.filename or "photo").rsplit(".", 1)[-1].lower()
    key = f"tenants/{user.tenant_id}/trees/{tree_id}/persons/{person_id}/photo/{uuid.uuid4()}.{ext}"

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.aws_access_key_id or "minioadmin",
        aws_secret_access_key=settings.aws_secret_access_key or "minioadmin",
        region_name=settings.aws_region,
        config=BotoCfg(signature_version="s3v4"),
    )
    bucket = settings.s3_bucket or "ourfamroots-local"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=file.content_type)

    # Persist only the S3 key — presigned URLs are generated at read time
    result = await session.execute(
        sa_text("""
            UPDATE persons SET photo_url = :url
            WHERE id = :pid AND tree_id = :tid AND tenant_id = :tenant AND is_deleted = false
            RETURNING id
        """),
        {"url": key, "pid": person_id, "tid": tree_id, "tenant": user.tenant_id},
    )
    if result.first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    from src.domain.collaboration.entities import Action, AuditEntityType
    await _audit(session, tree_id, user, Action.UPDATE_PHOTO, AuditEntityType.MEDIA,
                 entity_id=person_id, after={"s3_key": key})
    await session.commit()

    from src.api.v1._s3 import presign_photo
    return {"photo_url": presign_photo(key)}


# ── Remove profile photo ──────────────────────────────────────────

@router.delete(
    "/{person_id}/photo",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Remove the profile photo from a person",
)
async def remove_person_photo(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    user: EditableTreeDep,
    session: SessionDep,
):
    from sqlalchemy import text as sa_text

    result = await session.execute(
        sa_text("""
            UPDATE persons SET photo_url = NULL
            WHERE id = :pid AND tree_id = :tid AND tenant_id = :tenant AND is_deleted = false
            RETURNING id
        """),
        {"pid": person_id, "tid": tree_id, "tenant": user.tenant_id},
    )
    if result.first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    from src.domain.collaboration.entities import Action, AuditEntityType
    await _audit(session, tree_id, user, Action.DELETE_MEDIA, AuditEntityType.MEDIA,
                 entity_id=person_id, before={"had_photo": True})
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Gallery photos (up to 3 per person) ─────────────────────────

MAX_GALLERY_PHOTOS = 3


@router.get(
    "/{person_id}/gallery",
    summary="List gallery photos for a person",
)
async def list_gallery_photos(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
):
    from sqlalchemy import text as sa_text
    from src.api.v1._s3 import presign_photo

    rows = (await session.execute(
        sa_text("""
            SELECT id, photo_url, caption, position
            FROM person_gallery_photos
            WHERE person_id = :pid AND tree_id = :tid AND tenant_id = :tenant
            ORDER BY position
        """),
        {"pid": person_id, "tid": tree_id, "tenant": user.tenant_id},
    )).fetchall()

    return [
        {
            "id": str(r.id),
            "photoUrl": presign_photo(r.photo_url),
            "caption": r.caption,
            "position": r.position,
        }
        for r in rows
    ]


@router.post(
    "/{person_id}/gallery",
    status_code=201,
    summary="Upload a gallery photo (max 3 per person)",
)
async def upload_gallery_photo(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    file: UploadFile = File(...),
    caption: str = Query(default="", max_length=200),
    user: EditableTreeDep = None,
    session: SessionDep = None,
):
    import boto3
    from botocore.config import Config as BotoCfg
    from sqlalchemy import text as sa_text
    from src.config import get_settings

    settings = get_settings()

    count_row = (await session.execute(
        sa_text("SELECT count(*) AS cnt FROM person_gallery_photos WHERE person_id = :pid AND tree_id = :tid"),
        {"pid": person_id, "tid": tree_id},
    )).first()
    if count_row.cnt >= MAX_GALLERY_PHOTOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Maximum {MAX_GALLERY_PHOTOS} gallery photos allowed")

    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPEG, PNG, WEBP or GIF images are allowed")

    data = await file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 10 MB limit")

    ext = (file.filename or "photo").rsplit(".", 1)[-1].lower()
    photo_id = uuid.uuid4()
    key = f"tenants/{user.tenant_id}/trees/{tree_id}/persons/{person_id}/gallery/{photo_id}.{ext}"

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.aws_access_key_id or "minioadmin",
        aws_secret_access_key=settings.aws_secret_access_key or "minioadmin",
        region_name=settings.aws_region,
        config=BotoCfg(signature_version="s3v4"),
    )
    bucket = settings.s3_bucket or "ourfamroots-local"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=file.content_type)

    await session.execute(
        sa_text("""
            INSERT INTO person_gallery_photos (id, person_id, tree_id, tenant_id, photo_url, caption, position)
            VALUES (:id, :pid, :tid, :tenant, :url, :caption, :pos)
        """),
        {
            "id": photo_id,
            "pid": person_id,
            "tid": tree_id,
            "tenant": user.tenant_id,
            "url": key,
            "caption": caption.strip() or None,
            "pos": count_row.cnt,
        },
    )
    await session.commit()

    from src.api.v1._s3 import presign_photo
    return {"id": str(photo_id), "photoUrl": presign_photo(key), "caption": caption.strip() or None, "position": count_row.cnt}


@router.patch(
    "/{person_id}/gallery/{photo_id}",
    summary="Update a gallery photo's caption",
)
async def update_gallery_photo(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    photo_id: uuid.UUID,
    user: EditableTreeDep,
    session: SessionDep,
    caption: str = Query(default="", max_length=200),
):
    from sqlalchemy import text as sa_text

    result = await session.execute(
        sa_text("""
            UPDATE person_gallery_photos SET caption = :caption
            WHERE id = :gid AND person_id = :pid AND tree_id = :tid AND tenant_id = :tenant
            RETURNING id
        """),
        {"caption": caption.strip() or None, "gid": photo_id, "pid": person_id, "tid": tree_id, "tenant": user.tenant_id},
    )
    if result.first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gallery photo not found")
    await session.commit()
    return {"ok": True}


@router.delete(
    "/{person_id}/gallery/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Delete a gallery photo",
)
async def delete_gallery_photo(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    photo_id: uuid.UUID,
    user: EditableTreeDep,
    session: SessionDep,
):
    from sqlalchemy import text as sa_text

    result = await session.execute(
        sa_text("""
            DELETE FROM person_gallery_photos
            WHERE id = :gid AND person_id = :pid AND tree_id = :tid AND tenant_id = :tenant
            RETURNING id
        """),
        {"gid": photo_id, "pid": person_id, "tid": tree_id, "tenant": user.tenant_id},
    )
    if result.first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gallery photo not found")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Delete person ────────────────────────────────────────────────

@router.delete(
    "/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete a person from the tree",
)
async def delete_person(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    user: EditableTreeDep,
    session: SessionDep,
) -> None:
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone

    # Grab name before soft-delete
    name_row = (await session.execute(
        sa_text("SELECT display_given_name, display_surname FROM persons WHERE id=:pid AND is_deleted=false"),
        {"pid": person_id},
    )).first()
    person_name = f"{name_row.display_given_name} {name_row.display_surname}".strip() if name_row else None

    await session.execute(
        sa_text("""
            UPDATE persons
            SET is_deleted = true, deleted_at = :now
            WHERE id = :pid AND tree_id = :tid AND tenant_id = :tenant AND is_deleted = false
        """),
        {
            "pid": person_id,
            "tid": tree_id,
            "tenant": user.tenant_id,
            "now": datetime.now(timezone.utc),
        },
    )
    from src.domain.collaboration.entities import Action, AuditEntityType
    await _audit(session, tree_id, user, Action.DELETE_PERSON, AuditEntityType.PERSON,
                 entity_id=person_id, entity_name=person_name,
                 before={"name": person_name})
    await session.commit()


# ── Add parent ────────────────────────────────────────────────────

@router.post(
    "/{person_id}/parents",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Add a parent to a person",
)
async def add_parent(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    req: AddParentRequest,
    user: EditableTreeDep,
    session: SessionDep,
) -> None:
    from src.domain.collaboration.entities import Action, AuditEntityType
    svc = _svc(session)
    await svc.add_parent(tree_id, user.tenant_id, person_id, req)
    await _audit(session, tree_id, user, Action.ADD_RELATIONSHIP, AuditEntityType.PERSON,
                 entity_id=person_id,
                 after={"type": "parent", "parent_id": str(req.parent_id), "parentage": req.parentage_type.value})
    await session.commit()


# ── Add both parents (pair) ──────────────────────────────────────

@router.post(
    "/{person_id}/parents/pair",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Add a father and mother to a person in one atomic operation",
)
async def add_both_parents(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    req: AddBothParentsRequest,
    user: EditableTreeDep,
    session: SessionDep,
) -> None:
    from sqlalchemy import text as sa_text
    from src.domain.collaboration.entities import Action, AuditEntityType

    # Always remove any existing parent-family-group membership for this child
    # so the user's explicit choice of both parents replaces the old ones.
    await session.execute(
        sa_text("""
            DELETE FROM family_group_members
            WHERE person_id = :pid
              AND role = 'CHILD'
              AND family_group_id IN (
                  SELECT id FROM family_groups WHERE tree_id = :tid
              )
        """),
        {"pid": person_id, "tid": tree_id},
    )

    svc = _svc(session)
    await svc.add_both_parents(tree_id, user.tenant_id, person_id, req)
    await _audit(session, tree_id, user, Action.ADD_RELATIONSHIP, AuditEntityType.PERSON,
                 entity_id=person_id,
                 after={"type": "both_parents", "father_id": str(req.father_id), "mother_id": str(req.mother_id)})
    await session.commit()


# ── Add child ─────────────────────────────────────────────────────

@router.post(
    "/{person_id}/children",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Add a child to a person",
)
async def add_child(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    req: AddChildRequest,
    user: EditableTreeDep,
    session: SessionDep,
    force: bool = Query(default=False, description="Remove existing parent group before linking"),
) -> None:
    from sqlalchemy import text as sa_text

    if force:
        # Remove the child's existing parent-family-group membership so the
        # validator in the domain service won't reject the operation.
        await session.execute(
            sa_text("""
                DELETE FROM family_group_members
                WHERE person_id = :pid
                  AND role = 'CHILD'
                  AND family_group_id IN (
                      SELECT id FROM family_groups WHERE tree_id = :tid
                  )
            """),
            {"pid": req.child_id, "tid": tree_id},
        )

    from src.domain.collaboration.entities import Action, AuditEntityType
    svc = _svc(session)
    await svc.add_child(tree_id, user.tenant_id, person_id, req)
    await _audit(session, tree_id, user, Action.ADD_RELATIONSHIP, AuditEntityType.PERSON,
                 entity_id=person_id,
                 after={"type": "child", "child_id": str(req.child_id), "parentage": req.parentage_type.value})
    await session.commit()


# ── Add spouse ────────────────────────────────────────────────────

@router.post(
    "/{person_id}/spouses",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Add a spouse / partner relationship",
)
async def add_spouse(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    req: AddSpouseRequest,
    user: EditableTreeDep,
    session: SessionDep,
) -> None:
    from src.domain.collaboration.entities import Action, AuditEntityType
    svc = _svc(session)
    await svc.add_spouse(tree_id, user.tenant_id, person_id, req)
    await _audit(session, tree_id, user, Action.ADD_RELATIONSHIP, AuditEntityType.PERSON,
                 entity_id=person_id,
                 after={"type": "spouse", "spouse_id": str(req.spouse_id), "union_type": req.union_type.value})
    await session.commit()


# ── Add sibling ───────────────────────────────────────────────────

@router.post(
    "/{person_id}/siblings",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Add a sibling relationship",
)
async def add_sibling(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    req: AddSiblingRequest,
    user: EditableTreeDep,
    session: SessionDep,
) -> None:
    from src.domain.collaboration.entities import Action, AuditEntityType
    svc = _svc(session)
    await svc.add_sibling(tree_id, user.tenant_id, person_id, req)
    await _audit(session, tree_id, user, Action.ADD_RELATIONSHIP, AuditEntityType.PERSON,
                 entity_id=person_id,
                 after={"type": "sibling", "sibling_id": str(req.sibling_id), "parentage": req.parentage_type.value})
    await session.commit()


# ── Relationship queries ──────────────────────────────────────────

@router.get(
    "/{person_id}/ancestor-generations",
    response_model=AncestorsByGenerationResponse,
    summary="Get all ancestors grouped by generation",
)
async def get_ancestors(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
    max_depth: int = Query(default=100, ge=1, le=100),
) -> AncestorsByGenerationResponse:
    svc = _svc(session)
    return await svc.get_ancestors(tree_id, user.tenant_id, person_id, max_depth)


@router.get(
    "/{person_id}/descendant-generations",
    response_model=AncestorsByGenerationResponse,
    summary="Get all descendants grouped by generation",
)
async def get_descendants(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
    max_depth: int = Query(default=100, ge=1, le=100),
) -> AncestorsByGenerationResponse:
    svc = _svc(session)
    return await svc.get_descendants(tree_id, user.tenant_id, person_id, max_depth)


@router.get(
    "/{person_id}/kinship/{other_person_id}",
    response_model=KinshipResponse,
    summary="Calculate the relationship between two persons",
)
async def get_kinship(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    other_person_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
) -> KinshipResponse:
    svc = _svc(session)
    return await svc.get_kinship(tree_id, user.tenant_id, person_id, other_person_id)


@router.get(
    "/{person_id}/lineage-paths/{other_person_id}",
    response_model=list[LineagePathResponse],
    summary="Find all relationship paths between two persons",
)
async def get_lineage_paths(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    other_person_id: uuid.UUID,
    user: VerifiedUserDep,
    session: SessionDep,
) -> list[LineagePathResponse]:
    svc = _svc(session)
    return await svc.get_lineage_paths(
        tree_id, user.tenant_id, person_id, other_person_id
    )
