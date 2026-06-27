"""Add site_settings table for maintenance mode.

Revision ID: 0033
Revises: 0032
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "maintenance_message",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'We are currently performing scheduled maintenance. Please check back soon!'"),
        ),
        sa.Column("updated_by_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    # Seed the single settings row
    op.execute(
        "INSERT INTO site_settings (maintenance_mode, maintenance_message) "
        "VALUES (false, 'We are currently performing scheduled maintenance. Please check back soon!')"
    )


def downgrade() -> None:
    op.drop_table("site_settings")
