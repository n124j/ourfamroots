"""Create audit enum types and tables (audit_logs, person_versions).

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_AUDIT_ACTIONS = (
    "DELETE_TREE", "TRANSFER_OWNERSHIP", "UPDATE_TREE",
    "INVITE_MEMBER", "REMOVE_MEMBER", "CHANGE_MEMBER_ROLE", "VIEW_MEMBERS",
    "VIEW_AUDIT_LOG",
    "CREATE_PERSON", "UPDATE_PERSON", "DELETE_PERSON", "VIEW_PERSON",
    "ADD_RELATIONSHIP", "REMOVE_RELATIONSHIP",
    "CREATE_EVENT", "UPDATE_EVENT", "DELETE_EVENT",
    "UPLOAD_MEDIA", "DELETE_MEDIA",
    "VIEW_VERSION", "RESTORE_VERSION",
    "GENERATE_REPORT", "EXPORT_GEDCOM",
)

_AUDIT_ENTITY_TYPES = (
    "TREE", "PERSON", "FAMILY_GROUP", "EVENT", "MEDIA",
    "MEMBER", "INVITATION", "REPORT",
)


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tree_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_display_name", sa.String(255), nullable=False),
        sa.Column("action", sa.Enum(*_AUDIT_ACTIONS, name="audit_action_enum"), nullable=False, index=True),
        sa.Column("entity_type", sa.Enum(*_AUDIT_ENTITY_TYPES, name="audit_entity_type_enum"), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entity_display_name", sa.String(512), nullable=True),
        sa.Column("before", JSONB(), nullable=True),
        sa.Column("after", JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), index=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "person_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tree_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("audit_entry_id", UUID(as_uuid=True), sa.ForeignKey("audit_logs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("change_summary", sa.String(512), nullable=False, server_default=sa.text("''")),
    )


def downgrade() -> None:
    op.drop_table("person_versions")
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS audit_entity_type_enum")
    op.execute("DROP TYPE IF EXISTS audit_action_enum")
