"""Generic SQLAlchemy base repository.

Provides default CRUD implementations for any ORM model that has a UUID `id`
column. Concrete repositories extend this and add query methods specific to
their entity.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.repositories import AbstractRepository
from src.infrastructure.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class SqlAlchemyRepository(AbstractRepository[ModelT], Generic[ModelT]):
    """
    Generic async repository backed by SQLAlchemy.

    Subclasses must set `model_class` to the ORM model they manage:

        class SqlAlchemyUserRepository(SqlAlchemyRepository[UserModel]):
            model_class = UserModel
    """

    model_class: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── AbstractRepository interface ──────────────────────────────

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self._session.get(self.model_class, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.flush()  # populate server-generated fields (id, timestamps)
        await self._session.refresh(entity)
        return entity

    async def update(self, entity: ModelT) -> ModelT:
        # The entity is already tracked by the session; flush writes dirty state.
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity_id: uuid.UUID) -> None:
        entity = await self.get_by_id(entity_id)
        if entity is not None:
            await self._session.delete(entity)
            await self._session.flush()

    # ── Helpers for subclasses ────────────────────────────────────

    async def _first(self, stmt: Any) -> ModelT | None:
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def _all(self, stmt: Any) -> list[ModelT]:
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _scalar(self, stmt: Any) -> Any:
        result = await self._session.execute(stmt)
        return result.scalar()
