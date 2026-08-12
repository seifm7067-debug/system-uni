from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.redis import get_redis_client

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_status = "unhealthy"

    redis_client = get_redis_client()
    redis_status = "healthy" if redis_client is not None else "unavailable"

    is_ok = db_status == "healthy"

    return {
        "status": "healthy" if is_ok else "unhealthy",
        "components": {
            "postgres": db_status,
            "redis": redis_status,
            "worker": "ready",
        },
    }
