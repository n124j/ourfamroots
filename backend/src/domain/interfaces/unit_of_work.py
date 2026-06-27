"""Abstract Unit of Work interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing_extensions import Self

from src.domain.interfaces.repositories import (
    AbstractTenantRepository,
    AbstractUserRepository,
)


class AbstractUnitOfWork(ABC):
    """Manages atomicity across multiple repository operations."""

    users: AbstractUserRepository
    tenants: AbstractTenantRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """Flush and commit the current transaction."""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """Roll back the current transaction."""
        ...
