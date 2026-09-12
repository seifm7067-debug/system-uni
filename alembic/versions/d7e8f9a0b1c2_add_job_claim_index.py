"""add job claim composite index

Revision ID: d7e8f9a0b1c2
Revises: b1a2c3d4e5f6
Create Date: 2026-09-12

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d7e8f9a0b1c2"
down_revision = "b1a2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_job_claim",
        "job",
        ["status", "retry_at", "lease_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_claim", table_name="job")
