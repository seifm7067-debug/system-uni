"""fix enrollment code column

Revision ID: 403a366388eb
Revises: 261ef2b9bad0
Create Date: 2026-08-10 17:52:28.864611

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "403a366388eb"
down_revision: str | Sequence[str] | None = "261ef2b9bad0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "course", "department_id", existing_type=sa.INTEGER(), nullable=True
    )
    op.add_column(
        "enrollment", sa.Column("enrollment_code", sa.String(length=50), nullable=False)
    )
    op.drop_column("enrollment", "cenrollment_code")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "enrollment",
        sa.Column(
            "cenrollment_code",
            sa.VARCHAR(length=50),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_column("enrollment", "enrollment_code")
    op.alter_column(
        "course", "department_id", existing_type=sa.INTEGER(), nullable=False
    )
