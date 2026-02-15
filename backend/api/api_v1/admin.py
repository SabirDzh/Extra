import uuid
from typing import Annotated

from core.config import settings
from core.models.course import Course, CourseEnrollment
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.admin import (
    GradeSubmissionRequest,
    PendingSubmissionResponse,
    StatisticsResponse,
)
from core.schemas.user import UserRead
from crud.admin import (
    admin_grade_submission,
    get_pending_submissions,
    get_statistics,
    set_new_user_role,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin
from utils.role import UserRole

router = APIRouter(
    prefix=settings.api.v1.admin,
    tags=["Admin"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get(
    "/statistics",
    response_model=StatisticsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_admin_statistics(
    session: Session,
    admin: Annotated[User, Depends(current_admin)],
    course_id: Annotated[uuid.UUID | None, Query()] = None,
):
    return await get_statistics(session, course_id=course_id)


@router.get(
    "/submissions/pending",
    response_model=list[PendingSubmissionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_pending_submissions(
    session: Session,
    admin: Annotated[User, Depends(current_admin)],
    course_id: Annotated[uuid.UUID | None, Query()] = None,
):
    return await get_pending_submissions(session, course_id=course_id)


@router.post(
    "/submissions/{submission_id}/grade",
    status_code=status.HTTP_200_OK,
)
async def grade_submission_admin(
    session: Session,
    submission_id: uuid.UUID,
    data: GradeSubmissionRequest,
    admin: Annotated[User, Depends(current_admin)],
):
    return await admin_grade_submission(session, submission_id, data, admin.id)


@router.patch(
    "/users/{user_id}/role",
    status_code=status.HTTP_200_OK,
    response_model=UserRead,
)
async def update_user_role(
    session: Session,
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(current_admin)],
    role: UserRole = UserRole.user,
):
    return await set_new_user_role(
        session,
        user_id,
        role,
    )


@router.post(
    "/users/{user_id}/course/{course_id}",
    status_code=status.HTTP_201_CREATED,
)
async def assign_course(
    session: Session,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    admin: Annotated[User, Depends(current_admin)],
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    stmt = select(CourseEnrollment).where(
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.course_id == course_id,
    )
    result = await session.execute(stmt)
    existing_enrollment = result.scalar_one_or_none()

    if existing_enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already enrolled in this course",
        )

    enrollment = CourseEnrollment(user_id=user_id, course_id=course_id)
    session.add(enrollment)
    await session.commit()

    return {"detail": "Course assigned successfully"}
