import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Literal

from core.models.block import Block
from core.models.course import Course, CourseEnrollment, CourseLevel
from core.models.progress import UserBlockProgress
from core.schemas.course import CourseCreate, CourseUpdate
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from utils.db import ensure_unique_field


async def get_courses(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    published_only: bool = True,
):
    stmt = select(Course).offset(offset).limit(limit)
    if published_only:
        stmt = stmt.where(Course.is_published)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_course(
    session: AsyncSession,
    course_id: uuid.UUID,
    load_blocks: bool = False,
) -> Course | None:
    options = []
    if load_blocks:
        options.append(selectinload(Course.blocks))
    return await session.get(Course, course_id, options=options)


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
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


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
    await session.commit()
    await session.refresh(course)
    return course


async def delete_course(
    session: AsyncSession,
    course: Course,
) -> None:
    await session.delete(course)
    await session.commit()


async def get_enrollment(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> CourseEnrollment | None:
    stmt = select(CourseEnrollment).where(
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.course_id == course_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_enrollment(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> CourseEnrollment:
    enrollment = CourseEnrollment(user_id=user_id, course_id=course_id)
    session.add(enrollment)
    await session.commit()
    await session.refresh(enrollment)
    return enrollment


async def get_completed_blocks_count(
    session: AsyncSession,
    user_id: uuid.UUID,
    block_ids: List[uuid.UUID],
) -> int:
    stmt = select(func.count(UserBlockProgress.id)).where(
        UserBlockProgress.user_id == user_id,
        UserBlockProgress.block_id.in_(block_ids),
        UserBlockProgress.is_completed,
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def search_courses(
    session: AsyncSession,
    q: str | None = None,
    offset: int = 0,
    limit: int = 20,
    user_id: uuid.UUID | None = None,
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular", "beginner"] | None
    ) = None,
):
    query = select(Course).where(Course.is_published)

    # 1. Text Search
    if q:
        if len(q) < 3:
            search_pattern = f"%{q}%"
            query = query.where(
                (Course.title.ilike(search_pattern))
                | (Course.description.ilike(search_pattern))
            )
        else:
            query = query.where(
                (Course.title.bool_op("%")(q)) | (Course.description.bool_op("%")(q))
            )

    # 2. Specific Filters
    if filter_type == "beginner":
        query = query.where(Course.level == CourseLevel.beginner)

    elif filter_type == "new":
        # Added less than 24 hours ago
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        query = query.where(Course.created_at >= day_ago)

    elif filter_type == "popular":
        # Sort by number of enrollments
        # We need a subquery or join to count enrollments
        enrollment_count = (
            select(
                CourseEnrollment.course_id,
                func.count(CourseEnrollment.id).label("count"),
            )
            .group_by(CourseEnrollment.course_id)
            .subquery()
        )
        query = query.outerjoin(
            enrollment_count, Course.id == enrollment_count.c.course_id
        )
        query = query.order_by(func.coalesce(enrollment_count.c.count, 0).desc())

    elif filter_type == "not_started" and user_id:
        # Not enrolled
        subq = select(CourseEnrollment.course_id).where(CourseEnrollment.user_id == user_id)
        query = query.where(Course.id.not_in(subq))

    elif filter_type == "in_progress" and user_id:
        # Enrolled but not completed
        query = query.join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
        query = query.where(
            CourseEnrollment.user_id == user_id, CourseEnrollment.completed_at.is_(None)
        )

    elif filter_type == "completed" and user_id:
        # Enrolled and completed
        query = query.join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
        query = query.where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.completed_at.is_not(None),
        )

    # Default ordering if not popular
    if filter_type != "popular":
        if q and len(q) >= 3:
            query = query.order_by(
                func.similarity(Course.title, q).desc(),
                func.similarity(Course.description, q).desc(),
            )
        else:
            query = query.order_by(Course.title.asc())

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def delete_courses(session: AsyncSession, courses_id: list[uuid.UUID]):
    stmt = delete(Course).where(Course.id.in_(courses_id))
    await session.execute(stmt)
    await session.commit()


async def attach_course_progress(
    session: AsyncSession,
    courses: list[Course],
    user_id: uuid.UUID | None,
) -> None:
    if not courses:
        return

    course_ids = [c.id for c in courses]

    # 1. Total blocks per course
    stmt_total = (
        select(Block.course_id, func.count(Block.id).label("total"))
        .where(Block.course_id.in_(course_ids))
        .group_by(Block.course_id)
    )
    result_total = await session.execute(stmt_total)
    total_blocks_map = {row.course_id: row.total for row in result_total}

    # 2. Completed blocks per course (if user is logged in)
    completed_blocks_map = {}
    enrolled_courses = set()
    if user_id:
        stmt_completed = (
            select(Block.course_id, func.count(UserBlockProgress.id).label("completed"))
            .join(UserBlockProgress, Block.id == UserBlockProgress.block_id)
            .where(
                Block.course_id.in_(course_ids),
                UserBlockProgress.user_id == user_id,
                UserBlockProgress.is_completed == True,
            )
            .group_by(Block.course_id)
        )
        result_completed = await session.execute(stmt_completed)
        completed_blocks_map = {row.course_id: row.completed for row in result_completed}

        stmt_enroll = select(CourseEnrollment.course_id).where(
            CourseEnrollment.course_id.in_(course_ids),
            CourseEnrollment.user_id == user_id,
        )
        result_enroll = await session.execute(stmt_enroll)
        enrolled_courses = {row[0] for row in result_enroll}

    from core.schemas.course import CourseProgress

    for c in courses:
        if user_id and c.id in enrolled_courses:
            total = total_blocks_map.get(c.id, 0)
            completed = completed_blocks_map.get(c.id, 0)
            percent = round((completed / total) * 100, 2) if total > 0 else 0.0
            c.progress = CourseProgress(completed=completed, total=total, percent=percent)
        else:
            c.progress = None

