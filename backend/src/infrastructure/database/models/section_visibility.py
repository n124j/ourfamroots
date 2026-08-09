"""Section-visibility rule ORM model.

Controls which parts of a person's "More details" panel — and, later,
other tree sections — are visible to which users or user-groups, on a
per-tree basis. Absence of a rule means the section's hard-coded default
applies (currently: hidden for VIEWER-role members only; OWNER/ADMIN/EDITOR
always see it).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base, TimestampMixin


class SectionVisibilityRuleModel(Base, TimestampMixin):
    """An override granting or denying a user/user-group visibility into a
    named tree section (e.g. "person_more_details")."""

    __tablename__ = "section_visibility_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_trees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Identifies which part of the tree this rule governs. Only
    # "person_more_details" exists today; more section keys can be added
    # without a schema change.
    section_key: Mapped[str] = mapped_column(String(60), nullable=False)
    # "USER" | "USER_GROUP"
    subject_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # user.id or user_group.id, depending on subject_type — polymorphic, no FK
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "tree_id", "section_key", "subject_type", "subject_id",
            name="uq_section_visibility_tree_section_subject",
        ),
        CheckConstraint("subject_type IN ('USER', 'USER_GROUP')", name="ck_svr_subject_type"),
    )

    def __repr__(self) -> str:
        return f"<SectionVisibilityRuleModel tree={self.tree_id} section={self.section_key!r}>"
