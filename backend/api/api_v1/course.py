import uuid
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.course import Course, CourseEnrollment
from core.models.db_helper import db_helper
from core.models.progress import UserBlockProgress
from core.models.user import User
from core.schemas.course import CourseCreate, CourseProgress, CourseRead, CourseUpdate
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from utils.product import current_admin

router = APIRouter(prefix=settings.api.v1.courses, tags=["Courses"])

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("/", response_model=list[CourseRead])
async def list_courses(
    db: Session,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    result = await db.execute(
        select(Course).where(Course.is_published).offset(offset).limit(limit)
    )
    return result.scalars().all()


@router.post("/", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    db: Session,
    admin: Annotated[User, Depends(current_admin)],
):
    course = Course(**data.model_dump(), created_by=admin.id)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.get("/{course_id}", status_code=status.HTTP_200_OK, response_model=CourseRead)
async def get_course(course_id: uuid.UUID, db: Session):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    return course


@router.put(
    "/{course_id}", status_code=status.HTTP_202_ACCEPTED, response_model=CourseRead
)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdate,
    db: Session,
    admin: Annotated[User, Depends(current_admin)],
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await db.commit()
    await db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    db: Session,
    admin: Annotated[User, Depends(current_admin)],
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    await db.delete(course)
    await db.commit()


@router.post("/{course_id}/enroll", status_code=status.HTTP_201_CREATED)
async def enroll(
    course_id: uuid.UUID,
    db: Session,
    user: Annotated[User, Depends(current_active_user)],
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    existing = (
        await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.user_id == user.id,
                CourseEnrollment.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already enrolled"
        )
    enrollment = CourseEnrollment(user_id=user.id, course_id=course_id)
    db.add(enrollment)
    await db.commit()
    return {"detail": "Enrolled successfully"}


@router.get(
    "/{course_id}/progress",
    status_code=status.HTTP_200_OK,
    response_model=CourseProgress,
)
async def get_progress(
    course_id: uuid.UUID,
    db: Session,
    user: Annotated[User, Depends(current_active_user)],
):
    course = await db.get(Course, course_id, options=[selectinload(Course.blocks)])
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    total = len(course.blocks)
    if total == 0:
        return CourseProgress(completed=0, total=0, percent=0.0)

    block_ids = [b.id for b in course.blocks]
    completed_count = (
        await db.execute(
            select(func.count(UserBlockProgress.id)).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id.in_(block_ids),
                UserBlockProgress.is_completed,
            )
        )
    ).scalar()

    percent = round(((completed_count or 0) / total) * 100, 2)
    return CourseProgress(completed=completed_count, total=total, percent=percent)
