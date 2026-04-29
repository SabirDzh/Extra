from datetime import datetime
from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyUserDatabase as SQLAlchemyUserDatabaseGeneric,
)
from sqlalchemy import JSON, Boolean, DateTime, String, func, select
from sqlalchemy.dialects.postgresql import (
    ENUM as PgEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from Domain.Enums.user_role import UserRole

from .base import Base
from .mixins.id_int_pk import IdUuidPkMixin

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from core.models import AccessToken
    from core.models.certificates import Certificate
    from core.models.course import Course, CourseEnrollment
    from core.models.progress import UserBlockProgress
    from core.models.test import TestSubmission


class SQLAlchemyUserDatabase(SQLAlchemyUserDatabaseGeneric):
    async def get_users(self) -> list["User"]:
        statement = select(User).order_by(User.id)
        results = await self.session.scalars(statement)
        return list(results.all())


class User(IdUuidPkMixin, Base):
    email: Mapped[str] = mapped_column(
        String(length=320), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(length=1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    fullname: Mapped[str] = mapped_column(
        String(length=128),
        nullable=False,
    )

    access_tokens: Mapped[list["AccessToken"]] = relationship(
        back_populates="user",
    )

    role: Mapped[UserRole] = mapped_column(
        PgEnum(UserRole),
        default=UserRole.user,
    )

    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    enrollments: Mapped[list["CourseEnrollment"]] = relationship(back_populates="user")
    created_courses: Mapped[list["Course"]] = relationship(back_populates="creator")
    submissions: Mapped[list["TestSubmission"]] = relationship(
        back_populates="user",
        foreign_keys="TestSubmission.user_id",
    )
    block_progress: Mapped[list["UserBlockProgress"]] = relationship(
        back_populates="user"
    )

    certificates: Mapped[list["Certificate"]] = relationship(back_populates="user")
    progress: Mapped[list["UserBlockProgress"]] = relationship(
        back_populates="user",
        overlaps="block_progress",
    )

    @property
    def full_name(self) -> str:
        return self.fullname or "Unknown User"

    @classmethod
    def get_db(cls, session: "AsyncSession"):
        return SQLAlchemyUserDatabase(session, cls)

    def __str__(self):
        return self.email
