import uuid
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.block import UserBlockProgress
from core.models.course import Course, CourseBlock
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.course import (
    CourseBlockCreate,
    CourseBlockRead,
    CourseDetailCreate,
    CourseDetailRead,
    CourseRead,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(
    prefix=settings.api.v1.courses,
    tags=["Courses"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("", response_model=list[CourseRead])
async def get_list_courses(
    session: Session,
):
    stmt = select(Course).where(Course.is_published == True)
    courses = await session.scalars(stmt)
    return courses.all()


@router.get("/{course_id}", response_model=CourseDetailRead)
async def get_course(
    course_id: uuid.UUID,
    session: Session,
    user: User = Depends(current_active_user),
):
    stmt = (
        select(Course)
        .options(selectinload(Course.blocks))
        .where(Course.id == course_id)
    )
    course = await session.scalar(stmt)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # Fetch user progress for this course's blocks
    stmt_progress = select(UserBlockProgress).where(
        UserBlockProgress.user_id == user.id,
        UserBlockProgress.block_id.in_([b.id for b in course.blocks]),
    )
    progress_result = await session.scalars(stmt_progress)
    user_progress_map = {p.block_id: p for p in progress_result.all()}

    # Construct response with computed fields
    blocks_data = []
    completed_blocks = 0
    total_blocks = len(course.blocks)

    for block in course.blocks:
        progress = user_progress_map.get(block.id)
        is_locked = True  # Default locked
        video_watched = False
        test_passed = False

        if progress:
            is_locked = not progress.is_unlocked  # If record exists, use its status
            video_watched = progress.video_watched
            test_passed = progress.test_passed
        else:
            # logic for default first block unlocked or similar could go here
            # For now, let's assume default behavior handled by creation logic or similar
            # If no progress record, it's locked.
            # EXCEPT usually the first block is unlocked.
            # For simplicity, we stick to DB state.
            pass

        # Check if block is completed (logic might vary, e.g. test_passed)
        if test_passed:
            completed_blocks += 1

        blocks_data.append(
            CourseBlockRead(
                id=block.id,
                title=block.title,
                order=block.order_index,
                is_locked=is_locked,
                video_watched=video_watched,
                test_passed=test_passed,
            )
        )

    progress_percent = (
        (completed_blocks / total_blocks * 100) if total_blocks > 0 else 0.0
    )

    return CourseDetailRead(
        id=course.id,
        title=course.title,
        description=course.description,
        is_published=course.is_published,
        progress_percent=progress_percent,
        blocks=blocks_data,
    )


@router.get("/my/progress")
async def get_my_progress():
    pass


@router.post("", response_model=CourseDetailRead, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_data: CourseDetailCreate,
    session: Session,
):
    course = Course(
        title=course_data.title,
        description=course_data.description,
        is_published=course_data.is_published,
    )
    session.add(course)
    await session.commit()

    return CourseDetailRead(
        id=str(course.id),
        title=course.title,
        description=course.description,
        is_published=course.is_published,
        progress_percent=0.0,
        blocks=[],
    )


@router.post(
    "/{course_id}/blocks",
    response_model=CourseBlockRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_course_block(
    course_id: uuid.UUID,
    block_data: CourseBlockCreate,
    session: Session,
):
    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    block = CourseBlock(
        course_id=course.id,
        title=block_data.title,
        order_index=block_data.order_index,
        video_url=block_data.video_url,
        text_content=block_data.text_content,
    )
    session.add(block)
    await session.commit()

    return CourseBlockRead(
        id=block.id,
        title=block.title,
        order=block.order_index,
        is_locked=True,  # New blocks are locked by default
        video_watched=False,
        test_passed=False,
    )
