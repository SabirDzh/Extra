import uuid

from pydantic import BaseModel, ConfigDict, Field


class CourseRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    is_published: bool

    model_config = ConfigDict(from_attributes=True)


class CourseBlockRead(BaseModel):
    id: uuid.UUID
    title: str
    order: int = Field(validation_alias="order_index")
    is_locked: bool = True
    video_watched: bool = False
    test_passed: bool = False

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CourseBlockCreated(BaseModel):
    title: str = Field(..., max_length=128)
    order: int = Field(..., ge=0)


class CourseDetailRead(CourseRead):
    progress_percent: float = 0.0
    blocks: list[CourseBlockRead] = []

    model_config = ConfigDict(from_attributes=True)


class CourseDetailCreate(BaseModel):
    title: str = Field(..., max_length=128)
    description: str = Field(..., max_length=1024)
    is_published: bool = False


class CourseBlockCreate(BaseModel):
    title: str = Field(..., max_length=128)
    order_index: int = Field(..., ge=0)
    video_url: str | None = None
    text_content: str | None = None
