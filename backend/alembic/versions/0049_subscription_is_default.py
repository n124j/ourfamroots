"""Add subscriptions.is_default: when set, every user in the tenant is
entitled to the subscription's filters automatically, without needing a
subscription_members row (and it covers users who sign up afterward too).

Revision ID: 0049
Revises: 0048
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "is_default")
