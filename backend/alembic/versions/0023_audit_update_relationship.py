"""Add UPDATE_RELATIONSHIP to audit_action_enum.

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-08
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'UPDATE_RELATIONSHIP'")


def downgrade() -> None:
    pass
