"""add custom_label to family_groups

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "family_groups",
        sa.Column("custom_label", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("family_groups", "custom_label")
