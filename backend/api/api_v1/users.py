import hashlib
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Tuple,
    Union,
)

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi_cache import FastAPICache

from core.authentication.fastapi_users import (
    current_active_user,
    fastapi_users,
)
from core.config import settings
from core.models import User
from core.models.user import SQLAlchemyUserDatabase
from core.schemas.user import (
    UserRead,
    UserUpdate,
)
from fastapi_cache.decorator import cache

from api.dependencies.authentication import get_users_db
from profile.main import save_user_avatar

UsersDB = Annotated[SQLAlchemyUserDatabase, Depends(get_users_db)]
CurrentUser = Annotated[User, Depends(current_active_user)]

router = APIRouter(
    prefix=settings.api.v1.users,
    tags=["Users"],
)


def users_list_key_builder(
    func: Callable[..., Any],
    namespace: str = "",
    *,
    request: Optional[Request] = None,
    response: Optional[Response] = None,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Union[str, Awaitable[str]]:
    exclude_types = (SQLAlchemyUserDatabase,)
    cache_kw = {}
    for name, value in kwargs.items():
        if isinstance(value, exclude_types):
            continue
        cache_kw[name] = value

    cache_key = hashlib.md5(  # noqa: S324
        f"{func.__module__}:{func.__name__}:{args}:{cache_kw}".encode()
    ).hexdigest()
    return f"{namespace}:{cache_key}"


@router.get(
    "",
    response_model=list[UserRead],
)
@cache(
    expire=60,
    key_builder=users_list_key_builder,
    namespace=settings.cache.namespace.users_list,
)
async def get_users_list(
    users_db: UsersDB,
    # ) -> list["User"]:
) -> list[UserRead]:
    users = await users_db.get_users()
    return [UserRead.model_validate(user) for user in users]


@router.post(
    "/me/avatar",
    response_model=UserRead,
)
async def upload_my_avatar(
    user: CurrentUser,
    users_db: UsersDB,
    file: UploadFile = File(...),
) -> UserRead:
    image_url = save_user_avatar(
        user_id=str(user.id),
        file=file,
    )
    user.image_url = image_url

    users_db.session.add(user)
    await users_db.session.commit()
    await users_db.session.refresh(user)

    await FastAPICache.clear(
        namespace=settings.cache.namespace.users_list,
    )
    return UserRead.model_validate(user)


# /me
# /{id}
router.include_router(
    router=fastapi_users.get_users_router(
        UserRead,
        UserUpdate,
    ),
)
