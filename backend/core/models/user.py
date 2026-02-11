from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyUserDatabase as SQLAlchemyUserDatabaseGeneric,
)
from sqlalchemy import JSON, Boolean, String, select
from sqlalchemy.dialects.postgresql import (
    ENUM as PgEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.role import UserRole

from .base import Base
from .mixins.id_int_pk import IdUuidPkMixin

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from core.models import AccessToken
    from core.models.certificate import Certificate
    from core.models.course import Course
    from core.models.progress import CourseEnrollment
    from core.models.test import TestSubmission
    from core.models.block import UserBlockProgress


class SQLAlchemyUserDatabase(SQLAlchemyUserDatabaseGeneric):
    async def get_users(self) -> list["User"]:
        statement = select(User).order_by(User.id)
        results = await self.session.scalars(statement)
        return list(results.all())


# надо добавить проверку если название уже существует, то выкидывать HTTPExceptions(status_code=status.HTTP_409_CONFLICT, detail="Product exists")
class User(IdUuidPkMixin, Base):
    email: Mapped[str] = mapped_column(
        String(length=320), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(length=1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # stores first_name, last_name, and middle_name
    # TODO replace with JSONB; JSON is used for testing
    username: Mapped[dict[str, str | None]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "first_name": str,
            "last_name": None,
            "middle_name": None,
        },
    )

    access_tokens: Mapped[list["AccessToken"]] = relationship(
        back_populates="user",
    )

    role: Mapped[UserRole] = mapped_column(
        PgEnum(UserRole),
        default=UserRole.user,
    )

    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        back_populates="user"
    )
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
        if not self.username:
            return "Unknown User"

        first = self.username.get("first_name", "") or ""
        last = self.username.get("last_name", "") or ""
        middle = self.username.get("middle_name", "") or ""

        return f"{last} {first} {middle}".strip()

    @classmethod
    def get_db(cls, session: "AsyncSession"):
        return SQLAlchemyUserDatabase(session, cls)

    def __str__(self):
        return self.email
