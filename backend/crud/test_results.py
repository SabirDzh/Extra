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
    if not block or block.block_type not in (BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test):
        return None

    # 2. Fetch the latest TestSubmission for this user and block
    stmt_sub = (
        select(TestSubmission)
        .where(
            TestSubmission.user_id == user_id,
            TestSubmission.block_id == block_id,
        )
        .options(selectinload(TestSubmission.answers).selectinload(TestAnswer.selected_option))
        .order_by(TestSubmission.submitted_at.desc(), TestSubmission.id.desc())
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

    from collections import defaultdict
    from core.models.test import QuestionType
    
    # Create mapping of user answers: Each question_id points to a list of TestAnswer
    user_answers_map = defaultdict(list)
    for ans in submission.answers:
        user_answers_map[ans.question_id].append(ans)

    question_results = []
    for q in questions:
        # Find correct options
        correct_options = [opt for opt in q.options if opt.is_correct]
        correct_text = ", ".join([opt.text for opt in correct_options]) if correct_options else None
        correct_option_ids = {opt.id for opt in correct_options}
        
        q_answers = user_answers_map.get(q.id, [])
        user_answer_text = None
        status = TestResultStatus.INCORRECT
        score = 0

        # Calculate user answer text and selected IDs
        user_selected_texts = []
        user_selected_ids = set()
        text_answer = None
        
        for ans in q_answers:
            if ans.selected_option:
                user_selected_texts.append(ans.selected_option.text)
                user_selected_ids.add(ans.selected_answer_id)
            if ans.text_answer:
                text_answer = ans.text_answer
                
        if user_selected_texts:
            user_answer_text = ", ".join(user_selected_texts)
        elif text_answer:
            user_answer_text = text_answer

        if q_answers:
            if q.question_type == QuestionType.single_choice:
                if len(user_selected_ids) == 1 and list(user_selected_ids)[0] in correct_option_ids:
                    status = TestResultStatus.CORRECT
                    score = 1
                else:
                    status = TestResultStatus.INCORRECT
            elif q.question_type == QuestionType.multiple_choice:
                if user_selected_ids == correct_option_ids and correct_option_ids:
                    status = TestResultStatus.CORRECT
                    score = 1
                else:
                    status = TestResultStatus.INCORRECT
            elif q.question_type == QuestionType.free_text:
                if not submission.is_graded:
                    status = TestResultStatus.REQUIRES_REVIEW
                    score = 0
                else:
                   
                    if submission.score and submission.score >= (max_score if block.block_type == BlockType.auto_test else 1):
                         status = TestResultStatus.CORRECT
                         score = 1
                    else:
                         status = TestResultStatus.INCORRECT
                         score = 0
        else:
            if q.question_type == QuestionType.free_text and not submission.is_graded:
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

    # 4. Calculate stats (excluding REQUIRES_REVIEW)
    correct_count = sum(1 for r in question_results if r.status == TestResultStatus.CORRECT)
    incorrect_count = sum(1 for r in question_results if r.status == TestResultStatus.INCORRECT)

    return BlockTestResults(
        block_id=block_id,
        submission_id=submission.id,
        total_score=submission.score,
        max_score=len(questions),
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        questions=question_results,
    )
