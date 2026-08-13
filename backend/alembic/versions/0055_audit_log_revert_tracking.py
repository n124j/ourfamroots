"""Generalize point-in-time revert past change-requests: add REVERT_SNAPSHOT
audit action and reverted_at/reverted_by_id tracking directly on audit_logs,
so any entry carrying a full-tree snapshot (flagged via metadata.snapshot_kind)
can be reverted the same way an approved change request already can.

Revision ID: 0055
Revises: 0054
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'REVERT_SNAPSHOT'"))
    conn.execute(text("BEGIN"))

    op.add_column("audit_logs", sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("reverted_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    # Backfill: tag historical APPROVE_CHANGE snapshot entries with the marker
    # the new generic revert endpoint uses to decide an entry is revertible.
    conn.execute(text("""
        UPDATE audit_logs
        SET metadata = metadata || '{"snapshot_kind":"full_tree"}'::jsonb
        WHERE action = 'APPROVE_CHANGE' AND before IS NOT NULL
          AND NOT (metadata ? 'snapshot_kind')
    """))

    # Backfill: carry forward already-reverted state from tree_change_requests
    # so old approvals reverted via the change-request-specific endpoint are
    # correctly recognized as already-reverted by the new shared guard.
    conn.execute(text("""
        UPDATE audit_logs a
        SET reverted_at = tcr.reverted_at, reverted_by_id = tcr.reverted_by_id
        FROM tree_change_requests tcr
        WHERE a.action = 'APPROVE_CHANGE' AND a.entity_type = 'CHANGE_REQUEST'
          AND a.entity_id = tcr.id AND tcr.reverted_at IS NOT NULL
    """))


def downgrade() -> None:
    op.drop_column("audit_logs", "reverted_by_id")
    op.drop_column("audit_logs", "reverted_at")
    # Postgres doesn't support removing individual enum values; no-op, same
    # as every prior migration that added audit_action_enum values.
