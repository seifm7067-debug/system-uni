"""add_version_id_to_student

Revision ID: dd978d37882b
Revises: 4108c6f0c305
Create Date: 2026-08-30 21:07:45.958541

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dd978d37882b"
down_revision: str | Sequence[str] | None = "4108c6f0c305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "student",
        sa.Column("version_id", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("student", "version_id")
