import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base
from core.models.mixins.id_int_pk import IdUuidPkMixin


class UserBlockProgress(IdUuidPkMixin, Base):
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    block_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_blocks.id"))

    is_unlocked: Mapped[bool] = mapped_column(default=False)
    video_watched: Mapped[bool] = mapped_column(default=False)
    test_passed: Mapped[bool] = mapped_column(default=False)

    last_attempt_date: Mapped[datetime] = mapped_column(nullable=False)


class TestSubmission(IdUuidPkMixin, Base):
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    block_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_blocks.id"))

    status: Mapped[str] = mapped_column(default="pending")
    inspection_comment: Mapped[str | None] = mapped_column(Text)

    answers: Mapped[list["UserAnswer"]] = relationship(back_populates="submission")


class UserAnswer(IdUuidPkMixin, Base):
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_submissions.id"))
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_questions.id"))

    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_options.id")
    )
    text_answer: Mapped[str | None] = mapped_column(Text)

    submission: Mapped["TestSubmission"] = relationship(back_populates="answers")
