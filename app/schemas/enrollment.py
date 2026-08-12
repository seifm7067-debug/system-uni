from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnrollmentBase(BaseModel):
    student_id: int = Field(..., gt=0)
    course_offering_id: int = Field(..., gt=0)
    enrollment_code: str = Field(..., min_length=1, max_length=50)
    grade: int | None = Field(default=None, ge=0, le=100)
    is_active: bool = True
    is_withdrawn: bool = False


class EnrollmentCreate(EnrollmentBase):
    pass


class EnrollmentUpdate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    course_offering_id: int | None = Field(default=None, gt=0)
    enrollment_code: str | None = Field(default=None, min_length=1, max_length=50)
    grade: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    is_withdrawn: bool | None = None


class EnrollmentResponseSchema(EnrollmentBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
