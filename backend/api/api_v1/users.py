from datetime import datetime, timezone

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

from api.dependencies.authentication import get_users_db
from core.authentication.fastapi_users import (
    current_active_user,
    fastapi_users,
)
from core.config import settings
from core.models import (
    Block,
    CourseEnrollment,
    User,
    UserBlockProgress,
)
from core.models.block import TEST_BLOCK_TYPES
from core.models.user import SQLAlchemyUserDatabase
from core.schemas.stats import AdminSummaryRead, StatMetric
from core.schemas.user import (
    UserRead,
    UserUpdate,
)
from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from sqlalchemy import and_, func, select
from user_profile.main import save_user_avatar
from utils.product import current_admin

UsersDB = Annotated[SQLAlchemyUserDatabase, Depends(get_users_db)]
CurrentUser = Annotated[User, Depends(current_active_user)]
AdminUser = Annotated[User, Depends(current_admin)]


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

    cache_key = hashlib.md5(
        f"{func.__module__}:{func.__name__}:{args}:{cache_kw}".encode()
    ).hexdigest()
    return f"{namespace}:{cache_key}"


@router.get(
    "/summary",
    response_model=AdminSummaryRead,
)
async def get_admin_summary(
    users_db: UsersDB,
    admin: AdminUser,
) -> AdminSummaryRead:
    session = users_db.session


    total_users = await session.scalar(select(func.count(User.id)))
    total_tests_passed = await session.scalar(
        select(func.count(UserBlockProgress.id))
        .join(Block)
        .where(
            and_(
                UserBlockProgress.is_completed == True,
                Block.block_type.in_(TEST_BLOCK_TYPES),
            )
        )
    )


    now = datetime.now(timezone.utc)
    current_month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    if now.month == 1:
        prev_month_start = datetime(now.year - 1, 12, 1, tzinfo=timezone.utc)
    else:
        prev_month_start = datetime(now.year, now.month - 1, 1, tzinfo=timezone.utc)


    new_users_current = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= current_month_start)
    )
    new_users_prev = await session.scalar(
        select(func.count(User.id)).where(
            and_(
                User.created_at >= prev_month_start,
                User.created_at < current_month_start,
            )
        )
    )


    courses_current = await session.scalar(
        select(func.count(CourseEnrollment.id)).where(
            CourseEnrollment.completed_at >= current_month_start
        )
    )
    courses_prev = await session.scalar(
        select(func.count(CourseEnrollment.id)).where(
            and_(
                CourseEnrollment.completed_at >= prev_month_start,
                CourseEnrollment.completed_at < current_month_start,
            )
        )
    )

    def calculate_percent(current: int, previous: int) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    return AdminSummaryRead(
        total_users=total_users or 0,
        total_tests_passed=total_tests_passed or 0,
        course_stats=StatMetric(
            count=courses_current or 0,
            percent=calculate_percent(courses_current or 0, courses_prev or 0),
        ),
        new_users_stats=StatMetric(
            count=new_users_current or 0,
            percent=calculate_percent(new_users_current or 0, new_users_prev or 0),
        ),
    )


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
    admin: AdminUser,

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




router.include_router(
    router=fastapi_users.get_users_router(
        UserRead,
        UserUpdate,
    ),
)
