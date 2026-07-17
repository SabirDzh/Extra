import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from core.config import BASE_DIR
from core.models.block import Block
from core.models.course import Course, CourseAudience, CourseEnrollment, CourseLevel, CourseStatus
from core.schemas.course import CourseCreate, CourseUpdate
from Repository import course as repo
from Repository.search_engine import SearchIn, SearchSort
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Repository.common import ensure_unique_field


async def get_courses(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    published_only: bool = True,
):
    return await repo.get_courses(session, offset, limit, published_only)


async def get_course(
    session: AsyncSession,
    course_id: uuid.UUID,
    load_blocks: bool = False,
) -> Course | None:
    return await repo.get_course(session, course_id, load_blocks)


async def create_course(
    session: AsyncSession,
    course_in: CourseCreate,
    creator_id: uuid.UUID,
) -> Course:
    await ensure_unique_field(
        session,
        Course,
        "title",
        course_in.title,
        error_msg=f"Course with title '{course_in.title}' already exists",
    )
    course = Course(**course_in.model_dump(), created_by=creator_id)
    return await repo.create_course(session, course)


async def update_course(
    session: AsyncSession,
    course: Course,
    course_update: CourseUpdate,
) -> Course:
    patch = course_update.model_dump(exclude_unset=True)
    if "title" in patch and patch["title"]:
        await ensure_unique_field(
            session,
            Course,
            "title",
            patch["title"],
            exclude_id=course.id,
            error_msg=f"Course with title '{patch['title']}' already exists",
        )
    for field, value in patch.items():
        setattr(course, field, value)
    return await repo.update_course(session, course)


async def delete_course(
    session: AsyncSession,
    course: Course,
) -> None:
    await _delete_course_video_files(session, course.id)
    await repo.delete_course(session, course)


async def _delete_course_video_files(session: AsyncSession, course_id: uuid.UUID) -> None:
    """Delete video files associated with lesson blocks of a course."""
    result = await session.execute(
        select(Block.video_url).where(
            Block.course_id == course_id,
            Block.video_url.is_not(None),
        )
    )
    for video_url in result.scalars().all():
        if not video_url:
            continue
        try:
            file_path = Path(video_url)
            if file_path.is_absolute():
                path = file_path
            else:
                path = BASE_DIR / video_url.lstrip("/")
            if path.exists():
                path.unlink()
        except OSError:
            pass


async def get_enrollment(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> CourseEnrollment | None:
    return await repo.get_enrollment(session, user_id, course_id)


async def create_enrollment(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> CourseEnrollment:
    return await repo.create_enrollment(session, user_id, course_id)


async def get_completed_blocks_count(
    session: AsyncSession,
    user_id: uuid.UUID,
    block_ids: list[uuid.UUID],
) -> int:
    return await repo.get_completed_blocks_count(session, user_id, block_ids)


async def search_courses(
    session: AsyncSession,
    q: str | None = None,
    offset: int = 0,
    limit: int = 20,
    sort: SearchSort = "alphabet_asc",
    search_in: SearchIn = "all",
    user_id: uuid.UUID | None = None,
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"] | None
    ) = None,
    level: CourseLevel | None = None,
    audience: CourseAudience | None = None,
):
    return await repo.search_courses(
        session=session,
        q=q,
        offset=offset,
        limit=limit,
        sort=sort,
        search_in=search_in,
        user_id=user_id,
        filter_type=filter_type,
        level=level,
        audience=audience,
    )


async def delete_courses(session: AsyncSession, courses_id: list[uuid.UUID]):
    for course_id in courses_id:
        await _delete_course_video_files(session, course_id)
    await repo.delete_courses(session, courses_id)


async def update_course_completion_status(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> None:
    await repo.update_course_completion_status(session, user_id, course_id)


async def attach_course_progress(
    session: AsyncSession,
    courses: list[Course],
    user_id: uuid.UUID | None,
) -> None:
    await repo.attach_course_progress(session, courses, user_id)


async def reset_course_progress(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> bool:
    return await repo.reset_course_progress(session, user_id, course_id)


async def complete_course_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> bool:
    return await repo.complete_course_for_user(session, user_id, course_id)

