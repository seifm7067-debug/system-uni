"""add a per-execution token for job leases

Revision ID: 4f21c8e9b7a0
Revises: 843b988b5e47
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4f21c8e9b7a0"
down_revision: str | Sequence[str] | None = "843b988b5e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job", sa.Column("worker_token", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_job_worker_token"), "job", ["worker_token"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_worker_token"), table_name="job")
    op.drop_column("job", "worker_token")
