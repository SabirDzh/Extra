import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.models.notification import Notification
from core.models.user import User
from Domain.Enums.notification import NotificationType
from Domain.Enums.user_role import UserRole
from Domain.Enums.course import CourseAudience
from Services.notifications import notify_new_course, notify_manual_test_required

@pytest.mark.anyio
async def test_get_notifications_empty(client: AsyncClient, normal_user_token_headers):
    response = await client.get("/api/v1/notifications/")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.anyio
async def test_notifications_lifecycle(client: AsyncClient, normal_user_token_headers, session: AsyncSession):
    stmt = select(User).where(User.email == "normal@example.com")
    result = await session.execute(stmt)
    user = result.scalar_one()

    import uuid_utils
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    notification = Notification(
        id=uuid_utils.uuid7(),
        user_id=user.id,
        type=NotificationType.new_course,
        title="Test Title",
        message="Test Message",
        created_at=now
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)

    resp = await client.get("/api/v1/notifications/unread-count")
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 1

    resp = await client.get("/api/v1/notifications/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test Title"
    assert data[0]["is_read"] is False

    notif_id = data[0]["id"]
    resp = await client.patch(f"/api/v1/notifications/{notif_id}/read")
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    resp = await client.get("/api/v1/notifications/unread-count")
    assert resp.json()["unread_count"] == 0

@pytest.mark.anyio
async def test_mark_all_read(client: AsyncClient, normal_user_token_headers, session: AsyncSession):
    stmt = select(User).where(User.email == "normal@example.com")
    result = await session.execute(stmt)
    user = result.scalar_one()

    import uuid_utils
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for i in range(3):
        session.add(Notification(
            id=uuid_utils.uuid7(),
            user_id=user.id,
            type=NotificationType.other,
            title=f"Test {i}",
            message="Msg",
            created_at=now
        ))
    await session.commit()

    resp = await client.post("/api/v1/notifications/read-all")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/notifications/unread-count")
    assert resp.json()["unread_count"] == 0

@pytest.mark.anyio
async def test_notify_new_course_service(session: AsyncSession, create_user):
    installer = await create_user("inst@example.com", role=UserRole.installer.value)
    seller = await create_user("sell@example.com", role=UserRole.seller.value)
    buyer = await create_user("buyer@example.com", role=UserRole.buyer.value)

    class MockCourse:
        id = None
        title = "Mock Installer Course"
        audience = CourseAudience.installer

    await notify_new_course(session, MockCourse())

    stmt = select(Notification).where(Notification.user_id == installer.id)
    notifs_installer = (await session.execute(stmt)).scalars().all()
    assert len(notifs_installer) == 1

    stmt = select(Notification).where(Notification.user_id == seller.id)
    notifs_seller = (await session.execute(stmt)).scalars().all()
    assert len(notifs_seller) == 0

    stmt = select(Notification).where(Notification.user_id == buyer.id)
    notifs_buyer = (await session.execute(stmt)).scalars().all()
    assert len(notifs_buyer) == 0

@pytest.mark.anyio
async def test_notify_manual_test_required_service(session: AsyncSession, create_user):
    admin1 = await create_user("adm1@example.com", role=UserRole.admin.value, is_superuser=True)
    admin2 = await create_user("adm2@example.com", role=UserRole.admin.value, is_superuser=True)
    buyer = await create_user("buyer2@example.com", role=UserRole.buyer.value)

    class MockSubmission:
        id = None

    await notify_manual_test_required(session, MockSubmission(), "Student Test")

    stmt = select(Notification).where(Notification.user_id == admin1.id)
    assert len((await session.execute(stmt)).scalars().all()) == 1

    stmt = select(Notification).where(Notification.user_id == admin2.id)
    assert len((await session.execute(stmt)).scalars().all()) == 1

    stmt = select(Notification).where(Notification.user_id == buyer.id)
    assert len((await session.execute(stmt)).scalars().all()) == 0
