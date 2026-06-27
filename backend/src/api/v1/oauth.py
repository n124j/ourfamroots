"""OAuth 2.0 endpoints — Google and GitHub Authorization Code flow.

Flow:
  1. GET  /auth/oauth/{provider}           → redirect browser to provider
  2. GET  /auth/oauth/{provider}/callback  → exchange code, issue JWT, redirect to frontend
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from src.api.deps import JWTServiceDep, TokenStoreDep, UoWDep
from src.config import Settings, get_settings
from src.infrastructure.database.models.collaboration import OAuthConnectionModel
from src.infrastructure.database.models.login_event import LoginEventModel
from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.security.oauth import OAuthUserInfo, get_oauth_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/oauth", tags=["oauth"])

SUPPORTED_PROVIDERS = {"google", "github"}
_REFRESH_TTL = 60 * 60 * 24 * 30  # 30 days in seconds


# ── Step 1: redirect to provider ──────────────────────────────────────────────

@router.get("/{provider}")
async def oauth_redirect(
    provider: str,
    settings: Annotated[Settings, Depends(get_settings)],
    next: str | None = Query(default=None, max_length=512),
) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(404, f"Unknown OAuth provider: {provider}")

    client = get_oauth_client(provider, settings)
    state = client.generate_state()
    next_path = _safe_next_path(next)

    resp = RedirectResponse(client.build_authorization_url(state), status_code=302)
    resp.set_cookie(
        key=f"oauth_state_{provider}",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
    )
    resp.set_cookie(
        key=f"oauth_next_{provider}",
        value=next_path,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
    )
    return resp


# ── Step 2: callback from provider ────────────────────────────────────────────

@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    uow: UoWDep,
    jwt_service: JWTServiceDep,
    token_store: TokenStoreDep,
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(404, f"Unknown OAuth provider: {provider}")

    next_path = _safe_next_path(request.cookies.get(f"oauth_next_{provider}"))

    # User clicked "Cancel" / denied access on the provider's consent screen —
    # the provider redirects back with `error` and no `code`.
    if error or not code:
        return _redirect_error(settings, provider, next_path, "oauth_cancelled")

    # Validate CSRF state
    cookie_state = request.cookies.get(f"oauth_state_{provider}")
    if not cookie_state or cookie_state != state:
        return _redirect_error(settings, provider, next_path, "oauth_state_mismatch")

    client = get_oauth_client(provider, settings)

    try:
        access_token = await client.exchange_code(code)
        user_info: OAuthUserInfo = await client.get_user_info(access_token)
    except Exception:
        log.exception("OAuth %s callback failed during token exchange or user-info fetch", provider)
        return _redirect_error(settings, provider, next_path, "oauth_provider_error")

    try:
        async with uow:
            # 1. Find or provision user
            user = await _find_or_create_user(uow, user_info, settings)
            if user is None:
                return _redirect_error(settings, provider, next_path, "oauth_provisioning_disabled")

            # Flush so a brand-new user row exists before the FK-dependent
            # oauth_connections insert below — UserModel/OAuthConnectionModel have
            # no ORM relationship() linking them, so autoflush ordering can't be
            # relied on to insert the user first.
            await uow._session.flush()

            # 2. Upsert OAuth connection record
            result = await uow._session.execute(
                select(OAuthConnectionModel).where(
                    OAuthConnectionModel.provider == provider,
                    OAuthConnectionModel.provider_user_id == user_info.provider_user_id,
                )
            )
            conn = result.scalar_one_or_none()
            if conn:
                conn.last_used_at = datetime.now(timezone.utc)
                conn.avatar_url = user_info.avatar_url
            else:
                uow._session.add(OAuthConnectionModel(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    provider=provider,
                    provider_user_id=user_info.provider_user_id,
                    email=user_info.email,
                    display_name=user_info.display_name,
                    avatar_url=user_info.avatar_url,
                ))

            # 3. Update last login + record login event (mirrors password-login bookkeeping)
            ip_address = request.client.host if request.client else None
            user.last_login_at = datetime.now(timezone.utc)
            uow._session.add(LoginEventModel(
                tenant_id=user.tenant_id,
                user_id=user.id,
                user_display_name=user.full_name,
                user_email=user.email,
                event_type="LOGIN",
                success=True,
                ip_address=ip_address,
            ))

            # 4. Issue JWT pair
            jwt_access, _  = jwt_service.create_access_token(user.id, user.tenant_id, app_role=user.app_role)
            jwt_refresh, jti = jwt_service.create_refresh_token(user.id, user.tenant_id)
            await token_store.store(jti, user.id, _REFRESH_TTL)
            await uow.commit()
    except Exception:
        log.exception("OAuth %s callback failed during user provisioning / DB commit", provider)
        return _redirect_error(settings, provider, next_path, "oauth_db_error")

    # 5. Redirect frontend with token in query param (frontend moves it to memory)
    frontend_url = (
        f"{settings.frontend_base_url}/auth/callback"
        f"?access_token={jwt_access}&provider={provider}"
    )
    resp = RedirectResponse(frontend_url, status_code=302)
    resp.set_cookie(
        key="refresh_token",
        value=jwt_refresh,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        max_age=_REFRESH_TTL,
    )
    resp.delete_cookie(f"oauth_state_{provider}")
    resp.delete_cookie(f"oauth_next_{provider}")
    return resp


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_next_path(next_path: str | None) -> str:
    """Whitelist-free open-redirect guard: only allow same-origin relative paths."""
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/login"

async def _find_or_create_user(
    uow: UoWDep,
    info: OAuthUserInfo,
    settings: Settings,
) -> UserModel | None:
    # Check every tenant for an existing account with this email
    from sqlalchemy import select as sa_select
    result = await uow._session.execute(
        sa_select(UserModel).where(UserModel.email == info.email.lower())
    )
    user = result.scalars().first()
    if user:
        if info.given_name and not user.given_name:
            user.given_name = info.given_name
        if info.family_name and not user.family_name:
            user.family_name = info.family_name
        if info.avatar_url:
            user.avatar_url = info.avatar_url
        return user

    # Auto-provision: resolve the shared tenant by slug (same as registration)
    tenant_slug = settings.default_tenant_slug
    if not tenant_slug:
        return None

    result = await uow._session.execute(
        sa_select(TenantModel).where(TenantModel.slug == tenant_slug)
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = TenantModel(
            name=tenant_slug.replace("-", " ").title(),
            slug=tenant_slug,
        )
        uow._session.add(tenant)
        await uow._session.flush()

    tenant_id = tenant.id

    new_user = UserModel()
    new_user.id = uuid.uuid4()
    new_user.tenant_id = tenant_id
    new_user.email = info.email.lower()
    new_user.given_name = info.given_name or ""
    new_user.family_name = info.family_name or ""
    new_user.avatar_url = info.avatar_url
    new_user.email_verified = info.email_verified
    new_user.email_verified_at = datetime.now(timezone.utc) if info.email_verified else None
    new_user.is_active = True
    new_user.failed_login_attempts = 0

    uow._session.add(new_user)
    return new_user


def _redirect_error(settings: Settings, provider: str, next_path: str, reason: str) -> RedirectResponse:
    separator = "&" if "?" in next_path else "?"
    resp = RedirectResponse(
        f"{settings.frontend_base_url}{next_path}{separator}error={reason}",
        status_code=302,
    )
    resp.delete_cookie(f"oauth_state_{provider}")
    resp.delete_cookie(f"oauth_next_{provider}")
    return resp
