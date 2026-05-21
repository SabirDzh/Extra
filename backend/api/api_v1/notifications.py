import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.db_helper import db_helper
from core.models.notification import Notification
from core.models.user import User
from core.schemas.notification import NotificationRead, NotificationUpdate
from core.authentication.fastapi_users import current_active_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=list[NotificationRead])
async def get_notifications(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    offset: int = 0,
    limit: int = 20,
):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/unread-count")
async def get_unread_count(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
):
    stmt = select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.is_read == False
    )
    result = await session.execute(stmt)
    count = result.scalar() or 0
    return {"unread_count": count}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
):
    notification = await session.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await session.commit()
    await session.refresh(notification)
    return notification


@router.post("/read-all")
async def mark_all_notifications_read(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
):
    stmt = (
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await session.execute(stmt)
    await session.commit()
    return {"status": "success"}
