"""SqlAlchemy implementation of AbstractUserRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, select

from src.domain.interfaces.repositories import AbstractUserRepository
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.repositories.base import SqlAlchemyRepository


class SqlAlchemyUserRepository(
    SqlAlchemyRepository[UserModel],
    AbstractUserRepository,
):
    model_class = UserModel

    async def get_by_email(
        self, tenant_id: uuid.UUID, email: str
    ) -> UserModel | None:
        stmt = select(UserModel).where(
            UserModel.tenant_id == tenant_id,
            UserModel.email == email.lower(),
        )
        return await self._first(stmt)

    async def get_by_id_and_tenant(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> UserModel | None:
        stmt = select(UserModel).where(
            UserModel.id == user_id,
            UserModel.tenant_id == tenant_id,
        )
        return await self._first(stmt)

    async def exists_by_email(self, tenant_id: uuid.UUID, email: str) -> bool:
        stmt = select(
            exists().where(
                UserModel.tenant_id == tenant_id,
                UserModel.email == email.lower(),
            )
        )
        return bool(await self._scalar(stmt))

    async def get_by_password_reset_token(
        self, token: str
    ) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.password_reset_token == token)
        return await self._first(stmt)

    async def get_by_verification_token(
        self, token: str
    ) -> UserModel | None:
        stmt = select(UserModel).where(
            UserModel.email_verification_token == token
        )
        return await self._first(stmt)

    async def get_by_deletion_token(
        self, token: str
    ) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.deletion_request_token == token)
        return await self._first(stmt)

    async def get_by_login_verification_token(
        self, token: str
    ) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.login_verification_token == token)
        return await self._first(stmt)
