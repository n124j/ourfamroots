"""Add is_global flag to permission_groups."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "permission_groups",
        sa.Column("is_global", sa.Boolean, nullable=False, server_default=text("false")),
    )


def downgrade() -> None:
    op.drop_column("permission_groups", "is_global")
