"""SQLAlchemy ORM model for media items."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class MediaModel(Base):
    __tablename__ = "media_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_trees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # File identity
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str]      = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int]   = mapped_column(BigInteger, nullable=False)
    category: Mapped[str]          = mapped_column(String(32), nullable=False)   # MediaCategory value

    # Processing
    status: Mapped[str]                    = mapped_column(String(32), nullable=False, default="PENDING")
    celery_task_id: Mapped[str | None]     = mapped_column(String(256), nullable=True)
    processing_error: Mapped[str | None]   = mapped_column(Text, nullable=True)

    # S3 keys (variants)
    original_key: Mapped[str]              = mapped_column(String(1024), nullable=False)
    compressed_key: Mapped[str | None]     = mapped_column(String(1024), nullable=True)
    thumb_200_key: Mapped[str | None]      = mapped_column(String(1024), nullable=True)
    thumb_600_key: Mapped[str | None]      = mapped_column(String(1024), nullable=True)
    preview_key: Mapped[str | None]        = mapped_column(String(1024), nullable=True)
    metadata_key: Mapped[str | None]       = mapped_column(String(1024), nullable=True)

    # Extracted metadata
    image_width: Mapped[int | None]        = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None]       = mapped_column(Integer, nullable=True)
    exif_data: Mapped[dict | None]         = mapped_column(JSON, nullable=True)
    extracted_text: Mapped[str | None]     = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # User-supplied metadata
    title: Mapped[str | None]              = mapped_column(String(512), nullable=True)
    description: Mapped[str | None]        = mapped_column(Text, nullable=True)
    date_circa: Mapped[str | None]         = mapped_column(String(64), nullable=True)
    year: Mapped[int | None]               = mapped_column(Integer, nullable=True)
    tags: Mapped[list[str]]                = mapped_column(ARRAY(String), nullable=False, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
