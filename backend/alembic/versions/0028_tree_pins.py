"""Add tree_pins table — per-user pinned trees on the Dashboard.

Revision ID: 0028
Revises: 0027
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tree_pins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "tree_id", name="uq_tree_pin_user_tree"),
    )
    op.create_index("ix_tree_pins_user_id", "tree_pins", ["user_id"])
    op.create_index("ix_tree_pins_tree_id", "tree_pins", ["tree_id"])


def downgrade() -> None:
    op.drop_index("ix_tree_pins_tree_id", table_name="tree_pins")
    op.drop_index("ix_tree_pins_user_id", table_name="tree_pins")
    op.drop_table("tree_pins")
