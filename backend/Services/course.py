import uuid
from datetime import datetime, timezone
from typing import Literal

from core.models.course import Course, CourseAudience, CourseEnrollment, CourseLevel, CourseStatus
from core.schemas.course import CourseCreate, CourseUpdate
from Repository import course as repo
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
    title_changed = "title" in patch and patch["title"] and patch["title"] != course.title
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
    if title_changed:
        await repo.sync_course_title_to_blocks(session, course.id, course.title)
    return await repo.update_course(session, course)


async def delete_course(
    session: AsyncSession,
    course: Course,
) -> None:
    await repo.delete_course(session, course)


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
        user_id=user_id,
        filter_type=filter_type,
        level=level,
        audience=audience,
    )


async def delete_courses(session: AsyncSession, courses_id: list[uuid.UUID]):
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
