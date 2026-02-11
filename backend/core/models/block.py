import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class BlockType(str, enum.Enum):
    lesson = "lesson"
    auto_test = "auto_test"
    manual_test = "manual_test"


class Block(IdUuidPkMixin, Base):
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(500))
    block_type: Mapped[BlockType] = mapped_column(Enum(BlockType))
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    course = relationship("Course", back_populates="blocks")
    questions = relationship(
        "Question",
        back_populates="block",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    submissions = relationship(
        "TestSubmission", back_populates="block", cascade="all, delete-orphan"
    )
    progress_records = relationship(
        "UserBlockProgress", back_populates="block", cascade="all, delete-orphan"
    )
