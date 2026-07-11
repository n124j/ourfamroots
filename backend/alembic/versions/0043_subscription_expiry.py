"""Add expires_at / reminder_sent_at to subscriptions (promotional/time-limited subscriptions).

Revision ID: 0043
Revises: 0042
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "reminder_sent_at")
    op.drop_column("subscriptions", "expires_at")
