import uuid
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.block import TestSubmission, UserAnswer
from core.models.course import CourseBlock
from core.models.db_helper import db_helper
from core.models.question import TestQuestion
from core.models.user import User
from core.schemas.question import TestSubmissionCreate
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(
    prefix=settings.api.v1.blocks,
    tags=["Blocks"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("/{block_id}")
async def get_block_detail(
    block_id: uuid.UUID,
    session: Session,
    user: User = Depends(current_active_user),
):
    stmt = (
        select(CourseBlock)
        .options(selectinload(CourseBlock.questions).selectinload(TestQuestion.option))
        .where(CourseBlock.id == block_id)
    )
    block = await session.scalar(stmt)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block not found"
        )
    return block


@router.post("/{block_id}/watch")
async def watch_block():
    pass


@router.get("/{block_id}/test")
async def get_test_block():
    pass


@router.post("/{block_id}/test/submit")
async def check_test(
    block_id: uuid.UUID,
    submission_data: TestSubmissionCreate,
    session: Session,
    user: User = Depends(current_active_user),
):
    submission = TestSubmission(
        user_id=user.id,
        block_id=block_id,
        status="pending",
    )
    session.add(submission)
    await session.flush()

    for ans in submission_data.answers:
        user_answer = UserAnswer(
            submission_id=submission.id,
            question_id=ans.question_id,
            selected_option_id=ans.selected_option_id,
            text_answer=ans.text_answer,
        )
        session.add(user_answer)
    await session.commit()
    return {"status": "submitted", "submission_id": submission.id}


@router.get("/{block_id}/test/attempts")
async def attempts_history():
    pass
