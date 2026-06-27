"""Tenant ORM model."""
from __future__ import annotations
import uuid
from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infrastructure.database.base import Base, TimestampMixin


class TenantModel(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    users: Mapped[list["UserModel"]] = relationship(
        "UserModel",
        back_populates="tenant",
        lazy="noload",
        foreign_keys="[UserModel.tenant_id]",
    )

    def __repr__(self) -> str:
        return f"<TenantModel id={self.id!s} slug={self.slug!r}>"
