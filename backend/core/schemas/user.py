from fastapi_users import schemas
from pydantic import (
    BaseModel,
    Field,
    model_validator,
)
from utils.role import UserRole

from core.types.user_id import UuIDMixin


class UserUsername(BaseModel):  # structures for working with names
    first_name: str = Field(..., min_length=1, max_length=128, pattern="^[A-Za-z-_]+$")
    last_name: str | None = Field(None, max_length=128, pattern="^[A-Za-z-_]+$")
    middle_name: str | None = Field(None, max_length=128, pattern="^[A-Za-z-_]+$")


class UserRead(schemas.BaseUser[UuIDMixin]):
    role: UserRole
    username: UserUsername  # response


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(..., min_length=12, max_length=128)
    role: UserRole
    username: UserUsername  # registration
    # password_confirm: str | None = None

    # @model_validator(mode="after")
    # def check_passwords_match(self) -> Self:
    #     if self.password != self.password_confirm:
    #         raise ValueError("passwords do not match")
    #     return self

    # TODO устани конфликты полей, из-за того что второе поле пароля обязательное, в крудах при использовании схемы не передается поле password_confirm возникает ошибка


class UserUpdate(schemas.BaseUserUpdate):
    username: UserUsername | None = None


class UserRegisteredNotification(BaseModel):
    user: UserRead
    ts: int
