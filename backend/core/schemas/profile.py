import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from core.models.block import BlockType


class TestAttemptRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    block_id: uuid.UUID
    block_title: str
    block_type: BlockType
    submitted_at: datetime
    score: int | None
    max_score: int
    is_graded: bool
    admin_comment: str | None

    model_config = ConfigDict(from_attributes=True)


class CourseProgressRead(BaseModel):
    course_id: uuid.UUID
    course_title: str
    total_blocks: int
    completed_blocks: int
    percent: float

    model_config = ConfigDict(from_attributes=True)


class CertificateItemRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    certificate_number: str
    issued_at: datetime
    download_url: str

    model_config = ConfigDict(from_attributes=True)


class RecentCourseRead(BaseModel):
    course_id: uuid.UUID
    course_title: str
    last_activity: datetime

    model_config = ConfigDict(from_attributes=True)
