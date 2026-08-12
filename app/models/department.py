from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.college import College
    from app.models.course import Course
    from app.models.student import Student
    from app.models.teacher import Teacher


class Department(Base):
    __tablename__ = "department"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    college_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("college.id"), nullable=False
    )
    college: Mapped[College] = relationship("College", back_populates="departments")
    teachers: Mapped[list[Teacher]] = relationship(
        "Teacher", back_populates="department"
    )
    students: Mapped[list[Student]] = relationship(
        "Student", back_populates="department"
    )
    courses: Mapped[list[Course]] = relationship("Course", back_populates="department")
    __table_args__ = (
        UniqueConstraint("college_id", "name", name="uq_department_name"),
        UniqueConstraint("college_id", "code", name="uq_department_code"),
    )
