"""User and UserOAuthProvider ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base, TenantMixin, TimestampMixin


class UserModel(Base, TenantMixin, TimestampMixin):
    """Maps to the `users` table."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Override TenantMixin.tenant_id to add the FK constraint SQLAlchemy needs
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    given_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'en'")
    )
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'UTC'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_reset_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deletion_request_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deletion_request_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_verification_token: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    login_verification_token: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    login_verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    app_role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'STANDARD'")
    )
    broadcast_unsubscribed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # ── Relationships ─────────────────────────────────────────────
    tenant: Mapped["TenantModel"] = relationship(
        "TenantModel",
        back_populates="users",
        lazy="noload",
        foreign_keys="[UserModel.tenant_id]",
    )
    oauth_providers: Mapped[list["UserOAuthProviderModel"]] = relationship(
        "UserOAuthProviderModel",
        back_populates="user",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    @property
    def full_name(self) -> str:
        parts = [self.given_name, self.family_name]
        return " ".join(p for p in parts if p) or self.email

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        from datetime import timezone
        return self.locked_until > datetime.now(tz=timezone.utc)

    def __repr__(self) -> str:
        return f"<UserModel id={self.id!s} email={self.email!r}>"


class UserOAuthProviderModel(Base, TenantMixin, TimestampMixin):
    """Maps to the `user_oauth_providers` table."""

    __tablename__ = "user_oauth_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="oauth_providers",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "provider_user_id",
            name="uq_oauth_tenant_provider_uid",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserOAuthProviderModel provider={self.provider!r} user_id={self.user_id!s}>"
