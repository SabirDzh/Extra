from fastapi_users import schemas
from pydantic import BaseModel, Field
from utils.role import UserRole


from core.types.user_id import UserIdType


class UserRead(schemas.BaseUser[UserIdType]):
    role: UserRole


class UserCreate(schemas.BaseUserCreate):
    role: UserRole


class UserUpdate(schemas.BaseUserUpdate):
    pass


class UserRegisteredNotification(BaseModel):
    user: UserRead
    ts: int
