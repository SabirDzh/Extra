import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.block import Block
from core.models.course import Course
from core.models.db_helper import db_helper
from core.models.progress import UserBlockProgress
from core.models.user import User
from core.schemas.block import BlockCreate, BlockRead, BlockUpdate
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(prefix="/api/courses/{course_id}/blocks", tags=["Blocks"])

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
IsAdmin = Annotated[User, Depends(current_admin)]
isUser = Annotated[User, Depends(current_active_user)]


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


@router.get("/", response_model=list[BlockRead])
async def list_blocks(course_id: uuid.UUID, db: Session):
    await _get_course_or_404(db, course_id)
    result = await db.execute(
        select(Block).where(Block.course_id == course_id).order_by(Block.order_index)
    )
    return result.scalars().all()


@router.post("/", response_model=BlockRead, status_code=status.HTTP_201_CREATED)
async def create_block(
    course_id: uuid.UUID,
    data: BlockCreate,
    db: Session,
    admin: User = Depends(current_admin),
):
    await _get_course_or_404(db, course_id)
    block = Block(**data.model_dump(), course_id=course_id)
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


@router.get("/{block_id}", response_model=BlockRead)
async def get_block(course_id: uuid.UUID, block_id: uuid.UUID, db: Session):
    return await _get_block_or_404(db, block_id, course_id)


@router.put("/{block_id}", response_model=BlockRead)
async def update_block(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    data: BlockUpdate,
    db: Session,
    admin: User = Depends(current_admin),
):
    block = await _get_block_or_404(db, block_id, course_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(block, field, value)
    await db.commit()
    await db.refresh(block)
    return block


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
    return {"detail": "Block marked as completed"}
