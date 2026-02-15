from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PopularMistake(BaseModel):
    question: str
    answer: str
    count: int


class StatisticsResponse(BaseModel):
    completion_rate: float
    average_score: float
    popular_mistakes: list[PopularMistake]


class GradeSubmissionRequest(BaseModel):
    is_passed: bool
    admin_comment: Optional[str] = None


class PendingSubmissionResponse(BaseModel):
    id: UUID
    user_email: str
    course_title: str
    block_title: str
    max_score: int
    submitted_at: str
    answers: list[dict]

    model_config = {"from_attributes": True}