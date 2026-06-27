"""Add app_role column to users table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "app_role",
            sa.String(20),
            nullable=False,
            server_default="STANDARD",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "app_role")
