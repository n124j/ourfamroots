"""Rename city/country to born_city/born_country, add died location fields, add notes, drop social profile columns.

Revision ID: 0035
Revises: 0034
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("persons", "city", new_column_name="born_city")
    op.alter_column("persons", "country", new_column_name="born_country")
    op.add_column("persons", sa.Column("died_city", sa.String(200), nullable=True))
    op.add_column("persons", sa.Column("died_country", sa.String(100), nullable=True))
    op.add_column("persons", sa.Column("notes", sa.String(250), nullable=True))
    op.drop_column("persons", "facebook_handle")
    op.drop_column("persons", "x_handle")
    op.drop_column("persons", "linkedin_handle")


def downgrade() -> None:
    op.add_column("persons", sa.Column("linkedin_handle", sa.String(200), nullable=True))
    op.add_column("persons", sa.Column("x_handle", sa.String(200), nullable=True))
    op.add_column("persons", sa.Column("facebook_handle", sa.String(200), nullable=True))
    op.drop_column("persons", "notes")
    op.drop_column("persons", "died_country")
    op.drop_column("persons", "died_city")
    op.alter_column("persons", "born_country", new_column_name="country")
    op.alter_column("persons", "born_city", new_column_name="city")
