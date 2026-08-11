"""Add site-wide announcement banner columns to site_settings.

Independent of maintenance_mode/maintenance_message — the banner is a
non-blocking, informational, time-bounded announcement (e.g. "we'll be down
2-4am"), whereas maintenance mode is a hard blocking kill-switch. Both live
on the same singleton site_settings row since they're both "site-wide
Super-Admin-controlled settings," but are otherwise independent.

Revision ID: 0053
Revises: 0052
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("site_settings", sa.Column("banner_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("site_settings", sa.Column("banner_message", sa.Text(), nullable=True))
    op.add_column("site_settings", sa.Column("banner_starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("site_settings", sa.Column("banner_ends_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("site_settings", "banner_ends_at")
    op.drop_column("site_settings", "banner_starts_at")
    op.drop_column("site_settings", "banner_message")
    op.drop_column("site_settings", "banner_enabled")
