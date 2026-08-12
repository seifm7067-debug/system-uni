from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeacherBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    department_id: int = Field(..., gt=0)


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    department_id: int | None = Field(default=None, gt=0)


class TeacherResponseSchema(TeacherBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
