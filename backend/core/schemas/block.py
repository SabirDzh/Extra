import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from core.models.block import BlockType


class BlockCreate(BaseModel):
    title: str
    block_type: BlockType
    order_index: int = 0
    text_content: str | None = None
    video_url: str | None = None

    @model_validator(mode="after")
    def check_content(self):
        if (
            self.block_type == BlockType.lesson
            and not self.text_content
            and not self.video_url
        ):
            raise ValueError("Lesson block must have text_content or video_url")
        return self


class BlockUpdate(BaseModel):
    title: str | None = None
    order_index: int | None = None
    text_content: str | None = None
    video_url: str | None = None


class BlockRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    order_index: int
    title: str
    block_type: BlockType
    text_content: str | None
    video_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
