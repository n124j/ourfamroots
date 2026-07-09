"""Collaboration API — members, invitations, audit log, version history."""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel, EmailStr, Field

from src.api.deps import AdminUserDep, CurrentUserDep, EditableTreeDep, NotAuditorDep, UoWDep
from src.application.collaboration.service import CollaborationService
from src.domain.collaboration.entities import (
    Action, AppRole, AuditEntityType, AuditEntry, Invitation,
    PersonVersion, TreeMembership, TreeRole,
)
from src.domain.collaboration.exceptions import (
    AlreadyMemberError, CannotDowngradeOwnerError, CannotRemoveOwnerError,
    InsufficientPermissionError, InvitationAlreadyUsedError,
    InvitationExpiredError, InvitationNotFoundError,
)

router = APIRouter(tags=["collaboration"])


# ── Dependency ─────────────────────────────────────────────────────────────────

async def get_collaboration_service(uow: UoWDep) -> CollaborationService:
    return CollaborationService(uow._session)

CollabDep = Annotated[CollaborationService, Depends(get_collaboration_service)]


# ── Schemas ────────────────────────────────────────────────────────────────────

class MemberResponse(BaseModel):
    id: uuid.UUID
    tree_id: uuid.UUID
    user_id: uuid.UUID
    role: TreeRole
    joined_at: Optional[str]
    email: str = ""
    display_name: str = ""

    @classmethod
    def from_domain(cls, m: TreeMembership) -> "MemberResponse":
        return cls(
            id=m.id,
            tree_id=m.tree_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at.isoformat() if m.joined_at else None,
        )


class ChangeRoleRequest(BaseModel):
    role: TreeRole


class InviteRequest(BaseModel):
    email: EmailStr
    role: TreeRole = TreeRole.VIEWER
    message: Optional[str] = Field(None, max_length=500)


class InvitationResponse(BaseModel):
    id: uuid.UUID
    tree_id: uuid.UUID
    invitee_email: str
    role: TreeRole
    status: str
    expires_at: str
    created_at: str

    @classmethod
    def from_domain(cls, i: Invitation) -> "InvitationResponse":
        return cls(
            id=i.id,
            tree_id=i.tree_id,
            invitee_email=i.invitee_email,
            role=i.role,
            status=i.status.value,
            expires_at=i.expires_at.isoformat(),
            created_at=i.created_at.isoformat(),
        )


class AcceptInvitationRequest(BaseModel):
    token: str


class AuditEntryResponse(BaseModel):
    id: uuid.UUID
    actor_display_name: str
    action: str
    entity_type: str
    entity_id: Optional[uuid.UUID]
    entity_display_name: Optional[str]
    before: Optional[dict]
    after: Optional[dict]
    occurred_at: str

    @classmethod
    def from_domain(cls, e: AuditEntry) -> "AuditEntryResponse":
        return cls(
            id=e.id,
            actor_display_name=e.actor_display_name,
            action=e.action.value,
            entity_type=e.entity_type.value,
            entity_id=e.entity_id,
            entity_display_name=e.entity_display_name,
            before=e.before,
            after=e.after,
            occurred_at=e.occurred_at.isoformat(),
        )


class PersonVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    change_summary: str
    created_by_id: uuid.UUID
    created_at: str
    snapshot: dict

    @classmethod
    def from_domain(cls, v: PersonVersion) -> "PersonVersionResponse":
        return cls(
            id=v.id,
            version_number=v.version_number,
            change_summary=v.change_summary,
            created_by_id=v.created_by_id,
            created_at=v.created_at.isoformat(),
            snapshot=v.snapshot,
        )


# ── Tree listing ───────────────────────────────────────────────────────────────

class TreeSummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    cover_emoji: Optional[str] = None
    cover_image_url: Optional[str] = None
    role: TreeRole
    person_count: int
    member_count: int
    link_sharing: str = "RESTRICTED"
    share_token: Optional[uuid.UUID] = None
    is_pinned: bool = False
    is_searchable: bool = False
    is_globally_shared: bool = False


class CreateTreeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


@router.post("/trees", response_model=TreeSummaryResponse, status_code=status.HTTP_201_CREATED, summary="Create a new family tree")
async def create_tree(
    body: CreateTreeRequest,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> TreeSummaryResponse:
    from sqlalchemy import text

    tree_id = uuid.uuid4()
    share_token = uuid.uuid4()

    await uow._session.execute(text("""
        INSERT INTO family_trees (id, tenant_id, name, description, share_token)
        VALUES (:id, :tenant_id, :name, :description, :share_token)
    """), {"id": tree_id, "tenant_id": current_user.tenant_id, "name": body.name, "description": body.description, "share_token": share_token})

    await uow._session.execute(text("""
        INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
        VALUES (:id, :tree_id, :user_id, :tenant_id, 'OWNER', NOW())
    """), {"id": uuid.uuid4(), "tree_id": tree_id, "user_id": current_user.id, "tenant_id": current_user.tenant_id})

    return TreeSummaryResponse(
        id=tree_id,
        name=body.name,
        description=body.description,
        role=TreeRole.OWNER,
        person_count=0,
        member_count=1,
        link_sharing="RESTRICTED",
        share_token=share_token,
    )


@router.delete(
    "/trees/{tree_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete a tree (owner only, or Super Admin for any tree)",
)
async def delete_tree(
    tree_id: uuid.UUID,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> None:
    from sqlalchemy import text

    # Super Admin can delete any tree in the tenant, matching the "Owner" badge
    # already shown to them on every tree in the dashboard's elevated list view.
    if current_user.app_role != AppRole.SUPER_ADMIN:
        row = (await uow._session.execute(
            text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
            {"tid": tree_id, "uid": current_user.id},
        )).first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
        if row.role != "OWNER":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the tree owner can delete this tree")

    # Grab name before soft-delete for the audit record; also serves as the
    # real existence check for the Super Admin path above, which skips the
    # tree_members lookup that would otherwise catch a bad/already-deleted id.
    tree_row = (await uow._session.execute(
        text("SELECT name FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()
    if tree_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    tree_name = tree_row.name

    await uow._session.execute(
        text("UPDATE family_trees SET is_deleted = true WHERE id = :tid"),
        {"tid": tree_id},
    )

    from src.domain.collaboration.entities import AuditEntry, Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.DELETE_TREE,
            entity_type=AuditEntityType.TREE,
            entity_id=tree_id,
            entity_display_name=tree_name,
        )
    )
    await uow._session.commit()


class UpdateTreeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    cover_emoji: Optional[str] = Field(None, max_length=10)


@router.patch(
    "/trees/{tree_id}",
    response_model=TreeSummaryResponse,
    summary="Update a tree's name and description (admin or owner)",
)
async def update_tree(
    tree_id: uuid.UUID,
    body: UpdateTreeRequest,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> TreeSummaryResponse:
    from sqlalchemy import text

    # Require ADMIN or OWNER tree role
    member_row = (await uow._session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if member_row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can edit this tree")

    result = await uow._session.execute(
        text("""
            UPDATE family_trees
            SET name = :name, description = :description,
                cover_emoji = COALESCE(:cover_emoji, cover_emoji)
            WHERE id = :tid AND is_deleted = false
            RETURNING id, name, description, cover_emoji, cover_image_url, link_sharing, share_token
        """),
        {"tid": tree_id, "name": body.name, "description": body.description,
         "cover_emoji": body.cover_emoji},
    )
    row = result.first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")

    counts = (await uow._session.execute(
        text("""
            SELECT
              (SELECT COUNT(*) FROM persons WHERE tree_id = :tid AND is_deleted = false) AS person_count,
              (SELECT COUNT(*) FROM tree_members WHERE tree_id = :tid) AS member_count
        """),
        {"tid": tree_id},
    )).first()

    effective_role = TreeRole(member_row.role)

    from src.domain.collaboration.entities import AuditEntry, Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.UPDATE_TREE,
            entity_type=AuditEntityType.TREE,
            entity_id=tree_id,
            entity_display_name=row.name,
            after={"name": body.name, "description": body.description},
        )
    )
    await uow._session.commit()
    return TreeSummaryResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        cover_emoji=row.cover_emoji,
        cover_image_url=row.cover_image_url,
        role=effective_role,
        person_count=counts.person_count if counts else 0,
        member_count=counts.member_count if counts else 0,
        link_sharing=row.link_sharing or "RESTRICTED",
        share_token=row.share_token,
    )


_TREE_PHOTO_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_TREE_PHOTO_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/trees/{tree_id}/photo", summary="Upload a cover photo for a tree")
async def upload_tree_photo(
    tree_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: NotAuditorDep = None,
    uow: UoWDep = None,
) -> dict:
    import boto3
    from botocore.config import Config as BotoCfg
    from sqlalchemy import text
    from src.config import get_settings

    row = (await uow._session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can update this tree")

    if file.content_type not in _TREE_PHOTO_ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPEG, PNG, WEBP or GIF images are allowed")

    data = await file.read()
    if len(data) > _TREE_PHOTO_MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 10 MB limit")

    settings = get_settings()
    ext = (file.filename or "photo").rsplit(".", 1)[-1].lower()
    key = f"tenants/{current_user.tenant_id}/trees/{tree_id}/cover/{uuid.uuid4()}.{ext}"

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

    public_base = (settings.s3_public_url or settings.s3_endpoint_url or "").rstrip("/")
    photo_url = f"{public_base}/{bucket}/{key}" if public_base else f"/{bucket}/{key}"

    result = await uow._session.execute(
        text("""
            UPDATE family_trees SET cover_image_url = :url
            WHERE id = :tid AND tenant_id = :tenant AND is_deleted = false
            RETURNING id
        """),
        {"url": photo_url, "tid": tree_id, "tenant": current_user.tenant_id},
    )
    if result.first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")

    await uow._session.commit()
    return {"cover_image_url": photo_url}


@router.delete(
    "/trees/{tree_id}/photo",
    status_code=204,
    response_model=None,
    response_class=Response,
    summary="Remove a tree's cover photo",
)
async def delete_tree_photo(
    tree_id: uuid.UUID,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> None:
    from sqlalchemy import text

    row = (await uow._session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can update this tree")

    await uow._session.execute(
        text("UPDATE family_trees SET cover_image_url = NULL WHERE id = :tid AND tenant_id = :tenant AND is_deleted = false"),
        {"tid": tree_id, "tenant": current_user.tenant_id},
    )
    await uow._session.commit()


# ── Link sharing ───────────────────────────────────────────────────────────────

class UpdateLinkSharingRequest(BaseModel):
    link_sharing: str = Field(..., pattern="^(RESTRICTED|ANYONE)$")


@router.patch(
    "/trees/{tree_id}/link-sharing",
    response_model=TreeSummaryResponse,
    summary="Update public link-sharing setting (OWNER or ADMIN only)",
)
async def update_link_sharing(
    tree_id: uuid.UUID,
    body: UpdateLinkSharingRequest,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> TreeSummaryResponse:
    from sqlalchemy import text

    member_row = (await uow._session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if member_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if member_row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can change link sharing")

    result = await uow._session.execute(
        text("""
            UPDATE family_trees
            SET link_sharing = :link_sharing
            WHERE id = :tid AND is_deleted = false
            RETURNING id, name, description, cover_emoji, cover_image_url, link_sharing, share_token
        """),
        {"tid": tree_id, "link_sharing": body.link_sharing},
    )
    row = result.first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")

    counts = (await uow._session.execute(
        text("""
            SELECT
              (SELECT COUNT(*) FROM persons WHERE tree_id = :tid AND is_deleted = false) AS person_count,
              (SELECT COUNT(*) FROM tree_members WHERE tree_id = :tid) AS member_count
        """),
        {"tid": tree_id},
    )).first()

    effective_role = TreeRole(member_row.role)

    await uow._session.commit()
    return TreeSummaryResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        cover_emoji=row.cover_emoji,
        cover_image_url=row.cover_image_url,
        role=effective_role,
        person_count=counts.person_count if counts else 0,
        member_count=counts.member_count if counts else 0,
        link_sharing=row.link_sharing,
        share_token=row.share_token,
    )


@router.get(
    "/trees/shared/{share_token}/graph",
    summary="Public read-only tree graph — accessible without authentication when link_sharing is ANYONE",
)
async def get_shared_tree_graph(
    share_token: uuid.UUID,
    uow: UoWDep,
) -> dict:
    from sqlalchemy import text

    tree_row = (await uow._session.execute(
        text("SELECT id, name, description, link_sharing FROM family_trees WHERE share_token = :token AND is_deleted = false LIMIT 1"),
        {"token": share_token},
    )).first()

    if tree_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if tree_row.link_sharing != "ANYONE":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This tree is not publicly shared")

    tree_id = tree_row.id

    persons_q = text("""
        SELECT id, tree_id, display_given_name, display_surname,
               sex, is_living, is_deceased, photo_url,
               birth_date, death_date, birth_year, death_year,
               born_city, born_country, died_city, died_country,
               notes
        FROM persons
        WHERE tree_id = :tid AND is_deleted = false
        ORDER BY display_surname, display_given_name
    """)
    person_rows = (await uow._session.execute(persons_q, {"tid": tree_id})).fetchall()

    from src.api.v1._s3 import presign_photo as _presign_photo
    persons = [
        {
            "id": str(r.id),
            "treeId": str(r.tree_id),
            "displayGivenName": r.display_given_name,
            "displaySurname": r.display_surname,
            "sex": r.sex,
            "isLiving": r.is_living,
            "isDeceased": r.is_deceased,
            **({"photoUrl": _presign_photo(r.photo_url)} if r.photo_url else {}),
            **({"birthDate": r.birth_date.isoformat()} if r.birth_date else {}),
            **({"deathDate": r.death_date.isoformat()} if r.death_date else {}),
            **({"birthYear": r.birth_year} if r.birth_year is not None else {}),
            **({"deathYear": r.death_year} if r.death_year is not None else {}),
            **({"bornCity": r.born_city} if r.born_city else {}),
            **({"bornCountry": r.born_country} if r.born_country else {}),
            **({"diedCity": r.died_city} if r.died_city else {}),
            **({"diedCountry": r.died_country} if r.died_country else {}),
            **({"notes": r.notes} if r.notes else {}),
        }
        for r in person_rows
    ]

    fg_q = text("""
        SELECT fg.id, fg.tree_id, fg.union_type, fg.custom_label, fg.is_divorced,
               fg.union_date, fg.union_date_year, fg.union_end_date, fg.union_end_date_year,
               fgm.person_id, fgm.role, fgm.parentage_type
        FROM family_groups fg
        LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
        LEFT JOIN persons p ON p.id = fgm.person_id
        WHERE fg.tree_id = :tid
          AND (fgm.person_id IS NULL OR p.is_deleted = false)
        ORDER BY fg.id
    """)
    fg_rows = (await uow._session.execute(fg_q, {"tid": tree_id})).fetchall()

    groups: dict[str, dict] = {}
    for r in fg_rows:
        gid = str(r.id)
        if gid not in groups:
            groups[gid] = {
                "id": gid,
                "treeId": str(r.tree_id),
                "unionType": r.union_type,
                **({"customLabel": r.custom_label} if r.custom_label else {}),
                **({"isDivorced": True} if r.is_divorced else {}),
                **({"unionDate": r.union_date.isoformat()} if r.union_date else {}),
                **({"unionDateYear": r.union_date_year} if r.union_date_year is not None else {}),
                **({"unionEndDate": r.union_end_date.isoformat()} if r.union_end_date else {}),
                **({"unionEndDateYear": r.union_end_date_year} if r.union_end_date_year is not None else {}),
                "parentIds": [],
                "children": {},
            }
        if r.person_id is None:
            continue
        pid = str(r.person_id)
        if r.role == "PARENT":
            if pid not in groups[gid]["parentIds"]:
                groups[gid]["parentIds"].append(pid)
        elif r.role == "CHILD":
            groups[gid]["children"][pid] = r.parentage_type or "BIOLOGICAL"

    return {
        "treeId":          str(tree_id),
        "treeName":        tree_row.name,
        "treeDescription": tree_row.description,
        "userRole":        "VIEWER",
        "persons":         persons,
        "familyGroups":    list(groups.values()),
    }


@router.get(
    "/trees/shared/{share_token}/og-preview",
    summary="Server-rendered HTML with per-tree Open Graph tags, for social-media link-preview crawlers",
    response_class=Response,
)
async def get_shared_tree_og_preview(
    share_token: uuid.UUID,
    uow: UoWDep,
) -> Response:
    """
    Facebook/Twitter/WhatsApp/etc. crawlers do not execute JavaScript, so the
    client-side <SEO> tags set by SharedTreePage are invisible to them — they
    only ever see whatever is in the raw HTML response. The reverse proxy
    routes known crawler user-agents for /shared/{token} to this endpoint
    instead of the SPA so the preview shows the tree's own title/description.
    """
    import html as html_lib
    from sqlalchemy import text

    from src.config import get_settings

    settings = get_settings()
    base_url = settings.frontend_base_url.rstrip("/")
    share_url = f"{base_url}/shared/{share_token}"
    default_image = f"{base_url}/og-image-tree.svg"

    tree_row = (await uow._session.execute(
        text("""
            SELECT id, name, description, cover_image_url, link_sharing
            FROM family_trees WHERE share_token = :token AND is_deleted = false LIMIT 1
        """),
        {"token": share_token},
    )).first()

    if tree_row is None or tree_row.link_sharing != "ANYONE":
        title = "OurFamRoots"
        description = (
            "Free collaborative genealogy platform to build your family tree online."
        )
        og_image = default_image
    else:
        title = tree_row.name
        counts = (await uow._session.execute(
            text("""
                SELECT
                  (SELECT COUNT(*) FROM persons WHERE tree_id = :tid AND is_deleted = false) AS person_count,
                  (SELECT COUNT(*) FROM tree_members WHERE tree_id = :tid) AS member_count
            """),
            {"tid": tree_row.id},
        )).first()
        stats = f"{counts.person_count} people · {counts.member_count} members" if counts else None
        base_description = tree_row.description or (
            f"Explore the {tree_row.name} family tree on OurFamRoots. "
            "View ancestors, descendants, and family connections."
        )
        description = f"{base_description} · {stats}" if stats else base_description
        og_image = tree_row.cover_image_url or default_image

    title_esc = html_lib.escape(title)
    desc_esc = html_lib.escape(description)
    url_esc = html_lib.escape(share_url)
    image_esc = html_lib.escape(og_image)
    image_dims = (
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">'
        if og_image == default_image else ""
    )

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title_esc}</title>
<meta name="description" content="{desc_esc}">
<meta property="og:site_name" content="OurFamRoots">
<meta property="og:type" content="website">
<meta property="og:title" content="{title_esc}">
<meta property="og:description" content="{desc_esc}">
<meta property="og:url" content="{url_esc}">
<meta property="og:image" content="{image_esc}">
{image_dims}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title_esc}">
<meta name="twitter:description" content="{desc_esc}">
<meta name="twitter:image" content="{image_esc}">
</head>
<body>{title_esc}</body>
</html>"""

    return Response(content=body, media_type="text/html; charset=utf-8")


@router.get(
    "/trees/{tree_id}/export-zip",
    summary="Export tree as a ZIP archive containing the .frt backup and all member photos",
)
async def export_tree_zip(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> Response:
    import io
    import json
    import zipfile
    from fastapi.responses import StreamingResponse
    from sqlalchemy import text

    # Auditor + Super Admin bypass; all others (including app-level ADMIN) must be members
    if current_user.app_role not in (AppRole.AUDITOR, AppRole.SUPER_ADMIN):
        row = (await uow._session.execute(
            text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
            {"tid": tree_id, "uid": current_user.id},
        )).first()
        if row is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this tree")

    # Fetch tree metadata
    tree_row = (await uow._session.execute(
        text("SELECT name, description, cover_image_url FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()
    if tree_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")

    # Fetch all persons with all fields
    person_rows = (await uow._session.execute(text("""
        SELECT id, display_given_name, display_surname, sex, is_living, is_deceased, photo_url,
               birth_date, death_date, birth_year, death_year,
               born_city, born_country, died_city, died_country,
               notes
        FROM persons
        WHERE tree_id = :tid AND is_deleted = false
        ORDER BY display_surname, display_given_name
    """), {"tid": tree_id})).fetchall()

    # Fetch family groups + members
    fg_rows = (await uow._session.execute(text("""
        SELECT fg.id, fg.union_type, fg.custom_label, fg.is_divorced,
               fg.union_date, fg.union_date_year, fg.union_end_date, fg.union_end_date_year,
               fgm.person_id, fgm.role, fgm.parentage_type
        FROM family_groups fg
        LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
        WHERE fg.tree_id = :tid
    """), {"tid": tree_id})).fetchall()

    # Build family_groups dict
    fgs: dict[str, dict] = {}
    for r in fg_rows:
        fgid = str(r.id)
        if fgid not in fgs:
            fgs[fgid] = {
                "id": fgid,
                "union_type": r.union_type,
                **({"custom_label": r.custom_label} if r.custom_label else {}),
                **({"is_divorced": True} if r.is_divorced else {}),
                **({"union_date": r.union_date.isoformat()} if r.union_date else {}),
                **({"union_date_year": r.union_date_year} if r.union_date_year is not None else {}),
                **({"union_end_date": r.union_end_date.isoformat()} if r.union_end_date else {}),
                **({"union_end_date_year": r.union_end_date_year} if r.union_end_date_year is not None else {}),
                "parent_ids": [],
                "children": {},
            }
        if r.person_id is None:
            continue
        pid = str(r.person_id)
        if r.role == "PARENT":
            if pid not in fgs[fgid]["parent_ids"]:
                fgs[fgid]["parent_ids"].append(pid)
        elif r.role == "CHILD":
            fgs[fgid]["children"][pid] = r.parentage_type or "BIOLOGICAL"

    # Resolve S3 keys from photo_url
    from src.config import get_settings
    settings = get_settings()
    bucket = settings.s3_bucket or "ourfamroots-local"
    public_base = (settings.s3_public_url or settings.s3_endpoint_url or "").rstrip("/")
    url_prefix = f"{public_base}/{bucket}/" if public_base else f"/{bucket}/"

    def _resolve_s3_key(url: str) -> str:
        if url.startswith(url_prefix):
            return url[len(url_prefix):]
        if url.startswith("/"):
            return url.lstrip("/")
        return url  # bare S3 key (e.g. from import-zip)

    # Build persons list; track which need photos downloaded
    persons_payload = []
    photo_downloads: list[tuple[str, str, str]] = []  # (person_id, s3_key, filename_in_zip)

    # Tree profile (cover) picture
    tree_cover_filename = None
    if tree_row.cover_image_url:
        s3_key = _resolve_s3_key(tree_row.cover_image_url)
        if s3_key:
            ext = s3_key.rsplit(".", 1)[-1] if "." in s3_key else "jpg"
            tree_cover_filename = f"tree_cover.{ext}"
            photo_downloads.append(("tree", s3_key, tree_cover_filename))

    def _safe_slug(val):
        import re
        return re.sub(r'[^\w]', '_', (val or '').strip())[:40]

    for r in person_rows:
        photo_filename = None
        if r.photo_url:
            s3_key = _resolve_s3_key(r.photo_url)
            if s3_key:
                ext = s3_key.rsplit(".", 1)[-1] if "." in s3_key else "jpg"
                name_slug = f"{_safe_slug(r.display_given_name)}_{_safe_slug(r.display_surname)}"
                photo_filename = f"photos/{name_slug}_{r.id}.{ext}"
                photo_downloads.append((str(r.id), s3_key, photo_filename))

        person_entry = {
            "id": str(r.id),
            "display_given_name": r.display_given_name or "",
            "display_surname": r.display_surname or "",
            "sex": r.sex or "UNKNOWN",
            "is_living": r.is_living,
            "is_deceased": r.is_deceased,
            **({"photo_filename": photo_filename} if photo_filename else {}),
            **({"birth_date": r.birth_date.isoformat()} if r.birth_date else {}),
            **({"death_date": r.death_date.isoformat()} if r.death_date else {}),
            **({"birth_year": r.birth_year} if r.birth_year is not None else {}),
            **({"death_year": r.death_year} if r.death_year is not None else {}),
            **({"born_city": r.born_city} if r.born_city else {}),
            **({"born_country": r.born_country} if r.born_country else {}),
            **({"died_city": r.died_city} if r.died_city else {}),
            **({"died_country": r.died_country} if r.died_country else {}),
            **({"notes": r.notes} if r.notes else {}),
        }
        persons_payload.append(person_entry)

    # Fetch gallery photos for all persons in this tree
    gallery_rows = (await uow._session.execute(text("""
        SELECT id, person_id, photo_url, caption, position
        FROM person_gallery_photos
        WHERE tree_id = :tid AND tenant_id = :tenant
        ORDER BY person_id, position
    """), {"tid": tree_id, "tenant": current_user.tenant_id})).fetchall()

    gallery_by_person: dict[str, list[dict]] = {}
    for gr in gallery_rows:
        pid = str(gr.person_id)
        if pid not in gallery_by_person:
            gallery_by_person[pid] = []
        s3_key = gr.photo_url
        ext = s3_key.rsplit(".", 1)[-1] if "." in s3_key else "jpg"
        gal_filename = f"gallery/{pid}_{gr.position}.{ext}"
        photo_downloads.append((pid, s3_key, gal_filename))
        gallery_by_person[pid].append({
            "photo_filename": gal_filename,
            **({"caption": gr.caption} if gr.caption else {}),
            "position": gr.position,
        })

    for pe in persons_payload:
        gal = gallery_by_person.get(pe["id"])
        if gal:
            pe["gallery_photos"] = gal

    frt_payload = {
        "frt_version": "1.1",
        "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "tree_name": tree_row.name,
        "tree_description": tree_row.description,
        **({"tree_cover_photo_filename": tree_cover_filename} if tree_cover_filename else {}),
        "persons": persons_payload,
        "family_groups": list(fgs.values()),
    }

    # Build ZIP in memory
    import boto3
    from botocore.config import Config as BotoCfg

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write .frt JSON
        tree_slug = tree_row.name.replace(" ", "_")[:50]
        zf.writestr(f"{tree_slug}.frt", json.dumps(frt_payload, indent=2))

        # Download and write each photo
        if photo_downloads:
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url or None,
                aws_access_key_id=settings.aws_access_key_id or "minioadmin",
                aws_secret_access_key=settings.aws_secret_access_key or "minioadmin",
                region_name=settings.aws_region,
                config=BotoCfg(signature_version="s3v4"),
            )
            for _person_id, s3_key, zip_path in photo_downloads:
                try:
                    obj = s3.get_object(Bucket=bucket, Key=s3_key)
                    zf.writestr(zip_path, obj["Body"].read())
                except Exception:
                    pass  # skip missing photos silently

    zip_buffer.seek(0)

    safe_name = tree_row.name.replace(" ", "_")[:60]
    return StreamingResponse(
        iter([zip_buffer.read()]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


@router.delete(
    "/trees/{tree_id}/family-groups/{family_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Remove a union (family group) and all its member links",
)
async def delete_family_group(
    tree_id: uuid.UUID,
    family_group_id: uuid.UUID,
    current_user: EditableTreeDep,
    uow: UoWDep,
) -> None:
    from sqlalchemy import text
    from src.domain.collaboration.entities import Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository

    # Verify it belongs to this tree
    row = (await uow._session.execute(
        text("SELECT id FROM family_groups WHERE id = :fgid AND tree_id = :tid LIMIT 1"),
        {"fgid": family_group_id, "tid": tree_id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family group not found")

    # Remove all member links then the group itself
    await uow._session.execute(
        text("DELETE FROM family_group_members WHERE family_group_id = :fgid"),
        {"fgid": family_group_id},
    )
    await uow._session.execute(
        text("DELETE FROM family_groups WHERE id = :fgid"),
        {"fgid": family_group_id},
    )

    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.REMOVE_RELATIONSHIP,
            entity_type=AuditEntityType.FAMILY_GROUP,
            entity_id=family_group_id,
        )
    )
    await uow._session.commit()


class UpdateFamilyGroupRequest(BaseModel):
    custom_label: Optional[str] = Field(None, max_length=200)
    is_divorced: Optional[bool] = None
    union_type: Optional[str] = None
    union_date: Optional[str] = None
    union_date_year: Optional[int] = Field(None, ge=1, le=9999)
    union_end_date: Optional[str] = None
    union_end_date_year: Optional[int] = Field(None, ge=1, le=9999)


@router.patch(
    "/trees/{tree_id}/family-groups/{family_group_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a family group's custom label",
)
async def update_family_group(
    tree_id: uuid.UUID,
    family_group_id: uuid.UUID,
    body: UpdateFamilyGroupRequest,
    current_user: EditableTreeDep,
    uow: UoWDep,
) -> dict:
    from sqlalchemy import text
    from src.domain.collaboration.entities import Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository

    row = (await uow._session.execute(
        text("SELECT id FROM family_groups WHERE id = :fgid AND tree_id = :tid LIMIT 1"),
        {"fgid": family_group_id, "tid": tree_id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family group not found")

    updates: list[str] = []
    params: dict = {"fgid": family_group_id}
    audit_after: dict = {}

    if body.custom_label is not None or body.custom_label is None and "custom_label" in (body.model_fields_set or set()):
        label = body.custom_label.strip() if body.custom_label else None
        updates.append("custom_label = :label")
        params["label"] = label
        audit_after["custom_label"] = label

    if body.is_divorced is not None:
        updates.append("is_divorced = :divorced")
        params["divorced"] = body.is_divorced
        audit_after["is_divorced"] = body.is_divorced

    if body.union_type is not None:
        allowed = {"MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN"}
        if body.union_type not in allowed:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid union_type: {body.union_type}")
        updates.append("union_type = :utype")
        params["utype"] = body.union_type
        audit_after["union_type"] = body.union_type

    if body.union_date is not None or "union_date" in (body.model_fields_set or set()):
        from datetime import date as _date
        val = None
        if body.union_date:
            try:
                val = _date.fromisoformat(body.union_date)
            except ValueError:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid union_date format (expected YYYY-MM-DD)")
        updates.append("union_date = :udate")
        params["udate"] = val
        audit_after["union_date"] = body.union_date

    if body.union_date_year is not None or "union_date_year" in (body.model_fields_set or set()):
        updates.append("union_date_year = :udate_year")
        params["udate_year"] = body.union_date_year
        audit_after["union_date_year"] = body.union_date_year

    if body.union_end_date is not None or "union_end_date" in (body.model_fields_set or set()):
        from datetime import date as _date
        val = None
        if body.union_end_date:
            try:
                val = _date.fromisoformat(body.union_end_date)
            except ValueError:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid union_end_date format (expected YYYY-MM-DD)")
        updates.append("union_end_date = :uedate")
        params["uedate"] = val
        audit_after["union_end_date"] = body.union_end_date

    if body.union_end_date_year is not None or "union_end_date_year" in (body.model_fields_set or set()):
        updates.append("union_end_date_year = :uedate_year")
        params["uedate_year"] = body.union_end_date_year
        audit_after["union_end_date_year"] = body.union_end_date_year

    if updates:
        await uow._session.execute(
            text(f"UPDATE family_groups SET {', '.join(updates)} WHERE id = :fgid"),
            params,
        )

    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.UPDATE_RELATIONSHIP,
            entity_type=AuditEntityType.FAMILY_GROUP,
            entity_id=family_group_id,
            after=audit_after,
        )
    )
    await uow._session.commit()
    return {"family_group_id": str(family_group_id), **audit_after}


@router.delete(
    "/trees/{tree_id}/family-groups/{family_group_id}/members/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Remove a single person from a family group (parent or child link)",
)
async def remove_family_group_member(
    tree_id: uuid.UUID,
    family_group_id: uuid.UUID,
    person_id: uuid.UUID,
    current_user: EditableTreeDep,
    uow: UoWDep,
) -> None:
    from sqlalchemy import text
    from src.domain.collaboration.entities import Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository

    # Verify family group belongs to this tree
    row = (await uow._session.execute(
        text("SELECT id FROM family_groups WHERE id = :fgid AND tree_id = :tid LIMIT 1"),
        {"fgid": family_group_id, "tid": tree_id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family group not found")

    # Delete this person's membership row
    await uow._session.execute(
        text("DELETE FROM family_group_members WHERE family_group_id = :fgid AND person_id = :pid"),
        {"fgid": family_group_id, "pid": person_id},
    )

    # If no PARENT members remain, the family group is orphaned — delete it entirely
    parent_count = (await uow._session.execute(
        text("SELECT COUNT(*) FROM family_group_members WHERE family_group_id = :fgid AND role = 'PARENT'"),
        {"fgid": family_group_id},
    )).scalar_one()
    if parent_count == 0:
        await uow._session.execute(
            text("DELETE FROM family_group_members WHERE family_group_id = :fgid"),
            {"fgid": family_group_id},
        )
        await uow._session.execute(
            text("DELETE FROM family_groups WHERE id = :fgid"),
            {"fgid": family_group_id},
        )

    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.REMOVE_RELATIONSHIP,
            entity_type=AuditEntityType.FAMILY_GROUP,
            entity_id=family_group_id,
        )
    )
    await uow._session.commit()


class UpdateMemberParentageRequest(BaseModel):
    parentage_type: str = Field(..., pattern=r"^(BIOLOGICAL|ADOPTIVE|STEP|FOSTER|UNKNOWN)$")


@router.patch(
    "/trees/{tree_id}/family-groups/{family_group_id}/members/{person_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a child member's parentage type (e.g. mark as adopted)",
)
async def update_family_group_member(
    tree_id: uuid.UUID,
    family_group_id: uuid.UUID,
    person_id: uuid.UUID,
    body: UpdateMemberParentageRequest,
    current_user: EditableTreeDep,
    uow: UoWDep,
) -> dict:
    from sqlalchemy import text
    from src.domain.collaboration.entities import Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository

    row = (await uow._session.execute(
        text("""SELECT fgm.id, fgm.role FROM family_group_members fgm
                JOIN family_groups fg ON fg.id = fgm.family_group_id
                WHERE fgm.family_group_id = :fgid AND fgm.person_id = :pid AND fg.tree_id = :tid
                LIMIT 1"""),
        {"fgid": family_group_id, "pid": person_id, "tid": tree_id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found in family group")

    if body.parentage_type == "BIOLOGICAL":
        parent_rows = (await uow._session.execute(
            text("""SELECT p.sex FROM family_group_members fgm
                    JOIN persons p ON p.id = fgm.person_id
                    WHERE fgm.family_group_id = :fgid AND fgm.role = 'PARENT'"""),
            {"fgid": family_group_id},
        )).fetchall()
        sexes = [r.sex for r in parent_rows if r.sex not in ("UNKNOWN", "OTHER")]
        if len(sexes) >= 2 and len(set(sexes)) == 1:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Two {sexes[0].lower()} parents cannot have a biological child. "
                "Use Adoptive, Step, or Foster instead.",
            )

    await uow._session.execute(
        text("UPDATE family_group_members SET parentage_type = :pt WHERE family_group_id = :fgid AND person_id = :pid"),
        {"pt": body.parentage_type, "fgid": family_group_id, "pid": person_id},
    )

    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.UPDATE_RELATIONSHIP,
            entity_type=AuditEntityType.FAMILY_GROUP,
            entity_id=family_group_id,
            after={"person_id": str(person_id), "parentage_type": body.parentage_type},
        )
    )
    await uow._session.commit()
    return {"family_group_id": str(family_group_id), "person_id": str(person_id), "parentage_type": body.parentage_type}


@router.get("/trees", response_model=list[TreeSummaryResponse], summary="List trees the current user belongs to")
async def list_my_trees(
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> list[TreeSummaryResponse]:
    from sqlalchemy import text

    is_elevated = current_user.app_role in (AppRole.AUDITOR, AppRole.SUPER_ADMIN)

    if is_elevated:
        effective_role = "OWNER" if current_user.app_role == AppRole.SUPER_ADMIN else "VIEWER"
        q = text("""
            SELECT
                ft.id,
                ft.name,
                ft.description,
                ft.cover_emoji,
                ft.cover_image_url,
                ft.link_sharing,
                ft.share_token,
                ft.is_searchable,
                (SELECT COUNT(*) FROM persons p WHERE p.tree_id = ft.id AND p.is_deleted = false) AS person_count,
                (SELECT COUNT(*) FROM tree_members m WHERE m.tree_id = ft.id) AS member_count,
                (tp.id IS NOT NULL) AS is_pinned,
                EXISTS (
                    SELECT 1 FROM permission_group_trees pgt
                    JOIN permission_groups pg ON pg.id = pgt.group_id
                    WHERE pgt.tree_id = ft.id AND pg.is_global = true
                ) AS is_globally_shared
            FROM family_trees ft
            LEFT JOIN tree_pins tp ON tp.tree_id = ft.id AND tp.user_id = :user_id
            WHERE ft.is_deleted = false
            ORDER BY ft.created_at DESC
        """)
        result = await uow._session.execute(q, {"user_id": current_user.id})
        rows = result.fetchall()
        return [
            TreeSummaryResponse(
                id=row.id,
                name=row.name,
                description=row.description,
                cover_emoji=row.cover_emoji,
                cover_image_url=row.cover_image_url,
                role=TreeRole(effective_role),
                person_count=row.person_count,
                member_count=row.member_count,
                link_sharing=row.link_sharing or "RESTRICTED",
                share_token=row.share_token,
                is_pinned=row.is_pinned,
                is_searchable=row.is_searchable,
                is_globally_shared=row.is_globally_shared,
            )
            for row in rows
        ]

    # Standard user: trees where the current user is a member
    q = text("""
        SELECT
            ft.id,
            ft.name,
            ft.description,
            ft.cover_emoji,
            ft.cover_image_url,
            ft.link_sharing,
            ft.share_token,
            ft.is_searchable,
            tm.role,
            (SELECT COUNT(*) FROM persons p WHERE p.tree_id = ft.id AND p.is_deleted = false) AS person_count,
            (SELECT COUNT(*) FROM tree_members m WHERE m.tree_id = ft.id) AS member_count,
            (tp.id IS NOT NULL) AS is_pinned,
            EXISTS (
                SELECT 1 FROM permission_group_trees pgt
                JOIN permission_groups pg ON pg.id = pgt.group_id
                WHERE pgt.tree_id = ft.id AND pg.is_global = true
            ) AS is_globally_shared
        FROM family_trees ft
        JOIN tree_members tm ON tm.tree_id = ft.id
        LEFT JOIN tree_pins tp ON tp.tree_id = ft.id AND tp.user_id = :user_id
        WHERE tm.user_id = :user_id
          AND ft.is_deleted = false
        ORDER BY ft.created_at DESC
    """)
    result = await uow._session.execute(q, {"user_id": current_user.id})
    rows = result.fetchall()
    return [
        TreeSummaryResponse(
            id=row.id,
            name=row.name,
            description=row.description,
            cover_emoji=row.cover_emoji,
            cover_image_url=row.cover_image_url,
            role=TreeRole(row.role),
            person_count=row.person_count,
            member_count=row.member_count,
            link_sharing=row.link_sharing or "RESTRICTED",
            share_token=row.share_token,
            is_pinned=row.is_pinned,
            is_searchable=row.is_searchable,
            is_globally_shared=row.is_globally_shared,
        )
        for row in rows
    ]


# ── Tree pins (per-user Dashboard pins) ─────────────────────────────────────────

@router.post("/trees/{tree_id}/pin", status_code=status.HTTP_204_NO_CONTENT, response_model=None,
             response_class=Response, summary="Pin a tree to the top of the Dashboard")
async def pin_tree(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> Response:
    from sqlalchemy import text

    if current_user.app_role != AppRole.AUDITOR:
        member_row = (await uow._session.execute(
            text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
            {"tid": tree_id, "uid": current_user.id},
        )).first()
        if not member_row:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of this tree")

    await uow._session.execute(text("""
        INSERT INTO tree_pins (tree_id, user_id, tenant_id)
        VALUES (:tid, :uid, :tenant)
        ON CONFLICT (user_id, tree_id) DO NOTHING
    """), {"tid": tree_id, "uid": current_user.id, "tenant": current_user.tenant_id})
    await uow.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/trees/{tree_id}/pin", status_code=status.HTTP_204_NO_CONTENT, response_model=None,
               response_class=Response, summary="Unpin a tree from the Dashboard")
async def unpin_tree(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> Response:
    from sqlalchemy import text

    await uow._session.execute(text("""
        DELETE FROM tree_pins WHERE tree_id = :tid AND user_id = :uid
    """), {"tid": tree_id, "uid": current_user.id})
    await uow.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Tree graph ─────────────────────────────────────────────────────────────────

@router.get("/trees/{tree_id}/graph", summary="Full person + family-group graph for canvas rendering")
async def get_tree_graph(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> dict:
    from sqlalchemy import text

    # Auditor + Super Admin bypass; all others (including app-level ADMIN) must be members
    review_change_request_id: uuid.UUID | None = None
    if current_user.app_role == AppRole.AUDITOR:
        effective_tree_role = "VIEWER"
    elif current_user.app_role == AppRole.SUPER_ADMIN:
        effective_tree_role = "OWNER"
    else:
        membership_q = text(
            "SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"
        )
        row = (await uow._session.execute(membership_q, {"tid": tree_id, "uid": current_user.id})).first()
        if row is not None:
            effective_tree_role = row.role
        else:
            # Not a member of this (draft) tree — but if it's a draft built from a
            # tree the caller owns, and a proposal from it is awaiting their
            # review, grant a read-only peek so they can review it in tree form.
            review_row = (await uow._session.execute(
                text("""
                    SELECT tcr.id FROM tree_change_requests tcr
                    JOIN tree_members tm ON tm.tree_id = tcr.tree_id AND tm.user_id = :uid AND tm.role = 'OWNER'
                    WHERE tcr.draft_tree_id = :tid AND tcr.status = 'PENDING'
                    LIMIT 1
                """),
                {"tid": tree_id, "uid": current_user.id},
            )).first()
            if review_row is None:
                raise HTTPException(403, "Not a member of this tree")
            effective_tree_role = "VIEWER"
            review_change_request_id = review_row.id

    # Tree metadata
    tree_q = text("""
        SELECT ft.name, ft.description, ft.draft_of_tree_id,
            EXISTS (
                SELECT 1 FROM permission_group_trees pgt
                JOIN permission_groups pg ON pg.id = pgt.group_id
                WHERE pgt.tree_id = ft.id AND pg.is_global = true
            ) AS is_globally_shared
        FROM family_trees ft
        WHERE ft.id = :tid
    """)
    tree_row = (await uow._session.execute(tree_q, {"tid": tree_id})).first()

    # Persons
    persons_q = text("""
        SELECT id, tree_id, display_given_name, display_surname,
               sex, is_living, is_deceased, photo_url,
               birth_date, death_date, birth_year, death_year,
               born_city, born_country, died_city, died_country,
               notes
        FROM persons
        WHERE tree_id = :tid AND is_deleted = false
        ORDER BY display_surname, display_given_name
    """)
    person_rows = (await uow._session.execute(persons_q, {"tid": tree_id})).fetchall()

    from src.api.v1._s3 import presign_photo as _presign_photo
    persons = [
        {
            "id": str(r.id),
            "treeId": str(r.tree_id),
            "displayGivenName": r.display_given_name,
            "displaySurname": r.display_surname,
            "sex": r.sex,
            "isLiving": r.is_living,
            "isDeceased": r.is_deceased,
            **({"photoUrl": _presign_photo(r.photo_url)} if r.photo_url else {}),
            **({"birthDate": r.birth_date.isoformat()} if r.birth_date else {}),
            **({"deathDate": r.death_date.isoformat()} if r.death_date else {}),
            **({"birthYear": r.birth_year} if r.birth_year is not None else {}),
            **({"deathYear": r.death_year} if r.death_year is not None else {}),
            **({"bornCity": r.born_city} if r.born_city else {}),
            **({"bornCountry": r.born_country} if r.born_country else {}),
            **({"diedCity": r.died_city} if r.died_city else {}),
            **({"diedCountry": r.died_country} if r.died_country else {}),
            **({"notes": r.notes} if r.notes else {}),
        }
        for r in person_rows
    ]

    # Family groups + members
    fg_q = text("""
        SELECT fg.id, fg.tree_id, fg.union_type, fg.custom_label, fg.is_divorced,
               fg.union_date, fg.union_date_year, fg.union_end_date, fg.union_end_date_year,
               fgm.person_id, fgm.role, fgm.parentage_type
        FROM family_groups fg
        LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
        LEFT JOIN persons p ON p.id = fgm.person_id
        WHERE fg.tree_id = :tid
          AND (fgm.person_id IS NULL OR p.is_deleted = false)
        ORDER BY fg.id
    """)
    fg_rows = (await uow._session.execute(fg_q, {"tid": tree_id})).fetchall()

    groups: dict[str, dict] = {}
    for r in fg_rows:
        gid = str(r.id)
        if gid not in groups:
            groups[gid] = {
                "id": gid,
                "treeId": str(r.tree_id),
                "unionType": r.union_type,
                **({"customLabel": r.custom_label} if r.custom_label else {}),
                **({"isDivorced": True} if r.is_divorced else {}),
                **({"unionDate": r.union_date.isoformat()} if r.union_date else {}),
                **({"unionDateYear": r.union_date_year} if r.union_date_year is not None else {}),
                **({"unionEndDate": r.union_end_date.isoformat()} if r.union_end_date else {}),
                **({"unionEndDateYear": r.union_end_date_year} if r.union_end_date_year is not None else {}),
                "parentIds": [],
                "children": {},
            }
        if r.person_id is None:
            continue
        pid = str(r.person_id)
        if r.role == "PARENT":
            if pid not in groups[gid]["parentIds"]:
                groups[gid]["parentIds"].append(pid)
        elif r.role == "CHILD":
            groups[gid]["children"][pid] = r.parentage_type or "BIOLOGICAL"

    return {
        "treeId":            str(tree_id),
        "treeName":          tree_row.name if tree_row else "",
        "treeDescription":   tree_row.description if tree_row else None,
        "userRole":          effective_tree_role,
        "isGloballyShared":  tree_row.is_globally_shared if tree_row else False,
        **({"draftOfTreeId": str(tree_row.draft_of_tree_id)} if tree_row and tree_row.draft_of_tree_id else {}),
        **({"reviewChangeRequestId": str(review_change_request_id)} if review_change_request_id else {}),
        "persons":           persons,
        "familyGroups":      list(groups.values()),
    }


# ── Import tree (.frt) ─────────────────────────────────────────────────────────

_VALID_SEX = {"MALE", "FEMALE", "OTHER", "UNKNOWN"}
_VALID_UNION_TYPES = {"MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN"}
_VALID_PARENTAGE_TYPES = {"BIOLOGICAL", "ADOPTIVE", "STEP", "FOSTER", "UNKNOWN"}


class _FrtPerson(BaseModel):
    id: str
    display_given_name: str = ""
    display_surname: str = ""
    sex: str = "UNKNOWN"
    is_living: bool = True
    is_deceased: bool = False
    photo_url: Optional[str] = None
    birth_date: Optional[str] = None
    death_date: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    born_city: Optional[str] = None
    born_country: Optional[str] = None
    died_city: Optional[str] = None
    died_country: Optional[str] = None
    notes: Optional[str] = None
    facebook_handle: Optional[str] = None
    x_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None


class _FrtFamilyGroup(BaseModel):
    id: str
    union_type: str = "UNKNOWN"
    custom_label: Optional[str] = None
    is_divorced: bool = False
    union_date: Optional[str] = None
    union_date_year: Optional[int] = None
    union_end_date: Optional[str] = None
    union_end_date_year: Optional[int] = None
    parent_ids: list[str] = []
    children: dict[str, str] = {}   # old_person_id → parentage_type


class ImportTreeRequest(BaseModel):
    frt_version: str = "1.0"
    tree_name: str = Field(..., min_length=1, max_length=200)
    tree_description: Optional[str] = None
    persons: list[_FrtPerson] = []
    family_groups: list[_FrtFamilyGroup] = []


@router.post("/trees/{tree_id}/export-log", status_code=204, summary="Record a tree export event in the audit log")
async def log_tree_export(
    tree_id: uuid.UUID,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> Response:
    from sqlalchemy import text
    from src.domain.collaboration.entities import AuditEntry, Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.EXPORT_TREE,
            entity_type=AuditEntityType.TREE,
            entity_id=tree_id,
        )
    )
    await uow._session.commit()
    return Response(status_code=204)


@router.post("/trees/import", status_code=201, summary="Import a .frt backup file as a new tree")
async def import_tree(
    body: ImportTreeRequest,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> dict:
    from sqlalchemy import text

    # 1. Create the new tree
    new_tree_id = uuid.uuid4()
    await uow._session.execute(text("""
        INSERT INTO family_trees (id, tenant_id, name, description)
        VALUES (:id, :tenant, :name, :desc)
    """), {
        "id":     new_tree_id,
        "tenant": current_user.tenant_id,
        "name":   body.tree_name,
        "desc":   body.tree_description,
    })

    # 2. Add creator as OWNER
    await uow._session.execute(text("""
        INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role)
        VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER')
    """), {"tid": new_tree_id, "uid": current_user.id, "tenant": current_user.tenant_id})

    # 3. Create persons — map old_id → new_id
    old_to_new: dict[str, uuid.UUID] = {}
    for p in body.persons:
        new_pid = uuid.uuid4()
        old_to_new[p.id] = new_pid
        birth_date_val = None
        if p.birth_date:
            try:
                birth_date_val = __import__("datetime").date.fromisoformat(p.birth_date)
            except ValueError:
                pass
        death_date_val = None
        if p.death_date:
            try:
                death_date_val = __import__("datetime").date.fromisoformat(p.death_date)
            except ValueError:
                pass

        await uow._session.execute(text("""
            INSERT INTO persons
              (id, tenant_id, tree_id, display_given_name, display_surname,
               sex, is_living, is_deceased,
               birth_date, death_date, birth_year, death_year,
               born_city, born_country, died_city, died_country,
               notes)
            VALUES
              (:id, :tenant, :tid, :given, :surname, :sex, :living, :deceased,
               :birth_date, :death_date, :birth_year, :death_year,
               :born_city, :born_country, :died_city, :died_country,
               :notes)
        """), {
            "id":           new_pid,
            "tenant":       current_user.tenant_id,
            "tid":          new_tree_id,
            "given":        p.display_given_name,
            "surname":      p.display_surname,
            "sex":          p.sex if p.sex in _VALID_SEX else "UNKNOWN",
            "living":       p.is_living,
            "deceased":     p.is_deceased,
            "birth_date":   birth_date_val,
            "death_date":   death_date_val,
            "birth_year":   p.birth_year,
            "death_year":   p.death_year,
            "born_city":    p.born_city,
            "born_country": p.born_country,
            "died_city":    p.died_city,
            "died_country": p.died_country,
            "notes":        p.notes,
        })

    # 4. Create family groups + members
    for fg in body.family_groups:
        new_fg_id = uuid.uuid4()
        parent_ids = [old_to_new.get(pid) for pid in fg.parent_ids if pid in old_to_new]
        p1 = parent_ids[0] if len(parent_ids) > 0 else None
        p2 = parent_ids[1] if len(parent_ids) > 1 else None

        from datetime import date as _date
        udate_val = None
        if fg.union_date:
            try: udate_val = _date.fromisoformat(fg.union_date)
            except ValueError: pass
        uedate_val = None
        if fg.union_end_date:
            try: uedate_val = _date.fromisoformat(fg.union_end_date)
            except ValueError: pass

        await uow._session.execute(text("""
            INSERT INTO family_groups (id, tenant_id, tree_id, union_type, custom_label, is_divorced, union_date, union_date_year, union_end_date, union_end_date_year, parent1_id, parent2_id)
            VALUES (:id, :tenant, :tid, :utype, :clabel, :divorced, :udate, :udate_year, :uedate, :uedate_year, :p1, :p2)
        """), {
            "id":     new_fg_id,
            "tenant": current_user.tenant_id,
            "tid":    new_tree_id,
            "utype":  fg.union_type if fg.union_type in _VALID_UNION_TYPES else "UNKNOWN",
            "clabel": fg.custom_label,
            "divorced": fg.is_divorced,
            "udate":  udate_val,
            "udate_year": fg.union_date_year,
            "uedate": uedate_val,
            "uedate_year": fg.union_end_date_year,
            "p1":     p1,
            "p2":     p2,
        })

        for old_pid in fg.parent_ids:
            new_pid = old_to_new.get(old_pid)
            if new_pid is None:
                continue
            await uow._session.execute(text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')
            """), {"tenant": current_user.tenant_id, "tid": new_tree_id,
                   "fgid": new_fg_id, "pid": new_pid})

        for old_child_id, parentage in fg.children.items():
            new_child_id = old_to_new.get(old_child_id)
            if new_child_id is None:
                continue
            await uow._session.execute(text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', :pt)
            """), {"tenant": current_user.tenant_id, "tid": new_tree_id,
                   "fgid": new_fg_id, "pid": new_child_id,
                   "pt": parentage if parentage in _VALID_PARENTAGE_TYPES else "UNKNOWN"})

    # Audit: log the import action on the new tree
    from src.domain.collaboration.entities import AuditEntry, Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=new_tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.IMPORT_TREE,
            entity_type=AuditEntityType.TREE,
            entity_id=new_tree_id,
            entity_display_name=body.tree_name,
            after={"tree_name": body.tree_name, "person_count": len(body.persons)},
        )
    )
    await uow._session.commit()
    return {"tree_id": str(new_tree_id), "tree_name": body.tree_name}


@router.post("/trees/import-zip", status_code=201, summary="Import a .zip (tree + photos) produced by the export-zip endpoint")
async def import_tree_zip(
    current_user: NotAuditorDep,
    uow: UoWDep,
    file: UploadFile = File(...),
) -> dict:
    """Accept a ZIP produced by GET /trees/{id}/export-zip and restore the tree with photos."""
    import io
    import json
    import zipfile
    from sqlalchemy import text

    raw = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File is not a valid ZIP archive")

    # Find the .frt file inside the ZIP
    frt_names = [n for n in zf.namelist() if n.endswith(".frt") and "/" not in n]
    if not frt_names:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "ZIP does not contain a .frt file")
    frt_data = json.loads(zf.read(frt_names[0]))
    if not frt_data.get("frt_version") or not frt_data.get("tree_name"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid .frt format")

    tree_name = frt_data["tree_name"]
    tree_description = frt_data.get("tree_description")
    persons_raw = frt_data.get("persons", [])
    fgs_raw = frt_data.get("family_groups", [])

    # 1. Create tree
    new_tree_id = uuid.uuid4()
    await uow._session.execute(text("""
        INSERT INTO family_trees (id, tenant_id, name, description)
        VALUES (:id, :tenant, :name, :desc)
    """), {"id": new_tree_id, "tenant": current_user.tenant_id,
           "name": tree_name, "desc": tree_description})

    await uow._session.execute(text("""
        INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role)
        VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER')
    """), {"tid": new_tree_id, "uid": current_user.id, "tenant": current_user.tenant_id})

    # 2. Create persons — old_id → new_id
    old_to_new: dict[str, uuid.UUID] = {}
    photo_filename_map: dict[str, str] = {}  # old_id → photo_filename in ZIP

    for p in persons_raw:
        new_pid = uuid.uuid4()
        old_to_new[p["id"]] = new_pid
        if p.get("photo_filename"):
            photo_filename_map[p["id"]] = p["photo_filename"]
        birth_date_val = None
        if p.get("birth_date"):
            try:
                birth_date_val = __import__("datetime").date.fromisoformat(p["birth_date"])
            except ValueError:
                pass
        death_date_val = None
        if p.get("death_date"):
            try:
                death_date_val = __import__("datetime").date.fromisoformat(p["death_date"])
            except ValueError:
                pass
        await uow._session.execute(text("""
            INSERT INTO persons
              (id, tenant_id, tree_id, display_given_name, display_surname,
               sex, is_living, is_deceased,
               birth_date, death_date, birth_year, death_year,
               born_city, born_country, died_city, died_country,
               notes)
            VALUES (:id, :tenant, :tid, :given, :surname, :sex, :living, :deceased,
                    :birth_date, :death_date, :birth_year, :death_year,
                    :born_city, :born_country, :died_city, :died_country,
                    :notes)
        """), {
            "id":           new_pid,
            "tenant":       current_user.tenant_id,
            "tid":          new_tree_id,
            "given":        p.get("display_given_name", ""),
            "surname":      p.get("display_surname", ""),
            "sex":          p.get("sex", "UNKNOWN") if p.get("sex", "UNKNOWN") in _VALID_SEX else "UNKNOWN",
            "living":       p.get("is_living", True),
            "deceased":     p.get("is_deceased", False),
            "birth_date":   birth_date_val,
            "death_date":   death_date_val,
            "birth_year":   p.get("birth_year"),
            "death_year":   p.get("death_year"),
            "born_city":    p.get("born_city") or p.get("city"),
            "born_country": p.get("born_country") or p.get("country"),
            "died_city":    p.get("died_city"),
            "died_country": p.get("died_country"),
            "notes":        p.get("notes"),
        })

    # 3. Create family groups + members
    for fg in fgs_raw:
        new_fg_id = uuid.uuid4()
        parent_ids = [old_to_new.get(pid) for pid in fg.get("parent_ids", []) if pid in old_to_new]
        p1 = parent_ids[0] if len(parent_ids) > 0 else None
        p2 = parent_ids[1] if len(parent_ids) > 1 else None

        from datetime import date as _date
        udate_val = None
        if fg.get("union_date"):
            try: udate_val = _date.fromisoformat(fg["union_date"])
            except ValueError: pass
        uedate_val = None
        if fg.get("union_end_date"):
            try: uedate_val = _date.fromisoformat(fg["union_end_date"])
            except ValueError: pass

        await uow._session.execute(text("""
            INSERT INTO family_groups (id, tenant_id, tree_id, union_type, custom_label, is_divorced,
                                       union_date, union_date_year, union_end_date, union_end_date_year,
                                       parent1_id, parent2_id)
            VALUES (:id, :tenant, :tid, :utype, :clabel, :divorced,
                    :udate, :udate_year, :uedate, :uedate_year, :p1, :p2)
        """), {"id": new_fg_id, "tenant": current_user.tenant_id, "tid": new_tree_id,
               "utype": fg.get("union_type", "UNKNOWN") if fg.get("union_type", "UNKNOWN") in _VALID_UNION_TYPES else "UNKNOWN",
               "clabel": fg.get("custom_label"),
               "divorced": fg.get("is_divorced", False),
               "udate": udate_val,
               "udate_year": fg.get("union_date_year"),
               "uedate": uedate_val,
               "uedate_year": fg.get("union_end_date_year"),
               "p1": p1, "p2": p2})

        for old_pid in fg.get("parent_ids", []):
            new_pid = old_to_new.get(old_pid)
            if new_pid is None:
                continue
            await uow._session.execute(text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')
            """), {"tenant": current_user.tenant_id, "tid": new_tree_id,
                   "fgid": new_fg_id, "pid": new_pid})

        for old_child_id, parentage in fg.get("children", {}).items():
            new_child_id = old_to_new.get(old_child_id)
            if new_child_id is None:
                continue
            await uow._session.execute(text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', :pt)
            """), {"tenant": current_user.tenant_id, "tid": new_tree_id,
                   "fgid": new_fg_id, "pid": new_child_id,
                   "pt": parentage if parentage in _VALID_PARENTAGE_TYPES else "UNKNOWN"})

    await uow._session.commit()

    # 4. Upload photos to S3 and update photo_url on each person
    if photo_filename_map:
        from src.api.v1._s3 import _make_s3_client
        from src.config import get_settings
        settings = get_settings()
        bucket = settings.s3_bucket or "ourfamroots-local"
        s3 = _make_s3_client(settings)
        zip_names = set(zf.namelist())
        for old_pid, zip_path in photo_filename_map.items():
            new_pid = old_to_new.get(old_pid)
            if new_pid is None or zip_path not in zip_names:
                continue
            try:
                photo_bytes = zf.read(zip_path)
                ext = zip_path.rsplit(".", 1)[-1] if "." in zip_path else "jpg"
                content_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                                "png": "image/png", "webp": "image/webp",
                                "gif": "image/gif"}.get(ext.lower(), "image/jpeg")
                s3_key = f"tenants/{current_user.tenant_id}/trees/{new_tree_id}/persons/{new_pid}/photo/{uuid.uuid4()}.{ext}"
                s3.put_object(Bucket=bucket, Key=s3_key, Body=photo_bytes, ContentType=content_type)
                # Store only the S3 key — presigned URLs are generated at read time
                await uow._session.execute(text("""
                    UPDATE persons SET photo_url = :url WHERE id = :pid
                """), {"url": s3_key, "pid": new_pid})
            except Exception:
                pass  # skip individual photo failures

        # 4b. Import gallery photos
        for p in persons_raw:
            old_pid = p.get("id")
            new_pid = old_to_new.get(old_pid)
            if not new_pid:
                continue
            for gal in p.get("gallery_photos", []):
                gal_zip_path = gal.get("photo_filename")
                if not gal_zip_path or gal_zip_path not in zip_names:
                    continue
                try:
                    gal_bytes = zf.read(gal_zip_path)
                    ext = gal_zip_path.rsplit(".", 1)[-1] if "." in gal_zip_path else "jpg"
                    content_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                                    "png": "image/png", "webp": "image/webp",
                                    "gif": "image/gif"}.get(ext.lower(), "image/jpeg")
                    gal_id = uuid.uuid4()
                    gal_s3_key = f"tenants/{current_user.tenant_id}/trees/{new_tree_id}/persons/{new_pid}/gallery/{gal_id}.{ext}"
                    s3.put_object(Bucket=bucket, Key=gal_s3_key, Body=gal_bytes, ContentType=content_type)
                    await uow._session.execute(text("""
                        INSERT INTO person_gallery_photos (id, person_id, tree_id, tenant_id, photo_url, caption, position)
                        VALUES (:id, :pid, :tid, :tenant, :url, :caption, :pos)
                    """), {
                        "id": gal_id, "pid": new_pid, "tid": new_tree_id,
                        "tenant": current_user.tenant_id,
                        "url": gal_s3_key, "caption": gal.get("caption"),
                        "pos": gal.get("position", 0),
                    })
                except Exception:
                    pass

        await uow._session.commit()

    # Audit
    from src.domain.collaboration.entities import AuditEntry, Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=new_tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.IMPORT_TREE,
            entity_type=AuditEntityType.TREE,
            entity_id=new_tree_id,
            entity_display_name=tree_name,
            after={"tree_name": tree_name, "person_count": len(persons_raw),
                   "photos": len(photo_filename_map)},
        )
    )
    await uow._session.commit()
    return {"tree_id": str(new_tree_id), "tree_name": tree_name}


# ── Merge trees (admin only) ───────────────────────────────────────────────────

class MergeSource(BaseModel):
    tree_id: uuid.UUID
    pivot_person_id: uuid.UUID


class MergeTreesRequest(BaseModel):
    new_tree_name: str = Field(..., min_length=1, max_length=255)
    new_tree_description: Optional[str] = Field(None, max_length=1000)
    sources: list[MergeSource] = Field(..., min_length=2)
    merge_identical: bool = False


class AutoMergeRequest(BaseModel):
    new_tree_name: str = Field(..., min_length=1, max_length=255)
    new_tree_description: Optional[str] = Field(None, max_length=1000)
    tree_ids: list[uuid.UUID] = Field(..., min_length=2)


@router.post(
    "/trees/merge/auto",
    status_code=status.HTTP_201_CREATED,
    summary="Auto-detect pivot and merge trees (admin only)",
)
async def auto_merge_trees(
    body: AutoMergeRequest,
    current_user: AdminUserDep,
    uow: UoWDep,
) -> dict:
    """Find a common member across all selected trees by name, use them as the
    pivot, and merge all other identical members automatically."""
    from sqlalchemy import text

    tenant_id = current_user.tenant_id

    # Validate every requested tree exists in the tenant and user is a member
    for tree_id in body.tree_ids:
        row = (await uow._session.execute(
            text("SELECT id FROM family_trees WHERE id = :tid AND tenant_id = :tenant AND is_deleted = false LIMIT 1"),
            {"tid": tree_id, "tenant": tenant_id},
        )).first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tree {tree_id} not found")
        if current_user.app_role != AppRole.AUDITOR:
            member_row = (await uow._session.execute(
                text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
                {"tid": tree_id, "uid": current_user.id},
            )).first()
            if not member_row:
                raise HTTPException(status.HTTP_403_FORBIDDEN, f"You are not a member of tree {tree_id}")

    # Load persons (name + sex + birth_year) from every tree
    tree_name_map: dict[uuid.UUID, dict[str, uuid.UUID]] = {}   # tree_id → {name_key: person_id}
    for tree_id in body.tree_ids:
        rows = (await uow._session.execute(text("""
            SELECT id, display_given_name, display_surname
            FROM persons
            WHERE tree_id = :tid AND tenant_id = :tenant AND is_deleted = false
        """), {"tid": tree_id, "tenant": tenant_id})).fetchall()

        tree_name_map[tree_id] = {}
        for r in rows:
            given   = (r.display_given_name or "").strip().lower()
            surname = (r.display_surname or "").strip().lower()
            if not given and not surname:
                continue
            name_key = f"{given}|{surname}"
            # First occurrence of a name wins (no overwrite)
            if name_key not in tree_name_map[tree_id]:
                tree_name_map[tree_id][name_key] = r.id

    # Find names present in ALL selected trees
    common_names: set[str] = set(tree_name_map[body.tree_ids[0]])
    for tree_id in body.tree_ids[1:]:
        common_names &= set(tree_name_map[tree_id])

    if not common_names:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No member with the same name was found across all selected trees. "
            "Add a common member to each tree or choose pivot people manually.",
        )

    # Pick the first common name (alphabetical for determinism) as the pivot
    pivot_name = sorted(common_names)[0]
    sources = [
        MergeSource(tree_id=tid, pivot_person_id=tree_name_map[tid][pivot_name])
        for tid in body.tree_ids
    ]

    merge_body = MergeTreesRequest(
        new_tree_name=body.new_tree_name,
        new_tree_description=body.new_tree_description,
        sources=sources,
        merge_identical=True,
    )
    return await merge_trees(merge_body, current_user, uow)


async def _execute_merge(
    session,
    sources: list[dict],
    new_tree_name: str,
    tenant_id: uuid.UUID,
    owner_user_ids: list[uuid.UUID],
    new_tree_description: str | None = None,
    merge_identical: bool = True,
) -> uuid.UUID:
    """Core merge logic shared by admin merge endpoint and merge-request approval."""
    from sqlalchemy import text as _text
    import logging
    _log = logging.getLogger("ourfamroots.merge")
    _log.setLevel(logging.DEBUG)
    if not _log.handlers:
        _log.addHandler(logging.StreamHandler())

    new_tree_id = uuid.uuid4()
    await session.execute(_text("""
        INSERT INTO family_trees (id, tenant_id, name, description)
        VALUES (:id, :tenant, :name, :desc)
    """), {"id": new_tree_id, "tenant": tenant_id, "name": new_tree_name, "desc": new_tree_description})

    for uid in owner_user_ids:
        await session.execute(_text("""
            INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
            VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER', NOW())
            ON CONFLICT (tree_id, user_id) DO NOTHING
        """), {"tid": new_tree_id, "uid": uid, "tenant": tenant_id})

    merged_pivot_id = uuid.uuid4()
    id_map: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
    for src in sources:
        id_map[(src["tree_id"], src["pivot_person_id"])] = merged_pivot_id

    _log.info("MERGE START: new_tree=%s, pivot=%s, merge_identical=%s", new_tree_id, merged_pivot_id, merge_identical)
    for i, src in enumerate(sources):
        _log.info("  source[%d]: tree=%s pivot_person=%s", i, src["tree_id"], src["pivot_person_id"])

    all_persons: list[dict] = []
    pivot_data: dict | None = None

    _PERSON_FIELDS = [
        "display_given_name", "display_surname", "sex",
        "is_living", "is_deceased", "photo_url",
        "birth_date", "death_date", "birth_year", "death_year",
        "born_city", "born_country", "died_city", "died_country",
        "notes",
    ]

    def _person_dict(r, new_id, src_tree=None):
        d = {"id": new_id}
        for f in _PERSON_FIELDS:
            d[f] = getattr(r, f)
        if src_tree is not None:
            d["_src_tree"] = src_tree
        return d

    for src in sources:
        rows = (await session.execute(_text("""
            SELECT id, display_given_name, display_surname, sex,
                   is_living, is_deceased, photo_url,
                   birth_date, death_date, birth_year, death_year,
                   born_city, born_country, died_city, died_country,
                   notes
            FROM persons
            WHERE tree_id = :tid AND is_deleted = false
        """), {"tid": src["tree_id"]})).fetchall()

        for r in rows:
            key = (src["tree_id"], r.id)
            if key not in id_map:
                id_map[key] = uuid.uuid4()
            is_pivot = (r.id == src["pivot_person_id"])
            if is_pivot and pivot_data is None:
                pivot_data = _person_dict(r, merged_pivot_id)
            elif is_pivot and pivot_data is not None:
                for f in _PERSON_FIELDS:
                    val = getattr(r, f)
                    if val is not None and val != "" and (pivot_data[f] is None or pivot_data[f] == "" or pivot_data[f] == "UNKNOWN"):
                        pivot_data[f] = val
            elif not is_pivot:
                all_persons.append(_person_dict(r, id_map[key], src["tree_id"]))

        _log.info("  loaded %d persons from tree %s", len(rows), src["tree_id"])

    _log.info("id_map has %d entries, all_persons has %d entries", len(id_map), len(all_persons))
    for (tid, pid), new_id in id_map.items():
        _log.debug("  id_map[(%s, %s)] = %s", tid, pid, new_id)

    if merge_identical and all_persons:
        name_to_canonical: dict[str, dict] = {}
        collapse_map: dict[uuid.UUID, uuid.UUID] = {}

        for p in all_persons:
            given   = (p["display_given_name"] or "").strip().lower()
            surname = (p["display_surname"] or "").strip().lower()
            if not given and not surname:
                continue
            name_key = f"{given}|{surname}"

            if name_key not in name_to_canonical:
                name_to_canonical[name_key] = p
                continue

            canon = name_to_canonical[name_key]
            if p["_src_tree"] == canon["_src_tree"]:
                continue

            sex_c = canon["sex"] or "UNKNOWN"
            sex_p = p["sex"] or "UNKNOWN"
            if sex_c != "UNKNOWN" and sex_p != "UNKNOWN" and sex_c != sex_p:
                continue

            by_c = canon["birth_year"]
            by_p = p["birth_year"]
            if by_c is not None and by_p is not None and by_c != by_p:
                continue

            for f in _PERSON_FIELDS:
                val = p.get(f)
                if val is not None and val != "" and (canon.get(f) is None or canon.get(f) == "" or canon.get(f) == "UNKNOWN"):
                    canon[f] = val
            collapse_map[p["id"]] = canon["id"]

        if collapse_map:
            all_persons = [p for p in all_persons if p["id"] not in collapse_map]
            for k in list(id_map.keys()):
                if id_map[k] in collapse_map:
                    id_map[k] = collapse_map[id_map[k]]

    def _insert_params(person_dict, tenant, tree):
        return {
            "id": person_dict["id"], "tenant": tenant, "tid": tree,
            "given": person_dict["display_given_name"],
            "surname": person_dict["display_surname"],
            "sex": person_dict["sex"] or "UNKNOWN",
            "living": person_dict["is_living"],
            "deceased": person_dict["is_deceased"],
            "photo_url": person_dict["photo_url"],
            "birth_date": person_dict.get("birth_date"),
            "death_date": person_dict.get("death_date"),
            "birth_year": person_dict.get("birth_year"),
            "death_year": person_dict.get("death_year"),
            "born_city": person_dict.get("born_city"),
            "born_country": person_dict.get("born_country"),
            "died_city": person_dict.get("died_city"),
            "died_country": person_dict.get("died_country"),
            "notes": person_dict.get("notes"),
        }

    _MERGE_INSERT_SQL = _text("""
        INSERT INTO persons (id, tenant_id, tree_id, display_given_name, display_surname,
                             sex, is_living, is_deceased, photo_url,
                             birth_date, death_date, birth_year, death_year,
                             born_city, born_country, died_city, died_country,
                             notes)
        VALUES (:id, :tenant, :tid, :given, :surname, :sex, :living, :deceased, :photo_url,
                :birth_date, :death_date, :birth_year, :death_year,
                :born_city, :born_country, :died_city, :died_country,
                :notes)
    """)

    if pivot_data:
        await session.execute(_MERGE_INSERT_SQL, _insert_params(pivot_data, tenant_id, new_tree_id))

    inserted_person_ids: set[uuid.UUID] = {merged_pivot_id} if pivot_data else set()
    for p in all_persons:
        if p["id"] in inserted_person_ids:
            continue
        inserted_person_ids.add(p["id"])
        await session.execute(_MERGE_INSERT_SQL, _insert_params(p, tenant_id, new_tree_id))

    # ── Collect ALL family groups from ALL sources, remap person IDs ─────────
    _log.info("=== FAMILY GROUP PHASE ===")
    all_fgs: list[dict] = []

    for src in sources:
        _log.info("Loading family groups from tree %s", src["tree_id"])
        fg_rows = (await session.execute(_text("""
            SELECT fg.id AS fg_id, fg.union_type, fg.custom_label, fg.is_divorced,
                   fg.union_date, fg.union_date_year, fg.union_end_date, fg.union_end_date_year,
                   fg.parent1_id, fg.parent2_id,
                   fgm.person_id, fgm.role, fgm.parentage_type
            FROM family_groups fg
            LEFT JOIN family_group_members fgm ON fgm.family_group_id = fg.id
            WHERE fg.tree_id = :tid
        """), {"tid": src["tree_id"]})).fetchall()

        fg_map: dict[uuid.UUID, dict] = {}
        for r in fg_rows:
            fgid = r.fg_id
            if fgid not in fg_map:
                fg_map[fgid] = {
                    "union_type": r.union_type, "custom_label": r.custom_label,
                    "is_divorced": r.is_divorced,
                    "union_date": r.union_date, "union_date_year": r.union_date_year,
                    "union_end_date": r.union_end_date, "union_end_date_year": r.union_end_date_year,
                    "parent_ids": [], "children": {},
                    "_raw_parent1": r.parent1_id, "_raw_parent2": r.parent2_id,
                }

            if r.person_id is None:
                continue
            new_pid = id_map.get((src["tree_id"], r.person_id))
            if new_pid is None:
                _log.warning("merge: person %s in tree %s not in id_map — skipping", r.person_id, src["tree_id"])
                continue
            if r.role == "PARENT" and new_pid not in fg_map[fgid]["parent_ids"]:
                fg_map[fgid]["parent_ids"].append(new_pid)
            elif r.role == "CHILD":
                fg_map[fgid]["children"][new_pid] = r.parentage_type or "BIOLOGICAL"

        for fgid, fg_data in fg_map.items():
            if not fg_data["parent_ids"]:
                for raw_pid in [fg_data.get("_raw_parent1"), fg_data.get("_raw_parent2")]:
                    if raw_pid is None:
                        continue
                    new_pid = id_map.get((src["tree_id"], raw_pid))
                    if new_pid and new_pid not in fg_data["parent_ids"]:
                        fg_data["parent_ids"].append(new_pid)
                        _log.info("merge: recovered parent %s via parent1/2_id", raw_pid)

        for fgid, fg_data in fg_map.items():
            if not fg_data["parent_ids"] and not fg_data["children"]:
                continue
            all_fgs.append(fg_data)

        _log.info("  tree %s: %d family groups collected", src["tree_id"], len(fg_map))

    # ── Consolidate: merge family groups that share the same parent set ───────
    # e.g. if Aerys→Rhaegar (Tree 1) and Aerys→Daenerys,Viserys (Tree 2)
    # both have parent_ids=[merged_pivot], combine children as siblings.
    consolidated: list[dict] = []
    parent_key_map: dict[tuple, int] = {}

    for fg in all_fgs:
        pkey = tuple(sorted(str(p) for p in fg["parent_ids"])) if fg["parent_ids"] else None

        if pkey and pkey in parent_key_map:
            idx = parent_key_map[pkey]
            existing = consolidated[idx]
            for child_id, parentage in fg["children"].items():
                if child_id not in existing["children"]:
                    existing["children"][child_id] = parentage
            if not existing.get("custom_label") and fg.get("custom_label"):
                existing["custom_label"] = fg["custom_label"]
            _log.info("  consolidated FG: parents=%s gained %d children → total %d",
                       pkey, len(fg["children"]), len(existing["children"]))
        else:
            idx = len(consolidated)
            consolidated.append(fg)
            if pkey:
                parent_key_map[pkey] = idx

    _log.info("After consolidation: %d family groups (was %d)", len(consolidated), len(all_fgs))

    # ── Insert consolidated family groups ─────────────────────────────────────
    for fg_data in consolidated:
        parent_ids = fg_data["parent_ids"]
        children = fg_data["children"]

        new_fg_id = uuid.uuid4()
        p1 = parent_ids[0] if len(parent_ids) > 0 else None
        p2 = parent_ids[1] if len(parent_ids) > 1 else None

        _log.info("  INSERT FG %s: parents=%s children=%d union=%s",
                   new_fg_id, [str(p) for p in parent_ids], len(children), fg_data["union_type"])

        await session.execute(_text("""
            INSERT INTO family_groups (id, tenant_id, tree_id, union_type, custom_label, is_divorced, union_date, union_date_year, union_end_date, union_end_date_year, parent1_id, parent2_id)
            VALUES (:id, :tenant, :tid, :utype, :clabel, :divorced, :udate, :udate_year, :uedate, :uedate_year, :p1, :p2)
        """), {"id": new_fg_id, "tenant": tenant_id, "tid": new_tree_id,
               "utype": fg_data["union_type"] or "UNKNOWN",
               "clabel": fg_data.get("custom_label"),
               "divorced": fg_data.get("is_divorced", False),
               "udate": fg_data.get("union_date"),
               "udate_year": fg_data.get("union_date_year"),
               "uedate": fg_data.get("union_end_date"),
               "uedate_year": fg_data.get("union_end_date_year"),
               "p1": p1, "p2": p2})

        for pid in parent_ids:
            await session.execute(_text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')
            """), {"tenant": tenant_id, "tid": new_tree_id, "fgid": new_fg_id, "pid": pid})

        for child_pid, parentage in children.items():
            await session.execute(_text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', :pt)
            """), {"tenant": tenant_id, "tid": new_tree_id, "fgid": new_fg_id,
                   "pid": child_pid, "pt": parentage})

    return new_tree_id


@router.post("/trees/merge", status_code=status.HTTP_201_CREATED, summary="Merge multiple trees into one new tree (admin only)")
async def merge_trees(
    body: MergeTreesRequest,
    current_user: AdminUserDep,
    uow: UoWDep,
) -> dict:
    from sqlalchemy import text

    if len(body.sources) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least 2 source trees are required")

    tenant_id = current_user.tenant_id

    for src in body.sources:
        tree_row = (await uow._session.execute(
            text("SELECT id FROM family_trees WHERE id = :tid AND tenant_id = :tenant AND is_deleted = false LIMIT 1"),
            {"tid": src.tree_id, "tenant": tenant_id},
        )).first()
        if tree_row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tree {src.tree_id} not found")
        if current_user.app_role != AppRole.AUDITOR:
            member_row = (await uow._session.execute(
                text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
                {"tid": src.tree_id, "uid": current_user.id},
            )).first()
            if not member_row:
                raise HTTPException(status.HTTP_403_FORBIDDEN, f"You are not a member of tree {src.tree_id}")

    for src in body.sources:
        p_row = (await uow._session.execute(
            text("SELECT id FROM persons WHERE id = :pid AND tree_id = :tid AND is_deleted = false LIMIT 1"),
            {"pid": src.pivot_person_id, "tid": src.tree_id},
        )).first()
        if p_row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Person {src.pivot_person_id} not found in tree {src.tree_id}",
            )

    new_tree_id = await _execute_merge(
        session=uow._session,
        sources=[{"tree_id": s.tree_id, "pivot_person_id": s.pivot_person_id} for s in body.sources],
        new_tree_name=body.new_tree_name,
        tenant_id=tenant_id,
        owner_user_ids=[current_user.id],
        new_tree_description=body.new_tree_description,
        merge_identical=body.merge_identical,
    )

    person_count = (await uow._session.execute(
        text("SELECT COUNT(*) FROM persons WHERE tree_id = :tid AND is_deleted = false"),
        {"tid": new_tree_id},
    )).scalar_one()

    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=new_tree_id,
            tenant_id=tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.MERGE_TREES,
            entity_type=AuditEntityType.TREE,
            entity_id=new_tree_id,
            entity_display_name=body.new_tree_name,
            after={
                "tree_name": body.new_tree_name,
                "source_tree_ids": [str(s.tree_id) for s in body.sources],
                "person_count": person_count,
            },
        )
    )
    await uow._session.commit()

    return {
        "tree_id": str(new_tree_id),
        "tree_name": body.new_tree_name,
        "person_count": person_count,
    }


# ── Members ────────────────────────────────────────────────────────────────────

@router.get("/trees/{tree_id}/members", response_model=list[MemberResponse])
async def list_members(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> list[MemberResponse]:
    from sqlalchemy import text

    # Auditor + Super Admin bypass; all others (including app-level ADMIN) must be members
    if current_user.app_role not in (AppRole.AUDITOR, AppRole.SUPER_ADMIN):
        check = (await uow._session.execute(
            text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
            {"tid": tree_id, "uid": current_user.id},
        )).first()
        if check is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this tree")

    rows = (await uow._session.execute(text("""
        SELECT
            tm.id, tm.tree_id, tm.user_id, tm.role, tm.joined_at,
            u.email,
            COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS display_name
        FROM tree_members tm
        JOIN users u ON u.id = tm.user_id
        WHERE tm.tree_id = :tid
        ORDER BY
            CASE tm.role WHEN 'OWNER' THEN 0 WHEN 'ADMIN' THEN 1 WHEN 'EDITOR' THEN 2 ELSE 3 END,
            tm.joined_at
    """), {"tid": tree_id})).fetchall()

    return [
        MemberResponse(
            id=r.id,
            tree_id=r.tree_id,
            user_id=r.user_id,
            role=TreeRole(r.role),
            joined_at=r.joined_at.isoformat() if r.joined_at else None,
            email=r.email,
            display_name=r.display_name,
        )
        for r in rows
    ]


class AddMemberDirectRequest(BaseModel):
    user_id: uuid.UUID
    role: TreeRole = TreeRole.VIEWER


@router.post("/trees/{tree_id}/members", response_model=MemberResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Directly add an existing tenant user as a tree member (OWNER/ADMIN only)")
async def add_member_direct(
    tree_id: uuid.UUID,
    body: AddMemberDirectRequest,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> MemberResponse:
    from sqlalchemy import text

    # Require OWNER or ADMIN tree role
    caller_row = (await uow._session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if caller_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if caller_row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can add members directly")

    # Verify target user belongs to this tenant
    user_row = (await uow._session.execute(
        text("SELECT id, email, given_name, family_name FROM users WHERE id = :uid AND tenant_id = :tid LIMIT 1"),
        {"uid": body.user_id, "tid": current_user.tenant_id},
    )).first()
    if user_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in this tenant")

    # Upsert tree membership (handles already-member case gracefully)
    member_id = uuid.uuid4()
    await uow._session.execute(
        text("""
            INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, invited_by_id, joined_at)
            VALUES (:id, :tree_id, :user_id, :tenant_id, :role, :invited_by, now())
            ON CONFLICT (tree_id, user_id) DO UPDATE SET role = EXCLUDED.role
            RETURNING id, joined_at
        """),
        {
            "id": member_id,
            "tree_id": tree_id,
            "user_id": body.user_id,
            "tenant_id": current_user.tenant_id,
            "role": body.role.value,
            "invited_by": current_user.id,
        },
    )
    await uow._session.commit()

    display_name = f"{user_row.given_name or ''} {user_row.family_name or ''}".strip() or user_row.email

    # Fetch tree name for notification
    tree_name_row = (await uow._session.execute(
        text("SELECT name FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()
    tree_name = tree_name_row.name if tree_name_row else str(tree_id)

    actor_display = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email

    # Create in-app notification for the added user
    import json as _json
    _notif_data = _json.dumps({
        "tree_id": str(tree_id),
        "tree_name": tree_name,
        "shared_by_id": str(current_user.id),
        "shared_by_name": actor_display,
        "role": body.role.value,
    })
    await uow._session.execute(
        text("""
            INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
            VALUES (:user_id, :tenant_id, 'TREE_SHARED',
                    :title, :nbody, CAST(:data AS jsonb))
        """),
        {
            "user_id": body.user_id,
            "tenant_id": current_user.tenant_id,
            "title": f"You've been added to \"{tree_name}\"",
            "nbody": f"{actor_display} shared \"{tree_name}\" with you as {body.role.value.capitalize()}",
            "data": _notif_data,
        },
    )
    await uow._session.commit()

    import asyncio as _asyncio
    from src.api.v1.push import send_push_to_user as _push
    _asyncio.create_task(_push(
        uow._session,
        body.user_id,
        f"You've been added to \"{tree_name}\"",
        f"{actor_display} shared \"{tree_name}\" with you as {body.role.value.capitalize()}",
        {"type": "TREE_SHARED", "tree_id": str(tree_id), "tree_name": tree_name},
    ))

    return MemberResponse(
        id=member_id,
        tree_id=tree_id,
        user_id=body.user_id,
        role=body.role,
        joined_at=None,
        email=user_row.email,
        display_name=display_name,
    )


class TenantUserForShareResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str


@router.get("/trees/{tree_id}/tenant-users", response_model=list[TenantUserForShareResponse],
            summary="List tenant users not already in this tree (for share modal, OWNER/ADMIN only)")
async def list_tenant_users_for_share(
    tree_id: uuid.UUID,
    current_user: NotAuditorDep,
    uow: UoWDep,
) -> list[TenantUserForShareResponse]:
    from sqlalchemy import text

    row = (await uow._session.execute(
        text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
        {"tid": tree_id, "uid": current_user.id},
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tree not found")
    if row.role not in ("OWNER", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can share this tree")

    rows = (await uow._session.execute(text("""
        SELECT
            u.id,
            u.email,
            COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS display_name
        FROM users u
        WHERE u.tenant_id = :tenant_id
          AND u.is_active = true
          AND u.id NOT IN (
              SELECT user_id FROM tree_members WHERE tree_id = :tree_id
          )
        ORDER BY display_name
    """), {"tenant_id": current_user.tenant_id, "tree_id": tree_id})).fetchall()

    return [TenantUserForShareResponse(id=r.id, email=r.email, display_name=r.display_name) for r in rows]


@router.patch("/trees/{tree_id}/members/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def change_member_role(
    tree_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    request: Request,
    current_user: NotAuditorDep,
    svc: CollabDep,
) -> None:
    await svc.change_member_role(
        tree_id=tree_id,
        target_user_id=user_id,
        new_role=body.role,
        actor_id=current_user.id,
        actor_name=f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email,
        ip_address=request.client.host if request.client else None,
        app_role=current_user.app_role,
    )


@router.delete("/trees/{tree_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def remove_member(
    tree_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    current_user: NotAuditorDep,
    svc: CollabDep,
    uow: UoWDep,
) -> None:
    await svc.remove_member(
        tree_id=tree_id,
        target_user_id=user_id,
        actor_id=current_user.id,
        actor_name=f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email,
        tenant_id=current_user.tenant_id,
        ip_address=request.client.host if request.client else None,
        app_role=current_user.app_role,
    )


# ── Invitations ────────────────────────────────────────────────────────────────

@router.get("/trees/{tree_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: CollabDep,
) -> list[InvitationResponse]:
    await svc.require_permission(tree_id, current_user.id, Action.VIEW_MEMBERS, app_role=current_user.app_role)
    from src.infrastructure.repositories.collaboration import InvitationRepository
    repo = InvitationRepository(svc._session)
    invitations = await repo.list_by_tree(tree_id)
    return [InvitationResponse.from_domain(i) for i in invitations]


@router.post("/trees/{tree_id}/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def send_invitation(
    tree_id: uuid.UUID,
    body: InviteRequest,
    request: Request,
    current_user: NotAuditorDep,
    svc: CollabDep,
) -> InvitationResponse:
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email

    # Resolve tree name for the email
    from sqlalchemy import text as _text
    tree_row = (await svc._session.execute(
        _text("SELECT name FROM family_trees WHERE id = :tid AND is_deleted = false LIMIT 1"),
        {"tid": tree_id},
    )).first()
    tree_name = tree_row.name if tree_row else str(tree_id)

    invitation = await svc.send_invitation(
        tree_id=tree_id,
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        actor_name=actor_name,
        invitee_email=body.email,
        role=body.role,
        message=body.message,
        ip_address=request.client.host if request.client else None,
        app_role=current_user.app_role,
    )

    # Dispatch invitation email in the background (non-blocking)
    import asyncio as _asyncio
    from src.config import get_settings as _get_settings
    from src.infrastructure.email.service import send_email as _send_email, tree_invitation_email as _inv_email

    _settings = _get_settings()
    _accept_url = f"{_settings.frontend_base_url}/invitations/accept?token={invitation.token}"
    _html, _text = _inv_email(
        invitee_email=body.email,
        inviter_name=actor_name,
        tree_name=tree_name,
        role=body.role.value,
        accept_url=_accept_url,
        message=body.message,
    )
    _asyncio.create_task(_send_email(
        to=body.email,
        subject=f"{actor_name} invited you to join {tree_name} on OurFamRoots",
        html_body=_html,
        text_body=_text,
    ))

    # If invitee already has an account, create an in-app TREE_INVITE notification
    import json as _json
    from sqlalchemy import text as _sql
    invitee_row = (await svc._session.execute(
        _sql("SELECT id, tenant_id FROM users WHERE email = :email AND tenant_id = :tid LIMIT 1"),
        {"email": body.email, "tid": current_user.tenant_id},
    )).first()
    if invitee_row:
        await svc._session.execute(
            _sql("""
                INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
                VALUES (:uid, :tenant_id, 'TREE_INVITE',
                        :title, :nbody, CAST(:data AS jsonb))
            """),
            {
                "uid": invitee_row.id,
                "tenant_id": current_user.tenant_id,
                "title": f"{actor_name} invited you to \"{tree_name}\"",
                "nbody": f"You've been invited to join \"{tree_name}\" as {body.role.value.capitalize()}",
                "data": _json.dumps({
                    "token": invitation.token,
                    "tree_id": str(tree_id),
                    "tree_name": tree_name,
                    "shared_by_name": actor_name,
                    "role": body.role.value,
                }),
            },
        )
        await svc._session.commit()

        from src.api.v1.push import send_push_to_user as _push
        _asyncio.create_task(_push(
            svc._session,
            invitee_row.id,
            f"{actor_name} invited you to \"{tree_name}\"",
            f"Join \"{tree_name}\" as {body.role.value.capitalize()} on OurFamRoots",
            {"type": "TREE_INVITE", "tree_name": tree_name},
        ))

    return InvitationResponse.from_domain(invitation)


@router.post("/invitations/accept", response_model=MemberResponse)
async def accept_invitation(
    body: AcceptInvitationRequest,
    request: Request,
    current_user: CurrentUserDep,
    svc: CollabDep,
) -> MemberResponse:
    membership = await svc.accept_invitation(
        token=body.token,
        accepting_user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return MemberResponse.from_domain(membership)


@router.delete("/trees/{tree_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def revoke_invitation(
    tree_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: NotAuditorDep,
    svc: CollabDep,
) -> None:
    await svc.revoke_invitation(
        invitation_id=invitation_id,
        tree_id=tree_id,
        actor_id=current_user.id,
        tenant_id=current_user.tenant_id,
        actor_name=f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email,
        app_role=current_user.app_role,
    )


# ── Audit log ──────────────────────────────────────────────────────────────────

@router.get("/trees/{tree_id}/audit-log", response_model=list[AuditEntryResponse])
async def get_audit_log(
    tree_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: CollabDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    entity_type: Optional[AuditEntityType] = Query(None),
    entity_id: Optional[uuid.UUID] = Query(None),
    actor_id: Optional[uuid.UUID] = Query(None),
) -> list[AuditEntryResponse]:
    entries = await svc.get_audit_log(
        tree_id=tree_id,
        actor_id=current_user.id,
        limit=limit,
        offset=offset,
        entity_type=entity_type,
        entity_id=entity_id,
        filter_actor_id=actor_id,
        app_role=current_user.app_role,
    )
    return [AuditEntryResponse.from_domain(e) for e in entries]


# ── Version history ────────────────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/persons/{person_id}/versions",
    response_model=list[PersonVersionResponse],
)
async def list_person_versions(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: CollabDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[PersonVersionResponse]:
    versions = await svc.get_person_history(
        person_id=person_id,
        tree_id=tree_id,
        actor_id=current_user.id,
        limit=limit,
        offset=offset,
        app_role=current_user.app_role,
    )
    return [PersonVersionResponse.from_domain(v) for v in versions]


@router.post(
    "/trees/{tree_id}/persons/{person_id}/versions/{version_number}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def restore_person_version(
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    version_number: int,
    request: Request,
    current_user: CurrentUserDep,
    svc: CollabDep,
) -> None:
    snapshot = await svc.restore_person_version(
        person_id=person_id,
        tree_id=tree_id,
        version_number=version_number,
        actor_id=current_user.id,
        actor_name=f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email,
        tenant_id=current_user.tenant_id,
        ip_address=request.client.host if request.client else None,
    )
    # TODO: apply snapshot to persons table via PersonRepository.update_from_snapshot(snapshot)
