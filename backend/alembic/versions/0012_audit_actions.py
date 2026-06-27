"""Add EXPORT_TREE, IMPORT_TREE, UPDATE_PHOTO to audit_action_enum.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL allows adding enum values but not removing them
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'EXPORT_TREE'")
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'IMPORT_TREE'")
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'UPDATE_PHOTO'")


def downgrade() -> None:
    # Enum value removal is not supported in PostgreSQL
    pass
