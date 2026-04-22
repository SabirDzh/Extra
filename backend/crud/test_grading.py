import uuid
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
from crud import course as course_crud


async def auto_grade_submission(
    db: AsyncSession, submission: TestSubmission
) -> TestSubmission:
    block = await db.get(Block, submission.block_id)
    if block.block_type not in (BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test):
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
    has_manual_questions = False

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
    

    answer_map = defaultdict(list)
    for a in answers:
        answer_map[a.question_id].append(a)

    for question in questions:
        if question.question_type == QuestionType.free_text:
            has_manual_questions = True
            continue

        q_answers = answer_map.get(question.id, [])
        if not q_answers:

            continue

        correct_option_ids = {o.id for o in question.options if o.is_correct}
        user_selected_ids = {a.selected_answer_id for a in q_answers if a.selected_answer_id}

        if question.question_type == QuestionType.single_choice:

            if len(user_selected_ids) == 1 and list(user_selected_ids)[0] in correct_option_ids:
                score += 1
        elif question.question_type == QuestionType.multiple_choice:

            if user_selected_ids == correct_option_ids and correct_option_ids:
                score += 1

    submission.score = float(score) / float(max_score) if max_score > 0 else 0.0
    submission.max_score = 1.0
    


    if block.block_type in (BlockType.manual_test, BlockType.mixed_test):
        submission.is_graded = False
    else:
        submission.is_graded = not has_manual_questions

    if block.block_type == BlockType.auto_test or (submission.is_graded and submission.score > 0):


        await _mark_block_completed(db, submission.user_id, submission.block_id, block.course_id)

    return submission


async def _mark_block_completed(
    db: AsyncSession, user_id: uuid.UUID, block_id: uuid.UUID, course_id: uuid.UUID | None = None
) -> None:
    if course_id is None:
        block = await db.get(Block, block_id)
        if block:
            course_id = block.course_id

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
    
    await db.flush()

    if course_id:
        await course_crud.update_course_completion_status(db, user_id, course_id)
