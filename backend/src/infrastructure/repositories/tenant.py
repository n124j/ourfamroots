"""SqlAlchemy implementation of AbstractTenantRepository."""

from __future__ import annotations

from sqlalchemy import exists, select

from src.domain.interfaces.repositories import AbstractTenantRepository
from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.repositories.base import SqlAlchemyRepository


class SqlAlchemyTenantRepository(
    SqlAlchemyRepository[TenantModel],
    AbstractTenantRepository,
):
    model_class = TenantModel

    async def get_by_slug(self, slug: str) -> TenantModel | None:
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        return await self._first(stmt)

    async def exists_by_slug(self, slug: str) -> bool:
        stmt = select(exists().where(TenantModel.slug == slug))
        return bool(await self._scalar(stmt))
