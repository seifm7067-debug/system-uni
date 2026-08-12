from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CollegeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=10)


class CollegeCreate(CollegeBase):
    pass


class CollegeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=10)


class CollegeResponseSchema(CollegeBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
