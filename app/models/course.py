from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.courseoffering import CourseOffering
    from app.models.department import Department


class Course(Base):
    __tablename__ = "course"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id"), nullable=True
    )
    department: Mapped[Department] = relationship(
        "Department", back_populates="courses"
    )
    course_offerings: Mapped[list[CourseOffering]] = relationship(
        "CourseOffering", back_populates="course"
    )
    __table_args__ = (
        UniqueConstraint("department_id", "code", name="uq_course_code"),
        UniqueConstraint("department_id", "name", name="uq_course_name"),
    )
