from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from app.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.enrollment import Enrollment
    from app.models.user import User


class Student(Base):
    __tablename__ = "student"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("department.id"))
    department: Mapped[Department] = relationship(
        "Department", back_populates="students"
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        "Enrollment", back_populates="student"
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    user: Mapped[User] = relationship("User", back_populates="student")
    version_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    __mapper_args__: ClassVar[dict[str, Any]] = {
        "version_id_col": version_id,
    }
