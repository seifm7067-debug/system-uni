from app.config import settings
from app.database import get_db
from app.redis import check_redis_health, check_redis_url_health
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter()


def _component_statuses(db: Session) -> tuple[str, str, str]:
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_status = "unhealthy"

    redis_cache_status = check_redis_health()
    limiter_status = "not_required"
    if settings.rate_limit_fail_closed:
        limiter_status = check_redis_url_health(settings.rate_limit_storage_uri)

    return db_status, redis_cache_status, limiter_status


@router.get("/health/live")
def liveness_check():
    """Report that the web process can receive requests."""
    return {"status": "healthy"}


@router.get("/health")
@router.get("/health/ready")
def readiness_check(response: Response, db: Session = Depends(get_db)):
    """Report whether dependencies needed by this deployment are available."""
    db_status, redis_cache_status, limiter_status = _component_statuses(db)
    is_ok = db_status == "healthy" and (
        not settings.rate_limit_fail_closed or limiter_status == "healthy"
    )

    if not is_ok:
        response.status_code = 503

    return {
        "status": "healthy" if is_ok else "unhealthy",
        "components": {
            "postgres": db_status,
            "redis_cache": redis_cache_status,
            "rate_limit_storage": limiter_status,
        },
    }
