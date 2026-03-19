import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from core.models.course import CourseLevel


class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field("", max_length=1024)
    level: CourseLevel = Field(default=CourseLevel.beginner)
    is_published: bool = True


class CourseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = Field(None, max_length=1024)
    level: CourseLevel | None = None
    is_published: bool | None = None


class CourseRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    level: CourseLevel
    is_published: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CourseProgress(BaseModel):
    completed: int | None
    total: int
    percent: float
