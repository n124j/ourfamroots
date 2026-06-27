"""Redesign permission groups: add group-level trees and members tables.

Revision ID: 0027
Revises: 0026
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permission_group_trees",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("group_id", "tree_id", name="uq_pgt_group_tree"),
    )
    op.create_index("ix_pgt_group_id", "permission_group_trees", ["group_id"])
    op.create_index("ix_pgt_tree_id", "permission_group_trees", ["tree_id"])

    op.create_table(
        "permission_group_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("group_id", "user_id", name="uq_pgm_group_user"),
    )
    op.create_index("ix_pgm_group_id", "permission_group_members", ["group_id"])
    op.create_index("ix_pgm_user_id", "permission_group_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pgm_user_id", table_name="permission_group_members")
    op.drop_index("ix_pgm_group_id", table_name="permission_group_members")
    op.drop_table("permission_group_members")

    op.drop_index("ix_pgt_tree_id", table_name="permission_group_trees")
    op.drop_index("ix_pgt_group_id", table_name="permission_group_trees")
    op.drop_table("permission_group_trees")
