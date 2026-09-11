from typing import TYPE_CHECKING, Any

from app.database import Base
from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.job import Job


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result: Mapped[Any] = mapped_column(JSON, nullable=True)
    job_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("job.job_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    job: Mapped[Job] = relationship("Job", back_populates="report")
