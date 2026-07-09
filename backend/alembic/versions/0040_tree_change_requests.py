"""Add tree_change_requests table, draft-tree columns, and origin_person_id."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Add enum values (must run outside transaction) ────────────────────────
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'REQUEST_CHANGE'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'APPROVE_CHANGE'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'DENY_CHANGE'"))
    conn.execute(text("ALTER TYPE audit_entity_type_enum ADD VALUE IF NOT EXISTS 'CHANGE_REQUEST'"))
    conn.execute(text("BEGIN"))

    # ── Draft-tree columns on family_trees ────────────────────────────────────
    op.add_column(
        "family_trees",
        sa.Column("draft_of_tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column(
        "family_trees",
        sa.Column("draft_owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_family_trees_draft_of_tree_id", "family_trees", ["draft_of_tree_id"])

    # ── origin_person_id on persons ────────────────────────────────────────────
    op.add_column(
        "persons",
        sa.Column("origin_person_id", UUID(as_uuid=True), nullable=True),
    )

    # ── tree_change_requests table ────────────────────────────────────────────
    op.create_table(
        "tree_change_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requester_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=text("'PENDING'")),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("resolved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=text("now()")),
    )
    op.create_index("ix_tree_change_requests_tree_id", "tree_change_requests", ["tree_id"])
    op.create_index("ix_tree_change_requests_requester_id", "tree_change_requests", ["requester_id"])
    op.create_index(
        "uq_tree_change_requests_pending",
        "tree_change_requests",
        ["tree_id", "requester_id"],
        unique=True,
        postgresql_where=text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_tree_change_requests_pending", table_name="tree_change_requests")
    op.drop_index("ix_tree_change_requests_requester_id", table_name="tree_change_requests")
    op.drop_index("ix_tree_change_requests_tree_id", table_name="tree_change_requests")
    op.drop_table("tree_change_requests")

    op.drop_column("persons", "origin_person_id")

    op.drop_index("ix_family_trees_draft_of_tree_id", table_name="family_trees")
    op.drop_column("family_trees", "draft_owner_user_id")
    op.drop_column("family_trees", "draft_of_tree_id")
