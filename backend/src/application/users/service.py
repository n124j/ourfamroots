"""UserService — profile retrieval and mutation for the authenticated user."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog

from src.application.users.schemas import UpdateUserRequest, UserProfileResponse
from src.domain.exceptions import (
    InvalidCredentialsError,
    NotFoundError,
    TokenExpiredError,
    TokenInvalidError,
)
from src.domain.interfaces.repositories import AbstractRefreshTokenRepository
from src.domain.interfaces.unit_of_work import AbstractUnitOfWork
from src.infrastructure.security.password import PasswordHasher

log = structlog.get_logger(__name__)

_DELETION_TOKEN_EXPIRE = timedelta(hours=24)


class UserService:
    def __init__(
        self,
        uow: AbstractUnitOfWork,
        token_store: AbstractRefreshTokenRepository,
        hasher: PasswordHasher,
    ) -> None:
        self._uow = uow
        self._tokens = token_store
        self._hasher = hasher

    async def _oauth_providers(self, user_id: uuid.UUID) -> list[str]:
        from sqlalchemy import select as sa_select
        from src.infrastructure.database.models.user import UserOAuthProviderModel
        result = await self._uow._session.execute(
            sa_select(UserOAuthProviderModel.provider).where(
                UserOAuthProviderModel.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def _to_response(self, user) -> UserProfileResponse:
        resp = UserProfileResponse.model_validate(user)
        resp.oauth_providers = await self._oauth_providers(user.id)
        return resp

    async def get_me(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> UserProfileResponse:
        async with self._uow:
            user = await self._uow.users.get_by_id_and_tenant(user_id, tenant_id)
            if user is None:
                raise NotFoundError(resource="user", identifier=str(user_id))
            return await self._to_response(user)

    async def update_me(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        req: UpdateUserRequest,
    ) -> UserProfileResponse:
        async with self._uow:
            user = await self._uow.users.get_by_id_and_tenant(user_id, tenant_id)
            if user is None:
                raise NotFoundError(resource="user", identifier=str(user_id))

            update_data = req.model_dump(exclude_none=True)
            for field, value in update_data.items():
                setattr(user, field, value)

            user = await self._uow.users.update(user)
            log.info("user.updated", user_id=str(user_id))
            return await self._to_response(user)

    async def change_password(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> None:
        async with self._uow:
            user = await self._uow.users.get_by_id_and_tenant(user_id, tenant_id)
            if user is None:
                raise NotFoundError(resource="user", identifier=str(user_id))

            if not user.password_hash or not self._hasher.verify(current_password, user.password_hash):
                raise InvalidCredentialsError("Current password is incorrect")

            user.password_hash = self._hasher.hash(new_password)
            await self._uow.users.update(user)

        # Revoke all sessions — forces re-login on other devices
        await self._tokens.revoke_all_for_user(user_id)
        log.info("user.password_changed", user_id=str(user_id))

    async def delete_account(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        password: str,
    ) -> None:
        async with self._uow:
            user = await self._uow.users.get_by_id_and_tenant(user_id, tenant_id)
            if user is None:
                raise NotFoundError(resource="user", identifier=str(user_id))

            if not user.password_hash or not self._hasher.verify(password, user.password_hash):
                raise InvalidCredentialsError("Password is incorrect")

            # Soft-delete: mark inactive rather than hard DELETE
            user.is_active = False
            await self._uow.users.update(user)

        await self._tokens.revoke_all_for_user(user_id)
        log.info("user.deleted", user_id=str(user_id))

    async def request_deletion(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        async with self._uow:
            user = await self._uow.users.get_by_id_and_tenant(user_id, tenant_id)
            if user is None:
                raise NotFoundError(resource="user", identifier=str(user_id))

            token = secrets.token_hex(32)
            user.deletion_request_token = token
            user.deletion_request_expires_at = datetime.now(tz=timezone.utc) + _DELETION_TOKEN_EXPIRE
            await self._uow.users.update(user)

        await self._send_deletion_request_email(user.email, user.full_name, token)
        log.info("user.deletion_requested", user_id=str(user_id))

    async def confirm_deletion(self, token: str) -> None:
        async with self._uow:
            user = await self._uow.users.get_by_deletion_token(token)  # type: ignore[attr-defined]
            if user is None or user.deletion_request_expires_at is None:
                raise TokenInvalidError("Invalid or expired deletion token")

            if user.deletion_request_expires_at < datetime.now(tz=timezone.utc):
                raise TokenExpiredError()

            user.is_active = False
            user.deletion_request_token = None
            user.deletion_request_expires_at = None
            await self._uow.users.update(user)
            user_id = user.id

        await self._tokens.revoke_all_for_user(user_id)
        log.info("user.deletion_confirmed", user_id=str(user_id))

    async def _send_deletion_request_email(
        self,
        email: str,
        display_name: str,
        token: str,
    ) -> None:
        from src.config import get_settings
        from src.infrastructure.email.service import send_email, account_deletion_request_email
        settings = get_settings()
        confirm_url = f"{settings.frontend_base_url}/confirm-deletion?token={token}"
        html, text = account_deletion_request_email(display_name, confirm_url)
        await send_email(
            to=email,
            subject="Confirm your OurFamRoots account deletion",
            html_body=html,
            text_body=text,
        )
