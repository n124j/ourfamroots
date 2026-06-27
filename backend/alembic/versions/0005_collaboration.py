"""Create collaboration enum types and tables (tree_members, tree_invitations).

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_TREE_ROLES = ("OWNER", "ADMIN", "EDITOR", "VIEWER")
_INV_STATUSES = ("PENDING", "ACCEPTED", "DECLINED", "EXPIRED", "REVOKED")


def upgrade() -> None:
    op.create_table(
        "tree_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.Enum(*_TREE_ROLES, name="tree_role_enum"), nullable=False, server_default=sa.text("'VIEWER'")),
        sa.Column("invited_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tree_id", "user_id", name="uq_tree_member"),
    )

    op.create_table(
        "tree_invitations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inviter_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invitee_email", sa.String(255), nullable=False, index=True),
        sa.Column("role", sa.Enum(*_TREE_ROLES, name="tree_role_enum", create_type=False), nullable=False),
        sa.Column("token", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("status", sa.Enum(*_INV_STATUSES, name="invitation_status_enum"), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("tree_invitations")
    op.drop_table("tree_members")
    op.execute("DROP TYPE IF EXISTS invitation_status_enum")
    op.execute("DROP TYPE IF EXISTS tree_role_enum")
