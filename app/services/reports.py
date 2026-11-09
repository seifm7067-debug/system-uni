from typing import Any

from app.models.enrollment import Enrollment
from app.models.job import Job
from app.models.student import Student
from sqlalchemy import select
from sqlalchemy.orm import Session


class TranscriptOwnershipLost(Exception):
    """Raised when the worker generating a transcript lost the job lease."""


def _assert_worker_owns_job(db: Session, claim: Any) -> None:
    """Fail fast if this worker is no longer the owner of the job.

    Uses a fresh column SELECT (not the ORM identity map) so a takeover
    committed by another worker/session is visible immediately, even when
    the caller reuses the same ``db`` Session for transcript reads.
    """
    job_id = claim.job_id
    row = (
        db.execute(
            select(Job.worker_token, Job.job_version, Job.status).where(
                Job.job_id == job_id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise TranscriptOwnershipLost(f"Job {job_id} no longer exists")
    if row["status"] != "processing":
        raise TranscriptOwnershipLost(
            f"Job {job_id} is no longer processing (status={row['status']})"
        )
    if (
        row["worker_token"] != claim.worker_token
        or row["job_version"] != claim.job_version
    ):
        raise TranscriptOwnershipLost(f"Job {job_id} is owned by another worker now")


def calculate_gpa(grades: list[int]) -> float:
    if not grades:
        return 0.0
    gpas = []
    for g in grades:
        if g >= 90:
            gpas.append(4.0)
        elif g >= 85:
            gpas.append(3.7)
        elif g >= 80:
            gpas.append(3.3)
        elif g >= 75:
            gpas.append(3.0)
        elif g >= 70:
            gpas.append(2.7)
        elif g >= 65:
            gpas.append(2.3)
        elif g >= 60:
            gpas.append(2.0)
        else:
            gpas.append(0.0)
    return round(sum(gpas) / len(gpas), 2)


def generate_student_transcript(
    db: Session, student_id: int, claim: Any | None = None
) -> dict[str, Any] | None:
    """Build a student transcript, aborting immediately if the lease is lost.

    ``claim`` is the worker's ``ClaimedJob`` (any object with ``job_id``,
    ``worker_token`` and ``job_version``). When given, ownership is re-checked:
    on entry, after each DB read, before/after every enrollment row, and before
    returning — so a fenced worker stops at the earliest possible point instead
    of wasting work on a job owned by someone else. ``None`` (default) keeps
    the old behaviour for direct API calls without a background job.
    """

    def guard() -> None:
        if claim is not None:
            _assert_worker_owns_job(db, claim)

    # 1) Before doing any work.
    guard()

    student = db.get(Student, student_id)

    # 2) Right after loading the student, before touching enrollments.
    guard()

    if student is None:
        return None

    # Capture scalar fields now; the Student row could change mid-generation.
    student_id_value = student.id
    student_name = student.name
    student_email = student.email
    student_department_id = student.department_id

    # 3) Before issuing the enrollments query.
    guard()

    enrollments = (
        db.execute(select(Enrollment).where(Enrollment.student_id == student_id))
        .scalars()
        .all()
    )

    # 4) After loading enrollments, before the CPU loop.
    guard()

    course_records = []
    valid_grades = []
    for e in enrollments:
        # 5) Per-row check: abort before processing a row we may not own.
        guard()
        if e.grade is not None:
            valid_grades.append(e.grade)
        course_records.append(
            {
                "enrollment_code": e.enrollment_code,
                "course_offering_id": e.course_offering_id,
                "grade": e.grade,
                "is_active": e.is_active,
                "is_withdrawn": e.is_withdrawn,
            }
        )
        # 6) Per-row check after processing it, before moving to the next row.
        guard()

    # 7) Before the GPA computation.
    guard()

    gpa = calculate_gpa(valid_grades)

    # 8) Final check right before returning the result.
    guard()

    return {
        "student_id": student_id_value,
        "name": student_name,
        "email": student_email,
        "department_id": student_department_id,
        "gpa": gpa,
        "total_courses": len(enrollments),
        "courses": course_records,
    }
