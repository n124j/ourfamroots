"""
Abstract repository interfaces (ports).

The domain layer defines what repositories must provide.
The infrastructure layer provides the concrete implementations (adapters).
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class AbstractRepository(ABC, Generic[T]):
    """
    Generic read/write repository interface.
    All methods are coroutines — the infrastructure layer is async.
    """

    @abstractmethod
    async def get_by_id(self, entity_id: uuid.UUID) -> T | None:
        """Return entity by primary key, or None if not found."""
        ...

    @abstractmethod
    async def add(self, entity: T) -> T:
        """Persist a new entity and return it (with any DB-generated fields populated)."""
        ...

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Persist changes to an existing entity."""
        ...

    @abstractmethod
    async def delete(self, entity_id: uuid.UUID) -> None:
        """Hard-delete by primary key (use sparingly — prefer soft-delete)."""
        ...


class AbstractUserRepository(AbstractRepository["UserModel"]):  # type: ignore[type-arg]
    """User-specific query methods."""

    @abstractmethod
    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> "UserModel | None":  # type: ignore[name-defined]
        ...

    @abstractmethod
    async def get_by_id_and_tenant(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> "UserModel | None":  # type: ignore[name-defined]
        ...

    @abstractmethod
    async def exists_by_email(self, tenant_id: uuid.UUID, email: str) -> bool:
        ...

    @abstractmethod
    async def get_by_login_verification_token(self, token: str) -> "UserModel | None":  # type: ignore[name-defined]
        ...


class AbstractTenantRepository(AbstractRepository["TenantModel"]):  # type: ignore[type-arg]
    """Tenant-specific query methods."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> "TenantModel | None":  # type: ignore[name-defined]
        ...

    @abstractmethod
    async def exists_by_slug(self, slug: str) -> bool:
        ...


class AbstractRefreshTokenRepository(ABC):
    """Refresh token store — backed by Redis, not the DB."""

    @abstractmethod
    async def store(
        self, jti: str, user_id: uuid.UUID, expires_in_seconds: int
    ) -> None:
        ...

    @abstractmethod
    async def exists(self, jti: str) -> bool:
        ...

    @abstractmethod
    async def revoke(self, jti: str) -> None:
        ...

    @abstractmethod
    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        ...

    @abstractmethod
    async def has_active_sessions(self, user_id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    async def store_pending_login(
        self, token: str, user_id: uuid.UUID, ip_address: str | None, expires_in_seconds: int,
    ) -> None:
        ...

    @abstractmethod
    async def get_pending_login(self, token: str) -> dict | None:
        ...

    @abstractmethod
    async def delete_pending_login(self, token: str) -> None:
        ...
