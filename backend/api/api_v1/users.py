from datetime import datetime, timezone
import uuid

from typing import (
    Annotated,
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
    AdminRoleRequestDecision,
    AdminRoleRequestRead,
    UserPermissionsUpdate,
    UserRead,
    UserUpdate,
)
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy import and_, func, select
from Services.avatar_storage import save_user_avatar
from Services import admin_role_request as admin_role_request_crud
from api.dependencies.authorization import current_admin

UsersDB = Annotated[SQLAlchemyUserDatabase, Depends(get_users_db)]
CurrentUser = Annotated[User, Depends(current_active_user)]
AdminUser = Annotated[User, Depends(current_admin)]


router = APIRouter(
    prefix=settings.api.v1.users,
    tags=["Users"],
)


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
    return UserRead.model_validate(user)




@router.get("/admin-role-requests", response_model=list[AdminRoleRequestRead])
async def list_admin_role_requests(
    users_db: UsersDB,
    admin: AdminUser,
):
    return await admin_role_request_crud.list_pending_admin_role_requests(users_db.session)


@router.patch("/admin-role-requests/{request_id}", response_model=AdminRoleRequestRead)
async def review_admin_role_request(
    request_id: uuid.UUID,
    payload: AdminRoleRequestDecision,
    users_db: UsersDB,
    admin: AdminUser,
):
    result, error = await admin_role_request_crud.review_admin_role_request(
        users_db.session, request_id, payload.approve, admin.id
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Admin role request not found")
    if error == "already_reviewed":
        raise HTTPException(status_code=400, detail="Request already reviewed")
    if error == "not_whitelisted":
        raise HTTPException(
            status_code=403,
            detail="User is not in admin role whitelist",
        )
    return result


@router.patch("/{user_id}/permissions", response_model=UserRead)
async def update_user_permissions(
    user_id: uuid.UUID,
    payload: UserPermissionsUpdate,
    users_db: UsersDB,
    admin: AdminUser,
):
    target_user = await users_db.session.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    patch = payload.model_dump(exclude_unset=True)
    if "role" in patch and patch["role"] is not None:
        target_user.role = patch["role"]
    if "is_superuser" in patch and patch["is_superuser"] is not None:
        target_user.is_superuser = patch["is_superuser"]

    users_db.session.add(target_user)
    await users_db.session.commit()
    await users_db.session.refresh(target_user)
    return UserRead.model_validate(target_user)


router.include_router(
    router=fastapi_users.get_users_router(
        UserRead,
        UserUpdate,
    ),
)
