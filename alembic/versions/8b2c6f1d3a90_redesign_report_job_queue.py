"""redesign report job queue

Revision ID: 8b2c6f1d3a90
Revises: 4f21c8e9b7a0
Create Date: 2026-09-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b2c6f1d3a90"
down_revision: str | Sequence[str] | None = "4f21c8e9b7a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("job", "job_version", server_default="0")
    op.add_column(
        "job",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "job", sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("job", sa.Column("last_error", sa.String(length=1000), nullable=True))
    op.add_column(
        "job",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "job",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_job_retry_at"), "job", ["retry_at"], unique=False)
    op.create_index(op.f("ix_job_created_at"), "job", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_created_at"), table_name="job")
    op.drop_index(op.f("ix_job_retry_at"), table_name="job")
    op.drop_column("job", "updated_at")
    op.drop_column("job", "created_at")
    op.drop_column("job", "last_error")
    op.drop_column("job", "retry_at")
    op.drop_column("job", "attempt_count")
    op.alter_column("job", "job_version", server_default="1")
