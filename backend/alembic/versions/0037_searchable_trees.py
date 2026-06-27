"""Add searchable trees, access requests, and merge requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import text

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Add enum values (must run outside transaction) ────────────────────────
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'REQUEST_ACCESS'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'APPROVE_ACCESS'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'DENY_ACCESS'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'REQUEST_MERGE'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'APPROVE_MERGE'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'DENY_MERGE'"))
    conn.execute(text("ALTER TYPE audit_entity_type_enum ADD VALUE IF NOT EXISTS 'ACCESS_REQUEST'"))
    conn.execute(text("ALTER TYPE audit_entity_type_enum ADD VALUE IF NOT EXISTS 'MERGE_REQUEST'"))
    conn.execute(text("BEGIN"))

    # ── is_searchable column on family_trees ──────────────────────────────────
    op.add_column(
        "family_trees",
        sa.Column("is_searchable", sa.Boolean, nullable=False, server_default=text("false")),
    )

    # ── access_requests table ─────────────────────────────────────────────────
    op.create_table(
        "access_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_role", sa.String(16), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=text("'PENDING'")),
        sa.Column("resolved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=text("now()")),
    )
    op.create_index("ix_access_requests_tree_id", "access_requests", ["tree_id"])
    op.create_index("ix_access_requests_requester_id", "access_requests", ["requester_id"])
    op.create_index(
        "uq_access_requests_pending",
        "access_requests",
        ["tree_id", "requester_id"],
        unique=True,
        postgresql_where=text("status = 'PENDING'"),
    )

    # ── merge_requests table ──────────────────────────────────────────────────
    op.create_table(
        "merge_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("target_tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_pivot_person_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_pivot_person_id", UUID(as_uuid=True), nullable=False),
        sa.Column("new_tree_name", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=text("'PENDING'")),
        sa.Column("resolved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=text("now()")),
    )
    op.create_index("ix_merge_requests_target_tree_id", "merge_requests", ["target_tree_id"])
    op.create_index("ix_merge_requests_source_tree_id", "merge_requests", ["source_tree_id"])
    op.create_index("ix_merge_requests_requester_id", "merge_requests", ["requester_id"])
    op.create_index(
        "uq_merge_requests_pending",
        "merge_requests",
        ["target_tree_id", "source_tree_id"],
        unique=True,
        postgresql_where=text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_merge_requests_pending", table_name="merge_requests")
    op.drop_index("ix_merge_requests_requester_id", table_name="merge_requests")
    op.drop_index("ix_merge_requests_source_tree_id", table_name="merge_requests")
    op.drop_index("ix_merge_requests_target_tree_id", table_name="merge_requests")
    op.drop_table("merge_requests")

    op.drop_index("uq_access_requests_pending", table_name="access_requests")
    op.drop_index("ix_access_requests_requester_id", table_name="access_requests")
    op.drop_index("ix_access_requests_tree_id", table_name="access_requests")
    op.drop_table("access_requests")

    op.drop_column("family_trees", "is_searchable")
