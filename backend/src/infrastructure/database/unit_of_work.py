"""SQLAlchemy Unit of Work.

Wraps a single AsyncSession so that the service layer never touches the
session directly. All repository access goes through `uow.users`,
`uow.tenants`, etc.

Usage (in a service):

    async with uow:
        user = await uow.users.get_by_email(tenant_id, email)
        user.last_login_at = now()
        await uow.users.update(user)
    # commit happens automatically on clean __aexit__
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.unit_of_work import AbstractUnitOfWork
from src.infrastructure.repositories.tenant import SqlAlchemyTenantRepository
from src.infrastructure.repositories.user import SqlAlchemyUserRepository


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """Concrete UoW backed by a single AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Repository accessors ──────────────────────────────────────
    # Created fresh each time the UoW is used so they share the same session.

    @property
    def users(self) -> SqlAlchemyUserRepository:
        return SqlAlchemyUserRepository(self._session)

    @property
    def tenants(self) -> SqlAlchemyTenantRepository:
        return SqlAlchemyTenantRepository(self._session)

    # ── AbstractUnitOfWork interface ──────────────────────────────

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
