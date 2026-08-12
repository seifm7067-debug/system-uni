from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseScheduleBase(BaseModel):
    day: str = Field(..., min_length=1, max_length=10)
    schedule_type: str = Field(..., min_length=1, max_length=10)
    start_time: time
    end_time: time
    room: str = Field(..., min_length=1, max_length=10)
    course_offering_id: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        return self


class CourseScheduleCreate(CourseScheduleBase):
    pass


class CourseScheduleUpdate(BaseModel):
    day: str | None = Field(default=None, min_length=1, max_length=10)
    schedule_type: str | None = Field(default=None, min_length=1, max_length=10)
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(default=None, min_length=1, max_length=10)
    course_offering_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be strictly after start_time")
        return self


class CourseScheduleResponseSchema(CourseScheduleBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
