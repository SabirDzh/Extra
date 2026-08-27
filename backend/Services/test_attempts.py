"""Persistence helpers for the exact questions assigned to a test attempt."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.test import Question, TestSubmissionQuestion


async def get_attempt_questions(
    db: AsyncSession,
    submission_id: uuid.UUID,
) -> list[Question]:
    """Load questions assigned to one attempt in the order shown to the student.

    Args:
        db: Active database session.
        submission_id: Identifier of the test submission.

    Returns:
        Questions recorded for the attempt, including their answer options.
    """
    result = await db.execute(
        select(Question)
        .join(
            TestSubmissionQuestion,
            TestSubmissionQuestion.question_id == Question.id,
        )
        .where(TestSubmissionQuestion.submission_id == submission_id)
        .options(selectinload(Question.options))
        .order_by(TestSubmissionQuestion.order_index)
    )
    return list(result.scalars().all())
