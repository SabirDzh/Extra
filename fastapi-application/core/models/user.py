from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseUserTable,
    SQLAlchemyUserDatabase as SQLAlchemyUserDatabaseGeneric,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.types.user_id import UserIdType
from .base import Base
from .mixins.id_int_pk import IdUuidPkMixin
from utils.role import UserRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from core.models import AccessToken


class SQLAlchemyUserDatabase(SQLAlchemyUserDatabaseGeneric):

    async def get_users(self) -> list["User"]:
        statement = select(User).order_by(User.id)
        results = await self.session.scalars(statement)
        return list(results.all())


class User(Base, IdUuidPkMixin, SQLAlchemyBaseUserTable[UserIdType]):
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
