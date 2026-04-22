from fastapi import APIRouter

from core.authentication.fastapi_users import fastapi_users
from api.dependencies.authentication import authentication_backend
from core.config import settings
from core.schemas.user import (
    UserRead,
    UserCreate,
)

router = APIRouter(
    prefix=settings.api.v1.auth,
    tags=["Auth"],
)



router.include_router(
    router=fastapi_users.get_auth_router(
        authentication_backend,

    ),
)



router.include_router(
    router=fastapi_users.get_register_router(
        UserRead,
        UserCreate,
    ),
)



router.include_router(
    router=fastapi_users.get_verify_router(UserRead),
)



router.include_router(
    router=fastapi_users.get_reset_password_router(),
)
