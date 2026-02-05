from fastapi_users import schemas
from pydantic import (
    BaseModel,
    model_validator,
)
from typing_extensions import Self
from utils.role import UserRole

from core.types.user_id import UserIdType


class UserUsername(BaseModel):  # structures for working with names
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None


class UserRead(schemas.BaseUser[UserIdType]):
    role: UserRole
    username: UserUsername  # response


class UserCreate(schemas.BaseUserCreate):
    role: UserRole
    username: UserUsername  # registration
    password_confirm: str

    @model_validator(mode="after")
    def check_passwords_match(self) -> Self:
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self


class UserUpdate(schemas.BaseUserUpdate):
    username: UserUsername | None = None


class UserRegisteredNotification(BaseModel):
    user: UserRead
    ts: int
