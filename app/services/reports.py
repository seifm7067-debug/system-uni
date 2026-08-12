from typing import Any

from app.models.enrollment import Enrollment
from app.models.student import Student
from sqlalchemy import select
from sqlalchemy.orm import Session


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


def generate_student_transcript(db: Session, student_id: int) -> dict[str, Any] | None:
    student = db.get(Student, student_id)
    if student is None:
        return None

    enrollments = (
        db.execute(select(Enrollment).where(Enrollment.student_id == student_id))
        .scalars()
        .all()
    )

    course_records = []
    valid_grades = []
    for e in enrollments:
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

    gpa = calculate_gpa(valid_grades)

    return {
        "student_id": student.id,
        "name": student.name,
        "email": student.email,
        "department_id": student.department_id,
        "gpa": gpa,
        "total_courses": len(enrollments),
        "courses": course_records,
    }
