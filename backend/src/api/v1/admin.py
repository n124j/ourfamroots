"""Admin API — user management (ADMIN app_role only)."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text

from src.api.deps import AdminUserDep, SessionDep, SuperAdminDep, TokenStoreDep
from src.api.v1._admin_log import log_admin_action
from src.domain.collaboration.entities import AppRole
from src.config import get_settings
from src.infrastructure.database.global_access import grant_global_tree_access
from src.infrastructure.database.models.login_event import LoginEventModel
from src.infrastructure.database.models.user import UserModel

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Response / request schemas ─────────────────────────────────────────────────

class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    given_name: Optional[str]
    family_name: Optional[str]
    avatar_url: Optional[str] = None
    app_role: str
    email_verified: bool
    is_active: bool
    last_login_at: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class AdminUsersResponse(BaseModel):
    total: int
    items: list[AdminUserResponse]
    page: int
    page_size: int
    total_pages: int


class CreateUserRequest(BaseModel):
    email: EmailStr
    given_name: str = Field(..., min_length=1, max_length=100)
    family_name: str = Field("", max_length=100)
    app_role: str = Field("STANDARD", pattern="^(ADMIN|STANDARD|AUDITOR)$")


class UpdateUserRequest(BaseModel):
    given_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    app_role: Optional[str] = Field(None, pattern="^(ADMIN|STANDARD|AUDITOR|SUPER_ADMIN)$")
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _presign_avatar(url: str | None) -> str | None:
    if url and not url.startswith("http"):
        from src.api.v1._s3 import presign_photo
        return presign_photo(url)
    return url


def _serialize(u: UserModel) -> AdminUserResponse:
    return AdminUserResponse(
        id=u.id,
        email=u.email,
        given_name=u.given_name,
        family_name=u.family_name,
        avatar_url=_presign_avatar(getattr(u, "avatar_url", None)),
        app_role=u.app_role,
        email_verified=u.email_verified,
        is_active=u.is_active,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
        created_at=u.created_at.isoformat(),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED,
             summary="Create a new user and send them an activation email")
async def create_user(
    body: CreateUserRequest,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> AdminUserResponse:
    from src.infrastructure.security.password import PasswordHasher

    # Check email uniqueness within tenant
    existing = (await session.execute(
        select(UserModel).where(
            UserModel.tenant_id == current_user.tenant_id,
            UserModel.email == body.email.lower(),
        )
    )).scalars().first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A user with email {body.email} already exists")

    # Create with a random unusable password — user will set their own via the activation link
    hasher = PasswordHasher()
    reset_token = secrets.token_hex(32)
    user = UserModel(
        tenant_id=current_user.tenant_id,
        email=body.email.lower(),
        password_hash=hasher.hash(secrets.token_hex(32)),  # random, unusable
        given_name=body.given_name,
        family_name=body.family_name or None,
        app_role=body.app_role,
        email_verified=False,
        is_active=True,
        password_reset_token=reset_token,
        password_reset_expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=24),
    )
    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        current_user.full_name, "ADMIN_CREATE", user.email, _admin_ip(request),
    )
    session.add(user)
    await session.commit()  # commit before returning so fetchUsers sees the row immediately
    await session.refresh(user)

    await grant_global_tree_access(session, current_user.tenant_id, user.id)
    await session.commit()

    # Send activation email
    try:
        from src.infrastructure.email.service import account_created_email, send_email
        settings = get_settings()
        activate_url = f"{settings.frontend_base_url}/reset-password?token={reset_token}"
        creator_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
        display = f"{body.given_name} {body.family_name}".strip()
        html, text = account_created_email(display, activate_url, creator_name)
        await send_email(
            to=user.email,
            subject="Your OurFamRoots account has been created",
            html_body=html,
            text_body=text,
        )
    except Exception:
        pass  # email failure must never roll back the user creation

    return _serialize(user)


@router.get("/users", response_model=AdminUsersResponse, summary="List all users in tenant")
async def list_users(
    current_user: AdminUserDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=200),
    app_role: Optional[str] = Query(None),
    verified: Optional[bool] = Query(None),
    sort: str = Query("created_at_desc", pattern="^(created_at_desc|created_at_asc|name_asc|email_asc|last_login_desc)$"),
) -> AdminUsersResponse:
    import math

    base = select(UserModel).where(UserModel.tenant_id == current_user.tenant_id)

    if search:
        pattern = f"%{search}%"
        base = base.where(
            (UserModel.email.ilike(pattern))
            | (UserModel.given_name.ilike(pattern))
            | (UserModel.family_name.ilike(pattern))
        )
    if app_role:
        base = base.where(UserModel.app_role == app_role)
    if verified is not None:
        base = base.where(UserModel.email_verified == verified)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    order_map = {
        "created_at_desc": UserModel.created_at.desc(),
        "created_at_asc":  UserModel.created_at.asc(),
        "name_asc":        (UserModel.given_name.asc(), UserModel.family_name.asc()),
        "email_asc":       UserModel.email.asc(),
        "last_login_desc": UserModel.last_login_at.desc().nullslast(),
    }
    order_clause = order_map[sort]
    if isinstance(order_clause, tuple):
        base = base.order_by(*order_clause)
    else:
        base = base.order_by(order_clause)

    offset = (page - 1) * page_size
    rows = (await session.execute(base.offset(offset).limit(page_size))).scalars().all()

    return AdminUsersResponse(
        total=total,
        items=[_serialize(u) for u in rows],
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse, summary="Update a user's profile or role")
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> AdminUserResponse:
    user = (await session.execute(
        select(UserModel).where(
            UserModel.id == user_id,
            UserModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()

    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.id == current_user.id:
        if body.app_role is not None and body.app_role != "ADMIN":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot change your own role")
        if body.is_active is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot deactivate your own account")
        if body.email_verified is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot unverify your own account")

    if body.given_name is not None:
        user.given_name = body.given_name or None
    if body.family_name is not None:
        user.family_name = body.family_name or None
    if body.app_role is not None:
        user.app_role = body.app_role
    if body.is_active is not None:
        user.is_active = body.is_active

    verification_changed: bool | None = None  # True=verified, False=unverified
    if body.email_verified is not None and body.email_verified != user.email_verified:
        verification_changed = body.email_verified
        user.email_verified = body.email_verified
        if body.email_verified:
            user.email_verified_at = datetime.now(tz=timezone.utc)
            user.email_verification_token = None
        else:
            user.email_verified_at = None

    user_email = user.email
    user_name = user.full_name

    # Log each significant change as a separate activity entry
    if verification_changed is True:
        await log_admin_action(session, current_user.tenant_id, current_user.id,
                                current_user.full_name, "ADMIN_VERIFY", user_email, _admin_ip(request))
    elif verification_changed is False:
        await log_admin_action(session, current_user.tenant_id, current_user.id,
                                current_user.full_name, "ADMIN_UNVERIFY", user_email, _admin_ip(request))
    if body.is_active is not None:
        event = "ADMIN_ACTIVATE" if body.is_active else "ADMIN_DEACTIVATE"
        await log_admin_action(session, current_user.tenant_id, current_user.id,
                                current_user.full_name, event, user_email, _admin_ip(request))
    if verification_changed is None and body.is_active is None:
        await log_admin_action(session, current_user.tenant_id, current_user.id,
                                current_user.full_name, "ADMIN_UPDATE", user_email, _admin_ip(request))

    await session.commit()
    await session.refresh(user)

    if verification_changed is True:
        await _send_admin_verified_email(user_email, user_name)
    elif verification_changed is False:
        await _send_admin_unverified_email(user_email, user_name)

    return _serialize(user)


@router.post("/users/{user_id}/verify", response_model=AdminUserResponse, summary="Manually verify a user's email")
async def verify_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
) -> AdminUserResponse:
    user = (await session.execute(
        select(UserModel).where(
            UserModel.id == user_id,
            UserModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()

    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.email_verified = True
    user.email_verified_at = datetime.now(tz=timezone.utc)
    user.email_verification_token = None
    user_email = user.email
    user_name = user.full_name
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "ADMIN_VERIFY", user_email, _admin_ip(request))
    await session.commit()
    await session.refresh(user)
    await _send_admin_verified_email(user_email, user_name)
    return _serialize(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Deactivate (soft-delete) a user",
)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: AdminUserDep,
    session: SessionDep,
    token_store: TokenStoreDep,
) -> None:
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot deactivate your own account")

    user = (await session.execute(
        select(UserModel).where(
            UserModel.id == user_id,
            UserModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()

    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user_email = user.email
    user_name = user.full_name
    user.is_active = False
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "ADMIN_DEACTIVATE", user_email, _admin_ip(request))
    await session.commit()
    # Revoke all active sessions so they can't keep using the app
    await token_store.revoke_all_for_user(user_id)
    await _send_account_deactivated_email(user_email, user_name)


@router.delete(
    "/users/{user_id}/purge",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Permanently delete a deactivated user (Super Admin only)",
)
async def purge_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: SuperAdminDep,
    session: SessionDep,
    token_store: TokenStoreDep,
) -> None:
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete your own account")

    user = (await session.execute(
        select(UserModel).where(
            UserModel.id == user_id,
            UserModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()

    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "User must be deactivated before they can be permanently deleted",
        )

    # Capture identifying details for the audit trail before the row is gone for good.
    target_display = f"{user.email} (role={user.app_role}, id={user.id})"

    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        current_user.full_name, "ADMIN_DELETE", target_display, _admin_ip(request),
    )
    await session.delete(user)
    await session.commit()
    # Revoke any lingering sessions/tokens tied to the now-deleted user id
    await token_store.revoke_all_for_user(user_id)


# ── Email helpers ──────────────────────────────────────────────────────────────

def _admin_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _send_account_deactivated_email(email: str, display_name: str) -> None:
    try:
        from src.infrastructure.email.service import account_deactivated_email, send_email
        html, text = account_deactivated_email(display_name)
        await send_email(
            to=email,
            subject="Your OurFamRoots account has been deactivated",
            html_body=html,
            text_body=text,
        )
    except Exception:
        pass


async def _send_admin_verified_email(email: str, display_name: str) -> None:
    try:
        from src.config import get_settings
        from src.infrastructure.email.service import account_verified_by_admin_email, send_email
        settings = get_settings()
        login_url = f"{settings.frontend_base_url}/login"
        html, text = account_verified_by_admin_email(display_name, login_url)
        await send_email(
            to=email,
            subject="Your OurFamRoots account has been verified",
            html_body=html,
            text_body=text,
        )
    except Exception:
        pass


@router.get(
    "/trees/{tree_id}/persons",
    summary="List persons in a tree (for admin merge picker)",
)
async def list_tree_persons_admin(
    tree_id: uuid.UUID,
    current_user: AdminUserDep,
    session: SessionDep,
) -> list[dict]:
    from sqlalchemy import text
    if current_user.app_role != AppRole.AUDITOR:
        member_row = (await session.execute(
            text("SELECT 1 FROM tree_members WHERE tree_id = :tid AND user_id = :uid LIMIT 1"),
            {"tid": tree_id, "uid": current_user.id},
        )).first()
        if not member_row:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of this tree")
    rows = (await session.execute(text("""
        SELECT id, display_given_name, display_surname, photo_url, birth_year, sex
        FROM persons
        WHERE tree_id = :tid AND tenant_id = :tenant AND is_deleted = false
        ORDER BY display_surname, display_given_name
    """), {"tid": tree_id, "tenant": current_user.tenant_id})).fetchall()
    from src.api.v1._s3 import presign_photo
    return [
        {
            "id": str(r.id),
            "display_given_name": r.display_given_name or "",
            "display_surname": r.display_surname or "",
            "photo_url": presign_photo(r.photo_url),
            "birth_year": r.birth_year,
            "sex": r.sex or "UNKNOWN",
        }
        for r in rows
    ]


async def _send_admin_unverified_email(email: str, display_name: str) -> None:
    try:
        from src.infrastructure.email.service import account_unverified_by_admin_email, send_email
        html, text = account_unverified_by_admin_email(display_name)
        await send_email(
            to=email,
            subject="Your OurFamRoots account verification has been removed",
            html_body=html,
            text_body=text,
        )
    except Exception:
        pass
