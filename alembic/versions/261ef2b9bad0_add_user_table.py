"""add_user_table

Revision ID: 261ef2b9bad0
Revises: 1f13b6c5ebd7
Create Date: 2026-08-09 12:36:27.922324

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '261ef2b9bad0'
down_revision: str | Sequence[str] | None = '1f13b6c5ebd7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=150), nullable=False),
    sa.Column('role', sa.Enum('ADMIN', 'USER', 'GUEST', name='userrole'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.add_column('enrollment', sa.Column('cenrollment_code', sa.String(length=50), nullable=False))
    op.drop_constraint(op.f('enrollment_enrollment_code_key'), 'enrollment', type_='unique')
    op.drop_constraint(op.f('uq_enrollment_student_offering'), 'enrollment', type_='unique')
    op.create_unique_constraint('uq_student_course_offering', 'enrollment', ['student_id', 'course_offering_id'])
    op.drop_column('enrollment', 'enrollment_code')
    op.add_column('student', sa.Column('age', sa.Integer(), nullable=False))
    op.add_column('student', sa.Column('email', sa.String(length=150), nullable=False))
    op.create_unique_constraint(None, 'student', ['email'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'student', type_='unique')
    op.drop_column('student', 'email')
    op.drop_column('student', 'age')
    op.add_column('enrollment', sa.Column('enrollment_code', sa.VARCHAR(length=50), autoincrement=False, nullable=False))
    op.drop_constraint('uq_student_course_offering', 'enrollment', type_='unique')
    op.create_unique_constraint(op.f('uq_enrollment_student_offering'), 'enrollment', ['student_id', 'course_offering_id'], postgresql_nulls_not_distinct=False)
    op.create_unique_constraint(op.f('enrollment_enrollment_code_key'), 'enrollment', ['enrollment_code'], postgresql_nulls_not_distinct=False)
    op.drop_column('enrollment', 'cenrollment_code')
    op.drop_table('users')
