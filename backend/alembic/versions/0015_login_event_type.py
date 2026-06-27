"""Add event_type column to login_events.

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "login_events",
        sa.Column(
            "event_type",
            sa.String(20),
            nullable=False,
            server_default="LOGIN",
        ),
    )


def downgrade() -> None:
    op.drop_column("login_events", "event_type")
