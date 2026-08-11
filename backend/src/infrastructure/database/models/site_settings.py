"""SiteSettings ORM model — singleton row for site-wide configuration."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base, TimestampMixin


class SiteSettingsModel(Base, TimestampMixin):
    """Maps to the `site_settings` table. Exactly one row should exist."""

    __tablename__ = "site_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    maintenance_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    maintenance_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(
            "'We are currently performing scheduled maintenance. Please check back soon!'"
        ),
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Site-wide announcement banner — independent of maintenance mode (see
    # 0053_site_banner.py): a non-blocking, time-bounded informational message.
    banner_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    banner_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    banner_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    banner_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Hex colors (e.g. "#4f46e5"); null means "use the frontend's built-in default".
    banner_bg_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    banner_text_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
