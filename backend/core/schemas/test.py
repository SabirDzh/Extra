import uuid
from datetime import datetime

from pydantic import BaseModel

from core.models.test import QuestionType


class AnswerOptionCreate(BaseModel):
    text: str
    is_correct: bool = False
    order_index: int = 0


class AnswerOptionRead(BaseModel):
    id: uuid.UUID
    text: str
    order_index: int

    model_config = {"from_attributes": True}


class AnswerOptionReadAdmin(AnswerOptionRead):
    is_correct: bool


class QuestionCreate(BaseModel):
    text: str
    question_type: QuestionType
    order_index: int = 0
    options: list[AnswerOptionCreate] = []


class QuestionUpdate(BaseModel):
    text: str | None = None
    question_type: QuestionType | None = None
    order_index: int | None = None
    options: list[AnswerOptionCreate] | None = None


class QuestionRead(BaseModel):
    id: uuid.UUID
    block_id: uuid.UUID
    text: str
    order_index: int
    question_type: QuestionType
    options: list[AnswerOptionRead]

    model_config = {"from_attributes": True}


class QuestionReadAdmin(BaseModel):
    id: uuid.UUID
    block_id: uuid.UUID
    text: str
    order_index: int
    question_type: QuestionType
    options: list[AnswerOptionReadAdmin]

    model_config = {"from_attributes": True}


class TestAnswerSubmit(BaseModel):
    question_id: uuid.UUID
    selected_answer_id: int | None = None
    text_answer: str | None = None


class TestSubmit(BaseModel):
    answers: list[TestAnswerSubmit]


class TestAnswerRead(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    selected_answer_id: int | None
    text_answer: str | None

    model_config = {"from_attributes": True}


class TestSubmissionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    block_id: uuid.UUID
    submitted_at: datetime
    score: int | None
    max_score: int
    is_graded: bool
    graded_by: int | None
    admin_comment: str | None
    answers: list[TestAnswerRead]

    model_config = {"from_attributes": True}


class GradeSubmission(BaseModel):
    score: int
    admin_comment: str | None = None
