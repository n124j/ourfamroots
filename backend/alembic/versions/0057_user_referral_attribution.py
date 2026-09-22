"""Add referral attribution columns to users: which user (if any) referred
this signup, and through which channel (e.g. tree_invite, share_link).
Nullable, backfill-free — only newly attributed signups get a value.

Revision ID: 0057
Revises: 0056
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "referred_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("referral_channel", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "referral_channel")
    op.drop_column("users", "referred_by_user_id")
