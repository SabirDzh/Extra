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

from core.types.user_id import UuIDMixin

from .base import Base
from .mixins.id_int_pk import IdUuidPkMixin

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from core.models import AccessToken


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

    # stores first_name, last_name, and middle_name
    # TODO заменить на JSONB, используется JSON для тестирования
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

    @classmethod
    def get_db(cls, session: "AsyncSession"):
        return SQLAlchemyUserDatabase(session, cls)

    def __str__(self):
        return self.email
