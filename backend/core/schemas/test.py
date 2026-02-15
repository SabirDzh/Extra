import uuid
from datetime import datetime
from typing import Annotated, Optional

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
    text: Optional[str] = None
    question_type: Optional[QuestionType] = None
    order_index: Optional[int] = None
    options: Optional[list[AnswerOptionCreate]] = None


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
    selected_answer_id: Optional[uuid.UUID] = None
    text_answer: Optional[str] = None


class TestSubmit(BaseModel):
    answers: list[TestAnswerSubmit]


class TestAnswerRead(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    selected_answer_id: Optional[uuid.UUID]
    text_answer: Optional[str]

    model_config = {"from_attributes": True}


class TestSubmissionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    block_id: uuid.UUID
    submitted_at: datetime
    score: Optional[int]
    max_score: int
    is_graded: bool
    graded_by: Optional[uuid.UUID]
    admin_comment: Optional[str]
    answers: list[TestAnswerRead]

    model_config = {"from_attributes": True}


class GradeSubmission(BaseModel):
    score: int
    admin_comment: Optional[str] = None
