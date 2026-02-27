import re
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi_users import schemas
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
)
from utils.role import UserRole

from core.types.user_id import UuIDMixin


class UserUsername(BaseModel):  # structures for working with names
    first_name: str = Field(min_length=1, max_length=64, examples=["Mike"])
    last_name: str | None = Field("", max_length=64, examples=["Rose"])
    middle_name: Annotated[Optional[str], Field(max_length=64)] = ""


class UserRead(schemas.BaseUser[UuIDMixin]):
    role: UserRole
    username: UserUsername  # response


class UserCreate(schemas.BaseUserCreate):
    password: Annotated[
        str,
        Field(
            min_length=12,
            max_length=128,
            examples=["TestPassword1!"],
        ),
    ]
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
    username: Optional[UserUsername] = None

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


# NEW USER DTO
# улучшить наследование и перепроверить дто модели, рассмотреть поле is_verified и is_active, и username
class Password(BaseModel):
    password: str = Field(min_length=12, max_length=64)

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


class UserBase(BaseModel):
    email: EmailStr
    is_active: bool
    username: UserUsername
    is_verified: bool


class UserDTORead(UserBase):
    id: uuid.UUID
    role: UserRole
    is_superuser: bool


class UserDTOUpdate(BaseModel):
    email: EmailStr | None = None
    password: Password | None = None
    username: UserUsername | None = None


class UserAdminDTOUpdate(UserBase):
    role: UserRole | None = None
    is_superuser: bool | None = None


class UserDTOCreate(BaseModel):
    email: EmailStr
    password: Password
    username: UserUsername
