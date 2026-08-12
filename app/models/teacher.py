from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.courseoffering import CourseOffering
    from app.models.department import Department

class Teacher(Base):
    __tablename__ = "teacher"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("department.id"))
    department: Mapped[Department] = relationship("Department", back_populates="teachers")
    course_offerings: Mapped[list[CourseOffering]] = relationship("CourseOffering", back_populates="teacher")
