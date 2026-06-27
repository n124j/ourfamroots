"""Add union_date and union_end_date columns to family_groups.

Revision ID: 0030
Revises: 0029
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "family_groups",
        sa.Column("union_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "family_groups",
        sa.Column("union_end_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("family_groups", "union_end_date")
    op.drop_column("family_groups", "union_date")
