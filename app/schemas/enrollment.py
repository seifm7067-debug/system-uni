from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _validate_active_withdrawn(is_active: bool, is_withdrawn: bool) -> None:
    if is_active and is_withdrawn:
        raise ValueError("is_active and is_withdrawn cannot both be true")


class EnrollmentBase(BaseModel):
    student_id: int = Field(..., gt=0)
    course_offering_id: int = Field(..., gt=0)
    enrollment_code: str = Field(..., min_length=1, max_length=50)
    grade: int | None = Field(default=None, ge=0, le=100)
    is_active: bool = True
    is_withdrawn: bool = False

    @model_validator(mode="after")
    def validate_active_withdrawn(self):
        _validate_active_withdrawn(self.is_active, self.is_withdrawn)
        return self


class EnrollmentCreate(EnrollmentBase):
    pass


class EnrollmentUpdate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    course_offering_id: int | None = Field(default=None, gt=0)
    enrollment_code: str | None = Field(default=None, min_length=1, max_length=50)
    grade: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    is_withdrawn: bool | None = None

    @model_validator(mode="after")
    def validate_active_withdrawn(self):
        if self.is_active is not None and self.is_withdrawn is not None:
            _validate_active_withdrawn(self.is_active, self.is_withdrawn)
        return self


class EnrollmentResponseSchema(EnrollmentBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
