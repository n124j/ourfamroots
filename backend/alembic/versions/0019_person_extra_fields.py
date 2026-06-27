"""Add birth/death dates, social handles to persons table.

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("persons", sa.Column("death_date", sa.Date(), nullable=True))
    op.add_column("persons", sa.Column("birth_year", sa.Integer(), nullable=True))
    op.add_column("persons", sa.Column("death_year", sa.Integer(), nullable=True))
    op.add_column("persons", sa.Column("facebook_handle", sa.String(200), nullable=True))
    op.add_column("persons", sa.Column("x_handle", sa.String(200), nullable=True))
    op.add_column("persons", sa.Column("linkedin_handle", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("persons", "linkedin_handle")
    op.drop_column("persons", "x_handle")
    op.drop_column("persons", "facebook_handle")
    op.drop_column("persons", "death_year")
    op.drop_column("persons", "birth_year")
    op.drop_column("persons", "death_date")
    op.drop_column("persons", "birth_date")
