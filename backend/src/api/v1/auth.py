"""Authentication router — /api/v1/auth/*"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.deps import (
    HasherDep,
    JWTServiceDep,
    SettingsDep,
    TokenStoreDep,
    UoWDep,
)

from src.application.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
    VerifyNewLoginRequest,
)
from src.application.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


def _get_auth_service(uow: UoWDep, token_store: TokenStoreDep, jwt: JWTServiceDep, hasher: HasherDep) -> AuthService:
    return AuthService(uow=uow, token_store=token_store, jwt=jwt, hasher=hasher)


def _set_refresh_cookie(response: Response, token: str, secure: bool = False) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=secure,          # False in dev (HTTP), True in production (HTTPS)
        samesite="lax",         # "lax" works for same-site cross-port (localhost:7006 → 7004)
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


@router.post(
    "/register",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Register a new user — verification email is sent; no session is created",
)
async def register(
    req: RegisterRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> None:
    await svc.register(req)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    svc: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    ip = request.client.host if request.client else None
    token_resp, refresh_token = await svc.login(req, ip_address=ip)
    _set_refresh_cookie(response, refresh_token, secure=settings.is_production)
    return token_resp


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Exchange a refresh token for a new access token",
)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    svc: AuthService = Depends(_get_auth_service),
) -> RefreshResponse:
    if not refresh_token:
        from src.domain.exceptions import TokenInvalidError
        raise TokenInvalidError("Refresh token cookie is missing")

    access_token, expires_in = await svc.refresh(refresh_token)
    return RefreshResponse(access_token=access_token, expires_in=expires_in)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Revoke the current refresh token",
)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    svc: AuthService = Depends(_get_auth_service),
) -> None:
    if refresh_token:
        ip = request.client.host if request.client else None
        await svc.logout(refresh_token, ip_address=ip)
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/api/v1/auth",
        httponly=True,
        samesite="lax",
    )


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Verify email address using the token sent by email",
)
async def verify_email(
    req: VerifyEmailRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> None:
    await svc.verify_email(req.token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Resend the email verification link",
)
async def resend_verification(
    req: ForgotPasswordRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> None:
    await svc.resend_verification(req.email)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Request a password reset email",
)
async def forgot_password(
    req: ForgotPasswordRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> None:
    await svc.forgot_password(req.email)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Reset password using the token from email",
)
async def reset_password(
    req: ResetPasswordRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> None:
    await svc.reset_password(req.token, req.new_password)


@router.post(
    "/verify-new-login",
    response_model=TokenResponse,
    summary="Verify a new login when the account has active sessions",
)
async def verify_new_login(
    req: VerifyNewLoginRequest,
    response: Response,
    settings: SettingsDep,
    svc: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    token_resp, refresh_token = await svc.verify_new_login(req.token)
    _set_refresh_cookie(response, refresh_token, secure=settings.is_production)
    return token_resp
