"""Add MERGE_TREES to audit_action_enum.

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-02
"""
from __future__ import annotations

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'MERGE_TREES'")


def downgrade() -> None:
    pass
