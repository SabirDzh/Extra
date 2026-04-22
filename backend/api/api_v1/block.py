import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from core.authentication.fastapi_users import current_active_user, current_optional_user
from core.config import settings
from core.models.block import Block, BlockType
from core.models.course import Course, AUDIENCE_DISPLAY_NAMES, LEVEL_DISPLAY_NAMES
from core.models.db_helper import db_helper
from core.models.progress import UserBlockProgress
from core.models.user import User
from core.models.test import TestSubmission
from core.schemas.block import BlockCreate, BlockRead, BlockUpdate, CourseBlocksResponse
from crud.test_grading import _mark_block_completed
from crud import course as course_crud
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(prefix="/courses/{course_id}/blocks", tags=["Blocks"])

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
IsAdmin = Annotated[User, Depends(current_admin)]
isUser = Annotated[User, Depends(current_active_user)]
OptionalUser = Annotated[User | None, Depends(current_optional_user)]


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


async def _format_block_read(
    db: AsyncSession, 
    block: Block, 
    course: Course, 
    user_id: uuid.UUID | None = None
) -> BlockRead:
    from core.schemas.course import CourseProgress, CourseStatus
    
    aud_label = AUDIENCE_DISPLAY_NAMES.get(course.audience, str(course.audience))
    lvl_label = LEVEL_DISPLAY_NAMES.get(course.level, str(course.level))
    
    is_done = False
    is_attempted = False
    if user_id:
        stmt_done = select(UserBlockProgress.is_completed).where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.block_id == block.id,
            UserBlockProgress.is_completed == True,
        )
        is_done = (await db.execute(stmt_done)).scalar() or False
        
        if not is_done:
            stmt_attempt = select(TestSubmission.id).where(
                TestSubmission.user_id == user_id,
                TestSubmission.block_id == block.id,
            ).limit(1)
            is_attempted = (await db.execute(stmt_attempt)).scalar() is not None
        

    from core.models.test import Question
    from sqlalchemy import func
    stmt_count = select(func.count(Question.id)).where(Question.block_id == block.id)
    n_questions = (await db.execute(stmt_count)).scalar() or 0


    stmt_pos = select(func.count(Block.id)).where(
        Block.course_id == block.course_id,
        Block.order_index <= block.order_index,
    )
    pos_index = (await db.execute(stmt_pos)).scalar() or 1


    stmt_next = select(Block.id).where(
        Block.course_id == block.course_id,
        Block.order_index > block.order_index,
    ).order_by(Block.order_index).limit(1)
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
    )


@router.get("/", response_model=CourseBlocksResponse)
async def list_blocks(course_id: uuid.UUID, db: Session, user: OptionalUser):
    from core.schemas.course import CourseProgress, CourseStatus
    
    course = await _get_course_or_404(db, course_id)
    result = await db.execute(
        select(Block).where(Block.course_id == course_id).order_by(Block.order_index)
    )
    blocks = result.scalars().all()


    completed_block_ids = set()
    if user:
        stmt_progress = select(UserBlockProgress.block_id).where(
            UserBlockProgress.user_id == user.id,
            UserBlockProgress.block_id.in_([b.id for b in blocks]),
            UserBlockProgress.is_completed == True,
        )
        completed_block_ids = set((await db.execute(stmt_progress)).scalars().all())


        stmt_submissions = select(TestSubmission.block_id).where(
            TestSubmission.user_id == user.id,
            TestSubmission.block_id.in_([b.id for b in blocks]),
        )
        submitted_block_ids = set((await db.execute(stmt_submissions)).scalars().all())
    else:
        submitted_block_ids = set()


    from core.models.test import Question
    from sqlalchemy import func
    stmt_counts = select(Question.block_id, func.count(Question.id)).where(
        Question.block_id.in_([b.id for b in blocks])
    ).group_by(Question.block_id)
    counts_res = await db.execute(stmt_counts)
    question_counts = {row[0]: row[1] for row in counts_res.all()}

    aud_label = AUDIENCE_DISPLAY_NAMES.get(course.audience, str(course.audience))
    lvl_label = LEVEL_DISPLAY_NAMES.get(course.level, str(course.level))

    current_block_id = None
    active_stage = 1
    block_reads = []
    all_blocks_count = len(blocks)
    all_stages_count = (all_blocks_count + 1) // 2
    

    found_active = False
    for i, b in enumerate(blocks):
        if not found_active and b.id not in completed_block_ids:
            active_stage = (i // 2) + 1
            current_block_id = b.id
            found_active = True
            

    if user and (user.role == "administrator" or user.is_superuser):
        active_stage = all_stages_count

    elif not found_active and blocks:
        active_stage = all_stages_count


    for i, b in enumerate(blocks):
        pos_index = i + 1
        pos_stage = (i // 2) + 1
        

        if pos_stage > active_stage:
            continue
            
        next_id = blocks[i + 1].id if i + 1 < len(blocks) else None
        
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
                progress=CourseProgress(
                    completed=1 if b.id in completed_block_ids else 0,
                    total=question_counts.get(b.id, 0),
                    percent=100.0 if b.id in completed_block_ids else 0.0,
                    status=(
                        CourseStatus.completed if b.id in completed_block_ids 
                        else CourseStatus.in_progress if b.id in submitted_block_ids 
                        else CourseStatus.not_started
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


async def _get_course_progress(db: AsyncSession, course: Course, user_id: uuid.UUID | None):
    from crud import course as course_crud
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
    block = Block(**data.model_dump(), course_id=course_id)
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return await _format_block_read(db, block, course, admin.id)


@router.get("/{block_id}", response_model=BlockRead)
async def get_block(
    course_id: uuid.UUID, 
    block_id: uuid.UUID, 
    db: Session,
    user: OptionalUser,
):
    course = await _get_course_or_404(db, course_id)
    block = await _get_block_or_404(db, block_id, course_id)
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
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(block, field, value)
    await db.commit()
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
    user: User = Depends(current_active_user),
):
    block = await _get_block_or_404(db, block_id, course_id)

    await _mark_block_completed(db, user.id, block_id, course_id)

    await db.commit()


    return {"detail": "Block marked as completed"}


from core.schemas.test import BlockTestResults
from crud.test_results import get_test_results_for_block

@router.get("/{block_id}/test-results", response_model=BlockTestResults)
async def get_block_test_results(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    user: User = Depends(current_active_user),
):
    block = await _get_block_or_404(db, block_id, course_id)
    

    if block.block_type not in (BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test):
        raise HTTPException(status_code=400, detail="Block is not a test block")

    results = await get_test_results_for_block(db, user.id, block_id)
    if not results:
        raise HTTPException(status_code=404, detail="Test results not found or no submissions")
        
    return results
