import hashlib
import uuid
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

from core.authentication.fastapi_users import current_active_user, fastapi_users
from core.config import settings
from core.models.course import Course, CourseEnrollment
from core.models.db_helper import db_helper
from core.models.user import SQLAlchemyUserDatabase, User
from core.schemas.course import CourseRead
from core.schemas.user import (
    UserRead,
    UserUpdate,
)
from fastapi import APIRouter, Depends, Request, Response
from fastapi_cache.decorator import cache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.authentication import get_users_db

router = APIRouter(
    prefix=settings.api.v1.users,
    tags=["Users"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


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
    users_db: Annotated[
        "SQLAlchemyUserDatabase",
        Depends(get_users_db),
    ],
    # ) -> list["User"]:
) -> list[UserRead]:
    users = await users_db.get_users()
    return [UserRead.model_validate(user) for user in users]


@router.get("/{user_id}/courses", response_model=list[CourseRead])
async def get_user_courses(
    user_id: uuid.UUID,
    session: Session,
    user: Annotated[User, Depends(current_active_user)],
):
    stmt = (
        select(Course).join(CourseEnrollment).where(CourseEnrollment.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


# /me
# /{id}
router.include_router(
    router=fastapi_users.get_users_router(
        UserRead,
        UserUpdate,
    ),
)
