"""add token_version to user

Revision ID: c4d5e6f7a8b9
Revises: 8b2c6f1d3a90
Create Date: 2026-09-12

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4d5e6f7a8b9"
down_revision = "8b2c6f1d3a90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add as nullable first, backfill existing rows, then enforce NOT NULL.
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE users SET token_version = 0 WHERE token_version IS NULL")
    op.alter_column(
        "users", "token_version", existing_type=sa.Integer(), nullable=False
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
