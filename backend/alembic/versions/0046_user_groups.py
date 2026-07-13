"""Add user groups: reusable named collections of users, linkable to permission groups.

Revision ID: 0046
Revises: 0045
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_user_groups_tenant_name"),
    )
    op.create_index("ix_user_groups_tenant_id", "user_groups", ["tenant_id"])

    op.create_table(
        "user_group_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("group_id", "user_id", name="uq_ugm_group_user"),
    )
    op.create_index("ix_ugm_group_id", "user_group_members", ["group_id"])
    op.create_index("ix_ugm_user_id", "user_group_members", ["user_id"])

    op.create_table(
        "permission_group_user_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("permission_group_id", UUID(as_uuid=True), sa.ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_group_id", UUID(as_uuid=True), sa.ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("permission_group_id", "user_group_id", name="uq_pgug_pg_ug"),
    )
    op.create_index("ix_pgug_permission_group_id", "permission_group_user_groups", ["permission_group_id"])
    op.create_index("ix_pgug_user_group_id", "permission_group_user_groups", ["user_group_id"])


def downgrade() -> None:
    op.drop_index("ix_pgug_user_group_id", table_name="permission_group_user_groups")
    op.drop_index("ix_pgug_permission_group_id", table_name="permission_group_user_groups")
    op.drop_table("permission_group_user_groups")

    op.drop_index("ix_ugm_user_id", table_name="user_group_members")
    op.drop_index("ix_ugm_group_id", table_name="user_group_members")
    op.drop_table("user_group_members")

    op.drop_index("ix_user_groups_tenant_id", table_name="user_groups")
    op.drop_table("user_groups")
