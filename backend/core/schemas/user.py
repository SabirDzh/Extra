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
    fullname: str  # response
    image_url: str | None = None


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(
        min_length=4,
        max_length=64,
    )
    role: UserRole
    fullname: str = Field(min_length=1, max_length=128)  # registration
    image_url: str | None = None
    # password_confirm: str | None = None

    # @model_validator(mode="after")
    # def check_passwords_match(self) -> Self:
    #     if self.password != self.password_confirm:
    #         raise ValueError("passwords do not match")
    #     return self
    # TODO resolve field conflicts: since the second password field is required,
    # CRUD usage without password_confirm triggers a validation error
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
    password: str | None = None
    fullname: str | None = None
    image_url: str | None = None

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
