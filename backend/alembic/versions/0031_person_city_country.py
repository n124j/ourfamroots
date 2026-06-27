"""Add city and country columns to persons.

Revision ID: 0031
Revises: 0030
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column("city", sa.String(200), nullable=True),
    )
    op.add_column(
        "persons",
        sa.Column("country", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("persons", "country")
    op.drop_column("persons", "city")
