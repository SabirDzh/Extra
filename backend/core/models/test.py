import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Domain.Enums.test import QuestionType
from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class Question(IdUuidPkMixin, Base):
    block_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blocks.id", ondelete="CASCADE"), index=True
    )
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
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(String(1000))
    is_correct: Mapped[bool] = mapped_column(default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    question = relationship("Question", back_populates="options")


class TestSubmission(IdUuidPkMixin, Base):
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    block_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blocks.id", ondelete="CASCADE"), index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_graded: Mapped[bool] = mapped_column(default=False)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="submissions", foreign_keys=[user_id])
    grader = relationship("User", foreign_keys=[graded_by])
    block = relationship("Block", back_populates="submissions")
    answers = relationship(
        "TestAnswer", back_populates="submission", cascade="all, delete-orphan"
    )


class TestAnswer(IdUuidPkMixin, Base):
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_submissions.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    selected_answer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("answer_options.id", ondelete="CASCADE"), nullable=True, index=True
    )
    text_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission = relationship("TestSubmission", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    selected_option = relationship("AnswerOption")
