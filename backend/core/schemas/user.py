from fastapi_users import schemas
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    field_serializer,
)
from Domain.Enums.user_role import UserRole, normalize_user_role

from core.types.user_id import UuIDMixin


class UserRead(schemas.BaseUser[UuIDMixin]):
    role: UserRole
    fullname: str
    image_url: str | None = None

    @field_serializer("role")
    def serialize_role(self, role: UserRole) -> str:
        role_labels = {
            UserRole.admin: "Администратор",
            UserRole.installer: "Монтажник",
            UserRole.seller: "Продавец",
            UserRole.serviceman: "Сервисник",
            UserRole.buyer: "Покупатель",
        }
        return role_labels.get(role, role.value)


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(
        min_length=4,
        max_length=64,
    )
    role: UserRole
    fullname: str = Field(min_length=1, max_length=128)
    image_url: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_no_spaces(cls, v):
        if isinstance(v, str) and any(c.isspace() for c in v):
            raise ValueError("Email не должен содержать пробелов")
        return v

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_min_non_space(cls, v):
        if v is not None and isinstance(v, str):
            if len(v.strip()) < 4:
                raise ValueError("Пароль должен содержать не менее 4 символов (без учета внешних пробелов)")
        return v

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        return normalize_user_role(v)


class UserUpdate(schemas.BaseUserUpdate):
    password: str | None = None
    role: UserRole | None = None
    fullname: str | None = None
    image_url: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_no_spaces(cls, v):
        if v is not None and isinstance(v, str) and any(c.isspace() for c in v):
            raise ValueError("Email не должен содержать пробелов")
        return v

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_min_non_space(cls, v):
        if v is not None and isinstance(v, str):
            if len(v.strip()) < 4:
                raise ValueError("Пароль должен содержать не менее 4 символов (без учета внешних пробелов)")
        return v

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        if v is None:
            return v
        return normalize_user_role(v)


class UserPermissionsUpdate(BaseModel):
    role: UserRole | None = None
    is_superuser: bool | None = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        if v is None:
            return v
        return normalize_user_role(v)


class UserRegisteredNotification(BaseModel):
    user: UserRead
    ts: int


class AdminRoleRequestRead(BaseModel):
    id: UuIDMixin
    user_id: UuIDMixin
    user_email: str
    user_fullname: str
    status: str
    requested_at: str
    reviewed_at: str | None = None
    reviewed_by: UuIDMixin | None = None


class AdminRoleRequestDecision(BaseModel):
    approve: bool = Field(..., description="true -> approve admin role, false -> reject")
