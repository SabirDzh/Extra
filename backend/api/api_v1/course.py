import uuid
from typing import Annotated, Literal

from core.config import settings
from core.models.course import CourseAudience, CourseLevel
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.course import CourseCreate, CourseListRead, CourseProgress, CourseRead, CourseUpdate
from Repository.search_engine import SearchIn, SearchSort
from Services import course as course_crud
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.authorization import current_admin, current_course_allowed_user

router = APIRouter(
    prefix=settings.api.v1.courses,
    tags=["Courses"],
    dependencies=[Depends(current_course_allowed_user)],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
CourseAllowedUser = Annotated[User, Depends(current_course_allowed_user)]


@router.get("/", response_model=list[CourseListRead])
async def list_courses(
    db: Session,
    pagination: Annotated[PaginationParams, Depends()],
    user: CourseAllowedUser,
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"]
        | None
    ) = Query(None, description="Filter type for courses"),
    level: CourseLevel | None = Query(None, description="Filter by course level"),
    audience: CourseAudience | None = Query(None, description="Filter by audience"),
    sort: SearchSort = Query("alphabet_asc"),
):
    courses = await course_crud.search_courses(
        db,
        offset=pagination.offset,
        limit=pagination.limit,
        user_id=user.id,
        filter_type=filter_type,
        level=level,
        audience=audience,
        sort=sort,
    )
    await course_crud.attach_course_progress(db, courses, user.id)
    return courses


@router.get("/search", response_model=list[CourseListRead])
async def search_courses(
    db: Session,
    pagination: Annotated[PaginationParams, Depends()],
    user: CourseAllowedUser,
    q: str | None = Query(None, description="Search query"),
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"]
        | None
    ) = Query(None, description="Filter type for courses"),
    level: CourseLevel | None = Query(None, description="Filter by course level"),
    audience: Literal["installer", "seller", "serviceman", "buyer"] | None = Query(
        None, description="Filter by audience role (without admin)"
    ),
    search_in: Literal["title", "description", "all"] = Query("all"),
    sort: SearchSort = Query("alphabet_asc"),
):
    audience_filter = CourseAudience(audience) if audience else None

    courses = await course_crud.search_courses(
        db,
        q=q,
        offset=pagination.offset,
        limit=pagination.limit,
        user_id=user.id,
        filter_type=filter_type,
        level=level,
        audience=audience_filter,
        search_in=search_in,
        sort=sort,
    )
    await course_crud.attach_course_progress(db, courses, user.id)
    return courses


@router.get("/pending-review", response_model=list[CourseListRead])
async def list_pending_review_courses(
    db: Session,
    admin: AdminUser,
):
    """
    Returns all courses that have pending/ungraded manual/mixed test submissions.
    """
    from core.models.block import TEST_BLOCK_TYPES, Block
    from core.models.test import TestSubmission
    from core.models.course import Course
    from sqlalchemy import select, func
    
    subq = (
        select(
            TestSubmission.id,
            func.row_number().over(
                partition_by=(TestSubmission.user_id, TestSubmission.block_id),
                order_by=(TestSubmission.submitted_at.desc(), TestSubmission.id.desc())
            ).label("rn")
        )
        .subquery()
    )
    
    stmt = (
        select(Course)
        .join(Block, Block.course_id == Course.id)
        .join(TestSubmission, TestSubmission.block_id == Block.id)
        .join(subq, TestSubmission.id == subq.c.id)
        .where(
            subq.c.rn == 1,
            TestSubmission.is_graded == False,
            Block.block_type.in_(TEST_BLOCK_TYPES)
        )
        .distinct()
    )
    
    result = await db.execute(stmt)
    courses = list(result.scalars().all())
    await course_crud.attach_course_progress(db, courses, admin.id)
    return courses


@router.post("/", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    db: Session,
    admin: AdminUser,
):
    course = await course_crud.create_course(db, data, admin.id)
    if course.is_published:
        from Services.notifications import notify_new_course
        await notify_new_course(db, course)
    return course


@router.get("/{course_id}", response_model=CourseRead)
async def get_course(
    course_id: uuid.UUID,
    db: Session,
    user: CourseAllowedUser,
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"]
        | None
    ) = Query(None, description="Filter type for courses"),
):
    course = await course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )


    if filter_type in ["in_progress", "completed", "not_started"]:
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

    await course_crud.attach_course_progress(db, [course], user.id)
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
    was_published = course.is_published
    updated_course = await course_crud.update_course(db, course, data)
    
    if not was_published and updated_course.is_published:
        from Services.notifications import notify_new_course
        await notify_new_course(db, updated_course)
        
    return updated_course


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
    user: CourseAllowedUser,
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

    try:
        await course_crud.create_enrollment(db, user.id, course_id)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already enrolled"
        )
    return {"detail": "Enrolled successfully"}


@router.get("/{course_id}/progress", response_model=CourseProgress)
async def get_progress(
    course_id: uuid.UUID,
    db: Session,
    user: CourseAllowedUser,
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
