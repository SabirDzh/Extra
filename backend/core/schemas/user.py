from fastapi_users import schemas
from pydantic import (
    BaseModel,
    Field,
)
from utils.role import UserRole

from core.types.user_id import UuIDMixin


class UserRead(schemas.BaseUser[UuIDMixin]):
    role: UserRole
    fullname: str
    image_url: str | None = None


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(
        min_length=4,
        max_length=64,
    )
    role: UserRole
    fullname: str = Field(min_length=1, max_length=128)
    image_url: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    password: str | None = None
    fullname: str | None = None
    image_url: str | None = None


class UserRegisteredNotification(BaseModel):
    user: UserRead
    ts: int
