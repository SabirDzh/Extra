import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class QuestionType(str, enum.Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    free_text = "free_text"


class Question(IdUuidPkMixin, Base):
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id"))
    text: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType))

    block = relationship("Block", back_populates="questions")
    options = relationship(
        "AnswerOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="AnswerOption.order_index",
    )
    answers = relationship(
        "TestAnswer", back_populates="question", cascade="all, delete-orphan"
    )


class AnswerOption(IdUuidPkMixin, Base):
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    text: Mapped[str] = mapped_column(String(1000))
    is_correct: Mapped[bool] = mapped_column(default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    question = relationship("Question", back_populates="options")


class TestSubmission(IdUuidPkMixin, Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id"))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_score: Mapped[int] = mapped_column(Integer, default=0)
    is_graded: Mapped[bool] = mapped_column(default=False)
    graded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="submissions", foreign_keys=[user_id])
    grader = relationship("User", foreign_keys=[graded_by])
    block = relationship("Block", back_populates="submissions")
    answers = relationship(
        "TestAnswer", back_populates="submission", cascade="all, delete-orphan"
    )


class TestAnswer(IdUuidPkMixin, Base):
    submission_id: Mapped[int] = mapped_column(ForeignKey("test_submissions.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    selected_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey("answer_options.id"), nullable=True
    )
    text_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission = relationship("TestSubmission", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    selected_option = relationship("AnswerOption")
