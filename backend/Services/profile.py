from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import Block
from core.models.block import TEST_BLOCK_TYPES
from core.models.certificates import Certificate
from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress
from core.models.test import TestSubmission


async def get_test_attempts(
    db: AsyncSession,
    user_id,
    offset: int = 0,
    limit: int = 20,
):
    stmt = (
        select(TestSubmission, Block, Course)
        .join(Block, TestSubmission.block_id == Block.id)
        .join(Course, Block.course_id == Course.id)
        .where(TestSubmission.user_id == user_id)
        .order_by(TestSubmission.submitted_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = []
    for submission, block, course in result.all():
        items.append(
            {
                "id": submission.id,
                "course_id": course.id,
                "course_title": course.title,
                "block_id": block.id,
                "block_title": block.title,
                "block_type": block.block_type,
                "submitted_at": submission.submitted_at,
                "score": submission.score,
                "max_score": submission.max_score,
                "is_graded": submission.is_graded,
                "admin_comment": submission.admin_comment,
            }
        )
    return items


async def get_courses_progress(
    db: AsyncSession,
    user_id,
    offset: int = 0,
    limit: int = 20,
):
    stmt = (
        select(
            Course,
            CourseEnrollment.enrolled_at,
            func.count(Block.id).label("total_blocks"),
            func.count(UserBlockProgress.id).label("completed_blocks"),
        )
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id == user_id)
        .outerjoin(
            Block,
            (Block.course_id == Course.id) & (Block.block_type.in_(TEST_BLOCK_TYPES)),
        )
        .outerjoin(
            UserBlockProgress,
            (UserBlockProgress.block_id == Block.id)
            & (UserBlockProgress.user_id == user_id)
            & (UserBlockProgress.is_completed == True),
        )
        .group_by(Course.id, CourseEnrollment.enrolled_at)
        .order_by(CourseEnrollment.enrolled_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = []
    for course, _, total_blocks, completed_blocks in result.all():
        total_cnt = total_blocks or 0
        completed_cnt = completed_blocks or 0

        all_total = total_cnt
        completed = completed_cnt
        percent = round((completed / all_total) * 100, 2) if all_total else 0.0

        if completed == 0:
            status = "not_started"
        elif completed >= all_total and all_total > 0:
            status = "completed"
        else:
            status = "in_progress"

        items.append(
            {
                "course_id": course.id,
                "title": course.title,
                "status": status,
                "all_total": all_total,
                "completed": completed,
                "percent": percent,
            }
        )
    return items


async def ensure_completed_certificates(db: AsyncSession, user_id):
    total_subq = (
        select(
            Block.course_id.label("course_id"),
            func.count(Block.id).label("total_blocks"),
        )
        .group_by(Block.course_id)
        .subquery()
    )
    completed_subq = (
        select(
            Block.course_id.label("course_id"),
            func.count(UserBlockProgress.id).label("completed_blocks"),
        )
        .join(Block, UserBlockProgress.block_id == Block.id)
        .where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.is_completed == True,
        )
        .group_by(Block.course_id)
        .subquery()
    )

    stmt = (
        select(Course.id)
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id == user_id)
        .join(total_subq, total_subq.c.course_id == Course.id)
        .join(completed_subq, completed_subq.c.course_id == Course.id)
        .outerjoin(
            Certificate,
            (Certificate.course_id == Course.id) & (Certificate.user_id == user_id),
        )
        .where(
            total_subq.c.total_blocks > 0,
            completed_subq.c.completed_blocks == total_subq.c.total_blocks,
            Certificate.id.is_(None),
        )
    )
    result = await db.execute(stmt)
    course_ids = [row[0] for row in result.all()]
    if not course_ids:
        return

    for course_id in course_ids:
        db.add(Certificate(user_id=user_id, course_id=course_id))
    await db.commit()


async def get_certificates(db: AsyncSession, user_id):
    await ensure_completed_certificates(db, user_id)
    stmt = (
        select(Certificate, Course)
        .join(Course, Certificate.course_id == Course.id)
        .where(Certificate.user_id == user_id)
        .order_by(Certificate.issued_at.desc())
    )
    result = await db.execute(stmt)
    items = []
    for cert, course in result.all():
        items.append(
            {
                "id": cert.id,
                "course_id": course.id,
                "course_title": course.title,
                "certificate_number": cert.certificate_number,
                "issued_at": cert.issued_at,
                "download_url": f"/api/certificates/{cert.certificate_number}/download",
            }
        )
    return items


async def get_recent_courses(
    db: AsyncSession,
    user_id,
    limit: int = 5,
    offset: int = 0,
):
    enroll_q = select(
        CourseEnrollment.course_id.label("course_id"),
        CourseEnrollment.enrolled_at.label("last_activity"),
    ).where(CourseEnrollment.user_id == user_id)

    submission_q = (
        select(
            Block.course_id.label("course_id"),
            TestSubmission.submitted_at.label("last_activity"),
        )
        .join(Block, TestSubmission.block_id == Block.id)
        .where(TestSubmission.user_id == user_id)
    )

    progress_q = (
        select(
            Block.course_id.label("course_id"),
            UserBlockProgress.completed_at.label("last_activity"),
        )
        .join(Block, UserBlockProgress.block_id == Block.id)
        .where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.completed_at.is_not(None),
        )
    )

    union_subq = union_all(enroll_q, submission_q, progress_q).subquery()
    agg_subq = (
        select(
            union_subq.c.course_id,
            func.max(union_subq.c.last_activity).label("last_activity"),
        )
        .group_by(union_subq.c.course_id)
        .subquery()
    )

    stmt = (
        select(Course, agg_subq.c.last_activity)
        .join(agg_subq, agg_subq.c.course_id == Course.id)
        .order_by(agg_subq.c.last_activity.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = []
    for course, last_activity in result.all():
        items.append(
            {
                "course_id": course.id,
                "course_title": course.title,
                "last_activity": last_activity,
            }
        )
    return items
