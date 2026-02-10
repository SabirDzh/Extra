import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin

if TYPE_CHECKING:
    from core.models.block import UserBlockProgress
    from core.models.question import TestQuestion


class Course(IdUuidPkMixin, Base):
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(default=False)

    blocks: Mapped[list["CourseBlock"]] = relationship(
        back_populates="course", order_by="CourseBlock.order_index"
    )


class CourseBlock(IdUuidPkMixin, Base):
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"))

    title: Mapped[str] = mapped_column(String(128))
    order_index: Mapped[int] = mapped_column()

    video_url: Mapped[str | None] = mapped_column(String)
    text_content: Mapped[str | None] = mapped_column(Text)

    course: Mapped["Course"] = relationship(back_populates="blocks")
    questions: Mapped[list["TestQuestion"]] = relationship(back_populates="block")

    user_progress: Mapped[list["UserBlockProgress"]] = relationship(
        back_populates="block"
    )
