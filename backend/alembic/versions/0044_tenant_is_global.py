"""Add is_global flag to tenants (marks the default namespace new users land in).

Revision ID: 0044
Revises: 0043
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # At most one tenant can ever be the Global namespace.
    op.create_index(
        "uq_tenants_single_global",
        "tenants",
        ["is_global"],
        unique=True,
        postgresql_where=sa.text("is_global = true"),
    )

    # Mark the existing shared tenant (created by AuthService.register()) as global,
    # if it already exists. If it doesn't exist yet in this environment (fresh DB,
    # no one has registered), it will be created lazily by register() with
    # is_global=false — ops must run this UPDATE once by hand after first boot.
    # Read the slug directly from the environment (same default as config.Settings)
    # rather than importing the app's Settings object, which may require secrets
    # (JWT keys, etc.) that aren't necessarily present in a migration-only context.
    import os
    default_tenant_slug = os.environ.get("DEFAULT_TENANT_SLUG", "ourfamroots-system")
    op.execute(
        sa.text("UPDATE tenants SET is_global = true WHERE slug = :slug").bindparams(
            slug=default_tenant_slug
        )
    )


def downgrade() -> None:
    op.drop_index("uq_tenants_single_global", table_name="tenants")
    op.drop_column("tenants", "is_global")
