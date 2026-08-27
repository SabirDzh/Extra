import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.block import Block, BlockType
from core.models.test import Question, TestAnswer, TestSubmission
from core.schemas.test import (
    BlockTestResults,
    QuestionResult,
    SubmissionHistoryResponse,
    SubmissionWithResults,
    TestResultStatus,
)
from Services.test_attempts import get_attempt_questions
from Services.test_completion import is_perfect_score


async def get_test_results_for_block(
    db: AsyncSession,
    user_id: uuid.UUID,
    block_id: uuid.UUID,
) -> BlockTestResults | None:
    """
    Retrieves the latest test submission for the given block and user,
    and returns detailed results including correctness per question.
    """

    block = await db.get(Block, block_id)
    if not block or block.block_type not in (BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test):
        return None


    stmt_sub = (
        select(TestSubmission)
        .where(
            TestSubmission.user_id == user_id,
            TestSubmission.block_id == block_id,
            TestSubmission.is_submitted.is_(True),
        )
        .options(selectinload(TestSubmission.answers).selectinload(TestAnswer.selected_option))
        .order_by(TestSubmission.submitted_at.desc(), TestSubmission.id.desc())
        .limit(1)
    )
    result_sub = await db.execute(stmt_sub)
    submission = result_sub.scalar_one_or_none()

    if not submission:
        return None


    assigned_questions = await get_attempt_questions(db, submission.id)
    if assigned_questions:
        questions = assigned_questions
    else:
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
    

    user_answers_map = defaultdict(list)
    for ans in submission.answers:
        user_answers_map[ans.question_id].append(ans)

    if not assigned_questions and len(questions) > submission.max_score:
        submitted_question_ids = set(user_answers_map)
        questions = [q for q in questions if q.id in submitted_question_ids]

    question_results = []
    for q in questions:

        correct_options = [opt for opt in q.options if opt.is_correct]
        correct_text = ", ".join([opt.text for opt in correct_options]) if correct_options else None
        correct_option_ids = {opt.id for opt in correct_options}
        
        q_answers = user_answers_map.get(q.id, [])
        user_answer_text = None
        status = TestResultStatus.INCORRECT
        score = 0


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
                    if is_perfect_score(
                        submission.score,
                        submission.max_score,
                    ):
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


    correct_count = sum(1 for r in question_results if r.status == TestResultStatus.CORRECT)
    incorrect_count = sum(1 for r in question_results if r.status == TestResultStatus.INCORRECT)


    from core.models.course import Course
    from Services import course as course_crud

    course = await db.get(Course, block.course_id)
    await course_crud.attach_course_progress(db, [course], user_id)


    stmt_all_blocks = select(Block).where(Block.course_id == block.course_id).order_by(Block.order_index)
    all_blocks = (await db.execute(stmt_all_blocks)).scalars().all()
    total_stages = (len(all_blocks) + 1) // 2


    current_block_index = 1
    for i, b in enumerate(all_blocks):
        if b.id == block_id:
            current_block_index = i + 1
            break
    current_stage = (current_block_index - 1) // 2 + 1

    return BlockTestResults(
        block_id=block_id,
        submission_id=submission.id,
        total_score=submission.score,
        max_score=submission.max_score,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        completed_at=(
            submission.submitted_at
            if submission.is_graded
            and is_perfect_score(submission.score, submission.max_score)
            else None
        ),
        title=course.title,
        total_stages=total_stages,
        passed_stages=current_stage,
        progress=course.progress,
        questions=question_results,
    )


async def get_submission_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    block_id: uuid.UUID,
) -> SubmissionHistoryResponse | None:
    block = await db.get(Block, block_id)
    if not block or block.block_type not in (
        BlockType.auto_test,
        BlockType.manual_test,
        BlockType.mixed_test,
    ):
        return None

    stmt_sub = (
        select(TestSubmission)
        .where(
            TestSubmission.user_id == user_id,
            TestSubmission.block_id == block_id,
            TestSubmission.is_submitted.is_(True),
        )
        .options(selectinload(TestSubmission.answers).selectinload(TestAnswer.selected_option))
        .order_by(TestSubmission.submitted_at.desc(), TestSubmission.id.desc())
    )
    submissions = (await db.execute(stmt_sub)).scalars().all()

    if not submissions:
        return None

    stmt_q = (
        select(Question)
        .where(Question.block_id == block_id)
        .options(selectinload(Question.options))
        .order_by(Question.order_index)
    )
    questions = (await db.execute(stmt_q)).scalars().all()

    submission_results = []
    for sub in submissions:
        user_answers_map = {}
        for ans in sub.answers:
            user_answers_map.setdefault(ans.question_id, []).append(ans)

        assigned_questions = await get_attempt_questions(db, sub.id)
        submission_questions = assigned_questions or questions
        if not assigned_questions and len(questions) > sub.max_score:
            submitted_question_ids = set(user_answers_map)
            submission_questions = [
                question
                for question in questions
                if question.id in submitted_question_ids
            ]

        question_results = []
        for q in submission_questions:
            correct_options = [opt for opt in q.options if opt.is_correct]
            correct_text = ", ".join(o.text for o in correct_options) if correct_options else None
            correct_option_ids = {opt.id for opt in correct_options}

            q_answers = user_answers_map.get(q.id, [])
            user_answer_text = None
            res_status = TestResultStatus.INCORRECT
            score = 0

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
                if q.question_type == "single_choice":
                    if len(user_selected_ids) == 1 and list(user_selected_ids)[0] in correct_option_ids:
                        res_status = TestResultStatus.CORRECT
                        score = 1
                elif q.question_type == "multiple_choice":
                    if user_selected_ids == correct_option_ids and correct_option_ids:
                        res_status = TestResultStatus.CORRECT
                        score = 1
                elif q.question_type == "free_text":
                    if sub.is_graded:
                        if is_perfect_score(sub.score, sub.max_score):
                            res_status = TestResultStatus.CORRECT
                            score = 1
                    else:
                        res_status = TestResultStatus.REQUIRES_REVIEW
            else:
                if q.question_type == "free_text" and not sub.is_graded:
                    res_status = TestResultStatus.REQUIRES_REVIEW

            question_results.append(
                QuestionResult(
                    question_id=q.id,
                    text=q.text,
                    status=res_status,
                    correct_answer=correct_text,
                    user_answer=user_answer_text,
                    score=score,
                )
            )

        submission_results.append(
            SubmissionWithResults(
                submission_id=sub.id,
                submitted_at=sub.submitted_at,
                score=sub.score,
                max_score=sub.max_score,
                is_graded=sub.is_graded,
                admin_comment=sub.admin_comment,
                questions=question_results,
            )
        )

    return SubmissionHistoryResponse(
        block_id=block_id,
        total_attempts=len(submission_results),
        submissions=submission_results,
    )
