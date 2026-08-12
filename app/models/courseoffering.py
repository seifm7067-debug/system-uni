from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.courseschedule import CourseSchedule
    from app.models.enrollment import Enrollment
    from app.models.teacher import Teacher

class CourseOffering(Base):
    __tablename__ = "course_offering"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id"), nullable=False)
    semester: Mapped[str] = mapped_column(String(10), nullable=False)
    academic_year: Mapped[int] = mapped_column( nullable=False)
    section: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    course: Mapped[Course] = relationship("Course", back_populates="course_offerings")
    teacher: Mapped[Teacher] = relationship("Teacher", back_populates="course_offerings")
    course_schedules: Mapped[list[CourseSchedule]] = relationship("CourseSchedule", back_populates="course_offering")
    enrollments: Mapped[list[Enrollment]] = relationship("Enrollment", back_populates="course_offering")
    __table_args__ = (
        UniqueConstraint("course_id","teacher_id","semester","academic_year","section", name="uq_course_offering"),
    )
