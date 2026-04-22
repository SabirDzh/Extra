import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as SaEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class CourseLevel(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"




LEVEL_DISPLAY_NAMES: dict[str, str] = {
    CourseLevel.beginner: "Начинающий",
    CourseLevel.intermediate: "Продвинутый",
    CourseLevel.advanced: "Эксперт",
}


class CourseAudience(str, enum.Enum):
    everyone = "everyone"
    installer = "installer"


AUDIENCE_DISPLAY_NAMES: dict[str, str] = {
    CourseAudience.everyone: "Для всех",
    CourseAudience.installer: "Монтажник",
}


class CourseStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class Course(IdUuidPkMixin, Base):
    __table_args__ = (
        Index(
            "ix_course_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_course_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )

    title: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[CourseLevel] = mapped_column(
        SaEnum(CourseLevel),
        default=CourseLevel.beginner,
        nullable=False,
    )
    audience: Mapped[CourseAudience] = mapped_column(
        SaEnum(CourseAudience),
        default=CourseAudience.everyone,
        nullable=False,
    )
    is_published: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    creator = relationship("User", back_populates="created_courses")
    enrollments = relationship(
        "CourseEnrollment", back_populates="course", cascade="all, delete-orphan"
    )
    blocks = relationship(
        "Block",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Block.order_index",
    )
    certificates = relationship(
        "Certificate", back_populates="course", cascade="all, delete-orphan"
    )


class CourseEnrollment(IdUuidPkMixin, Base):
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE")
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
