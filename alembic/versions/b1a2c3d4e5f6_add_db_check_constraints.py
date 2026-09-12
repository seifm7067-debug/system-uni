"""add db check constraints and server defaults

Revision ID: b1a2c3d4e5f6
Revises: c4d5e6f7a8b9
Create Date: 2026-09-12

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1a2c3d4e5f6"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_enrollment_grade_range",
        "enrollment",
        "grade IS NULL OR (grade >= 0 AND grade <= 100)",
    )
    op.create_check_constraint(
        "ck_enrollment_active_xor_withdrawn",
        "enrollment",
        "NOT (is_active AND is_withdrawn)",
    )
    op.alter_column(
        "enrollment",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
        existing_nullable=False,
    )
    op.alter_column(
        "enrollment",
        "is_withdrawn",
        existing_type=sa.Boolean(),
        server_default=sa.text("false"),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_course_schedule_time_order",
        "course_schedule",
        "end_time > start_time",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_course_schedule_time_order", "course_schedule", type_="check"
    )
    op.alter_column(
        "enrollment",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "enrollment",
        "is_withdrawn",
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=False,
    )
    op.drop_constraint(
        "ck_enrollment_active_xor_withdrawn", "enrollment", type_="check"
    )
    op.drop_constraint("ck_enrollment_grade_range", "enrollment", type_="check")
