import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from core.models.block import BlockType


class BlockCreate(BaseModel):
    title: str
    block_type: BlockType
    order_index: int = 0
    text_content: Optional[str] = None
    video_url: Optional[str] = None

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
    title: Optional[str] = None
    order_index: Optional[int] = None
    text_content: Optional[str] = None
    video_url: Optional[str] = None


class BlockRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    order_index: int
    title: str
    block_type: BlockType
    text_content: Optional[str]
    video_url: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
