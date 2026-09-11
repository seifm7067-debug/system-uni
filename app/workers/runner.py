import logging
import time

from app.config import settings
from app.database import SessionLocal
from app.workers.tasks import (
    ClaimedJob,
    claim_next_job,
    process_claimed_report,
    reconcile_reported_jobs,
)
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def reconcile_once() -> None:
    """Repair reported jobs once at worker startup, not on every poll cycle."""
    db = SessionLocal()
    try:
        reconciled = reconcile_reported_jobs(db)
        if reconciled:
            logger.info("[WORKER] Reconciled %s reported job(s)", reconciled)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("[WORKER] Could not reconcile reported jobs")
    finally:
        db.close()


def _claim_with_retry(attempts: int | None = None) -> ClaimedJob | None:
    """Try to claim the next job, retrying transient DB errors up to `attempts`."""
    if attempts is None:
        attempts = settings.worker_retry_attempts
    for attempt in range(1, attempts + 1):
        db = SessionLocal()
        try:
            return claim_next_job(db)
        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "[WORKER] Could not claim the next report job (attempt %s/%s)",
                attempt,
                attempts,
            )
            if attempt == attempts:
                raise
        finally:
            db.close()
    return None


def run_once() -> bool:
    """Claim and execute at most one report job."""
    claim = _claim_with_retry()
    if claim is None:
        return False

    process_claimed_report(claim)
    return True


def main() -> None:
    logger.info("[WORKER] Report worker started")
    reconcile_once()
    while True:
        try:
            claimed = run_once()
        except Exception:
            logger.exception("[WORKER] Unhandled worker-loop error")
            claimed = False

        if not claimed:
            time.sleep(settings.job_poll_interval_seconds)


if __name__ == "__main__":
    main()
