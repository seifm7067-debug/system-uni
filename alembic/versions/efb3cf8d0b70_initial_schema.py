"""initial schema

Revision ID: efb3cf8d0b70
Revises:
Create Date: 2026-08-06 12:08:06.207593

"""
from collections.abc import Sequence

revision: str = 'efb3cf8d0b70'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
