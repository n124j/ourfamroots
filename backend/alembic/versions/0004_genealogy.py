"""Create genealogy enum types and tables (persons, family_groups, family_group_members).

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sex", sa.Enum("MALE", "FEMALE", "OTHER", "UNKNOWN", name="person_sex"), nullable=False, server_default=sa.text("'UNKNOWN'")),
        sa.Column("display_given_name", sa.String(200), nullable=False, server_default=sa.text("''")),
        sa.Column("display_surname", sa.String(200), nullable=False, server_default=sa.text("''")),
        sa.Column("is_living", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deceased", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "family_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("union_type", sa.Enum("MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN", name="union_type"), nullable=False, server_default=sa.text("'UNKNOWN'")),
        sa.Column("parent1_id", UUID(as_uuid=True), nullable=True),
        sa.Column("parent2_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "family_group_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tree_id", UUID(as_uuid=True), sa.ForeignKey("family_trees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("family_group_id", UUID(as_uuid=True), sa.ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("person_id", UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.Enum("PARENT", "CHILD", name="family_role"), nullable=False),
        sa.Column("parentage_type", sa.Enum("BIOLOGICAL", "ADOPTIVE", "STEP", "FOSTER", "UNKNOWN", name="parentage_type"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("family_group_id", "person_id", name="uq_fgm_fg_person"),
    )


def downgrade() -> None:
    op.drop_table("family_group_members")
    op.drop_table("family_groups")
    op.drop_table("persons")
    for name in ("parentage_type", "family_role", "union_type", "person_sex"):
        op.execute(f"DROP TYPE IF EXISTS {name}")
