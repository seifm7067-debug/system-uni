"""make student age nullable

Revision ID: 4108c6f0c305
Revises: feb7795f68f3
Create Date: 2026-08-13 00:10:46.693200

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4108c6f0c305"
down_revision: str | Sequence[str] | None = "feb7795f68f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("student", "age", existing_type=sa.INTEGER(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("student", "age", existing_type=sa.INTEGER(), nullable=False)
