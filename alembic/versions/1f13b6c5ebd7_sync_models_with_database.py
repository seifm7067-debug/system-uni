"""sync models with database

Revision ID: 1f13b6c5ebd7
Revises: fe5279b329bf
Create Date: 2026-08-08 19:46:54.893241

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '1f13b6c5ebd7'
down_revision: str | Sequence[str] | None = 'fe5279b329bf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('enrollment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('course_offering_id', sa.Integer(), nullable=False),
    sa.Column('enrollment_code', sa.String(length=50), nullable=False),
    sa.Column('grade', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_withdrawn', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['course_offering_id'], ['course_offering.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['student.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('enrollment_code'),
    sa.UniqueConstraint('student_id', 'course_offering_id', name='uq_enrollment_student_offering')
    )
    op.add_column('course_offering', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('course_schedule', sa.Column('day', sa.String(length=10), nullable=False))
    op.add_column('course_schedule', sa.Column('schedule_type', sa.String(length=10), nullable=False))
    op.add_column('course_schedule', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.alter_column('course_schedule', 'room',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=10),
               existing_nullable=False)
    op.create_unique_constraint('uq_course_schedule', 'course_schedule', ['course_offering_id', 'day', 'start_time', 'end_time'])
    op.drop_column('course_schedule', 'day_of_week')
    op.drop_index(op.f('ix_teacher_name'), table_name='teacher')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index(op.f('ix_teacher_name'), 'teacher', ['name'], unique=False)
    op.add_column('course_schedule', sa.Column('day_of_week', sa.VARCHAR(length=15), autoincrement=False, nullable=False))
    op.drop_constraint('uq_course_schedule', 'course_schedule', type_='unique')
    op.alter_column('course_schedule', 'room',
               existing_type=sa.String(length=10),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)
    op.drop_column('course_schedule', 'created_at')
    op.drop_column('course_schedule', 'schedule_type')
    op.drop_column('course_schedule', 'day')
    op.drop_column('course_offering', 'created_at')
    op.drop_table('enrollment')
