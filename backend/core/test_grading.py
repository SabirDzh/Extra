import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.block import (
    Block,
    BlockType,
)
from core.models.progress import UserBlockProgress
from core.models.test import Question, QuestionType, TestAnswer, TestSubmission


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

    has_free_text = any(q.question_type == QuestionType.free_text for q in questions)

    answers = (
        (
            await db.execute(
                select(TestAnswer).where(TestAnswer.submission_id == submission.id)
            )
        )
        .scalars()
        .all()
    )

    user_answers = defaultdict(set)
    for a in answers:
        if a.selected_answer_id:
            user_answers[a.question_id].add(a.selected_answer_id)

    for question in questions:
        selected_option_ids = user_answers.get(question.id, set())
        correct_option_ids = {o.id for o in question.options if o.is_correct}

        if question.question_type == QuestionType.single_choice:
            if (
                selected_option_ids
                and list(selected_option_ids)[0] in correct_option_ids
            ):
                score += 1

        elif question.question_type == QuestionType.multiple_choice:
            if (
                selected_option_ids == correct_option_ids
                and len(correct_option_ids) > 0
            ):
                score += 1

        elif question.question_type == QuestionType.free_text:
            pass

    submission.score = score
    submission.max_score = max_score

    submission.is_graded = not has_free_text

    if score == max_score and not has_free_text:
        await _mark_block_completed(db, submission.user_id, submission.block_id)

    return submission


async def _mark_block_completed(
    db: AsyncSession, user_id: uuid.UUID, block_id: uuid.UUID
) -> None:
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
