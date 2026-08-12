from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=10)
    department_id: int | None = Field(default=None, gt=0)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=10)
    department_id: int | None = Field(default=None, gt=0)


class CourseResponseSchema(CourseBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
