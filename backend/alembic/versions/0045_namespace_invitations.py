"""Create namespace_invitations table (invite a Global-namespace user into a namespace).

Revision ID: 0045
Revises: 0044
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "namespace_invitations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # Target namespace being invited into.
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("inviter_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # Always an existing account (Global-namespace users are transferred, not created).
        sa.Column("invitee_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invitee_email", sa.String(255), nullable=False, index=True),
        # AppRole value the invitee will get in the new namespace — ADMIN|STANDARD|AUDITOR.
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token", sa.String(128), nullable=False, unique=True, index=True),
        # Reuses the enum type already created by migration 0005 for tree invitations.
        sa.Column("status", PGEnum("PENDING", "ACCEPTED", "DECLINED", "EXPIRED", "REVOKED",
                                    name="invitation_status_enum", create_type=False),
                  nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_namespace_invitations_invitee_status",
        "namespace_invitations",
        ["invitee_user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_namespace_invitations_invitee_status", table_name="namespace_invitations")
    op.drop_table("namespace_invitations")
