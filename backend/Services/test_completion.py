from __future__ import annotations

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import TEST_BLOCK_TYPES, Block, BlockType
from core.models.progress import UserBlockProgress
from core.models.test import TestSubmission

DEFAULT_TEST_QUESTIONS_COUNT = 5


def get_test_max_score(
    total_questions: int,
    configured_questions_count: int | None,
) -> int:
    """Return the number of questions that form one test attempt."""
    question_limit = (
        configured_questions_count
        if configured_questions_count is not None
        else DEFAULT_TEST_QUESTIONS_COUNT
    )
    return min(total_questions, question_limit) if question_limit > 0 else total_questions


def is_perfect_score(score: float | None, max_score: float | None) -> bool:
    """Return True only when a graded test has a positive exact maximum score."""
    return (
        score is not None
        and max_score is not None
        and max_score > 0
        and score == max_score
    )


def perfect_test_submission_exists(user_id, block_id):
    return exists(
        select(TestSubmission.id).where(
            TestSubmission.user_id == user_id,
            TestSubmission.block_id == block_id,
            TestSubmission.is_submitted.is_(True),
            TestSubmission.is_graded.is_(True),
            TestSubmission.score.is_not(None),
            TestSubmission.max_score > 0,
            TestSubmission.score == TestSubmission.max_score,
        )
    )


async def get_completed_block_ids(
    db: AsyncSession,
    user_id,
    course_id=None,
    block_ids: set | list | None = None,
) -> set:
    """Return completed lesson blocks and only perfectly passed test blocks."""
    filters = []
    if course_id is not None:
        filters.append(Block.course_id == course_id)
    if block_ids:
        filters.append(Block.id.in_(block_ids))

    lesson_progress_exists = exists(
        select(UserBlockProgress.id).where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.block_id == Block.id,
            UserBlockProgress.is_completed.is_(True),
        )
    )
    perfect_submission_exists = perfect_test_submission_exists(user_id, Block.id)

    stmt = select(Block.id).where(
        *filters,
        or_(
            and_(Block.block_type == BlockType.lesson, lesson_progress_exists),
            and_(Block.block_type.in_(TEST_BLOCK_TYPES), perfect_submission_exists),
        ),
    )
    return set((await db.execute(stmt)).scalars().all())


async def is_block_completed(db: AsyncSession, user_id, block: Block) -> bool:
    return block.id in await get_completed_block_ids(db, user_id, block.course_id, {block.id})


async def sync_test_block_completion(
    db: AsyncSession,
    user_id,
    block_id,
) -> bool:
    """Synchronize the legacy progress flag from successful test submissions."""
    await db.flush()
    progress = (
        await db.execute(
            select(UserBlockProgress).where(
                UserBlockProgress.user_id == user_id,
                UserBlockProgress.block_id == block_id,
            )
        )
    ).scalar_one_or_none()
    completed = await db.scalar(
        select(perfect_test_submission_exists(user_id, block_id))
    )

    if completed:
        if progress is None:
            progress = UserBlockProgress(
                user_id=user_id,
                block_id=block_id,
                is_completed=True,
            )
            db.add(progress)
        else:
            progress.is_completed = True
        return True

    if progress is not None:
        progress.is_completed = False
        progress.completed_at = None
    return False
