"""AuthService — register, login, refresh, logout, verify email, password reset.

Design:
- Depends on AbstractUnitOfWork (DB), AbstractRefreshTokenRepository (Redis),
  JWTService, and PasswordHasher.
- Raises domain exceptions only; HTTP mapping is in the API layer.
- Never imports FastAPI or HTTPException.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog

from src.application.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from src.domain.exceptions import (
    AccountLockedError,
    AccountNotVerifiedError,
    ActiveSessionConflictError,
    AlreadyExistsError,
    InvalidCredentialsError,
    NotFoundError,
    TokenExpiredError,
    TokenInvalidError,
)
from src.domain.interfaces.repositories import AbstractRefreshTokenRepository
from src.domain.interfaces.unit_of_work import AbstractUnitOfWork
from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.security.jwt import JWTService
from src.infrastructure.security.password import PasswordHasher

log = structlog.get_logger(__name__)

# Lock account for 15 minutes after 5 failed attempts
_MAX_FAILED_ATTEMPTS = 5
_LOCK_DURATION = timedelta(minutes=15)
# Password reset / email verification tokens expire in 1 hour
_TOKEN_EXPIRE = timedelta(hours=1)


class AuthService:
    def __init__(
        self,
        uow: AbstractUnitOfWork,
        token_store: AbstractRefreshTokenRepository,
        jwt: JWTService,
        hasher: PasswordHasher,
    ) -> None:
        self._uow = uow
        self._tokens = token_store
        self._jwt = jwt
        self._hasher = hasher

    # ── Register ──────────────────────────────────────────────────

    async def register(self, req: RegisterRequest) -> None:
        from src.config import get_settings
        settings = get_settings()
        tenant_slug = settings.default_tenant_slug
        async with self._uow:
            # 1. Create or fetch the Global namespace — every self-registered
            # user lands here first; they move to a specific namespace later
            # via the namespace-invitation transfer flow.
            tenant = await self._uow.tenants.get_by_slug(tenant_slug)
            is_new_tenant = tenant is None
            if tenant is None:
                tenant = TenantModel(
                    name=tenant_slug.replace("-", " ").title(),
                    slug=tenant_slug,
                    is_active=True,
                    is_global=True,
                )
                tenant = await self._uow.tenants.add(tenant)

            # 2. Check email uniqueness across all namespaces — a user has
            # exactly one account, which later moves between namespaces via
            # the namespace-invitation transfer flow rather than a second
            # account being created.
            if await self._uow.users.exists_by_email_anywhere(req.email):
                raise AlreadyExistsError(
                    resource="user", field="email", value=req.email
                )

            # 3. Create user — first user in a new tenant becomes ADMIN automatically
            sa_email = settings.super_admin_email
            if sa_email and req.email.lower() == sa_email.lower():
                role = "SUPER_ADMIN"
            elif is_new_tenant:
                role = "ADMIN"
            else:
                role = "STANDARD"

            auto_verify = settings.auto_verify_email

            verification_token = secrets.token_hex(32)
            user = UserModel(
                tenant_id=tenant.id,
                email=req.email.lower(),
                password_hash=self._hasher.hash(req.password),
                given_name=req.given_name,
                family_name=req.family_name,
                email_verified=auto_verify,
                email_verification_token=None if auto_verify else verification_token,
                app_role=role,
                is_active=True,
                failed_login_attempts=0,
            )
            user = await self._uow.users.add(user)
            await self._uow.users.grant_global_tree_access(user)

        log.info("user.registered", user_id=str(user.id), tenant_id=str(tenant.id))

        if not auto_verify:
            await self._send_verification_email(user.email, user.full_name, verification_token)

    # ── Login ─────────────────────────────────────────────────────

    async def login(self, req: LoginRequest, ip_address: str | None = None) -> tuple[TokenResponse, str]:
        session_conflict = False
        async with self._uow:
            # 1. Find tenant implicitly via email (single-tenant mode for now;
            #    multi-tenant login requires tenant slug in request)
            user = await self._find_user_by_email(req.email)

            # 2. Check account is active
            if not user.is_active:
                raise InvalidCredentialsError()

            # 3. Check account lock
            if user.is_locked:
                assert user.locked_until is not None
                retry_in = int((user.locked_until - datetime.now(tz=timezone.utc)).total_seconds())
                raise AccountLockedError(retry_after_seconds=retry_in)

            # 4. Verify password
            if not user.password_hash or not self._hasher.verify(req.password, user.password_hash):
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
                    user.locked_until = datetime.now(tz=timezone.utc) + _LOCK_DURATION
                await self._uow.users.update(user)
                raise InvalidCredentialsError()

            # 5. Check email verification
            if not user.email_verified:
                raise AccountNotVerifiedError()

            # 6. Check for active sessions — require email verification
            from src.config import get_settings
            settings = get_settings()
            if not settings.auto_verify_email:
                has_sessions = await self._tokens.has_active_sessions(user.id)
                if has_sessions:
                    verification_token = secrets.token_hex(32)
                    user.login_verification_token = verification_token
                    user.login_verification_expires_at = datetime.now(tz=timezone.utc) + _TOKEN_EXPIRE
                    await self._uow.users.update(user)
                    session_conflict = True

            if not session_conflict:
                # 7. Auto-promote to SUPER_ADMIN if email matches config
                sa_email = settings.super_admin_email
                if sa_email and user.email.lower() == sa_email.lower():
                    if user.app_role != "SUPER_ADMIN":
                        user.app_role = "SUPER_ADMIN"
                elif user.app_role == "SUPER_ADMIN":
                    user.app_role = "ADMIN"

                # 8. Reset failure counter, update last login
                user.failed_login_attempts = 0
                user.locked_until = None
                user.last_login_at = datetime.now(tz=timezone.utc)
                await self._uow.users.update(user)

                # 9. Record login event
                await self._record_login_event(
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    display_name=user.full_name,
                    email=user.email,
                    success=True,
                    ip_address=ip_address,
                )

        # Raise after UoW commits so the verification token is persisted
        if session_conflict:
            await self._tokens.store_pending_login(
                token=verification_token,
                user_id=user.id,
                ip_address=ip_address,
                expires_in_seconds=int(_TOKEN_EXPIRE.total_seconds()),
            )
            await self._send_login_verification_email(
                email=user.email,
                display_name=user.full_name,
                token=verification_token,
                ip_address=ip_address,
            )
            raise ActiveSessionConflictError()

        log.info("user.login", user_id=str(user.id))
        return await self._issue_tokens(user, remember_me=req.remember_me)

    # ── Refresh ───────────────────────────────────────────────────

    async def refresh(self, refresh_token: str) -> tuple[str, int]:
        """
        Validate refresh token and issue a new access token.
        Returns (new_access_token, expires_in_seconds).
        """
        payload = self._jwt.decode_refresh_token(refresh_token)
        jti = self._jwt.extract_jti(payload)

        if not await self._tokens.exists(jti):
            raise TokenInvalidError("Refresh token has been revoked")

        user_id = self._jwt.extract_user_id(payload)
        tenant_id = self._jwt.extract_tenant_id(payload)

        app_role: str | None = None
        try:
            from src.infrastructure.database.session import get_session_factory
            factory = get_session_factory()
            async with factory() as fresh_session:
                user = await fresh_session.get(UserModel, user_id)
                if user:
                    app_role = user.app_role
        except Exception as exc:
            import structlog
            structlog.get_logger(__name__).warning("refresh.role_lookup_failed", user_id=str(user_id), error=str(exc))

        access_token, _ = self._jwt.create_access_token(user_id, tenant_id, app_role=app_role)
        return access_token, 900  # 15 min in seconds

    # ── Logout ────────────────────────────────────────────────────

    async def logout(self, refresh_token: str, ip_address: str | None = None) -> None:
        try:
            payload = self._jwt.decode_refresh_token(refresh_token)
            jti = self._jwt.extract_jti(payload)
            user_id = self._jwt.extract_user_id(payload)
            tenant_id = self._jwt.extract_tenant_id(payload)
            await self._tokens.revoke(jti)

            # Record logout in login_events
            async with self._uow:
                user = await self._find_user_by_email_by_id(user_id, tenant_id)
                if user:
                    await self._record_login_event(
                        user_id=user.id,
                        tenant_id=user.tenant_id,
                        display_name=user.full_name,
                        email=user.email,
                        success=True,
                        ip_address=ip_address,
                        event_type="LOGOUT",
                    )
        except (TokenExpiredError, TokenInvalidError):
            pass  # Token already invalid — logout is idempotent

    async def logout_all(self, user_id: uuid.UUID) -> None:
        """Revoke all refresh tokens for a user (logout from all devices)."""
        await self._tokens.revoke_all_for_user(user_id)

    # ── Email verification ────────────────────────────────────────

    async def verify_email(self, token: str) -> None:
        async with self._uow:
            user = await self._uow.users.get_by_verification_token(token)
            if user is None:
                raise TokenInvalidError("Invalid or expired verification token")

            user.email_verified = True
            user.email_verified_at = datetime.now(tz=timezone.utc)
            user.email_verification_token = None
            await self._uow.users.update(user)

        log.info("user.email_verified", user_id=str(user.id))

    async def resend_verification(self, email: str) -> None:
        """Re-send the verification email. Silent no-op if already verified or unknown."""
        async with self._uow:
            user = await self._find_user_by_email(email, raise_if_missing=False)
            if user is None or user.email_verified:
                return

            token = secrets.token_hex(32)
            user.email_verification_token = token
            await self._uow.users.update(user)

        await self._send_verification_email(user.email, user.full_name, token)

    # ── Password reset ────────────────────────────────────────────

    async def forgot_password(self, email: str) -> None:
        async with self._uow:
            user = await self._find_user_by_email(email, raise_if_missing=False)
            if user is None:
                return  # silent no-op — avoid email enumeration

            if not user.email_verified:
                raise AccountNotVerifiedError()

            reset_token = secrets.token_hex(32)
            user.password_reset_token = reset_token
            user.password_reset_expires_at = datetime.now(tz=timezone.utc) + _TOKEN_EXPIRE
            await self._uow.users.update(user)

        await self._send_password_reset_email(user.email, user.full_name, reset_token)

    async def reset_password(self, token: str, new_password: str) -> None:
        async with self._uow:
            user = await self._uow.users.get_by_password_reset_token(token)
            if user is None or user.password_reset_expires_at is None:
                raise TokenInvalidError("Invalid or expired reset token")

            if user.password_reset_expires_at < datetime.now(tz=timezone.utc):
                raise TokenExpiredError()

            user.password_hash = self._hasher.hash(new_password)
            user.password_reset_token = None
            user.password_reset_expires_at = None
            user.failed_login_attempts = 0
            user.locked_until = None
            # Using the reset link proves ownership of the email address
            if not user.email_verified:
                user.email_verified = True
                user.email_verified_at = datetime.now(tz=timezone.utc)
                user.email_verification_token = None
            await self._uow.users.update(user)

        # Revoke all refresh tokens so attacker can't reuse old sessions
        await self._tokens.revoke_all_for_user(user.id)
        log.info("user.password_reset", user_id=str(user.id))

    # ── Verify new login (active session takeover) ─────────────────

    async def verify_new_login(self, token: str) -> tuple[TokenResponse, str]:
        pending = await self._tokens.get_pending_login(token)
        if pending is None:
            raise TokenInvalidError("Invalid or expired login verification token")

        new_login_ip = pending.get("ip_address")

        async with self._uow:
            user = await self._uow.users.get_by_login_verification_token(token)
            if user is None:
                raise TokenInvalidError("Invalid or expired login verification token")

            if (
                user.login_verification_expires_at is None
                or user.login_verification_expires_at < datetime.now(tz=timezone.utc)
            ):
                raise TokenExpiredError()

            # Get IP of the last active session from login_events
            old_session_ip = await self._get_last_login_ip(user.id)

            # Revoke all existing sessions
            await self._tokens.revoke_all_for_user(user.id)

            # Clear verification token
            user.login_verification_token = None
            user.login_verification_expires_at = None

            # Auto-promote to SUPER_ADMIN if email matches config
            from src.config import get_settings
            sa_email = get_settings().super_admin_email
            if sa_email and user.email.lower() == sa_email.lower():
                if user.app_role != "SUPER_ADMIN":
                    user.app_role = "SUPER_ADMIN"
            elif user.app_role == "SUPER_ADMIN":
                user.app_role = "ADMIN"

            # Update login state
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = datetime.now(tz=timezone.utc)
            await self._uow.users.update(user)

            # Record login event
            await self._record_login_event(
                user_id=user.id,
                tenant_id=user.tenant_id,
                display_name=user.full_name,
                email=user.email,
                success=True,
                ip_address=new_login_ip,
            )

        # Clean up pending login from Redis
        await self._tokens.delete_pending_login(token)

        # Send session takeover notification email
        await self._send_session_takeover_email(
            email=user.email,
            display_name=user.full_name,
            old_ip=old_session_ip,
        )

        log.info("user.login_verified", user_id=str(user.id), old_ip=old_session_ip)
        return await self._issue_tokens(user, remember_me=False)

    async def _get_last_login_ip(self, user_id: uuid.UUID) -> str | None:
        from sqlalchemy import select
        from src.infrastructure.database.models.login_event import LoginEventModel
        session = self._uow._session  # type: ignore[attr-defined]
        result = await session.execute(
            select(LoginEventModel.ip_address)
            .where(
                LoginEventModel.user_id == user_id,
                LoginEventModel.event_type == "LOGIN",
                LoginEventModel.success.is_(True),
            )
            .order_by(LoginEventModel.occurred_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    # ── Helpers ───────────────────────────────────────────────────

    async def _find_user_by_email(
        self,
        email: str,
        raise_if_missing: bool = True,
    ) -> UserModel | None:
        """
        Looks up a user by email with no tenant/namespace scoping. This is safe
        because email is enforced globally unique at registration and admin
        user-creation time (see AuthService.register(), admin.py::create_user) —
        a user has exactly one account, which moves between namespaces via the
        namespace-invitation transfer flow rather than a second account being
        created for the same email in a different namespace.
        """
        from sqlalchemy import select
        from src.infrastructure.database.models.user import UserModel as _U

        # Access raw session via UoW's internal session (infrastructure concern)
        session = self._uow._session  # type: ignore[attr-defined]
        result = await session.execute(
            select(_U).where(_U.email == email.lower()).limit(1)
        )
        user = result.scalars().first()

        if user is None and raise_if_missing:
            raise InvalidCredentialsError()
        return user

    async def _issue_tokens(
        self,
        user: UserModel,
        remember_me: bool = False,
    ) -> tuple[TokenResponse, str]:
        """Returns (TokenResponse, refresh_token_string).

        The caller (API layer) is responsible for setting the refresh token as
        an HttpOnly cookie — it must NOT be included in the response body.
        """
        access_token, _ = self._jwt.create_access_token(user.id, user.tenant_id, app_role=user.app_role)
        refresh_token_str, refresh_jti = self._jwt.create_refresh_token(user.id, user.tenant_id)

        expire_seconds = self._jwt.refresh_expire_seconds
        await self._tokens.store(refresh_jti, user.id, expire_seconds)

        token_response = TokenResponse(
            access_token=access_token,
            expires_in=900,  # 15 min
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        return token_response, refresh_token_str

    async def _send_verification_email(
        self,
        email: str,
        display_name: str,
        token: str,
    ) -> None:
        from src.config import get_settings
        from src.infrastructure.email.service import send_email, verification_email
        settings = get_settings()
        verify_url = f"{settings.frontend_base_url}/verify-email?token={token}"
        html, text = verification_email(display_name, verify_url)
        await send_email(
            to=email,
            subject="Verify your OurFamRoots email address",
            html_body=html,
            text_body=text,
        )

    async def _send_password_reset_email(
        self,
        email: str,
        display_name: str,
        token: str,
    ) -> None:
        from src.config import get_settings
        from src.infrastructure.email.service import send_email, password_reset_email
        settings = get_settings()
        reset_url = f"{settings.frontend_base_url}/reset-password?token={token}"
        html, text = password_reset_email(display_name, reset_url)
        await send_email(
            to=email,
            subject="Reset your OurFamRoots password",
            html_body=html,
            text_body=text,
        )

    async def _send_login_verification_email(
        self,
        email: str,
        display_name: str,
        token: str,
        ip_address: str | None,
    ) -> None:
        from src.config import get_settings
        from src.infrastructure.email.service import send_email, login_verification_email
        settings = get_settings()
        verify_url = f"{settings.frontend_base_url}/verify-new-login?token={token}"
        html, text = login_verification_email(display_name, verify_url, ip_address)
        await send_email(
            to=email,
            subject="Verify new login to your OurFamRoots account",
            html_body=html,
            text_body=text,
        )

    async def _send_session_takeover_email(
        self,
        email: str,
        display_name: str,
        old_ip: str | None,
    ) -> None:
        from src.config import get_settings
        from src.infrastructure.email.service import send_email, session_takeover_email
        settings = get_settings()
        change_pw_url = f"{settings.frontend_base_url}/settings/security"
        html, text = session_takeover_email(display_name, old_ip, change_pw_url)
        await send_email(
            to=email,
            subject="Security alert: New login to your OurFamRoots account",
            html_body=html,
            text_body=text,
        )

    async def _find_user_by_email_by_id(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> "UserModel | None":
        from sqlalchemy import select
        from src.infrastructure.database.models.user import UserModel as _U
        session = self._uow._session  # type: ignore[attr-defined]
        result = await session.execute(
            select(_U).where(_U.id == user_id, _U.tenant_id == tenant_id).limit(1)
        )
        return result.scalars().first()

    async def _record_login_event(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        display_name: str,
        email: str,
        success: bool,
        ip_address: str | None,
        event_type: str = "LOGIN",
    ) -> None:
        from src.infrastructure.database.models.login_event import LoginEventModel
        session = self._uow._session  # type: ignore[attr-defined]
        event = LoginEventModel(
            tenant_id=tenant_id,
            user_id=user_id,
            user_display_name=display_name,
            user_email=email,
            event_type=event_type,
            success=success,
            ip_address=ip_address,
        )
        session.add(event)
