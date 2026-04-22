import uuid
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.models.block import (
    Block,
    BlockType,
    TEST_BLOCK_TYPES,
)
from core.models.db_helper import db_helper
from core.models.test import AnswerOption, Question, TestAnswer, TestSubmission
from core.models.user import User
from core.schemas.test import (
    GradeSubmission,
    QuestionCreate,
    QuestionRead,
    QuestionReadAdmin,
    QuestionUpdate,
    TestSubmissionRead,
    TestSubmit,
)
from crud.test_grading import auto_grade_submission, _mark_block_completed
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from utils.product import current_admin
from utils.role import UserRole
from core.config import settings 

router = APIRouter(prefix=settings.api.v1.tests, tags=["Tests"])

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.post(
    "/blocks/{block_id}/questions",
    response_model=QuestionReadAdmin,
    status_code=status.HTTP_201_CREATED,
)
async def create_question(
    block_id: uuid.UUID,
    data: QuestionCreate,
    db: Session,
    admin: User = Depends(current_admin),
):
    block = await db.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    if block.block_type not in TEST_BLOCK_TYPES:
        raise HTTPException(status_code=400, detail="Questions can only be added to test blocks")
    question = Question(
        block_id=block_id,
        text=data.text,
        question_type=data.question_type,
        order_index=data.order_index,
    )
    db.add(question)
    await db.flush()
    for opt in data.options:
        db.add(AnswerOption(question_id=question.id, **opt.model_dump()))
    await db.commit()
    return await _load_question(db, question.id)


@router.patch("/questions/{question_id}", response_model=QuestionReadAdmin)
@router.put("/questions/{question_id}", response_model=QuestionReadAdmin)
async def update_question(
    question_id: uuid.UUID,
    data: QuestionUpdate,
    db: Session,
    admin: User = Depends(current_admin),
):
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    for field, value in data.model_dump(
        exclude_unset=True, exclude={"options"}
    ).items():
        setattr(question, field, value)
    if data.options is not None:
        old_options = (
            (
                await db.execute(
                    select(AnswerOption).where(AnswerOption.question_id == question_id)
                )
            )
            .scalars()
            .all()
        )
        for o in old_options:
            await db.delete(o)
        await db.flush()
        for opt in data.options:
            db.add(AnswerOption(question_id=question_id, **opt.model_dump()))
    await db.commit()
    return await _load_question(db, question_id)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: uuid.UUID, db: Session, admin: User = Depends(current_admin)
):
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    await db.delete(question)
    await db.commit()


@router.get("/blocks/{block_id}/questions")
async def list_questions(
    block_id: uuid.UUID, db: Session, user: User = Depends(current_active_user)
):
    block = await db.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    questions = (
        (
            await db.execute(
                select(Question)
                .where(Question.block_id == block_id)
                .options(selectinload(Question.options))
                .order_by(Question.order_index)
            )
        )
        .scalars()
        .all()
    )

    if user.role == UserRole.admin:
        return [QuestionReadAdmin.model_validate(q) for q in questions]
    return [QuestionRead.model_validate(q) for q in questions]


@router.post("/blocks/{block_id}/submit", response_model=TestSubmissionRead)
async def submit_test(
    block_id: uuid.UUID,
    data: TestSubmit,
    db: Session,
    user: User = Depends(current_active_user),
):
    block = await db.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    if block.block_type not in (BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test):
        raise HTTPException(status_code=400, detail="Block is not a test")

    questions = (
        (await db.execute(select(Question).where(Question.block_id == block_id)))
        .scalars()
        .all()
    )

    submission = TestSubmission(
        user_id=user.id,
        block_id=block_id,
        max_score=len(questions),
        is_graded=False,
    )
    db.add(submission)
    await db.flush()

    for ans in data.answers:
        db.add(
            TestAnswer(
                submission_id=submission.id,
                question_id=ans.question_id,
                selected_answer_id=ans.selected_answer_id,
                text_answer=ans.text_answer,
            )
        )
    await db.flush()

    submission = await auto_grade_submission(db, submission)

    await db.commit()
    return await _load_submission(db, submission.id)


@router.get("/submissions/{submission_id}", response_model=TestSubmissionRead)
async def get_submission(
    submission_id: uuid.UUID, db: Session, user: User = Depends(current_active_user)
):
    submission = await _load_submission(db, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if user.role != UserRole.admin and submission.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return submission


@router.get("/blocks/{block_id}/submissions", response_model=list[TestSubmissionRead])
async def list_submissions(
    block_id: uuid.UUID, db: Session, admin: User = Depends(current_admin)
):
    result = await db.execute(
        select(TestSubmission)
        .where(TestSubmission.block_id == block_id)
        .options(selectinload(TestSubmission.answers))
    )
    return result.scalars().all()


@router.get("/courses/{course_id}/pending-submissions", response_model=list[TestSubmissionRead])
async def list_pending_course_submissions(
    course_id: uuid.UUID, 
    db: Session, 
    admin: User = Depends(current_admin)
):
    """
    Returns all ungraded submissions for manual test blocks within a specific course.
    Used by admins to find work that needs review.
    """
    result = await db.execute(
        select(TestSubmission)
        .join(Block, TestSubmission.block_id == Block.id)
        .where(
            Block.course_id == course_id,
            Block.block_type == BlockType.manual_test,
            TestSubmission.is_graded == False
        )
        .options(selectinload(TestSubmission.answers))
        .order_by(TestSubmission.submitted_at.desc())
    )
    return result.scalars().all()


@router.post("/submissions/{submission_id}/grade", response_model=TestSubmissionRead)
async def grade_submission(
    submission_id: uuid.UUID,
    data: GradeSubmission,
    db: Session,
    admin: User = Depends(current_admin),
):
    submission = await db.get(TestSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission.score = float(data.score)
    submission.admin_comment = data.admin_comment
    submission.is_graded = True
    submission.graded_by = admin.id

    if data.score > 0:
        await _mark_block_completed(db, submission.user_id, submission.block_id)

    await db.commit()
    return await _load_submission(db, submission_id)


async def _load_question(db, question_id: uuid.UUID):
    return (
        await db.execute(
            select(Question)
            .where(Question.id == question_id)
            .options(selectinload(Question.options))
        )
    ).scalar_one()


async def _load_submission(db, submission_id: uuid.UUID):
    return (
        await db.execute(
            select(TestSubmission)
            .where(TestSubmission.id == submission_id)
            .options(selectinload(TestSubmission.answers))
        )
    ).scalar_one_or_none()
