from datetime import datetime, time
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import DateTime, ForeignKey, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.courseoffering import CourseOffering


class CourseSchedule(Base):
    __tablename__ = "course_schedule"
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[str] = mapped_column(String(10), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    room: Mapped[str] = mapped_column(String(10), nullable=False)
    course_offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offering.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    course_offering: Mapped[CourseOffering] = relationship(
        "CourseOffering", back_populates="course_schedules"
    )
    __table_args__ = (
        UniqueConstraint(
            "course_offering_id",
            "day",
            "start_time",
            "end_time",
            name="uq_course_schedule",
        ),
    )
