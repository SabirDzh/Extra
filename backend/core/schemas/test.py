import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from core.models.test import QuestionType


class TestResultStatus(str, Enum):
    CORRECT = "Верно"
    INCORRECT = "Неверно"
    REQUIRES_REVIEW = "Требует проверки"


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
    selected_answer_id: uuid.UUID | None = None
    text_answer: str | None = None


class TestSubmit(BaseModel):
    answers: list[TestAnswerSubmit]


class TestAnswerRead(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    selected_answer_id: uuid.UUID | None
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
    graded_by: uuid.UUID | None
    admin_comment: str | None
    answers: list[TestAnswerRead]

    model_config = {"from_attributes": True}


class GradeSubmission(BaseModel):
    score: int
    admin_comment: str | None = None


class QuestionResult(BaseModel):
    question_id: uuid.UUID
    text: str
    status: TestResultStatus
    correct_answer: str | None
    user_answer: str | None
    score: int


class BlockTestResults(BaseModel):
    block_id: uuid.UUID
    submission_id: uuid.UUID | None
    total_score: int | None
    max_score: int
    questions: list[QuestionResult]
