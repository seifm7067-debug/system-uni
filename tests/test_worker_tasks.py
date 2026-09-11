from datetime import UTC, datetime, timedelta

import pytest
from app.database import Base
from app.models.job import Job
from app.models.report import Report
from app.workers import runner, tasks
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def job_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'jobs.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(runner, "SessionLocal", session_factory)
    monkeypatch.setattr(tasks.settings, "job_heartbeat_seconds", 3600)
    yield session_factory
    Base.metadata.drop_all(bind=engine)


def create_job(db, job_id="job-1", status="queued", **values):
    job = Job(
        job_id=job_id,
        status=status,
        owner_id=values.pop("owner_id", 1),
        report_type=values.pop("report_type", "transcript"),
        target_id=values.pop("target_id", 10),
        **values,
    )
    db.add(job)
    db.commit()
    return job


def test_runner_processes_persisted_job(job_db, monkeypatch):
    db = job_db()
    create_job(db)
    transcript = {"student_id": 10, "gpa": 3.8, "courses": []}
    monkeypatch.setattr(tasks, "generate_student_transcript", lambda *_: transcript)

    assert runner.run_once() is True

    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "completed"
    assert job.attempt_count == 1
    assert job.report.result == transcript
    db.close()


def test_two_workers_claim_different_jobs(job_db):
    db_a = job_db()
    create_job(db_a, "job-a")
    create_job(db_a, "job-b")
    db_b = job_db()

    claim_a = tasks.claim_next_job(db_a)
    claim_b = tasks.claim_next_job(db_b)

    assert claim_a is not None
    assert claim_b is not None
    assert claim_a.job_id != claim_b.job_id
    db_a.close()
    db_b.close()


def test_expired_lease_is_recovered_by_another_worker(job_db, monkeypatch):
    db = job_db()
    create_job(
        db,
        status="processing",
        worker_token="dead-worker",
        job_version=1,
        attempt_count=1,
        lease_until=datetime.now(UTC) - timedelta(seconds=1),
    )
    transcript = {"student_id": 10, "gpa": 3.7}
    monkeypatch.setattr(tasks, "generate_student_transcript", lambda *_: transcript)

    assert runner.run_once() is True

    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "completed"
    assert job.attempt_count == 2
    assert job.job_version == 2
    assert job.report.result == transcript
    db.close()


def test_transient_failure_is_retried_and_then_completed(job_db, monkeypatch):
    db = job_db()
    create_job(db)
    transcript = {"student_id": 10, "gpa": 4.0}
    monkeypatch.setattr(
        tasks,
        "generate_student_transcript",
        lambda *_: (_ for _ in ()).throw(RuntimeError("temporary failure")),
    )

    assert runner.run_once() is True

    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "queued"
    assert job.attempt_count == 1
    assert job.retry_at is not None
    assert "temporary failure" in job.last_error

    db.execute(
        update(Job)
        .where(Job.job_id == job.job_id)
        .values(retry_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()
    monkeypatch.setattr(tasks, "generate_student_transcript", lambda *_: transcript)

    assert runner.run_once() is True

    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "completed"
    assert job.attempt_count == 2
    assert job.last_error is None
    assert job.report.result == transcript
    db.close()


def test_first_persisted_report_wins_after_a_takeover(job_db, monkeypatch):
    db = job_db()
    create_job(db)
    claim_a = tasks.claim_next_job(db)
    assert claim_a is not None
    transcript_a = {"student_id": 10, "worker": "a"}

    def complete_a_after_worker_b_claims(*_):
        takeover_db = job_db()
        try:
            takeover_db.execute(
                update(Job)
                .where(Job.job_id == claim_a.job_id)
                .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
            )
            takeover_db.commit()
            assert tasks.claim_next_job(takeover_db) is not None
        finally:
            takeover_db.close()
        return transcript_a

    monkeypatch.setattr(
        tasks, "generate_student_transcript", complete_a_after_worker_b_claims
    )

    result = tasks.process_claimed_report(claim_a)

    assert result == {"status": "completed", "job_id": "job-1", "result": transcript_a}
    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "completed"
    assert job.report.result == transcript_a
    db.close()


def test_runner_repairs_job_with_existing_report(job_db, monkeypatch):
    db = job_db()
    create_job(db, status="processing", worker_token="interrupted", job_version=1)
    db.add(Report(job_id="job-1", result={"student_id": 10, "gpa": 3.5}))
    db.commit()
    monkeypatch.setattr(
        tasks,
        "generate_student_transcript",
        lambda *_: pytest.fail("a persisted report must not be regenerated"),
    )

    runner.reconcile_once()
    assert runner.run_once() is False

    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "completed"
    assert job.worker_token is None
    db.close()


def test_missing_claim_returns_job_not_found(job_db, monkeypatch):
    db = job_db()
    claim = tasks.ClaimedJob(job_id="missing-job", worker_token="w", job_version=1)
    monkeypatch.setattr(
        tasks,
        "generate_student_transcript",
        lambda *_: pytest.fail("a missing job must not be processed"),
    )

    result = tasks.process_claimed_report(claim)

    assert result == {"status": "job_not_found", "job_id": "missing-job"}
    db.close()


def test_completed_job_is_not_reprocessed(job_db, monkeypatch):
    db = job_db()
    create_job(db, status="completed", worker_token=None, job_version=1)
    monkeypatch.setattr(
        tasks,
        "generate_student_transcript",
        lambda *_: pytest.fail("a completed job must not be processed"),
    )
    claim = tasks.ClaimedJob(job_id="job-1", worker_token="stale", job_version=99)

    result = tasks.process_claimed_report(claim)

    assert result == {"status": "completed", "job_id": "job-1"}
    db.close()


def test_fenced_worker_cannot_fail_a_job_taken_over_by_another_worker(
    job_db, monkeypatch
):
    db = job_db()
    create_job(db)
    claim_a = tasks.claim_next_job(db)
    assert claim_a is not None

    takeover_db = job_db()
    try:
        takeover_db.execute(
            update(Job)
            .where(Job.job_id == claim_a.job_id)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        takeover_db.commit()
        claim_b = tasks.claim_next_job(takeover_db)
        assert claim_b is not None
        assert claim_b.job_version > claim_a.job_version
    finally:
        takeover_db.close()

    fenced_error = RuntimeError("fenced worker failure")
    status = tasks._record_failure(db, claim_a, fenced_error, permanent=True)

    db.expire_all()
    job = db.get(Job, "job-1")
    assert status == "already_processing"
    assert job.status == "processing"
    assert job.worker_token == claim_b.worker_token
    assert job.job_version == claim_b.job_version
    assert job.last_error is None
    db.close()


def test_record_failure_reports_job_not_found(job_db):
    claim = tasks.ClaimedJob(job_id="missing-job", worker_token="w", job_version=1)
    db = job_db()

    status = tasks._record_failure(db, claim, RuntimeError("boom"), permanent=True)

    assert status == "job_not_found"
    db.close()


def test_record_failure_reports_terminal_status_without_touching_it(job_db):
    db = job_db()
    create_job(db, status="failed", worker_token="stale", job_version=1)
    claim = tasks.ClaimedJob(job_id="job-1", worker_token="stale", job_version=1)

    status = tasks._record_failure(db, claim, RuntimeError("boom"), permanent=True)

    assert status == "failed"
    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "failed"
    assert job.last_error is None
    db.close()


def test_missing_student_is_a_permanent_failure(job_db, monkeypatch):
    db = job_db()
    create_job(db)
    monkeypatch.setattr(tasks, "generate_student_transcript", lambda *_: None)

    assert runner.run_once() is True

    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "failed"
    assert job.attempt_count == 1
    assert job.retry_at is None
    assert "no longer exists" in job.last_error
    db.close()


def test_transient_failure_is_exhausted_after_max_attempts(job_db, monkeypatch):
    db = job_db()
    create_job(db)
    monkeypatch.setattr(
        tasks,
        "generate_student_transcript",
        lambda *_: (_ for _ in ()).throw(RuntimeError("always failing")),
    )

    for expected_attempts in range(1, tasks.settings.job_max_attempts + 1):
        assert runner.run_once() is True

        db.expire_all()
        job = db.get(Job, "job-1")
        if expected_attempts < tasks.settings.job_max_attempts:
            assert job.status == "queued"
            assert job.retry_at is not None
            db.execute(
                update(Job)
                .where(Job.job_id == job.job_id)
                .values(retry_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            db.commit()

    db.expire_all()
    job = db.get(Job, "job-1")
    assert job.status == "failed"
    assert job.attempt_count == tasks.settings.job_max_attempts
    assert job.retry_at is None
    assert "always failing" in job.last_error
    assert job.report is None
    db.close()


def test_main_sleeps_only_when_no_job_was_claimed(job_db, monkeypatch):
    db = job_db()
    create_job(db, "job-a")
    create_job(db, "job-b")
    monkeypatch.setattr(tasks, "generate_student_transcript", lambda *_: {"gpa": 3.0})
    sleeps: list[float] = []

    def stop_after_first_sleep(seconds):
        sleeps.append(seconds)
        raise KeyboardInterrupt

    monkeypatch.setattr(runner.time, "sleep", stop_after_first_sleep)
    monkeypatch.setattr(runner.settings, "job_poll_interval_seconds", 0.5)

    with pytest.raises(KeyboardInterrupt):
        runner.main()

    assert sleeps == [0.5]
    db.expire_all()
    assert db.get(Job, "job-a").status == "completed"
    assert db.get(Job, "job-b").status == "completed"

    create_job(db, "job-c")
    monkeypatch.setattr(
        tasks,
        "generate_student_transcript",
        lambda *_: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(runner.time, "sleep", stop_after_first_sleep)
    sleeps.clear()

    with pytest.raises(KeyboardInterrupt):
        runner.main()

    assert sleeps == [0.5]
    db.close()


def test_claim_with_retry_recovers_after_transient_failures(job_db, monkeypatch):
    db = job_db()
    create_job(db, "job-retry-claim")
    from sqlalchemy.exc import OperationalError

    attempts: list[int] = []

    def flaky_claim(session):
        attempts.append(1)
        if len(attempts) < 3:
            raise OperationalError("stmt", {}, Exception("db restarted"))
        return tasks.claim_next_job(session)

    monkeypatch.setattr(runner, "claim_next_job", flaky_claim)
    monkeypatch.setattr(runner.settings, "worker_retry_attempts", 3)

    claim = runner._claim_with_retry()

    assert claim is not None
    assert claim.job_id == "job-retry-claim"
    assert len(attempts) == 3
    db.close()


def test_claim_with_retry_raises_after_exhausting_attempts(job_db, monkeypatch):
    from sqlalchemy.exc import OperationalError

    attempts: list[int] = []

    def always_failing_claim(session):
        attempts.append(1)
        raise OperationalError("stmt", {}, Exception("db is down"))

    monkeypatch.setattr(runner, "claim_next_job", always_failing_claim)
    monkeypatch.setattr(runner.settings, "worker_retry_attempts", 3)

    with pytest.raises(OperationalError):
        runner._claim_with_retry()

    assert len(attempts) == 3


def test_claim_with_retry_does_not_retry_unexpected_errors(job_db, monkeypatch):
    attempts: list[int] = []

    def broken_claim(session):
        attempts.append(1)
        raise TypeError("programmer error")

    monkeypatch.setattr(runner, "claim_next_job", broken_claim)

    with pytest.raises(TypeError):
        runner._claim_with_retry()

    assert len(attempts) == 1
