import logging
import uuid

from app.database import get_db
from app.models.job import Job
from app.models.report import Report
from app.models.student import Student
from app.models.user import User, UserRole
from app.security.auth import require_admin_or_user
from app.services.reports import generate_student_transcript
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/reports/transcript/{student_id}")
def get_transcript_endpoint(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )
    if current_user.role != UserRole.ADMIN and student.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this transcript",
        )
    transcript = generate_student_transcript(db, student_id)
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )
    return transcript


@router.post("/reports/export/{student_id}", status_code=status.HTTP_202_ACCEPTED)
def export_transcript_async(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )

    if current_user.role != UserRole.ADMIN and student.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to export this transcript",
        )

    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        status="queued",
        owner_id=current_user.id,
        report_type="transcript",
        target_id=student_id,
    )
    db.add(job)
    db.commit()

    return {
        "message": "Report generation queued successfully",
        "job_id": job_id,
        "student_id": student_id,
        "status": "queued",
    }


@router.get("/reports/jobs/{job_id}")
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    db_job = db.get(Job, job_id)
    if db_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    if current_user.role != UserRole.ADMIN and current_user.id != db_job.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this job",
        )

    report = db.query(Report).filter(Report.job_id == job_id).first()
    report_result = report.result if report is not None else None
    actual_status = "completed" if report is not None else db_job.status
    job_data = {
        "job_id": job_id,
        "status": actual_status,
        "owner_id": db_job.owner_id,
        "report_type": db_job.report_type,
        "target_id": db_job.target_id,
        "result": report_result,
    }
    return job_data
