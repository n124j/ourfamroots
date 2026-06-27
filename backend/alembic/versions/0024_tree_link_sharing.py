"""Add link_sharing and share_token to family_trees.

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "family_trees",
        sa.Column("link_sharing", sa.String(16), nullable=False, server_default="RESTRICTED"),
    )
    op.add_column(
        "family_trees",
        sa.Column(
            "share_token",
            UUID(as_uuid=True),
            nullable=False,
            server_default=text("gen_random_uuid()"),
        ),
    )
    op.create_index("ix_family_trees_share_token", "family_trees", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_family_trees_share_token", table_name="family_trees")
    op.drop_column("family_trees", "share_token")
    op.drop_column("family_trees", "link_sharing")
