"""Add full-text search vector and indexes for genealogy search.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # search_vector column already created in 0004; populate existing rows
    op.execute("""
        UPDATE persons SET search_vector =
            setweight(to_tsvector('simple', unaccent(coalesce(display_given_name, ''))), 'A')
            || setweight(to_tsvector('simple', unaccent(coalesce(display_surname, ''))), 'A')
    """)

    # Trigger: keep search_vector fresh on INSERT / UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION persons_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple', unaccent(coalesce(NEW.display_given_name, ''))), 'A')
                || setweight(to_tsvector('simple', unaccent(coalesce(NEW.display_surname, ''))), 'A');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)

    op.execute("DROP TRIGGER IF EXISTS trg_persons_search_vector ON persons")
    op.execute("""
        CREATE TRIGGER trg_persons_search_vector
        BEFORE INSERT OR UPDATE OF display_given_name, display_surname
        ON persons
        FOR EACH ROW EXECUTE FUNCTION persons_search_vector_update()
    """)

    # GIN index on tsvector
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_persons_search_vector
        ON persons USING GIN (search_vector)
        WHERE is_deleted = FALSE
    """)

    # Trigram indexes for fuzzy name matching
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_persons_given_trgm
        ON persons USING GIN (display_given_name gin_trgm_ops)
        WHERE is_deleted = FALSE
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_persons_surname_trgm
        ON persons USING GIN (display_surname gin_trgm_ops)
        WHERE is_deleted = FALSE
    """)

    # Graph traversal indexes on family_group_members
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_fgm_person_fg
        ON family_group_members (person_id, family_group_id, role)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_fgm_fg_role_person
        ON family_group_members (family_group_id, role, person_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_fgm_tree
        ON family_group_members (tree_id)
    """)

    # Scoping indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_persons_tree_tenant
        ON persons (tree_id, tenant_id)
        WHERE is_deleted = FALSE
    """)

    # Composite: surname prefix search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_persons_surname_prefix
        ON persons (tree_id, lower(display_surname) text_pattern_ops)
        WHERE is_deleted = FALSE
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_persons_search_vector ON persons")
    op.execute("DROP FUNCTION IF EXISTS persons_search_vector_update()")
    op.execute("DROP INDEX IF EXISTS idx_persons_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_persons_given_trgm")
    op.execute("DROP INDEX IF EXISTS idx_persons_surname_trgm")
    op.execute("DROP INDEX IF EXISTS idx_fgm_person_fg")
    op.execute("DROP INDEX IF EXISTS idx_fgm_fg_role_person")
    op.execute("DROP INDEX IF EXISTS idx_fgm_tree")
    op.execute("DROP INDEX IF EXISTS idx_persons_tree_tenant")
    op.execute("DROP INDEX IF EXISTS idx_persons_surname_prefix")
