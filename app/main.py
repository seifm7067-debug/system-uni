import logging
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine
from app.limiter import limiter
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)
from app.routers import (
    college,
    course,
    courseoffering,
    courseschedule,
    department,
    enrollment,
    health,
    reports,
    student,
    teacher,
    user,
)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(title="University Management API", version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
    logger.warning(f"DataError on {request.url.path}: {exc}")
    return JSONResponse(status_code=422, content={"detail": "Invalid request data"})


def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning(f"IntegrityError on {request.url.path}: {exc}")
    return JSONResponse(status_code=409, content={"detail": "Constraint violation"})


app.add_exception_handler(DataError, data_error_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(reports.router)
app.include_router(college.router)
app.include_router(course.router)
app.include_router(courseoffering.router)
app.include_router(department.router)
app.include_router(teacher.router)
app.include_router(student.router)
app.include_router(enrollment.router)
app.include_router(courseschedule.router)
app.include_router(user.router)
