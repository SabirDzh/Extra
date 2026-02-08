import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.qestion import QuestionType

from core.models.base import Base
from core.models.course import CourseBlock

from .mixins.id_int_pk import IdUuidPkMixin


class TestQuestion(IdUuidPkMixin, Base):
    block_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_block.id"))

    text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column()

    block: Mapped["CourseBlock"] = relationship(back_populates="questions")
    option: Mapped[list["QuestionOption"]] = relationship(back_populates="question")


class QuestionOption(IdUuidPkMixin, Base):
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("testquestions.id"))

    text: Mapped[str] = mapped_column(String)
    is_correct: Mapped[bool] = mapped_column(default=False)

    question: Mapped["TestQuestion"] = relationship(back_populates="options")
