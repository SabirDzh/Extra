from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.block import (
    Block,
    BlockType,
)
from core.models.progress import UserBlockProgress
from core.models.test import Question, TestAnswer, TestSubmission


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

    from collections import defaultdict
    from core.models.test import QuestionType
    
    # Group all TestAnswers by question_id to support multi-select
    answer_map = defaultdict(list)
    for a in answers:
        answer_map[a.question_id].append(a)

    for question in questions:
        q_answers = answer_map.get(question.id, [])
        if not q_answers and question.block.block_type == BlockType.auto_test:
            # No answer provided for this question
            continue

        correct_option_ids = {o.id for o in question.options if o.is_correct}
        user_selected_ids = {a.selected_answer_id for a in q_answers if a.selected_answer_id}

        if question.question_type == QuestionType.single_choice:
            # Single choice: Exactly one answer provided and it matches any correct ID
            if len(user_selected_ids) == 1 and list(user_selected_ids)[0] in correct_option_ids:
                score += 1
        elif question.question_type == QuestionType.multiple_choice:
            # Multiple choice: Set of selected IDs must exactly match set of correct IDs
            if user_selected_ids == correct_option_ids and correct_option_ids:
                score += 1
        # Free text questions (manual tests) are not auto-graded here

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
