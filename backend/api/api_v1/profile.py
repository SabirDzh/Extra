from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.profile import (
    CertificateItemRead,
    CourseProgressRead,
    RecentCourseRead,
    TestAttemptRead,
)
from profile.service import (
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
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await get_test_attempts(db, user.id, offset=offset, limit=limit)


@router.get("/courses-progress", response_model=list[CourseProgressRead])
async def list_courses_progress(
    db: Session,
    user: User = Depends(current_active_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await get_courses_progress(db, user.id, offset=offset, limit=limit)


@router.get("/certificates", response_model=list[CertificateItemRead])
async def list_certificates(
    db: Session,
    user: User = Depends(current_active_user),
):
    return await get_certificates(db, user.id)


@router.get("/recent-courses", response_model=list[RecentCourseRead])
async def list_recent_courses(
    db: Session,
    user: User = Depends(current_active_user),
    limit: int = Query(5, ge=1, le=20),
):
    return await get_recent_courses(db, user.id, limit=limit)
