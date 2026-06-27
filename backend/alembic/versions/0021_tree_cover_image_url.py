"""add cover_image_url to family_trees

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "family_trees",
        sa.Column("cover_image_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("family_trees", "cover_image_url")
