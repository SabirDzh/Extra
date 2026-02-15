import uuid
from typing import Optional

from core.models.block import Block, BlockType
from core.models.course import Course, CourseEnrollment
from core.models.test import AnswerOption, Question, TestAnswer, TestSubmission
from core.models.user import User
from core.schemas.admin import (
    GradeSubmissionRequest,
    PendingSubmissionResponse,
    PopularMistake,
    StatisticsResponse,
)
from core.test_grading import _mark_block_completed
from fastapi import HTTPException, status
from sqlalchemy import Float, case, cast, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from utils.role import UserRole


async def get_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> User:
    stmt = select(User).where(User.id == user_id)
    result = (await session.execute(stmt)).scalar_one_or_none()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return result


async def set_new_user_role(
    session: AsyncSession,
    user_id: uuid.UUID,
    new_role: UserRole,
) -> User:
    await get_user(session, user_id)

    stmt = update(User).values(role=new_role).where(User.id == user_id).returning(User)
    result = (await session.execute(stmt)).scalars().one_or_none()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await session.commit()
    return result


async def get_statistics(
    session: AsyncSession, course_id: Optional[uuid.UUID] = None
) -> StatisticsResponse:
    stmt_completion = select(
        func.count(CourseEnrollment.completed_at), func.count(CourseEnrollment.id)
    )

    if course_id:
        stmt_completion = stmt_completion.where(CourseEnrollment.course_id == course_id)

    result_completion = await session.execute(stmt_completion)
    completed_count, total_enrollments = result_completion.one()

    completion_rate = 0.0
    if total_enrollments and total_enrollments > 0:
        completion_rate = (completed_count / total_enrollments) * 100.0

    stmt_avg_score = select(
        func.avg(
            case(
                (
                    TestSubmission.max_score > 0,
                    cast(TestSubmission.score, Float)
                    / cast(TestSubmission.max_score, Float)
                    * 100.0,
                ),
                else_=0.0,
            )
        )
    ).where(TestSubmission.is_graded)

    if course_id:
        stmt_avg_score = stmt_avg_score.join(TestSubmission.block).where(
            Block.course_id == course_id
        )

    result_avg = await session.execute(stmt_avg_score)
    average_score = result_avg.scalar() or 0.0

    stmt_mistakes = (
        select(
            Question.text, AnswerOption.text, func.count(TestAnswer.id).label("count")
        )
        .join(AnswerOption, TestAnswer.selected_answer_id == AnswerOption.id)
        .join(Question, TestAnswer.question_id == Question.id)
        .where(AnswerOption.is_correct == False)
    )

    if course_id:
        stmt_mistakes = stmt_mistakes.join(Question.block).where(
            Block.course_id == course_id
        )

    stmt_mistakes = (
        stmt_mistakes.group_by(Question.text, AnswerOption.text)
        .order_by(desc("count"))
        .limit(5)
    )

    result_mistakes = await session.execute(stmt_mistakes)
    mistakes_data = result_mistakes.all()

    popular_mistakes = [
        PopularMistake(question=m[0], answer=m[1], count=m[2]) for m in mistakes_data
    ]

    return StatisticsResponse(
        completion_rate=round(completion_rate, 2),
        average_score=round(average_score, 2),
        popular_mistakes=popular_mistakes,
    )


async def get_pending_submissions(
    session: AsyncSession, course_id: Optional[uuid.UUID] = None
) -> list[PendingSubmissionResponse]:
    stmt = (
        select(TestSubmission)
        .join(Block)
        .where(
            TestSubmission.is_graded == False,
            Block.block_type.in_([BlockType.manual_test, BlockType.auto_test]),
        )
        .order_by(TestSubmission.submitted_at.desc())
        .options(
            selectinload(TestSubmission.user),
            selectinload(TestSubmission.block).selectinload(Block.course),
            selectinload(TestSubmission.answers).selectinload(TestAnswer.question),
        )
    )

    if course_id:
        stmt = stmt.where(Block.course_id == course_id)

    result = await session.execute(stmt)
    submissions = result.scalars().all()

    response = []
    for sub in submissions:
        answers_data = []
        for ans in sub.answers:
            answers_data.append(
                {
                    "question_text": ans.question.text,
                    "answer_text": ans.text_answer or "(No text answer)",
                    "selected_option_id": ans.selected_answer_id,
                }
            )

        response.append(
            PendingSubmissionResponse(
                id=sub.id,
                user_email=sub.user.email,
                course_title=sub.block.course.title,
                block_title=sub.block.title,
                max_score=sub.max_score,
                submitted_at=sub.submitted_at.isoformat(),
                answers=answers_data,
            )
        )

    return response


async def admin_grade_submission(
    session: AsyncSession,
    submission_id: uuid.UUID,
    data: GradeSubmissionRequest,
    admin_id: uuid.UUID,
):
    submission = await session.get(TestSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission.is_graded = True
    submission.graded_by = admin_id
    submission.admin_comment = data.admin_comment

    if data.is_passed:
        submission.score = submission.max_score
        await _mark_block_completed(session, submission.user_id, submission.block_id)
    else:
        submission.score = 0

    await session.commit()
    return {"detail": "Submission graded successfully"}
