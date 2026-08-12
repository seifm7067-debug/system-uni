"""Add teacher student and course schedule models

Revision ID: fe5279b329bf
Revises: c2c3a82ed581
Create Date: 2026-08-07 09:21:54.703886

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'fe5279b329bf'
down_revision: str | Sequence[str] | None = 'c2c3a82ed581'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('college',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_college_name'), 'college', ['name'], unique=False)
    op.create_table('department',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('college_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['college_id'], ['college.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('college_id', 'code', name='uq_department_code'),
    sa.UniqueConstraint('college_id', 'name', name='uq_department_name')
    )
    op.create_index(op.f('ix_department_name'), 'department', ['name'], unique=False)
    op.create_table('course',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('department_id', 'code', name='uq_course_code'),
    sa.UniqueConstraint('department_id', 'name', name='uq_course_name')
    )
    op.create_table('student',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_student_name'), 'student', ['name'], unique=False)
    op.create_table('teacher',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teacher_name'), 'teacher', ['name'], unique=False)
    op.create_table('course_offering',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('semester', sa.String(length=10), nullable=False),
    sa.Column('academic_year', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=10), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['course.id'], ),
    sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('course_id', 'teacher_id', 'semester', 'academic_year', 'section', name='uq_course_offering')
    )
    op.create_table('course_schedule',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_offering_id', sa.Integer(), nullable=False),
    sa.Column('day_of_week', sa.String(length=15), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('room', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['course_offering_id'], ['course_offering.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('course_schedule')
    op.drop_table('course_offering')
    op.drop_index(op.f('ix_teacher_name'), table_name='teacher')
    op.drop_table('teacher')
    op.drop_index(op.f('ix_student_name'), table_name='student')
    op.drop_table('student')
    op.drop_table('course')
    op.drop_index(op.f('ix_department_name'), table_name='department')
    op.drop_table('department')
    op.drop_index(op.f('ix_college_name'), table_name='college')
    op.drop_table('college')
