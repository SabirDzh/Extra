import re
from typing import Optional

from fastapi_users import schemas
from pydantic import (
    BaseModel,
    Field,
    field_validator,
)
from utils.role import UserRole

from core.types.user_id import UuIDMixin


class UserUsername(BaseModel):  # structures for working with names
    first_name: str = Field(
        ..., min_length=1, max_length=64, pattern="^[A-Za-zА-Яа-яёЁ0-9_-]+$"
    )
    last_name: str | None = Field(
        None,
        max_length=64,
        pattern="^[A-Za-zА-Яа-яёЁ0-9_-]+$",
    )
    middle_name: str | None = Field(
        None, max_length=64, pattern="^[A-Za-zА-Яа-яёЁ0-9_-]+$"
    )


class UserRead(schemas.BaseUser[UuIDMixin]):
    role: UserRole
    username: UserUsername  # response


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
    )
    role: UserRole
    username: UserUsername  # registration
    # password_confirm: str | None = None

    # @model_validator(mode="after")
    # def check_passwords_match(self) -> Self:
    #     if self.password != self.password_confirm:
    #         raise ValueError("passwords do not match")
    #     return self
    # TODO устани конфликты полей, из-за того что второе поле пароля обязательное, в крудах при использовании схемы не передается поле password_confirm возникает ошибка
    #
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"\d", v):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")

        if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", v):
            raise ValueError("Пароль должен содержать буквы")

        if not re.search(r"[A-ZА-Я]", v):
            raise ValueError("Пароль должен содержать заглавную букву")

        if not re.search(r"[\W_]", v):
            raise ValueError("Пароль должен содержать спецсимвол (например, ! @ # $)")

        return v


# schemas.BaseUserUpdate
class UserUpdate(schemas.BaseUserUpdate):
    password: Optional[str] = None
    username: UserUsername | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"\d", v):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")

        if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", v):
            raise ValueError("Пароль должен содержать буквы")

        if not re.search(r"[A-ZА-Я]", v):
            raise ValueError("Пароль должен содержать заглавную букву")

        if not re.search(r"[\W_]", v):
            raise ValueError("Пароль должен содержать спецсимвол (например, ! @ # $)")

        return v


class UserRegisteredNotification(BaseModel):
    user: UserRead
    ts: int
