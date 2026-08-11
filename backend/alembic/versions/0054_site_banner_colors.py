"""Add customizable foreground/background colors to the announcement banner.

Both nullable — null means "use the app's default banner colors" (the
frontend falls back to its built-in indigo/white when unset).

Revision ID: 0054
Revises: 0053
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("site_settings", sa.Column("banner_bg_color", sa.String(7), nullable=True))
    op.add_column("site_settings", sa.Column("banner_text_color", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("site_settings", "banner_text_color")
    op.drop_column("site_settings", "banner_bg_color")
