"""AiTreeImportJob ORM model — tracks an admin's screenshot-to-tree AI extraction job."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base, TimestampMixin


class AiTreeImportJobModel(Base, TimestampMixin):
    """Maps to the `ai_tree_import_jobs` table."""

    __tablename__ = "ai_tree_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    screenshot_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    photo_staging_prefix: Mapped[str] = mapped_column(String(512), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AiTreeImportJobModel id={self.id!r} status={self.status!r}>"
