from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=10)
    college_id: int = Field(..., gt=0)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=10)
    college_id: int | None = Field(default=None, gt=0)


class DepartmentResponseSchema(DepartmentBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
