"""Add section_visibility_rules: per-tree overrides for which users/groups
can see specific "More details" sections of a person's profile.

Revision ID: 0048
Revises: 0047
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "section_visibility_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_key", sa.String(60), nullable=False),
        sa.Column("subject_type", sa.String(10), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("subject_type IN ('USER', 'USER_GROUP')", name="ck_svr_subject_type"),
        sa.UniqueConstraint("tree_id", "section_key", "subject_type", "subject_id", name="uq_section_visibility_tree_section_subject"),
    )
    op.create_index("ix_svr_tree_id", "section_visibility_rules", ["tree_id"])
    op.create_index("ix_svr_subject_id", "section_visibility_rules", ["subject_id"])


def downgrade() -> None:
    op.drop_index("ix_svr_subject_id", table_name="section_visibility_rules")
    op.drop_index("ix_svr_tree_id", table_name="section_visibility_rules")
    op.drop_table("section_visibility_rules")
