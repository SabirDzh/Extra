import uuid

from pydantic import BaseModel
from utils.question import QuestionType


class QuestionOptionRead(BaseModel):
    id: uuid.UUID
    text: str


class TestQuestionRead(BaseModel):
    id: uuid.UUID
    text: str
    type: QuestionType
    options: list[QuestionOptionRead] = []


class AnswerCreate(BaseModel):
    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None = None
    text_answer: str | None = None


class TestSubmissionCreate(BaseModel):
    answers: list[AnswerCreate]
