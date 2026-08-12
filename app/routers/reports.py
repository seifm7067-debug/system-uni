from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security.auth import require_admin_or_user
from app.services.reports import generate_student_transcript
from app.workers.tasks import process_async_report

router = APIRouter()


@router.get("/reports/transcript/{student_id}")
def get_transcript_endpoint(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    transcript = generate_student_transcript(db, student_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return transcript


@router.post("/reports/export/{student_id}")
def export_transcript_async(
    student_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    transcript = generate_student_transcript(db, student_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    background_tasks.add_task(process_async_report, "transcript", student_id)
    return {
        "message": "Report generation queued successfully in background",
        "student_id": student_id,
        "status": "queued",
    }
