"""Add cover_emoji to family_trees."""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "family_trees",
        sa.Column("cover_emoji", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("family_trees", "cover_emoji")
