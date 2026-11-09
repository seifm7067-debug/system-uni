import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.config import settings
from app.models.job import Job
from app.models.user import User, UserRole
from app.workers.tasks import claim_next_job
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
RUN_POSTGRES_TESTS = os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1"
RUN_MIGRATION_TESTS = os.getenv("RUN_MIGRATION_COMPATIBILITY_TESTS") == "1"


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


@pytest.mark.skipif(
    not RUN_MIGRATION_TESTS,
    reason="set RUN_MIGRATION_COMPATIBILITY_TESTS=1 to run migration compatibility tests",
)
def test_enrollment_code_migration_preserves_existing_rows():
    """Upgrade from the legacy column after it already contains enrollment data."""
    config = _alembic_config()
    engine = create_engine(settings.database_url)
    marker = uuid.uuid4().hex[:10]
    enrollment_id = 900000

    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert revision == "261ef2b9bad0"

        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO college (id, name, code) VALUES (:id, :name, :code)"),
                {"id": enrollment_id, "name": f"College {marker}", "code": marker},
            )
            connection.execute(
                text(
                    "INSERT INTO department (id, name, code, college_id) "
                    "VALUES (:id, :name, :code, :college_id)"
                ),
                {
                    "id": enrollment_id,
                    "name": f"Department {marker}",
                    "code": marker,
                    "college_id": enrollment_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO student (id, name, department_id, age, email) "
                    "VALUES (:id, :name, :department_id, :age, :email)"
                ),
                {
                    "id": enrollment_id,
                    "name": f"Student {marker}",
                    "department_id": enrollment_id,
                    "age": 20,
                    "email": f"student-{marker}@test.local",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO teacher (id, name, department_id) "
                    "VALUES (:id, :name, :department_id)"
                ),
                {
                    "id": enrollment_id,
                    "name": f"Teacher {marker}",
                    "department_id": enrollment_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO course (id, name, code, department_id) "
                    "VALUES (:id, :name, :code, :department_id)"
                ),
                {
                    "id": enrollment_id,
                    "name": f"Course {marker}",
                    "code": marker,
                    "department_id": enrollment_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO course_offering "
                    "(id, course_id, teacher_id, semester, academic_year, section) "
                    "VALUES (:id, :course_id, :teacher_id, 'Fall', 2026, 'A')"
                ),
                {
                    "id": enrollment_id,
                    "course_id": enrollment_id,
                    "teacher_id": enrollment_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO enrollment "
                    "(id, student_id, course_offering_id, cenrollment_code, grade, "
                    "is_active, is_withdrawn) "
                    "VALUES (:id, :student_id, :course_offering_id, :code, 90, true, false)"
                ),
                {
                    "id": enrollment_id,
                    "student_id": enrollment_id,
                    "course_offering_id": enrollment_id,
                    "code": f"LEGACY-{marker}",
                },
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            code = connection.execute(
                text("SELECT enrollment_code FROM enrollment WHERE id = :id"),
                {"id": enrollment_id},
            ).scalar_one()
        assert code == f"LEGACY-{marker}"
    finally:
        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM enrollment WHERE id = :id"), {"id": enrollment_id}
            )
            connection.execute(
                text("DELETE FROM course_offering WHERE id = :id"),
                {"id": enrollment_id},
            )
            connection.execute(
                text("DELETE FROM course WHERE id = :id"), {"id": enrollment_id}
            )
            connection.execute(
                text("DELETE FROM teacher WHERE id = :id"), {"id": enrollment_id}
            )
            connection.execute(
                text("DELETE FROM student WHERE id = :id"), {"id": enrollment_id}
            )
            connection.execute(
                text("DELETE FROM department WHERE id = :id"), {"id": enrollment_id}
            )
            connection.execute(
                text("DELETE FROM college WHERE id = :id"), {"id": enrollment_id}
            )
        engine.dispose()


@pytest.mark.skipif(
    not RUN_POSTGRES_TESTS,
    reason="set RUN_POSTGRES_INTEGRATION_TESTS=1 to run PostgreSQL integration tests",
)
def test_postgres_workers_claim_different_jobs():
    engine = create_engine(settings.database_url)
    session_factory = sessionmaker(bind=engine)
    db_a = session_factory()
    db_b = session_factory()
    marker = uuid.uuid4().hex
    username = f"worker-owner-{marker}"

    try:
        owner = User(
            username=username,
            email=f"{username}@test.local",
            password_hash="not-used-in-worker-test",
            role=UserRole.USER,
        )
        db_a.add(owner)
        db_a.commit()
        db_a.refresh(owner)
        db_a.add_all(
            [
                Job(
                    job_id=f"worker-{marker}-a",
                    owner_id=owner.id,
                    status="queued",
                    report_type="transcript",
                    target_id=1,
                ),
                Job(
                    job_id=f"worker-{marker}-b",
                    owner_id=owner.id,
                    status="queued",
                    report_type="transcript",
                    target_id=2,
                ),
            ]
        )
        db_a.commit()

        claim_a = claim_next_job(db_a)
        claim_b = claim_next_job(db_b)

        assert claim_a is not None
        assert claim_b is not None
        assert {claim_a.job_id, claim_b.job_id} == {
            f"worker-{marker}-a",
            f"worker-{marker}-b",
        }
    finally:
        db_a.rollback()
        db_b.rollback()
        db_a.execute(delete(Job).where(Job.job_id.like(f"worker-{marker}-%")))
        db_a.execute(delete(User).where(User.username == username))
        db_a.commit()
        db_a.close()
        db_b.close()
        engine.dispose()
