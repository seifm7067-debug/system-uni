"""add job owner foreign key

Revision ID: e6f7a8b9c0d1
Revises: d7e8f9a0b1c2
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing orphaned jobs are retained for audit, while all new writes are checked.
    op.create_foreign_key(
        "fk_job_owner_id_users",
        "job",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
        postgresql_not_valid=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_job_owner_id_users", "job", type_="foreignkey")
