import uuid
from datetime import datetime, timezone
from typing import List, Literal

from core.models.block import TEST_BLOCK_TYPES, Block, BlockType
from core.models.course import (
    Course,
    CourseAudience,
    CourseEnrollment,
    CourseLevel,
    CourseStatus,
)
from core.models.progress import UserBlockProgress
from core.models.test import TestSubmission
from core.models.notification import Notification
from Domain.Enums.notification import NotificationType
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload
from Repository.search_engine import (
    MAX_SEARCH_CANDIDATES,
    SearchIn,
    SearchSort,
    filter_and_rank_items,
    paginate_items,
    sort_items,
)


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


async def create_course(session: AsyncSession, course: Course) -> Course:
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def update_course(session: AsyncSession, course: Course) -> Course:
    await session.commit()
    await session.refresh(course)
    return course


async def delete_course(
    session: AsyncSession,
    course: Course,
) -> None:
    # Select block ids for this course
    stmt_block_ids = select(Block.id).where(Block.course_id == course.id)
    block_ids = (await session.execute(stmt_block_ids)).scalars().all()

    # Select submission ids for those blocks
    submission_ids = []
    if block_ids:
        stmt_submission_ids = select(TestSubmission.id).where(TestSubmission.block_id.in_(block_ids))
        submission_ids = (await session.execute(stmt_submission_ids)).scalars().all()

    # Explicitly delete user progress and submissions for auditability,
    # even though cascade deletes would handle them via block deletion.
    if block_ids:
        await session.execute(
            delete(UserBlockProgress).where(
                UserBlockProgress.block_id.in_(block_ids),
            )
        )
        await session.execute(
            delete(TestSubmission).where(
                TestSubmission.block_id.in_(block_ids),
            )
        )

    # Delete notifications with new_course type referencing this course
    stmt_del_course_notif = delete(Notification).where(
        Notification.type == NotificationType.new_course,
        Notification.reference_id == course.id
    )
    await session.execute(stmt_del_course_notif)

    # Delete notifications with manual_test_check type referencing block submissions
    if submission_ids:
        stmt_del_sub_notif = delete(Notification).where(
            Notification.type == NotificationType.manual_test_check,
            Notification.reference_id.in_(submission_ids)
        )
        await session.execute(stmt_del_sub_notif)

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
    sort: SearchSort = "alphabet_asc",
    search_in: SearchIn = "all",
    user_id: uuid.UUID | None = None,
    filter_type: (
        Literal["in_progress", "completed", "not_started", "new", "popular"] | None
    ) = None,
    level: CourseLevel | None = None,
    audience: CourseAudience | None = None,
):
    from datetime import timedelta

    query = (
        select(Course)
        .where(Course.is_published)
        .options(
            load_only(
                Course.id,
                Course.title,
                Course.description,
                Course.level,
                Course.audience,
                Course.created_at,
            )
        )
    )

    if level is not None:
        query = query.where(Course.level == level)

    if audience is not None:
        query = query.where(Course.audience == audience)

    if filter_type == "new":
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        query = query.where(Course.created_at >= day_ago)

    elif filter_type == "popular":
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

        subq = select(CourseEnrollment.course_id).where(
            CourseEnrollment.user_id == user_id
        )
        query = query.where(Course.id.not_in(subq))

    elif filter_type == "in_progress" and user_id:

        query = query.join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
        query = query.where(
            CourseEnrollment.user_id == user_id, CourseEnrollment.completed_at.is_(None)
        )

    elif filter_type == "completed" and user_id:

        query = query.join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
        query = query.where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.completed_at.is_not(None),
        )
    query = query.limit(MAX_SEARCH_CANDIDATES)
    result = await session.execute(query)
    courses = list(result.scalars().all())
    ranked = filter_and_rank_items(
        courses,
        q=q,
        search_in=search_in,
        title_getter=lambda item: item.title,
        description_getter=lambda item: item.description,
    )
    sorted_items = sort_items(
        ranked,
        sort=sort,
        title_getter=lambda item: item.title,
        date_getter=lambda item: item.created_at,
    )
    return paginate_items(sorted_items, offset=offset, limit=limit)


async def delete_courses(session: AsyncSession, courses_id: list[uuid.UUID]):
    if not courses_id:
        return

    # Select block ids for these courses
    stmt_block_ids = select(Block.id).where(Block.course_id.in_(courses_id))
    block_ids = (await session.execute(stmt_block_ids)).scalars().all()

    # Select submission ids for those blocks
    submission_ids = []
    if block_ids:
        stmt_submission_ids = select(TestSubmission.id).where(TestSubmission.block_id.in_(block_ids))
        submission_ids = (await session.execute(stmt_submission_ids)).scalars().all()

    # Explicitly delete user progress and submissions for auditability,
    # even though cascade deletes would handle them via block deletion.
    if block_ids:
        await session.execute(
            delete(UserBlockProgress).where(
                UserBlockProgress.block_id.in_(block_ids),
            )
        )
        await session.execute(
            delete(TestSubmission).where(
                TestSubmission.block_id.in_(block_ids),
            )
        )

    # Delete notifications with new_course type referencing these courses
    stmt_del_course_notif = delete(Notification).where(
        Notification.type == NotificationType.new_course,
        Notification.reference_id.in_(courses_id)
    )
    await session.execute(stmt_del_course_notif)

    # Delete notifications with manual_test_check type referencing block submissions
    if submission_ids:
        stmt_del_sub_notif = delete(Notification).where(
            Notification.type == NotificationType.manual_test_check,
            Notification.reference_id.in_(submission_ids)
        )
        await session.execute(stmt_del_sub_notif)

    stmt = delete(Course).where(Course.id.in_(courses_id))
    await session.execute(stmt)
    await session.commit()


async def sync_course_title_to_blocks(
    session: AsyncSession,
    course_id: uuid.UUID,
    title: str,
) -> None:
    await session.execute(
        (
            Block.__table__.update()
            .where(
                Block.course_id == course_id,
                Block.block_type == BlockType.lesson,
            )
            .values(title=title)
        )
    )


async def update_course_completion_status(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> None:
    """
    Пересчитывает статус прохождения курса для пользователя.

    Правила:
    - Если пользователь НЕ записан — ничего не делаем.
    - Если все блоки курса пройдены — ставим enrollment.completed_at.
    - Если хотя бы один блок пройден, но не все — снимаем completed_at (откат).
    """
    enrollment = await get_enrollment(session, user_id, course_id)
    if not enrollment:
        return

    stmt_total = select(func.count(Block.id)).where(
        Block.course_id == course_id,
        Block.block_type.in_(TEST_BLOCK_TYPES),
    )
    total: int = (await session.execute(stmt_total)).scalar() or 0

    if total == 0:
        return

    stmt_done = (
        select(func.count(UserBlockProgress.id))
        .join(Block, UserBlockProgress.block_id == Block.id)
        .where(
            Block.course_id == course_id,
            Block.block_type.in_(TEST_BLOCK_TYPES),
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.is_completed == True,
        )
    )
    completed: int = (await session.execute(stmt_done)).scalar() or 0

    if completed >= total:

        if enrollment.completed_at is None:
            enrollment.completed_at = datetime.now(timezone.utc)
            await session.commit()
    else:

        if enrollment.completed_at is not None:
            enrollment.completed_at = None
            await session.commit()


async def attach_course_progress(
    session: AsyncSession,
    courses: list[Course],
    user_id: uuid.UUID | None,
) -> None:
    """
    Attaches progress information to each course object.

    - Enrolled users: completed/total/percent based on their actual block progress.
    - Unenrolled or anonymous users: completed=0, total=total blocks, percent=0.0.
    """
    if not courses:
        return

    course_ids = [c.id for c in courses]

    stmt_total = (
        select(Block.course_id, func.count(Block.id).label("total"))
        .where(
            Block.course_id.in_(course_ids),
            Block.block_type.in_(TEST_BLOCK_TYPES),
        )
        .group_by(Block.course_id)
    )
    result_total = await session.execute(stmt_total)
    total_blocks_map = {row.course_id: row.total for row in result_total}

    completed_blocks_map: dict[uuid.UUID, int] = {}
    enrolled_courses: set[uuid.UUID] = set()

    if user_id:
        stmt_completed = (
            select(Block.course_id, func.count(UserBlockProgress.id).label("completed"))
            .join(UserBlockProgress, Block.id == UserBlockProgress.block_id)
            .where(
                Block.course_id.in_(course_ids),
                Block.block_type.in_(TEST_BLOCK_TYPES),
                UserBlockProgress.user_id == user_id,
                UserBlockProgress.is_completed == True,
            )
            .group_by(Block.course_id)
        )
        result_completed = await session.execute(stmt_completed)
        completed_blocks_map = {
            row.course_id: row.completed for row in result_completed
        }

        stmt_enroll = select(CourseEnrollment.course_id).where(
            CourseEnrollment.course_id.in_(course_ids),
            CourseEnrollment.user_id == user_id,
        )
        result_enroll = await session.execute(stmt_enroll)
        enrolled_courses = {row[0] for row in result_enroll}

    from core.schemas.course import CourseProgress

    for c in courses:
        total = total_blocks_map.get(c.id, 0)

        if user_id and c.id in enrolled_courses:
            completed = completed_blocks_map.get(c.id, 0)
            percent = round((completed / total) * 100, 2) if total > 0 else 0.0

            if completed == 0:
                status = CourseStatus.not_started
            elif total > 0 and completed >= total:
                status = CourseStatus.completed
            else:
                status = CourseStatus.in_progress
        else:

            completed = 0
            percent = 0.0
            status = CourseStatus.not_started

        c.progress = CourseProgress(
            completed=completed,
            total=total,
            percent=percent,
            status=status,
            all_total=total,
            current_stage=min(completed + 1, total) if total > 0 else 0,
            progress={"total": completed},
        )


async def reset_course_progress(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> bool:
    """
    Permanently deletes all progress and test submissions for a user in a course.
    Returns True if enrollment was found and reset, False otherwise.
    """
    enrollment = await get_enrollment(session, user_id, course_id)
    if not enrollment:
        return False

    stmt_blocks = select(Block.id).where(Block.course_id == course_id)
    result_blocks = await session.execute(stmt_blocks)
    block_ids = [row[0] for row in result_blocks.all()]

    if block_ids:

        await session.execute(
            delete(UserBlockProgress).where(
                UserBlockProgress.user_id == user_id,
                UserBlockProgress.block_id.in_(block_ids),
            )
        )

        await session.execute(
            delete(TestSubmission).where(
                TestSubmission.user_id == user_id,
                TestSubmission.block_id.in_(block_ids),
            )
        )

    enrollment.completed_at = None

    await session.commit()
    return True


async def complete_course_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> bool:
    stmt_course = select(Course).where(Course.id == course_id).options(selectinload(Course.blocks))
    res_course = await session.execute(stmt_course)
    course = res_course.scalar_one_or_none()
    if not course:
        return False

    enrollment = await get_enrollment(session, user_id, course_id)
    if not enrollment:
        enrollment = CourseEnrollment(user_id=user_id, course_id=course_id)
        session.add(enrollment)
        await session.flush()

    for block in course.blocks:
        stmt = select(UserBlockProgress).where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.block_id == block.id
        )
        res = await session.execute(stmt)
        progress = res.scalar_one_or_none()
        if not progress:
            progress = UserBlockProgress(
                user_id=user_id,
                block_id=block.id,
                is_completed=True,
                completed_at=datetime.now(timezone.utc)
            )
            session.add(progress)
        else:
            progress.is_completed = True
            if not progress.completed_at:
                progress.completed_at = datetime.now(timezone.utc)

    enrollment.completed_at = datetime.now(timezone.utc)
    await session.commit()
    return True

