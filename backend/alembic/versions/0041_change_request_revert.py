"""Add revert tracking columns to tree_change_requests and REVERT_CHANGE audit action."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'REVERT_CHANGE'"))
    conn.execute(text("BEGIN"))

    op.add_column(
        "tree_change_requests",
        sa.Column("reverted_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "tree_change_requests",
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tree_change_requests", "reverted_at")
    op.drop_column("tree_change_requests", "reverted_by_id")
