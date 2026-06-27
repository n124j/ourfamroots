"""Add union_date_year and union_end_date_year columns to family_groups.

Revision ID: 0032
Revises: 0031
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "family_groups",
        sa.Column("union_date_year", sa.Integer(), nullable=True),
    )
    op.add_column(
        "family_groups",
        sa.Column("union_end_date_year", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("family_groups", "union_end_date_year")
    op.drop_column("family_groups", "union_date_year")
