import uuid
from typing import List

from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress
from core.schemas.course import CourseCreate, CourseUpdate
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def get_courses(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    published_only: bool = True,
) -> List[Course]:
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
    for field, value in course_update.model_dump(exclude_unset=True).items():
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
) -> List[Course]:
    query = select(Course).where(Course.is_published)

    if q:
        if len(q) < 3:
            search_pattern = f"%{q}%"
            query = query.where(
                (Course.title.ilike(search_pattern))
                | (Course.description.ilike(search_pattern))
            ).order_by(Course.title.asc())
        else:
            query = query.where(
                (Course.title.bool_op("%")(q)) | (Course.description.bool_op("%")(q))
            ).order_by(
                func.similarity(Course.title, q).desc(),
                func.similarity(Course.description, q).desc(),
            )

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def delete_courses(session: AsyncSession, courses_id: list[uuid.UUID]):
    stmt = delete(Course).where(Course.id.in_(courses_id))
    await session.execute(stmt)
    await session.commit()
