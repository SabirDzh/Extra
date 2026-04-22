import uuid
from typing import Annotated, Literal

from core.authentication.fastapi_users import current_active_user, current_optional_user
from core.config import settings
from core.models.course import CourseAudience, CourseLevel
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.course import CourseCreate, CourseListRead, CourseProgress, CourseRead, CourseUpdate
from crud import course as course_crud
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(
    prefix=settings.api.v1.courses,
    tags=["Courses"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
IsUser = Annotated[User, Depends(current_active_user)]
OptionalUser = Annotated[User | None, Depends(current_optional_user)]


@router.get("/", response_model=list[CourseListRead])
async def list_courses(
    db: Session,
    pagination: Annotated[PaginationParams, Depends()],
    user: OptionalUser,
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"]
        | None
    ) = Query(None, description="Filter type for courses"),
    level: CourseLevel | None = Query(None, description="Filter by course level"),
    audience: CourseAudience | None = Query(None, description="Filter by audience"),
):
    if filter_type in ["in_progress", "completed", "not_started"] and not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must be logged in to use this filter",
        )

    courses = await course_crud.search_courses(
        db,
        offset=pagination.offset,
        limit=pagination.limit,
        user_id=user.id if user else None,
        filter_type=filter_type,
        level=level,
        audience=audience,
    )
    await course_crud.attach_course_progress(db, courses, user.id if user else None)
    return courses


@router.get("/search", response_model=list[CourseListRead])
async def search_courses(
    db: Session,
    pagination: Annotated[PaginationParams, Depends()],
    user: OptionalUser,
    q: str | None = Query(None, description="Search query"),
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"]
        | None
    ) = Query(None, description="Filter type for courses"),
    level: CourseLevel | None = Query(None, description="Filter by course level"),
    audience: CourseAudience | None = Query(None, description="Filter by audience"),
):
    if filter_type in ["in_progress", "completed", "not_started"] and not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must be logged in to use this filter",
        )

    courses = await course_crud.search_courses(
        db,
        q=q,
        offset=pagination.offset,
        limit=pagination.limit,
        user_id=user.id if user else None,
        filter_type=filter_type,
        level=level,
        audience=audience,
    )
    await course_crud.attach_course_progress(db, courses, user.id if user else None)
    return courses


@router.post("/", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    db: Session,
    admin: AdminUser,
):
    return await course_crud.create_course(db, data, admin.id)


@router.get("/{course_id}", response_model=CourseRead)
async def get_course(
    course_id: uuid.UUID,
    db: Session,
    user: OptionalUser,
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"]
        | None
    ) = Query(None, description="Filter type for courses"),
):
    if filter_type in ["in_progress", "completed", "not_started"] and not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must be logged in to use this filter",
        )

    course = await course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )


    if user and filter_type in ["in_progress", "completed", "not_started"]:
        enrollment = await course_crud.get_enrollment(db, user.id, course_id)
        if filter_type == "not_started" and enrollment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
            )
        elif filter_type == "in_progress" and (
            not enrollment or enrollment.completed_at
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
            )
        elif filter_type == "completed" and (
            not enrollment or not enrollment.completed_at
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
            )

    await course_crud.attach_course_progress(db, [course], user.id if user else None)
    return course


@router.patch("/{course_id}", response_model=CourseRead)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdate,
    db: Session,
    admin: AdminUser,
):
    course = await course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    return await course_crud.update_course(db, course, data)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
):
    course = await course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    await course_crud.delete_course(db, course)


@router.post("/{course_id}/enroll", status_code=status.HTTP_201_CREATED)
async def enroll(
    course_id: uuid.UUID,
    db: Session,
    user: IsUser,
):
    course = await course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    existing = await course_crud.get_enrollment(db, user.id, course_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already enrolled"
        )

    await course_crud.create_enrollment(db, user.id, course_id)
    return {"detail": "Enrolled successfully"}


@router.get("/{course_id}/progress", response_model=CourseProgress)
async def get_progress(
    course_id: uuid.UUID,
    db: Session,
    user: IsUser,
):
    course = await course_crud.get_course(db, course_id, load_blocks=True)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    from core.models.block import TEST_BLOCK_TYPES
    test_blocks = [b for b in course.blocks if b.block_type in TEST_BLOCK_TYPES]
    total = len(test_blocks)
    
    if total == 0:
        return CourseProgress(completed=0, total=0, percent=0.0, progress={"total": 0})

    block_ids = [b.id for b in test_blocks]
    completed_count = await course_crud.get_completed_blocks_count(
        db, user.id, block_ids
    )

    percent = round((completed_count / total) * 100, 2)
    return CourseProgress(
        completed=completed_count,
        total=total,
        percent=percent,
        all_total=total,
        current_stage=min(completed_count + 1, total) if total > 0 else 0,
        progress={"total": completed_count},
    )


@router.post("/{course_id}/users/{user_id}/reset")
async def reset_progress(
    course_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
):
    course = await course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    reset_done = await course_crud.reset_course_progress(db, user_id, course_id)
    if not reset_done:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not enrolled in this course"
        )

    return {"detail": "Progress reset successfully"}


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_courses(
    db: Session, courses_id: Annotated[list[uuid.UUID], Query()], admin: AdminUser
):
    await course_crud.delete_courses(db, courses_id)
