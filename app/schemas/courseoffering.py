from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseOfferingBase(BaseModel):
    course_id: int = Field(..., gt=0)
    teacher_id: int = Field(..., gt=0)
    semester: str = Field(..., min_length=1, max_length=10)
    academic_year: int = Field(..., ge=2000, le=2100)
    section: str = Field(..., min_length=1, max_length=10)


class CourseOfferingCreate(CourseOfferingBase):
    pass


class CourseOfferingUpdate(BaseModel):
    course_id: int | None = Field(default=None, gt=0)
    teacher_id: int | None = Field(default=None, gt=0)
    semester: str | None = Field(default=None, min_length=1, max_length=10)
    academic_year: int | None = Field(default=None, ge=2000, le=2100)
    section: str | None = Field(default=None, min_length=1, max_length=10)


class CourseOfferingResponseSchema(CourseOfferingBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
