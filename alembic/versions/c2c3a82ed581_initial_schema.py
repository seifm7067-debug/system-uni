"""initial schema

Revision ID: c2c3a82ed581
Revises: efb3cf8d0b70
Create Date: 2026-08-06 12:20:15.721452

"""
from collections.abc import Sequence

revision: str = 'c2c3a82ed581'
down_revision: str | Sequence[str] | None = 'efb3cf8d0b70'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
