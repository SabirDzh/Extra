import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from core.models.block import BlockType, TEST_BLOCK_TYPES
from core.schemas.course import CourseProgress

class BlockCreate(BaseModel):
    title: str | None = None
    block_type: BlockType
    order_index: int = 0
    text_content: str | None = None
    video_url: str | None = None

    @model_validator(mode="after")
    def normalize_by_block_type(self):
        if self.block_type in TEST_BLOCK_TYPES:

            self.text_content = None
            self.video_url = None
        elif self.block_type == BlockType.lesson:
            if not self.text_content and not self.video_url:
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
    
    audience_label: str
    level_label: str
    description: str | None = None
    progress: CourseProgress | None
    next_block_id: uuid.UUID | None = None
    stage: int = 1
    under_review: bool = False

    model_config = ConfigDict(from_attributes=True)


class CourseBlocksResponse(BaseModel):
    blocks: list[BlockRead]
    audience_label: str
    level_label: str
    progress: CourseProgress | None
    current_block_id: uuid.UUID | None = None
    all_blocks: int = 0
    all_stages: int = 0
