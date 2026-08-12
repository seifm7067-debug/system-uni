"""add_user_id_to_student_and_unique_enrollment_code

Revision ID: feb7795f68f3
Revises: 403a366388eb
Create Date: 2026-08-11 12:43:38.545843

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "feb7795f68f3"
down_revision: str | Sequence[str] | None = "403a366388eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        op.f("ix_enrollment_enrollment_code"),
        "enrollment",
        ["enrollment_code"],
        unique=True,
    )
    op.add_column("student", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_student_user_id"), "student", ["user_id"], unique=True)
    op.create_foreign_key(None, "student", "users", ["user_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, "student", type_="foreignkey")
    op.drop_index(op.f("ix_student_user_id"), table_name="student")
    op.drop_column("student", "user_id")
    op.drop_index(op.f("ix_enrollment_enrollment_code"), table_name="enrollment")
