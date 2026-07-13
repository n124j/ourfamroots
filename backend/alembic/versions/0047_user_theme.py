"""Add theme (portal appearance) preference to users.

Revision ID: 0047
Revises: 0046
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("theme", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "theme")
