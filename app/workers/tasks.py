import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import settings
from app.database import SessionLocal
from app.models.job import Job
from app.models.report import Report
from app.services.notifications import send_notification_email
from app.services.reports import generate_student_transcript
from sqlalchemy import and_, case, exists, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PermanentJobError(Exception):
    """An error that cannot succeed by retrying the same report job."""


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    worker_token: str
    job_version: int


def _now() -> datetime:
    return datetime.now(UTC)


def process_background_notification(
    recipient: str, subject: str, body: str
) -> dict[str, Any]:
    """Retained for the existing direct notification integration."""
    logger.info("[WORKER] Processing background notification for %s", recipient)
    return send_notification_email(recipient, subject, body)


def _complete_values(now: datetime) -> dict[str, Any]:
    return {
        "status": "completed",
        "worker_token": None,  # nosec B105 - lease column name, not a secret
        "lease_until": None,
        "retry_at": None,
        "last_error": None,
        "updated_at": now,
    }


def reconcile_reported_job(db: Session, job_id: str) -> Report | None:
    """Treat an existing report as the final result and repair its Job state."""
    report = db.scalar(select(Report).where(Report.job_id == job_id))
    if report is None:
        return None

    now = _now()
    db.execute(
        update(Job)
        .where(Job.job_id == job_id)
        .where(Job.status != "completed")
        .values(**_complete_values(now))
    )
    db.commit()
    return report


def reconcile_reported_jobs(db: Session) -> int:
    """Repair legacy or interrupted jobs that already have a persisted report."""
    now = _now()
    has_report = exists(select(1).where(Report.job_id == Job.job_id))
    result = db.execute(
        update(Job)
        .where(Job.status != "completed")
        .where(has_report)
        .values(**_complete_values(now))
    )
    db.commit()
    return result.rowcount or 0


def claim_next_job(db: Session) -> ClaimedJob | None:
    """Atomically claim one ready or abandoned job for this worker process."""
    now = _now()
    worker_token = uuid.uuid4().hex
    ready = and_(
        Job.status == "queued",
        or_(Job.retry_at.is_(None), Job.retry_at <= now),
    )
    abandoned = and_(
        Job.status == "processing",
        or_(Job.lease_until.is_(None), Job.lease_until < now),
    )
    candidate = (
        select(Job.job_id)
        .where(or_(ready, abandoned))
        .order_by(
            case((Job.status == "queued", 0), else_=1),
            Job.retry_at.asc().nullsfirst(),
            Job.created_at.asc(),
            Job.job_id.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(1)
        .scalar_subquery()
    )
    result = db.execute(
        update(Job)
        .where(Job.job_id == candidate)
        .values(
            status="processing",
            worker_token=worker_token,
            job_version=Job.job_version + 1,
            attempt_count=Job.attempt_count + 1,
            lease_until=now + timedelta(seconds=settings.job_lease_seconds),
            retry_at=None,
            last_error=None,
            updated_at=now,
        )
        .returning(Job.job_id, Job.job_version)
    )
    row = result.one_or_none()
    db.commit()
    if row is None:
        return None

    return ClaimedJob(
        job_id=row.job_id,
        worker_token=worker_token,
        job_version=row.job_version,
    )


def _owns_job(job: Job, claim: ClaimedJob) -> bool:
    return (
        job.worker_token == claim.worker_token and job.job_version == claim.job_version
    )


def _renew_lease(db: Session, claim: ClaimedJob) -> bool:
    result = db.execute(
        update(Job)
        .where(Job.job_id == claim.job_id)
        .where(Job.status == "processing")
        .where(Job.worker_token == claim.worker_token)
        .where(Job.job_version == claim.job_version)
        .values(
            lease_until=_now() + timedelta(seconds=settings.job_lease_seconds),
            updated_at=_now(),
        )
    )
    db.commit()
    return (result.rowcount or 0) == 1


@contextmanager
def job_heartbeat(claim: ClaimedJob) -> Iterator[None]:
    """Renew the lease while report generation is running in the foreground."""
    stop_event = threading.Event()

    def heartbeat_loop() -> None:
        while not stop_event.wait(settings.job_heartbeat_seconds):
            db = SessionLocal()
            try:
                # A report may have been written by an older worker that resumed late.
                if reconcile_reported_job(db, claim.job_id) is not None:
                    return
                if not _renew_lease(db, claim):
                    return
            except SQLAlchemyError:
                db.rollback()
                logger.exception(
                    "[WORKER] Could not renew lease for job %s", claim.job_id
                )
            finally:
                db.close()

    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=1.0)


def _persist_or_adopt_report(
    db: Session, job_id: str, result: dict[str, Any]
) -> Report:
    """Persist the first result and atomically mark its job as completed."""
    try:
        report = Report(job_id=job_id, result=result)
        db.add(report)
        db.flush()
        db.execute(
            update(Job).where(Job.job_id == job_id).values(**_complete_values(_now()))
        )
        db.commit()
        return report
    except IntegrityError:
        db.rollback()
        winner = reconcile_reported_job(db, job_id)
        if winner is None:
            raise
        return winner


def _record_failure(
    db: Session,
    claim: ClaimedJob,
    error: Exception,
    *,
    permanent: bool,
) -> str:
    """Retry transient failures only while this execution still owns the job."""
    job = db.get(Job, claim.job_id)
    if job is None:
        return "job_not_found"
    if job.status != "processing":
        return job.status
    if not _owns_job(job, claim):
        return "already_processing"

    now = _now()
    message = f"{type(error).__name__}: {error}"[:1000]
    failed = permanent or job.attempt_count >= settings.job_max_attempts
    values: dict[str, Any] = {
        "status": "failed" if failed else "queued",
        "worker_token": None,  # nosec B105 - lease column name, not a secret
        "lease_until": None,
        "retry_at": None,
        "last_error": message,
        "updated_at": now,
    }
    if not failed:
        delay = settings.job_retry_base_seconds * (2 ** (job.attempt_count - 1))
        values["retry_at"] = now + timedelta(seconds=delay)

    update_result = db.execute(
        update(Job)
        .where(Job.job_id == claim.job_id)
        .where(Job.status == "processing")
        .where(Job.worker_token == claim.worker_token)
        .where(Job.job_version == claim.job_version)
        .values(**values)
    )
    db.commit()
    if (update_result.rowcount or 0) != 1:
        return "already_processing"
    return "failed" if failed else "queued"


def process_claimed_report(claim: ClaimedJob) -> dict[str, Any]:
    """Generate one claimed transcript using parameters read only from PostgreSQL."""
    db = SessionLocal()
    try:
        job = db.get(Job, claim.job_id)
        if job is None:
            return {"status": "job_not_found", "job_id": claim.job_id}

        existing = reconcile_reported_job(db, claim.job_id)
        if existing is not None:
            return {
                "status": "completed",
                "job_id": claim.job_id,
                "result": existing.result,
            }

        if job.status != "processing":
            return {"status": job.status, "job_id": claim.job_id}

        if not _owns_job(job, claim):
            return {"status": "already_processing", "job_id": claim.job_id}

        report_type = job.report_type
        target_id = job.target_id
        with job_heartbeat(claim):
            existing = reconcile_reported_job(db, claim.job_id)
            if existing is not None:
                return {
                    "status": "completed",
                    "job_id": claim.job_id,
                    "result": existing.result,
                }

            if report_type != "transcript":
                raise PermanentJobError(f"Unsupported report type: {report_type}")

            transcript = generate_student_transcript(db, target_id)

        existing = reconcile_reported_job(db, claim.job_id)
        if existing is not None:
            return {
                "status": "completed",
                "job_id": claim.job_id,
                "result": existing.result,
            }
        if transcript is None:
            raise PermanentJobError(f"Student {target_id} no longer exists")

        report = _persist_or_adopt_report(db, claim.job_id, transcript)
        return {"status": "completed", "job_id": claim.job_id, "result": report.result}
    except PermanentJobError as exc:
        db.rollback()
        status = _record_failure(db, claim, exc, permanent=True)
        logger.info(
            "[WORKER] Job %s ended with status %s: %s", claim.job_id, status, exc
        )
        return {"status": status, "job_id": claim.job_id}
    except Exception as exc:
        db.rollback()
        existing = reconcile_reported_job(db, claim.job_id)

        if existing is not None:
            return {
                "status": "completed",
                "job_id": claim.job_id,
                "result": existing.result,
            }
        try:
            status = _record_failure(db, claim, exc, permanent=False)
        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "[WORKER] Could not schedule retry for job %s", claim.job_id
            )
            raise
        logger.exception("[WORKER] Job %s ended with status %s", claim.job_id, status)
        return {"status": status, "job_id": claim.job_id}
    finally:
        db.close()
