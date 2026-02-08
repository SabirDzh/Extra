import uuid

from pydantic import BaseModel, Field


class CourseBlockRead(BaseModel):
    id: uuid.UUID
    title: str
    order: int
    is_locked: bool  # Вычисляемое поле на основе прогресса
    video_watched: bool  #
    test_passed: bool


class CoruseBlockCreated(BaseModel):
    title: str = Field(..., max_length=128)
    order: int = Field(..., ge=0)


class CourseDetailRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    progress_percent: float  # Прогресс-бар [cite: 98]
    blocks: list[CourseBlockRead]


class CourseDetailCreate(BaseModel):
    title: str = Field(..., max_length=128)
    description: str = Field(..., max_length=1024)
