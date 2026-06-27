"""Add permission_groups and permission_group_assignments tables.

Revision ID: 0016
Revises: 0015
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permission_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("permission_level", sa.String(20), nullable=False),  # VISIBLE | READ | READ_WRITE
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_permission_groups_tenant_name"),
    )
    op.create_index("ix_permission_groups_tenant_id", "permission_groups", ["tenant_id"])

    op.create_table(
        "permission_group_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("group_id", "user_id", "tree_id", name="uq_pga_group_user_tree"),
    )
    op.create_index("ix_pga_group_id", "permission_group_assignments", ["group_id"])
    op.create_index("ix_pga_user_id",  "permission_group_assignments", ["user_id"])
    op.create_index("ix_pga_tree_id",  "permission_group_assignments", ["tree_id"])


def downgrade() -> None:
    op.drop_index("ix_pga_tree_id",  table_name="permission_group_assignments")
    op.drop_index("ix_pga_user_id",  table_name="permission_group_assignments")
    op.drop_index("ix_pga_group_id", table_name="permission_group_assignments")
    op.drop_table("permission_group_assignments")

    op.drop_index("ix_permission_groups_tenant_id", table_name="permission_groups")
    op.drop_table("permission_groups")
