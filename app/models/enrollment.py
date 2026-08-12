from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.courseoffering import CourseOffering
    from app.models.student import Student


class Enrollment(Base):
    __tablename__ = "enrollment"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    course_offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offering.id"), nullable=False
    )
    enrollment_code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    grade: Mapped[int] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_withdrawn: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    student: Mapped[Student] = relationship("Student", back_populates="enrollments")
    course_offering: Mapped[CourseOffering] = relationship(
        "CourseOffering", back_populates="enrollments"
    )
    __table_args__ = (
        UniqueConstraint(
            "student_id", "course_offering_id", name="uq_student_course_offering"
        ),
    )
