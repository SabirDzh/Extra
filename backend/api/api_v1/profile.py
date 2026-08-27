from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.profile import (
    CertificateItemRead,
    CourseProgressRead,
    RecentCourseRead,
    TestAttemptRead,
)
from Services.profile import (
    get_certificates,
    get_courses_progress,
    get_recent_courses,
    get_test_attempts,
)

router = APIRouter(
    prefix=settings.api.v1.profile,
    tags=["Profile"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("/test-attempts", response_model=list[TestAttemptRead])
async def list_test_attempts(
    db: Session,
    user: User = Depends(current_active_user),
    pagination: PaginationParams = Depends(),
):
    return await get_test_attempts(
        db,
        user.id,
        user.role,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/courses-progress", response_model=list[CourseProgressRead])
async def list_courses_progress(
    db: Session,
    user: User = Depends(current_active_user),
    pagination: PaginationParams = Depends(),
):
    return await get_courses_progress(
        db,
        user.id,
        user.role,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/certificates", response_model=list[CertificateItemRead])
async def list_certificates(
    db: Session,
    user: User = Depends(current_active_user),
):
    return await get_certificates(db, user.id, user.role)


@router.get("/recent-courses", response_model=list[RecentCourseRead])
async def list_recent_courses(
    db: Session,
    user: User = Depends(current_active_user),
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=20),
):
    offset = (page - 1) * limit
    return await get_recent_courses(
        db,
        user.id,
        user.role,
        limit=limit,
        offset=offset,
    )
