import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.block import Block, BlockType
from core.models.test import Question, TestAnswer, TestSubmission
from core.schemas.test import BlockTestResults, QuestionResult, TestResultStatus


async def get_test_results_for_block(
    db: AsyncSession,
    user_id: uuid.UUID,
    block_id: uuid.UUID,
) -> BlockTestResults | None:
    """
    Retrieves the latest test submission for the given block and user,
    and returns detailed results including correctness per question.
    """
    # 1. Fetch Block
    block = await db.get(Block, block_id)
    if not block or block.block_type not in (BlockType.auto_test, BlockType.manual_test):
        return None

    # 2. Fetch the latest TestSubmission for this user and block
    stmt_sub = (
        select(TestSubmission)
        .where(
            TestSubmission.user_id == user_id,
            TestSubmission.block_id == block_id,
        )
        .options(selectinload(TestSubmission.answers).selectinload(TestAnswer.selected_option))
        .order_by(TestSubmission.submitted_at.desc())
        .limit(1)
    )
    result_sub = await db.execute(stmt_sub)
    submission = result_sub.scalar_one_or_none()

    if not submission:
        return None

    # 3. Fetch questions and their options
    stmt_q = (
        select(Question)
        .where(Question.block_id == block_id)
        .options(selectinload(Question.options))
        .order_by(Question.order_index)
    )
    result_q = await db.execute(stmt_q)
    questions = result_q.scalars().all()

    # Create mapping of user answers
    # Each question_id points to the user's TestAnswer
    user_answers_map = {ans.question_id: ans for ans in submission.answers}

    question_results = []
    for q in questions:
        # Find correct options text
        correct_options = [opt for opt in q.options if opt.is_correct]
        correct_text = ", ".join([opt.text for opt in correct_options]) if correct_options else None
        
        user_answer_obj = user_answers_map.get(q.id)
        user_answer_text = None
        status = TestResultStatus.INCORRECT
        score = 0

        if user_answer_obj:
            if user_answer_obj.selected_option:
                user_answer_text = user_answer_obj.selected_option.text
            elif user_answer_obj.text_answer:
                user_answer_text = user_answer_obj.text_answer

            if block.block_type == BlockType.auto_test:
                correct_option_ids = {opt.id for opt in correct_options}
                if user_answer_obj.selected_answer_id and user_answer_obj.selected_answer_id in correct_option_ids:
                    status = TestResultStatus.CORRECT
                    score = 1
            elif block.block_type == BlockType.manual_test:
                if not submission.is_graded:
                    status = TestResultStatus.REQUIRES_REVIEW
                else:
                    # For manual test, if it's graded and overall score > 0, we'll mark it Верно,
                    # since we lack per-question score in DB. Otherwise, Неверно.
                    # Or we could just fallback to checking if submission score is max_score.
                    if submission.score and submission.score > 0:
                        status = TestResultStatus.CORRECT
                        score = 1
                    else:
                        status = TestResultStatus.INCORRECT
                        score = 0
        else:
            if block.block_type == BlockType.manual_test and not submission.is_graded:
                status = TestResultStatus.REQUIRES_REVIEW
            else:
                status = TestResultStatus.INCORRECT

        question_results.append(
            QuestionResult(
                question_id=q.id,
                text=q.text,
                status=status,
                correct_answer=correct_text,
                user_answer=user_answer_text,
                score=score,
            )
        )

    return BlockTestResults(
        block_id=block_id,
        submission_id=submission.id,
        total_score=submission.score,
        max_score=len(questions),
        questions=question_results,
    )
