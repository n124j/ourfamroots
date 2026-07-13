"""FastAPI dependency functions.

Usage in routers:

    @router.get("/me")
    async def get_me(
        user: UserModel = Depends(get_current_user),
        uow: AbstractUnitOfWork = Depends(get_uow),
    ):
        ...
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException
from src.config import Settings, get_settings
from src.domain.collaboration.entities import AppRole
from src.domain.exceptions import AccountNotVerifiedError, AuthenticationError, TokenInvalidError
from src.domain.interfaces.repositories import AbstractRefreshTokenRepository
from src.domain.interfaces.unit_of_work import AbstractUnitOfWork
from src.infrastructure.cache.redis import RedisRefreshTokenRepository, get_redis
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.database.session import get_db_session
from src.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from src.infrastructure.security.jwt import JWTService
from src.infrastructure.security.password import PasswordHasher


# ── Settings ──────────────────────────────────────────────────────

def get_settings_dep() -> Settings:
    return get_settings()

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


# ── JWT service ───────────────────────────────────────────────────

def get_jwt_service(settings: SettingsDep) -> JWTService:
    return JWTService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
        refresh_token_expire_days=settings.jwt_refresh_token_expire_days,
    )

JWTServiceDep = Annotated[JWTService, Depends(get_jwt_service)]


# ── Password hasher ───────────────────────────────────────────────

def get_password_hasher() -> PasswordHasher:
    return PasswordHasher()

HasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


# ── Database session & Unit of Work ───────────────────────────────

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_uow(session: SessionDep) -> AsyncGenerator[AbstractUnitOfWork, None]:
    yield SqlAlchemyUnitOfWork(session)

UoWDep = Annotated[AbstractUnitOfWork, Depends(get_uow)]


# ── Redis / refresh-token store ───────────────────────────────────

def get_token_store() -> AbstractRefreshTokenRepository:
    return RedisRefreshTokenRepository(get_redis())

TokenStoreDep = Annotated[AbstractRefreshTokenRepository, Depends(get_token_store)]


# ── Current user ──────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    session: SessionDep,
    jwt: JWTServiceDep,
) -> UserModel:
    """
    Resolve the authenticated user from the request state populated by
    TenantMiddleware. Raises 401 if the token is missing or invalid.
    """
    user_id_str: str | None = getattr(request.state, "user_id", None)
    tenant_id_str: str | None = getattr(request.state, "tenant_id", None)

    if not user_id_str or not tenant_id_str:
        raise AuthenticationError("Authentication required")

    try:
        user_id = uuid.UUID(user_id_str)
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError as exc:
        raise TokenInvalidError("Malformed token claims") from exc

    from sqlalchemy import select
    result = await session.execute(
        select(UserModel).where(
            UserModel.id == user_id,
            UserModel.tenant_id == tenant_id,
            UserModel.is_active.is_(True),
        )
    )
    user = result.scalars().first()
    if user is None:
        raise AuthenticationError("User not found or inactive")

    return user

CurrentUserDep = Annotated[UserModel, Depends(get_current_user)]


async def require_verified_user(user: CurrentUserDep) -> UserModel:
    """Like get_current_user but also requires email to be verified."""
    if not user.email_verified:
        raise AccountNotVerifiedError("Email verification required")
    return user

VerifiedUserDep = Annotated[UserModel, Depends(require_verified_user)]


async def require_not_auditor(user: VerifiedUserDep) -> UserModel:
    """Block auditor accounts from any write operation."""
    if user.app_role == AppRole.AUDITOR:
        raise HTTPException(status_code=403, detail="Auditor accounts are read-only")
    return user

NotAuditorDep = Annotated[UserModel, Depends(require_not_auditor)]


async def require_direct_edit_allowed(
    tree_id: uuid.UUID,
    user: NotAuditorDep,
    session: SessionDep,
) -> UserModel:
    """Blocks direct writes to a tree that must instead go through the
    change-request ("Post") flow: a globally-shared tree for anyone but its
    OWNER, or a draft tree that's already been posted and is awaiting review."""
    from sqlalchemy import text

    row = (await session.execute(
        text("""
            SELECT
                tm.role,
                EXISTS (
                    SELECT 1 FROM permission_group_trees pgt
                    JOIN permission_groups pg ON pg.id = pgt.group_id
                    WHERE pgt.tree_id = :tid AND pg.is_global = true
                ) AS is_globally_shared,
                EXISTS (
                    SELECT 1 FROM tree_change_requests tcr
                    WHERE tcr.draft_tree_id = :tid AND tcr.status = 'PENDING'
                ) AS is_pending_draft
            FROM tree_members tm
            WHERE tm.tree_id = :tid AND tm.user_id = :uid
        """),
        {"tid": tree_id, "uid": user.id},
    )).first()

    if row is not None:
        if row.is_pending_draft:
            raise HTTPException(
                status_code=403,
                detail="This proposal has already been submitted and is awaiting the owner's review.",
            )
        if row.is_globally_shared and row.role != "OWNER":
            raise HTTPException(
                status_code=403,
                detail="This tree is globally shared — submit your changes as a proposal instead.",
            )
    return user

EditableTreeDep = Annotated[UserModel, Depends(require_direct_edit_allowed)]


async def require_admin(user: VerifiedUserDep) -> UserModel:
    """Restrict endpoint to system administrators (ADMIN or SUPER_ADMIN)."""
    if user.app_role not in (AppRole.ADMIN, AppRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user

AdminUserDep = Annotated[UserModel, Depends(require_admin)]


async def require_super_admin(user: VerifiedUserDep) -> UserModel:
    """Restrict endpoint to the single Super Administrator only."""
    if user.app_role != AppRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Administrator access required")
    return user

SuperAdminDep = Annotated[UserModel, Depends(require_super_admin)]


async def require_namespace_owner_or_super_admin(
    namespace_id: uuid.UUID,
    user: VerifiedUserDep,
) -> UserModel:
    """Restrict endpoint to the Super Administrator, or an ADMIN of the target namespace."""
    if user.app_role == AppRole.SUPER_ADMIN:
        return user
    if user.app_role == AppRole.ADMIN and user.tenant_id == namespace_id:
        return user
    raise HTTPException(status_code=403, detail="Namespace administrator access required")

NamespaceOwnerDep = Annotated[UserModel, Depends(require_namespace_owner_or_super_admin)]
