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
from core.schemas.block import BlockCreate, BlockRead, BlockUpdate, CourseBlocksResponse
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
    if user_id:
        stmt = select(UserBlockProgress.is_completed).where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.block_id == block.id,
            UserBlockProgress.is_completed == True,
        )
        is_done = (await db.execute(stmt)).scalar() or False
        
    # Count questions in this block
    from core.models.test import Question
    from sqlalchemy import func
    stmt_count = select(func.count(Question.id)).where(Question.block_id == block.id)
    n_questions = (await db.execute(stmt_count)).scalar() or 0

    block_progress = CourseProgress(
        completed=1 if is_done else 0,
        total=n_questions,
        percent=100.0 if is_done else 0.0,
        status=CourseStatus.completed if is_done else CourseStatus.not_started,
    )
    
    return BlockRead(
        id=block.id,
        course_id=block.course_id,
        order_index=block.order_index,
        title=block.title,
        block_type=block.block_type,
        text_content=block.text_content,
        video_url=block.video_url,
        created_at=block.created_at,
        audience_label=aud_label,
        level_label=lvl_label,
        progress=block_progress,
    )


@router.get("/", response_model=CourseBlocksResponse)
async def list_blocks(course_id: uuid.UUID, db: Session, user: OptionalUser):
    from core.schemas.course import CourseProgress, CourseStatus
    
    course = await _get_course_or_404(db, course_id)
    result = await db.execute(
        select(Block).where(Block.course_id == course_id).order_by(Block.order_index)
    )
    blocks = result.scalars().all()

    # Optimized progress fetch for list
    completed_block_ids = set()
    if user:
        stmt_progress = select(UserBlockProgress.block_id).where(
            UserBlockProgress.user_id == user.id,
            UserBlockProgress.block_id.in_([b.id for b in blocks]),
            UserBlockProgress.is_completed == True,
        )
        completed_block_ids = set((await db.execute(stmt_progress)).scalars().all())

    # Fetch question counts for all blocks in the course
    from core.models.test import Question
    from sqlalchemy import func
    stmt_counts = select(Question.block_id, func.count(Question.id)).where(
        Question.block_id.in_([b.id for b in blocks])
    ).group_by(Question.block_id)
    counts_res = await db.execute(stmt_counts)
    question_counts = {row[0]: row[1] for row in counts_res.all()}

    aud_label = AUDIENCE_DISPLAY_NAMES.get(course.audience, str(course.audience))
    lvl_label = LEVEL_DISPLAY_NAMES.get(course.level, str(course.level))

    block_reads = [
        BlockRead(
            id=b.id,
            course_id=b.course_id,
            order_index=b.order_index,
            title=b.title,
            block_type=b.block_type,
            text_content=b.text_content,
            video_url=b.video_url,
            created_at=b.created_at,
            audience_label=aud_label,
            level_label=lvl_label,
            progress=CourseProgress(
                completed=1 if b.id in completed_block_ids else 0,
                total=question_counts.get(b.id, 0),
                percent=100.0 if b.id in completed_block_ids else 0.0,
                status=CourseStatus.completed if b.id in completed_block_ids else CourseStatus.not_started,
            ),
        )
        for b in blocks
    ]

    return CourseBlocksResponse(
        blocks=block_reads,
        audience_label=aud_label,
        level_label=lvl_label,
        progress=await _get_course_progress(db, course, user.id if user else None),
    )


async def _get_course_progress(db: AsyncSession, course: Course, user_id: uuid.UUID | None):
    from crud import course as course_crud
    if not user_id:
        return None
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


@router.put("/{block_id}", response_model=BlockRead)
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

    existing = (
        await db.execute(
            select(UserBlockProgress).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id == block_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.is_completed = True
        existing.completed_at = datetime.now(timezone.utc)
    else:
        db.add(
            UserBlockProgress(
                user_id=user.id,
                block_id=block_id,
                is_completed=True,
                completed_at=datetime.now(timezone.utc),
            )
        )

    await db.commit()

    # Automatically recalculate course completion status (business logic in crud)
    await course_crud.update_course_completion_status(db, user.id, course_id)

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
    
    # Needs to handle if it's not a test block
    if block.block_type not in (BlockType.auto_test, BlockType.manual_test):
        raise HTTPException(status_code=400, detail="Block is not a test block")

    results = await get_test_results_for_block(db, user.id, block_id)
    if not results:
        raise HTTPException(status_code=404, detail="Test results not found or no submissions")
        
    return results
