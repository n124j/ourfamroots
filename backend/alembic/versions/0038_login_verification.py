"""Add login verification token fields to users table."""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login_verification_token", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("login_verification_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "login_verification_expires_at")
    op.drop_column("users", "login_verification_token")
