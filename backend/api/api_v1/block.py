import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from core.authentication.fastapi_users import current_active_user, current_optional_user
from core.config import settings
from core.models.block import Block, BlockType
from core.models.course import AUDIENCE_DISPLAY_NAMES, LEVEL_DISPLAY_NAMES, Course
from core.models.db_helper import db_helper
from core.models.progress import UserBlockProgress
from core.models.test import TestSubmission
from core.models.user import User
from core.schemas.block import BlockCreate, BlockRead, BlockUpdate, CourseBlocksResponse
from core.schemas.test import BlockTestResults, SubmissionHistoryResponse
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from Services import course as course_crud
from Services.test_grading import _mark_block_completed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Repository.common import ensure_unique_field
from api.dependencies.authorization import current_admin, current_course_allowed_user
from Domain.Enums.user_role import UserRole

from Services.test_results import get_submission_history, get_test_results_for_block

router = APIRouter(
    prefix="/courses/{course_id}/blocks",
    tags=["Blocks"],
    dependencies=[Depends(current_course_allowed_user)],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
IsAdmin = Annotated[User, Depends(current_admin)]
CourseAllowedUser = Annotated[User, Depends(current_course_allowed_user)]


async def _get_course_or_404(db, course_id: uuid.UUID) -> Course:
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


async def _get_block_or_404(db, block_id: uuid.UUID, course_id: uuid.UUID) -> Block:
    block = await db.get(Block, block_id)
    if not block or block.course_id != course_id:
        raise HTTPException(status_code=404, detail="Block not found")
    return block


async def _validate_block_sequence(
    db: AsyncSession,
    course_id: uuid.UUID,
    new_block_data: dict | None = None,
    update_block_id: uuid.UUID | None = None,
    update_block_data: dict | None = None,
) -> None:
    from core.models.block import TEST_BLOCK_TYPES

    stmt = select(Block).where(Block.course_id == course_id)
    result = await db.execute(stmt)
    blocks = list(result.scalars().all())

    # Map blocks to a list of dicts simulating the new state after commit
    block_states = []
    for b in blocks:
        if update_block_id and b.id == update_block_id:
            block_states.append({
                "id": b.id,
                "order_index": update_block_data.get("order_index", b.order_index) if update_block_data and "order_index" in update_block_data else b.order_index,
                "block_type": b.block_type,
            })
        else:
            block_states.append({
                "id": b.id,
                "order_index": b.order_index,
                "block_type": b.block_type,
            })

    if new_block_data:
        block_states.append({
            "id": uuid.uuid4(),
            "order_index": new_block_data.get("order_index", 0),
            "block_type": new_block_data.get("block_type"),
        })

    # Sort blocks based on order_index, then by id as a tie-breaker
    block_states.sort(key=lambda x: (x["order_index"], str(x["id"])))

    # Validate alternating sequence:
    # Even index: BlockType.lesson
    # Odd index: one of TEST_BLOCK_TYPES
    for idx, b_state in enumerate(block_states):
        b_type = b_state["block_type"]
        if idx % 2 == 0:
            if b_type != BlockType.lesson:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Нарушена последовательность этапов: блок на позиции {idx + 1} (с индексом порядка {b_state['order_index']}) должен быть лекцией, но является {b_type}."
                )
        else:
            if b_type not in TEST_BLOCK_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Нарушена последовательность этапов: блок на позиции {idx + 1} (с индексом порядка {b_state['order_index']}) должен быть тестом, но является {b_type}."
                )



async def _format_block_read(
    db: AsyncSession, block: Block, course: Course, user_id: uuid.UUID | None = None
) -> BlockRead:
    from core.schemas.course import CourseProgress, CourseStatus

    aud_label = AUDIENCE_DISPLAY_NAMES.get(course.audience, str(course.audience))
    lvl_label = LEVEL_DISPLAY_NAMES.get(course.level, str(course.level))

    is_done = False
    is_attempted = False
    under_review = False
    if user_id:
        stmt_done = select(UserBlockProgress.is_completed).where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.block_id == block.id,
            UserBlockProgress.is_completed,
        )
        is_done = (await db.execute(stmt_done)).scalar() or False

        # Fetch the latest submission to check if it's graded/under review
        stmt_sub = (
            select(TestSubmission)
            .where(
                TestSubmission.user_id == user_id,
                TestSubmission.block_id == block.id,
            )
            .order_by(TestSubmission.submitted_at.desc())
            .limit(1)
        )
        sub = (await db.execute(stmt_sub)).scalar_one_or_none()
        if sub:
            is_attempted = True
            if not sub.is_graded:
                under_review = True

    from core.models.test import Question
    from sqlalchemy import func

    stmt_count = select(func.count(Question.id)).where(Question.block_id == block.id)
    n_questions = (await db.execute(stmt_count)).scalar() or 0

    stmt_pos = select(func.count(Block.id)).where(
        Block.course_id == block.course_id,
        Block.order_index <= block.order_index,
    )
    pos_index = (await db.execute(stmt_pos)).scalar() or 1

    stmt_next = (
        select(Block.id)
        .where(
            Block.course_id == block.course_id,
            Block.order_index > block.order_index,
        )
        .order_by(Block.order_index)
        .limit(1)
    )
    next_id = (await db.execute(stmt_next)).scalar()

    stmt_all = select(func.count(Block.id)).where(Block.course_id == block.course_id)
    all_blocks_count = (await db.execute(stmt_all)).scalar() or 0

    pos_stage = (pos_index - 1) // 2 + 1

    status = CourseStatus.not_started
    if is_done:
        status = CourseStatus.completed
    elif is_attempted:
        status = CourseStatus.in_progress

    block_progress = CourseProgress(
        completed=1 if is_done else 0,
        total=n_questions,
        percent=100.0 if is_done else 0.0,
        status=status,
    )

    return BlockRead(
        id=block.id,
        course_id=block.course_id,
        order_index=pos_index,
        title=block.title,
        block_type=block.block_type,
        text_content=block.text_content,
        video_url=block.video_url,
        created_at=block.created_at,
        audience_label=aud_label,
        level_label=lvl_label,
        description=course.description,
        progress=block_progress,
        next_block_id=next_id,
        stage=pos_stage,
        under_review=under_review,
    )


@router.get("/", response_model=CourseBlocksResponse)
async def list_blocks(course_id: uuid.UUID, db: Session, user: CourseAllowedUser):
    from core.schemas.course import CourseProgress, CourseStatus

    course = await _get_course_or_404(db, course_id)
    result = await db.execute(
        select(Block).where(Block.course_id == course_id).order_by(Block.order_index)
    )
    blocks = result.scalars().all()

    completed_block_ids = set()
    latest_submissions = {}
    if user:
        stmt_progress = select(UserBlockProgress.block_id).where(
            UserBlockProgress.user_id == user.id,
            UserBlockProgress.block_id.in_([b.id for b in blocks]),
            UserBlockProgress.is_completed,
        )
        completed_block_ids = set((await db.execute(stmt_progress)).scalars().all())

        stmt_submissions = select(TestSubmission.block_id).where(
            TestSubmission.user_id == user.id,
            TestSubmission.block_id.in_([b.id for b in blocks]),
        )
        submitted_block_ids = set((await db.execute(stmt_submissions)).scalars().all())

        # Get all submissions for this user on these blocks, sorted by submitted_at desc
        stmt_sub_details = select(TestSubmission).where(
            TestSubmission.user_id == user.id,
            TestSubmission.block_id.in_([b.id for b in blocks])
        ).order_by(TestSubmission.submitted_at.desc())
        
        sub_details_res = await db.execute(stmt_sub_details)
        all_subs = sub_details_res.scalars().all()
        
        for sub in all_subs:
            if sub.block_id not in latest_submissions:
                latest_submissions[sub.block_id] = sub
    else:
        submitted_block_ids = set()

    interacted_block_ids = completed_block_ids | submitted_block_ids

    from core.models.test import Question
    from sqlalchemy import func

    stmt_counts = (
        select(Question.block_id, func.count(Question.id))
        .where(Question.block_id.in_([b.id for b in blocks]))
        .group_by(Question.block_id)
    )
    counts_res = await db.execute(stmt_counts)
    question_counts = {row[0]: row[1] for row in counts_res.all()}

    aud_label = AUDIENCE_DISPLAY_NAMES.get(course.audience, str(course.audience))
    lvl_label = LEVEL_DISPLAY_NAMES.get(course.level, str(course.level))

    all_blocks_count = len(blocks)
    all_stages_count = (all_blocks_count + 1) // 2

    # Auto-complete lesson blocks in unlocked stages for the user
    if user:
        newly_completed = False
        for stage_num in range(1, all_stages_count + 1):
            is_unlocked = True
            for prev_stage in range(1, stage_num):
                prev_blocks = [b for idx, b in enumerate(blocks) if (idx // 2) + 1 == prev_stage]
                for pb in prev_blocks:
                    if pb.block_type == BlockType.lesson:
                        if pb.id not in completed_block_ids:
                            is_unlocked = False
                    else:
                        if pb.id not in interacted_block_ids:
                            is_unlocked = False
                        else:
                            sub = latest_submissions.get(pb.id)
                            if sub is not None:
                                if not sub.is_graded or sub.score is None or sub.score < sub.max_score:
                                    is_unlocked = False

            if not is_unlocked:
                break

            stage_blocks = [b for idx, b in enumerate(blocks) if (idx // 2) + 1 == stage_num]
            for b in stage_blocks:
                if b.block_type == BlockType.lesson and b.id not in completed_block_ids:
                    await _mark_block_completed(db, user.id, b.id, course_id)
                    completed_block_ids.add(b.id)
                    interacted_block_ids.add(b.id)
                    newly_completed = True

        if newly_completed:
            await db.commit()

    # Map each stage to whether it is passed 100%
    stage_passed_100 = {}
    stage_unlocks_next = {}
    for stage_num in range(1, all_stages_count + 1):
        stage_blocks = [b for idx, b in enumerate(blocks) if (idx // 2) + 1 == stage_num]
        
        all_passed = True
        unlocks_next = True
        for b in stage_blocks:
            if b.block_type == BlockType.lesson:
                if b.id not in completed_block_ids:
                    all_passed = False
                    unlocks_next = False
            else: # test block
                if b.id not in interacted_block_ids:
                    all_passed = False
                    unlocks_next = False
                else:
                    sub = latest_submissions.get(b.id)
                    if sub is not None:
                        if not sub.is_graded:
                            all_passed = False
                        elif sub.score is None or sub.score < sub.max_score:
                            all_passed = False
                            unlocks_next = False
        
        stage_passed_100[stage_num] = all_passed
        stage_unlocks_next[stage_num] = unlocks_next

    highest_unlocked_stage = 1
    for stage_num in range(1, all_stages_count):
        if stage_unlocks_next[stage_num]:
            highest_unlocked_stage = stage_num + 1
        else:
            break

    is_course_finished = all_stages_count > 0 and all(stage_passed_100.values())

    current_block_id = None
    # Find current block id for highest unlocked stage
    active_stage_blocks = [b for idx, b in enumerate(blocks) if (idx // 2) + 1 == highest_unlocked_stage]
    for b in active_stage_blocks:
        if b.block_type == BlockType.lesson:
            if b.id not in completed_block_ids:
                current_block_id = b.id
                break
        else:
            is_passed = False
            if b.id in interacted_block_ids:
                sub = latest_submissions.get(b.id)
                if sub is None:
                    is_passed = True
                elif sub.is_graded and sub.score is not None and sub.score >= sub.max_score:
                    is_passed = True
            if not is_passed:
                current_block_id = b.id
                break
    else:
        if active_stage_blocks:
            current_block_id = active_stage_blocks[0].id

    is_admin = user and (user.role == UserRole.admin or user.is_superuser)

    block_reads = []
    for i, b in enumerate(blocks):
        pos_index = i + 1
        pos_stage = (i // 2) + 1

        if not is_admin:
            if is_course_finished:
                if pos_stage != all_stages_count:
                    continue
            else:
                if pos_stage > highest_unlocked_stage:
                    continue
                if stage_passed_100.get(pos_stage, False):
                    continue

        next_id = blocks[i + 1].id if i + 1 < len(blocks) else None

        sub = latest_submissions.get(b.id) if user else None
        under_review = (sub is not None and not sub.is_graded) if sub else False

        block_reads.append(
            BlockRead(
                id=b.id,
                course_id=b.course_id,
                order_index=pos_index,
                title=b.title,
                block_type=b.block_type,
                text_content=b.text_content,
                video_url=b.video_url,
                created_at=b.created_at,
                audience_label=aud_label,
                level_label=lvl_label,
                description=course.description,
                next_block_id=next_id,
                stage=pos_stage,
                under_review=under_review,
                progress=CourseProgress(
                    completed=1 if b.id in completed_block_ids else 0,
                    total=question_counts.get(b.id, 0),
                    percent=100.0 if b.id in completed_block_ids else 0.0,
                    status=(
                        CourseStatus.completed
                        if b.id in completed_block_ids
                        else (
                            CourseStatus.in_progress
                            if b.id in submitted_block_ids
                            else CourseStatus.not_started
                        )
                    ),
                ),
            )
        )

    return CourseBlocksResponse(
        blocks=block_reads,
        audience_label=aud_label,
        level_label=lvl_label,
        progress=await _get_course_progress(db, course, user.id if user else None),
        current_block_id=current_block_id,
        all_blocks=all_blocks_count,
        all_stages=all_stages_count,
    )


async def _get_course_progress(
    db: AsyncSession, course: Course, user_id: uuid.UUID | None
):
    await course_crud.attach_course_progress(db, [course], user_id)
    return course.progress


@router.post("/", response_model=BlockRead, status_code=status.HTTP_201_CREATED)
async def create_block(
    course_id: uuid.UUID,
    data: BlockCreate,
    db: Session,
    admin: User = Depends(current_admin),
):
    course = await _get_course_or_404(db, course_id)
    await _validate_block_sequence(
        db,
        course_id=course_id,
        new_block_data={"block_type": data.block_type, "order_index": data.order_index},
    )
    payload = data.model_dump()
    if not payload.get("title"):
        payload["title"] = course.title
    block = Block(**payload, course_id=course_id)
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return await _format_block_read(db, block, course, admin.id)


@router.get("/{block_id}", response_model=BlockRead)
async def get_block(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    user: CourseAllowedUser,
):
    course = await _get_course_or_404(db, course_id)
    block = await _get_block_or_404(db, block_id, course_id)
    if block.block_type == BlockType.lesson and user:
        await _mark_block_completed(db, user.id, block.id, course_id)
        await db.commit()
    return await _format_block_read(db, block, course, user.id if user else None)


@router.patch("/{block_id}", response_model=BlockRead)
async def update_block(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    data: BlockUpdate,
    db: Session,
    admin: User = Depends(current_admin),
):
    course = await _get_course_or_404(db, course_id)
    block = await _get_block_or_404(db, block_id, course_id)
    patch = data.model_dump(exclude_unset=True)

    if "order_index" in patch:
        await _validate_block_sequence(
            db,
            course_id=course_id,
            update_block_id=block_id,
            update_block_data={"order_index": patch["order_index"]},
        )

    for field, value in patch.items():
        setattr(block, field, value)
    await db.commit()
    await db.refresh(course)
    await db.refresh(block)
    return await _format_block_read(db, block, course, admin.id)


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    admin: User = Depends(current_admin),
):
    block = await _get_block_or_404(db, block_id, course_id)
    await db.delete(block)
    await db.commit()


@router.post("/{block_id}/upload-video", response_model=BlockRead)
async def upload_video(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    file: UploadFile,
    db: Session,
    admin: User = Depends(current_admin),
):
    block = await _get_block_or_404(db, block_id, course_id)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1]
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    block.video_url = filepath
    await db.commit()
    await db.refresh(block)
    return block


@router.post("/{block_id}/complete")
async def mark_complete(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    admin: User = Depends(current_admin),
):
    block = await _get_block_or_404(db, block_id, course_id)

    await _mark_block_completed(db, admin.id, block_id, course_id)

    await db.commit()

    return {"detail": "Block marked as completed"}


@router.get("/{block_id}/test-results", response_model=BlockTestResults)
async def get_block_test_results(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    user: CourseAllowedUser,
):
    block = await _get_block_or_404(db, block_id, course_id)

    if block.block_type not in (
        BlockType.auto_test,
        BlockType.manual_test,
        BlockType.mixed_test,
    ):
        raise HTTPException(status_code=400, detail="Block is not a test block")

    results = await get_test_results_for_block(db, user.id, block_id)
    if not results:
        raise HTTPException(
            status_code=404, detail="Test results not found or no submissions"
        )

    return results


@router.get("/{block_id}/submission-history", response_model=SubmissionHistoryResponse)
async def get_block_submission_history(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    user: CourseAllowedUser,
):
    block = await _get_block_or_404(db, block_id, course_id)

    if block.block_type not in (
        BlockType.auto_test,
        BlockType.manual_test,
        BlockType.mixed_test,
    ):
        raise HTTPException(status_code=400, detail="Block is not a test block")

    history = await get_submission_history(db, user.id, block_id)
    if not history:
        raise HTTPException(
            status_code=404, detail="No submissions found"
        )

    return history
