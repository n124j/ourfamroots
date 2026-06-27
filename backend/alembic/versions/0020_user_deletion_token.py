"""Add deletion request token columns to users table.

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deletion_request_token", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("deletion_request_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "deletion_request_expires_at")
    op.drop_column("users", "deletion_request_token")
