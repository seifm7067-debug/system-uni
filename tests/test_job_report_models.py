from datetime import UTC, datetime

import pytest
from app.database import Base
from app.models.job import Job
from app.models.report import Report
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_job_and_fields(db):
    now = datetime.now(UTC)
    job = Job(
        job_id="123",
        job_version=1,
        status="queued",
        owner_id=42,
        lease_until=now,
        report_type="transcript",
        target_id=10,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    assert job.job_id == "123"
    assert job.job_version == 1
    assert job.status == "queued"
    assert job.owner_id == 42
    assert job.lease_until is not None
    assert job.report_type == "transcript"
    assert job.target_id == 10
    assert job.report is None


def test_one_to_one_job_report_relationship(db):
    job = Job(
        job_id="job-abc-456",
        owner_id=1,
        report_type="transcript",
        target_id=20,
    )
    db.add(job)
    db.commit()

    report_data = {
        "student_id": 20,
        "name": "Ali",
        "gpa": 3.8,
        "courses": [{"course_id": 1, "grade": 95}],
    }
    report = Report(
        job_id=job.job_id,
        result=report_data,
    )
    db.add(report)
    db.commit()
    db.refresh(job)
    db.refresh(report)

    # Verify 1-to-1 relationship bidirectionally
    assert job.report is not None
    assert not isinstance(job.report, list)
    assert job.report.id == report.id
    assert job.report.result == report_data
    assert report.job.job_id == "job-abc-456"


def test_unique_job_id_constraint_on_report(db):
    """Ensure that only one Report can exist per Job (Job 123 -> Report واحد فقط)."""
    job = Job(
        job_id="123",
        owner_id=5,
        report_type="transcript",
        target_id=15,
    )
    db.add(job)
    db.commit()

    # First report for Job 123 succeeds
    report1 = Report(job_id="123", result={"summary": "first report"})
    db.add(report1)
    db.commit()

    # Second report for Job 123 MUST fail due to UNIQUE(job_id)
    report2 = Report(job_id="123", result={"summary": "duplicate report"})
    db.add(report2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cascade_delete_job_deletes_report(db):
    job = Job(
        job_id="job-delete-test",
        owner_id=2,
        report_type="transcript",
        target_id=30,
    )
    db.add(Report(job=job, result={"status": "done"}))
    db.add(job)
    db.commit()

    assert db.query(Report).filter(Report.job_id == "job-delete-test").count() == 1

    db.delete(job)
    db.commit()

    assert db.query(Report).filter(Report.job_id == "job-delete-test").count() == 0
