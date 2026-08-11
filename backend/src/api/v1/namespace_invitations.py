"""Namespace invitation API — invite a Global-namespace user into a specific namespace.

A namespace invitation transfers an existing user account (always one that
currently lives in the Global namespace — see AuthService.register()) into
the target namespace with a chosen role. Accepting changes the user's
tenant_id/app_role in place; it does not create a second account.
"""
from __future__ import annotations

import math
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select, text

from src.api.deps import NamespaceOwnerDep, SessionDep, TokenStoreDep, VerifiedUserDep
from src.api.v1._admin_log import log_admin_action
from src.config import get_settings
from src.domain.collaboration.entities import InvitationStatus
from src.infrastructure.database.global_access import (
    get_global_tenant_id,
    grant_global_tree_access,
)
from src.infrastructure.database.models.collaboration import TreeMemberModel
from src.infrastructure.database.models.namespace_invitation import NamespaceInvitationModel
from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel

router = APIRouter(tags=["Admin", "Namespaces"])

_TTL_HOURS = 168  # 7 days — longer than tree invites, this is an account-level move


class CreateNamespaceInvitationRequest(BaseModel):
    invitee_email: EmailStr
    role: str = Field(..., pattern="^(ADMIN|STANDARD|AUDITOR)$")
    message: Optional[str] = Field(None, max_length=500)


class NamespaceInvitationResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    namespace_name: str
    inviter_name: str
    invitee_email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class NamespaceInvitationsResponse(BaseModel):
    total: int
    items: list[NamespaceInvitationResponse]
    page: int
    page_size: int
    total_pages: int


def _admin_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/admin/namespaces/{namespace_id}/invitations",
    response_model=NamespaceInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a Global-namespace user into this namespace",
)
async def create_namespace_invitation(
    namespace_id: uuid.UUID,
    body: CreateNamespaceInvitationRequest,
    request: Request,
    current_user: NamespaceOwnerDep,
    session: SessionDep,
) -> NamespaceInvitationResponse:
    namespace = await session.get(TenantModel, namespace_id)
    if namespace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Namespace not found")

    global_tenant_id = await get_global_tenant_id(session)
    if global_tenant_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No Global namespace is configured")
    if namespace_id == global_tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot invite users into the Global namespace")

    invitee = (await session.execute(
        select(UserModel).where(UserModel.email == body.invitee_email.lower())
    )).scalars().first()
    if invitee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user found with that email")
    if invitee.tenant_id == namespace_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This user is already a member of this namespace")
    if invitee.tenant_id != global_tenant_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This user already belongs to another namespace — remove them from it before inviting them here",
        )

    now = datetime.now(timezone.utc)

    existing_pending = (await session.execute(
        select(NamespaceInvitationModel).where(
            NamespaceInvitationModel.tenant_id == namespace_id,
            NamespaceInvitationModel.invitee_email == invitee.email,
            NamespaceInvitationModel.status == InvitationStatus.PENDING.value,
            NamespaceInvitationModel.expires_at >= now,
        )
    )).scalars().first()
    if existing_pending is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An invitation is already pending for this email")

    invitation = NamespaceInvitationModel(
        tenant_id=namespace_id,
        inviter_id=current_user.id,
        invitee_user_id=invitee.id,
        invitee_email=invitee.email,
        role=body.role,
        token=secrets.token_urlsafe(32),
        status=InvitationStatus.PENDING.value,
        expires_at=now + timedelta(hours=_TTL_HOURS),
        message=body.message,
    )
    session.add(invitation)
    await log_admin_action(
        session, namespace_id, current_user.id, current_user.full_name,
        "NS_INVITE", invitee.email, _admin_ip(request),
    )
    await session.commit()
    await session.refresh(invitation)

    settings = get_settings()
    accept_url = f"{settings.frontend_base_url}/namespace-invitations/{invitation.token}"
    try:
        from src.infrastructure.email.service import namespace_invitation_email, send_email
        email_html, email_text = namespace_invitation_email(
            invitee_email=invitee.email,
            inviter_name=current_user.full_name,
            namespace_name=namespace.name,
            role=body.role,
            accept_url=accept_url,
            message=body.message,
        )
        await send_email(
            to=invitee.email,
            subject=f"You've been invited to join {namespace.name} on OurFamRoots",
            html_body=email_html,
            text_body=email_text,
        )
    except Exception:
        pass  # email failure must never roll back the invitation

    # In-app notification + Web Push — the invitee always already has an
    # account (namespace invitations only target existing Global-namespace
    # users), so unlike tree invites this doesn't need an "if user exists" guard.
    notif_title = f"{current_user.full_name} invited you to join {namespace.name}"
    notif_body = f"Accept to move your account into {namespace.name} as {body.role.capitalize()}"
    try:
        import json as _json
        await session.execute(
            text("""
                INSERT INTO notifications (user_id, tenant_id, type, title, body, data)
                VALUES (:uid, :tenant_id, 'NAMESPACE_INVITE', :title, :nbody, CAST(:data AS jsonb))
            """),
            {
                "uid": invitee.id,
                "tenant_id": invitee.tenant_id,
                "title": notif_title,
                "nbody": notif_body,
                "data": _json.dumps({
                    "token": invitation.token,
                    "namespace_id": str(namespace_id),
                    "namespace_name": namespace.name,
                    "invited_by_name": current_user.full_name,
                    "role": body.role,
                }),
            },
        )
        await session.commit()
    except Exception:
        pass  # notification failure must never roll back the invitation

    import asyncio as _asyncio
    from src.api.v1.push import send_push_to_user as _push
    _asyncio.create_task(_push(
        session,
        invitee.id,
        notif_title,
        notif_body,
        {"type": "NAMESPACE_INVITE", "namespace_id": str(namespace_id), "namespace_name": namespace.name},
    ))

    return NamespaceInvitationResponse(
        id=invitation.id, tenant_id=namespace_id, namespace_name=namespace.name,
        inviter_name=current_user.full_name, invitee_email=invitee.email,
        role=body.role, status=invitation.status, expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.get(
    "/admin/namespaces/{namespace_id}/invitations",
    response_model=NamespaceInvitationsResponse,
    summary="List invitations sent for this namespace, paginated, most recent first",
)
async def list_namespace_invitations(
    namespace_id: uuid.UUID,
    current_user: NamespaceOwnerDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> NamespaceInvitationsResponse:
    namespace = await session.get(TenantModel, namespace_id)
    if namespace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Namespace not found")

    base = (
        select(NamespaceInvitationModel, UserModel)
        .join(UserModel, UserModel.id == NamespaceInvitationModel.inviter_id)
        .where(NamespaceInvitationModel.tenant_id == namespace_id)
    )
    total = (await session.execute(
        select(func.count()).select_from(
            select(NamespaceInvitationModel.id)
            .where(NamespaceInvitationModel.tenant_id == namespace_id)
            .subquery()
        )
    )).scalar_one()

    offset = (page - 1) * page_size
    rows = (await session.execute(
        base.order_by(NamespaceInvitationModel.created_at.desc()).offset(offset).limit(page_size)
    )).all()

    now = datetime.now(timezone.utc)
    items: list[NamespaceInvitationResponse] = []
    for inv, inviter in rows:
        # Reflect expiry immediately in the list even if nothing has touched
        # this row since it lapsed (status only flips to EXPIRED lazily, on
        # an accept attempt) — Super Admin shouldn't see a stale "Pending".
        display_status = inv.status
        if display_status == InvitationStatus.PENDING.value and inv.expires_at < now:
            display_status = InvitationStatus.EXPIRED.value
        items.append(NamespaceInvitationResponse(
            id=inv.id, tenant_id=namespace_id, namespace_name=namespace.name,
            inviter_name=inviter.full_name, invitee_email=inv.invitee_email,
            role=inv.role, status=display_status, expires_at=inv.expires_at,
            created_at=inv.created_at,
        ))
    return NamespaceInvitationsResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.delete(
    "/admin/namespaces/{namespace_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Revoke a pending namespace invitation",
)
async def revoke_namespace_invitation(
    namespace_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: NamespaceOwnerDep,
    session: SessionDep,
) -> None:
    invitation = (await session.execute(
        select(NamespaceInvitationModel).where(
            NamespaceInvitationModel.id == invitation_id,
            NamespaceInvitationModel.tenant_id == namespace_id,
        )
    )).scalars().first()
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a pending invitation can be revoked")

    invitation.status = InvitationStatus.REVOKED.value
    await log_admin_action(
        session, namespace_id, current_user.id, current_user.full_name,
        "NS_INVITE_REVOKE", invitation.invitee_email, None,
    )
    await session.commit()


@router.get(
    "/namespace-invitations/pending",
    response_model=list[NamespaceInvitationResponse],
    summary="List pending namespace invitations addressed to the current user",
)
async def list_pending_invitations(
    current_user: VerifiedUserDep,
    session: SessionDep,
) -> list[NamespaceInvitationResponse]:
    rows = (await session.execute(
        select(NamespaceInvitationModel, TenantModel, UserModel)
        .join(TenantModel, TenantModel.id == NamespaceInvitationModel.tenant_id)
        .join(UserModel, UserModel.id == NamespaceInvitationModel.inviter_id)
        .where(
            NamespaceInvitationModel.invitee_user_id == current_user.id,
            NamespaceInvitationModel.status == InvitationStatus.PENDING.value,
        )
        .order_by(NamespaceInvitationModel.created_at.desc())
    )).all()

    return [
        NamespaceInvitationResponse(
            id=inv.id, tenant_id=inv.tenant_id, namespace_name=tenant.name,
            inviter_name=inviter.full_name, invitee_email=inv.invitee_email,
            role=inv.role, status=inv.status, expires_at=inv.expires_at,
            created_at=inv.created_at,
        )
        for inv, tenant, inviter in rows
    ]


@router.post(
    "/namespace-invitations/{token}/accept",
    summary="Accept a namespace invitation — transfers your account into that namespace",
)
async def accept_namespace_invitation(
    token: str,
    current_user: VerifiedUserDep,
    session: SessionDep,
    token_store: TokenStoreDep,
) -> dict:
    invitation = (await session.execute(
        select(NamespaceInvitationModel).where(NamespaceInvitationModel.token == token)
    )).scalars().first()

    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This invitation is no longer pending")
    if invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = InvitationStatus.EXPIRED.value
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This invitation has expired")
    if invitation.invitee_user_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This invitation was addressed to a different account — log in as that account to accept it",
        )

    old_tenant_id = current_user.tenant_id

    current_user.tenant_id = invitation.tenant_id
    current_user.app_role = invitation.role

    # Drop stale tree access from the old namespace, then grant this namespace's
    # globally-shared trees (mirrors what happens on normal registration).
    await session.execute(
        delete(TreeMemberModel).where(
            TreeMemberModel.user_id == current_user.id,
            TreeMemberModel.tenant_id == old_tenant_id,
        )
    )
    await grant_global_tree_access(session, current_user.id)

    invitation.status = InvitationStatus.ACCEPTED.value
    invitation.accepted_at = datetime.now(timezone.utc)

    await log_admin_action(
        session, invitation.tenant_id, current_user.id, current_user.full_name,
        "NS_INVITE_ACCEPT", current_user.email, None,
    )
    await session.commit()

    # The JWT's 'tid'/'role' claims are now stale — force re-login everywhere.
    await token_store.revoke_all_for_user(current_user.id)

    return {"tenant_id": str(invitation.tenant_id), "app_role": invitation.role}


@router.post(
    "/namespace-invitations/{token}/decline",
    summary="Decline a namespace invitation",
)
async def decline_namespace_invitation(
    token: str,
    current_user: VerifiedUserDep,
    session: SessionDep,
) -> dict:
    invitation = (await session.execute(
        select(NamespaceInvitationModel).where(NamespaceInvitationModel.token == token)
    )).scalars().first()

    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This invitation is no longer pending")
    if invitation.invitee_user_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This invitation was addressed to a different account",
        )

    invitation.status = InvitationStatus.DECLINED.value

    await log_admin_action(
        session, invitation.tenant_id, current_user.id, current_user.full_name,
        "NS_INVITE_DECLINE", current_user.email, None,
    )
    await session.commit()

    return {"status": invitation.status}
