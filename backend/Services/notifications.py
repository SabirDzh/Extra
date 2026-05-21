import logging
import os
import time

import aiohttp
from core.models import User
from core.schemas.user import UserRead, UserRegisteredNotification

log = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://httpbin.org/post")


async def send_new_user_notification(user: User) -> None:
    if not WEBHOOK_URL:
        log.debug("WEBHOOK_URL is empty, skipping new user notification webhook")
        return

    try:
        wh_data = UserRegisteredNotification(
            user=UserRead.model_validate(user),
            ts=int(time.time()),
        ).model_dump(mode="json")

        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(WEBHOOK_URL, json=wh_data) as response:
                response.raise_for_status()
                await response.json()

    except Exception:
        # Webhook must be best-effort and should never break user registration/tests.
        log.exception("Failed to send webhook for new user")


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.models.notification import Notification
from Domain.Enums.notification import NotificationType
from Domain.Enums.user_role import UserRole
from Domain.Enums.course import CourseAudience

async def notify_new_course(db: AsyncSession, course) -> None:
    target_roles = []
    if course.audience == CourseAudience.installer:
        target_roles = [UserRole.installer]
    elif course.audience == CourseAudience.seller:
        target_roles = [UserRole.seller]
    elif course.audience == CourseAudience.serviceman:
        target_roles = [UserRole.serviceman]
    elif course.audience == CourseAudience.everyone:
        target_roles = [UserRole.installer, UserRole.seller, UserRole.serviceman]
    
    if not target_roles:
        return
        
    stmt = select(User.id).where(User.role.in_(target_roles))
    result = await db.execute(stmt)
    user_ids = result.scalars().all()
    
    notifications = []
    for uid in user_ids:
        notifications.append(
            Notification(
                user_id=uid,
                type=NotificationType.new_course,
                title=f"Новый курс: {course.title}",
                message=f"Доступен новый курс '{course.title}'. Приглашаем к изучению!",
                reference_id=course.id
            )
        )
    
    if notifications:
        db.add_all(notifications)
        await db.commit()

async def notify_manual_test_required(db: AsyncSession, submission, user_name: str) -> None:
    stmt = select(User.id).where(User.role == UserRole.admin)
    result = await db.execute(stmt)
    admin_ids = result.scalars().all()
    
    notifications = []
    for aid in admin_ids:
        notifications.append(
            Notification(
                user_id=aid,
                type=NotificationType.manual_test_check,
                title="Требуется проверка теста",
                message=f"Пользователь {user_name} прошел тест, который требует ручной проверки.",
                reference_id=submission.id
            )
        )
        
    if notifications:
        db.add_all(notifications)
        await db.commit()
