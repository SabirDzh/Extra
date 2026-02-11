from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.block import (
    Block,
    BlockType,
)
from core.models.progress import UserBlockProgress
from core.models.test import AnswerOption, Question, TestAnswer, TestSubmission


async def auto_grade_submission(
    db: AsyncSession, submission: TestSubmission
) -> TestSubmission:
    block = await db.get(Block, submission.block_id)
    if block.block_type != BlockType.auto_test:
        return submission

    questions = (
        (
            await db.execute(
                select(Question)
                .where(Question.block_id == submission.block_id)
                .options(selectinload(Question.options))
            )
        )
        .scalars()
        .all()
    )

    max_score = len(questions)
    score = 0

    answers = (
        (
            await db.execute(
                select(TestAnswer).where(TestAnswer.submission_id == submission.id)
            )
        )
        .scalars()
        .all()
    )

    answer_map = {a.question_id: a for a in answers}

    for question in questions:
        answer = answer_map.get(question.id)
        if not answer:
            continue

        correct_option_ids = {o.id for o in question.options if o.is_correct}

        if (
            answer.selected_answer_id
            and answer.selected_answer_id in correct_option_ids
        ):
            score += 1

    submission.score = score
    submission.max_score = max_score
    submission.is_graded = True

    if score == max_score:
        await _mark_block_completed(db, submission.user_id, submission.block_id)

    return submission


async def _mark_block_completed(db: AsyncSession, user_id: int, block_id: int) -> None:
    existing = (
        await db.execute(
            select(UserBlockProgress).where(
                UserBlockProgress.user_id == user_id,
                UserBlockProgress.block_id == block_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.is_completed = True
        existing.completed_at = datetime.now(timezone.utc)
    else:
        db.add(
            UserBlockProgress(
                user_id=user_id,
                block_id=block_id,
                is_completed=True,
                completed_at=datetime.now(timezone.utc),
            )
        )
