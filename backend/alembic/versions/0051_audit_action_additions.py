"""Add CREATE_TREE, REVOKE_INVITATION audit actions; backfill the
MANAGE_SECTION_VISIBILITY action and SECTION_VISIBILITY_RULE entity type that
0048_section_visibility_rules.py added Python-side support for but never
added to the Postgres enum types (a pre-existing gap — those two values have
been referenced by src/api/v1/collaboration.py's section-visibility-rule
endpoints since 0048, and would raise an "invalid input value for enum"
error on any DB where this migration hadn't been hand-patched in).

Revision ID: 0051
Revises: 0050
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'CREATE_TREE'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'REVOKE_INVITATION'"))
    conn.execute(text("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'MANAGE_SECTION_VISIBILITY'"))
    conn.execute(text("ALTER TYPE audit_entity_type_enum ADD VALUE IF NOT EXISTS 'SECTION_VISIBILITY_RULE'"))
    conn.execute(text("BEGIN"))


def downgrade() -> None:
    # Postgres doesn't support removing individual enum values; no-op, same
    # as every prior migration that added audit_action_enum/audit_entity_type_enum values.
    pass
