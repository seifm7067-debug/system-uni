from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StudentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    department_id: int = Field(..., gt=0)
    age: int | None = Field(default=None, gt=0, le=120)
    email: EmailStr


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    department_id: int | None = Field(default=None, gt=0)
    age: int | None = Field(default=None, gt=0, le=120)
    email: EmailStr | None = None


class StudentResponseSchema(StudentBase):
    id: int
    user_id: int | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
