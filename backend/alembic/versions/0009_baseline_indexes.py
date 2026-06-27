"""Add baseline performance indexes.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # persons — scoped lookups
    op.execute("CREATE INDEX IF NOT EXISTS ix_persons_tree_id ON persons (tree_id) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_persons_tenant_tree ON persons (tenant_id, tree_id) WHERE is_deleted = FALSE")

    # family_group_members — graph traversal
    op.execute("CREATE INDEX IF NOT EXISTS ix_fgm_person_id ON family_group_members (person_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fgm_family_group_id ON family_group_members (family_group_id)")

    # users — tenant-scoped email lookup
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_tenant_email ON users (tenant_id, email)")

    # tree_members — membership checks
    op.execute("CREATE INDEX IF NOT EXISTS ix_tree_members_user_tree ON tree_members (user_id, tree_id)")

    # audit_logs — time-ordered tree log
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_tree_occurred ON audit_logs (tree_id, occurred_at DESC)")

    # person_versions — per-person version list
    op.execute("CREATE INDEX IF NOT EXISTS ix_pv_person_version ON person_versions (person_id, version_number DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_pv_person_version")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_tree_occurred")
    op.execute("DROP INDEX IF EXISTS ix_tree_members_user_tree")
    op.execute("DROP INDEX IF EXISTS ix_users_tenant_email")
    op.execute("DROP INDEX IF EXISTS ix_fgm_family_group_id")
    op.execute("DROP INDEX IF EXISTS ix_fgm_person_id")
    op.execute("DROP INDEX IF EXISTS ix_persons_tenant_tree")
    op.execute("DROP INDEX IF EXISTS ix_persons_tree_id")
