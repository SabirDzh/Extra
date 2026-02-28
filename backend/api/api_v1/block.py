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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin
from utils.role import UserRole

router = APIRouter(prefix="/courses/{course_id}/blocks", tags=["Blocks"])

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


async def _get_course_or_404(db, course_id: uuid.UUID) -> Course:
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    return course


async def _get_block_or_404(db, block_id: uuid.UUID, course_id: uuid.UUID) -> Block:
    block = await db.get(Block, block_id)
    if not block or block.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block not found"
        )
    return block


async def check_previous_blocks_completed(
    db: AsyncSession, user: User, block: Block
) -> bool:
    if user.role == UserRole.admin:
        return True

    previous_blocks = (
        (
            await db.execute(
                select(Block.id).where(
                    Block.course_id == block.course_id,
                    Block.order_index < block.order_index,
                )
            )
        )
        .scalars()
        .all()
    )

    if not previous_blocks:
        return True

    completed_count = (
        await db.execute(
            select(func.count(UserBlockProgress.id)).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id.in_(previous_blocks),
                UserBlockProgress.is_completed,
            )
        )
    ).scalar()

    return completed_count == len(previous_blocks)


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[BlockRead])
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
    admin: Annotated[User, Depends(current_admin)],
):
    await _get_course_or_404(db, course_id)
    block = Block(**data.model_dump(), course_id=course_id)
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


@router.get("/{block_id}", status_code=status.HTTP_200_OK, response_model=BlockRead)
async def get_block(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    user: Annotated[User, Depends(current_active_user)],
):
    block = await _get_block_or_404(db, block_id, course_id)

    if not await check_previous_blocks_completed(db, user, block):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Previous blocks must be completed first",
        )

    return block


@router.put("/{block_id}", response_model=BlockRead)
async def update_block(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    data: BlockUpdate,
    db: Session,
    admin: Annotated[User, Depends(current_admin)],
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
    admin: Annotated[User, Depends(current_admin)],
):
    block = await _get_block_or_404(db, block_id, course_id)
    await db.delete(block)
    await db.commit()


@router.post(
    "/{block_id}/upload-video",
    status_code=status.HTTP_201_CREATED,
    response_model=BlockRead,
)
async def upload_video(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    file: UploadFile,
    db: Session,
    admin: Annotated[User, Depends(current_admin)],
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


@router.post(
    "/{block_id}/complete",
    status_code=status.HTTP_201_CREATED,
)
async def mark_complete(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session,
    user: Annotated[User, Depends(current_active_user)],
):
    block = await _get_block_or_404(db, block_id, course_id)

    if not await check_previous_blocks_completed(db, user, block):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Previous blocks must be completed first before completing this one",
        )

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
