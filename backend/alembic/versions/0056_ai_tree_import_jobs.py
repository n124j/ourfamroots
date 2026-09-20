"""Add ai_tree_import_jobs table for the AI screenshot-to-tree import feature.

Revision ID: 0056
Revises: 0055
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_tree_import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("screenshot_storage_key", sa.String(512), nullable=False),
        sa.Column("photo_staging_prefix", sa.String(512), nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_tree_import_jobs_tenant_id", "ai_tree_import_jobs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_tree_import_jobs_tenant_id", table_name="ai_tree_import_jobs")
    op.drop_table("ai_tree_import_jobs")
