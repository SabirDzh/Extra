import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Domain.Enums.block import BlockType
from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin




TEST_BLOCK_TYPES = {BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test}


class Block(IdUuidPkMixin, Base):
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(500))
    block_type: Mapped[BlockType] = mapped_column(Enum(BlockType))
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    questions_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
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
