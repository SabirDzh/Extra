from typing import Annotated

from core.authentication.fastapi_users import (
    current_active_superuser,
    current_active_user,
)
from core.config import settings
from core.models.block import TestSubmission, UserAnswer
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.admin import OpenQuestionReview
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(
    prefix=settings.api.v1.admin,
    tags=["Admin"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("/submissions/pending")
async def get_pending_submissions(
    session: Session, user: User = Depends(current_active_user)
):
    stmt = (
        select(TestSubmission)
        .options(
            selectinload(TestSubmission.answers).selectinload(UserAnswer.submission)
        )
        .where(TestSubmission.status == "pending")
    )
    submissions = await session.scalars(stmt)
    return submissions.all()


@router.post("/reviews/{submission_id}")
async def guestion_status():
    pass


@router.post("/submissions/review")
async def review_submission(
    review_data: OpenQuestionReview,
    session: Session,
    user: User = Depends(current_active_superuser),
):
    submission = await session.get(TestSubmission, review_data.submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
        )

    submission.status = review_data.status
    submission.inspection_comment = review_data.comment

    await session.commit()
    return {"status": "ok"}
