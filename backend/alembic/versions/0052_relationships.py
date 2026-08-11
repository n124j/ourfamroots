"""Create relationships table for non-family-group person links (Godparent,
Guardian, Mentor, Custom) — independent of the parent-child/spouse family
group graph, which stays exclusive/singular as before. Also registers the
new RELATIONSHIP audit entity type (ADD_RELATIONSHIP/REMOVE_RELATIONSHIP
actions already exist in audit_action_enum since 0006_audit.py).

Revision ID: 0052
Revises: 0051
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relationships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("person1_id", UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("person2_id", UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("relationship_type", sa.Enum("GODPARENT", "GUARDIAN", "MENTOR", "CUSTOM", name="relationship_type_enum"), nullable=False),
        sa.Column("custom_label", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("person1_id <> person2_id", name="ck_relationship_distinct_persons"),
        sa.UniqueConstraint("tree_id", "person1_id", "person2_id", "relationship_type", name="uq_relationship_pair_type"),
    )

    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(sa.text("ALTER TYPE audit_entity_type_enum ADD VALUE IF NOT EXISTS 'RELATIONSHIP'"))
    conn.execute(sa.text("BEGIN"))


def downgrade() -> None:
    op.drop_table("relationships")
    op.execute("DROP TYPE IF EXISTS relationship_type_enum")
    # Postgres doesn't support removing individual enum values from
    # audit_entity_type_enum; no-op, same as every prior migration that
    # added a value to it.
