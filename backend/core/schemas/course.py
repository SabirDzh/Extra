import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from core.models.course import (
    AUDIENCE_DISPLAY_NAMES,
    LEVEL_DISPLAY_NAMES,
    CourseAudience,
    CourseLevel,
    CourseStatus,
)


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str = Field("", max_length=1024)
    level: CourseLevel = Field(default=CourseLevel.beginner)
    audience: CourseAudience = Field(default=CourseAudience.everyone)
    is_published: bool = True


class CourseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = Field(None, max_length=1024)
    level: CourseLevel | None = None
    audience: CourseAudience | None = None
    is_published: bool | None = None


class CourseRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    level: CourseLevel
    audience: CourseAudience
    is_published: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    progress: "CourseProgress" = None  # type: ignore[assignment]

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[misc]
    @property
    def level_label(self) -> str:
        """Human-readable level name for the frontend (e.g. 'Начинающий')."""
        return LEVEL_DISPLAY_NAMES[self.level]

    @computed_field  # type: ignore[misc]
    @property
    def audience_label(self) -> str:
        """Human-readable audience name for the frontend (e.g. 'Для всех')."""
        return AUDIENCE_DISPLAY_NAMES[self.audience]


class CourseProgress(BaseModel):
    completed: int = 0
    total: int = 0
    percent: float = 0.0
    status: CourseStatus = CourseStatus.not_started

