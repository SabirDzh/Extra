import uuid

import pytest
from core.models.block import Block, BlockType
from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.anyio

# --- Course Creation Tests ---


async def test_create_course_admin_success(
    client: AsyncClient, superuser_token_headers
):
    response = await client.post(
        "/api/v1/courses/",
        json={"title": "New Course", "description": "Desc", "is_published": True},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Course"
    assert "id" in data


async def test_create_course_user_forbidden(
    client: AsyncClient, normal_user_token_headers
):
    response = await client.post(
        "/api/v1/courses/",
        json={"title": "Hacker Course", "description": "Desc"},
    )
    assert response.status_code == 403


async def test_create_course_unauth_forbidden(client: AsyncClient):
    response = await client.post(
        "/api/v1/courses/",
        json={"title": "Anon Course"},
    )
    assert response.status_code == 401


async def test_create_course_validation_error(
    client: AsyncClient, superuser_token_headers
):
    # Title too long (>256)
    long_title = "a" * 300
    response = await client.post(
        "/api/v1/courses/",
        json={"title": long_title},
    )
    assert response.status_code == 422


async def test_create_course_empty_payload(
    client: AsyncClient, superuser_token_headers
):
    response = await client.post(
        "/api/v1/courses/",
        json={},
    )
    assert response.status_code == 422


async def test_create_course_max_length_description(
    client: AsyncClient, superuser_token_headers
):
    desc = "a" * 1024
    response = await client.post(
        "/api/v1/courses/",
        json={"title": "Max Desc", "description": desc},
    )
    assert response.status_code == 201


async def test_create_course_special_chars(
    client: AsyncClient, superuser_token_headers
):
    response = await client.post(
        "/api/v1/courses/",
        json={"title": "Course 🚀 ✨", "description": "Special chars & symbols"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Course 🚀 ✨"


# --- List Courses Tests ---


async def test_list_courses_empty(client: AsyncClient):
    response = await client.get("/api/v1/courses/")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_courses_public(
    client: AsyncClient, session: AsyncSession, create_user
):
    # Create published course manually or via admin
    user = await create_user("admin@list.com", is_superuser=True)
    c1 = Course(title="Public Course", is_published=True, created_by=user.id)
    session.add(c1)
    await session.commit()

    response = await client.get("/api/v1/courses/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Public Course"


async def test_list_courses_pagination(
    client: AsyncClient, session: AsyncSession, create_user
):

    user = await create_user("admin@page.com", is_superuser=True)

    for i in range(5):
        session.add(Course(title=f"C{i}", is_published=True, created_by=user.id))

        await session.commit()

    response = await client.get("/api/v1/courses/?limit=2&offset=0")

    assert response.status_code == 200

    assert len(response.json()) == 2

    response = await client.get("/api/v1/courses/?limit=2&offset=2")

    assert len(response.json()) == 2

    response = await client.get("/api/v1/courses/?limit=2&offset=4")

    assert len(response.json()) == 1


async def test_list_courses_filter_published(
    client: AsyncClient, session: AsyncSession, create_user
):

    user = await create_user("admin@hidden.com", is_superuser=True)

    c1 = Course(title="Hidden", is_published=False, created_by=user.id)

    session.add(c1)

    await session.commit()

    c2 = Course(title="Visible", is_published=True, created_by=user.id)

    session.add(c2)

    await session.commit()

    response = await client.get("/api/v1/courses/")

    data = response.json()

    assert len(data) == 1

    assert data[0]["title"] == "Visible"


# --- Get Course Tests ---


async def test_get_course_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("creator@get.com", is_superuser=True)
    c = Course(title="Get Me", is_published=True, created_by=user.id)
    session.add(c)
    await session.commit()

    response = await client.get(f"/api/v1/courses/{c.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(c.id)


async def test_get_course_not_found(client: AsyncClient):
    response = await client.get(f"/api/v1/courses/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_get_course_invalid_uuid(client: AsyncClient):
    response = await client.get("/api/v1/courses/not-a-uuid")
    assert response.status_code == 422  # Validation error by FastAPI


# --- Update Course Tests ---


async def test_update_course_admin_success(
    client: AsyncClient, session: AsyncSession, superuser_token_headers, create_user
):
    # We need to know the ID, create one first
    # Using the client from superuser_token_headers which is logged in as superuser
    # But create_course fixture helper? No, we can just use DB or API
    # Let's use API to be safe with the logged in user
    create_resp = await client.post(
        "/api/v1/courses/", json={"title": "Old", "description": "Old"}
    )
    course_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/courses/{course_id}",
        json={"title": "New", "description": "New Desc"},
    )
    assert response.status_code == 202
    assert response.json()["title"] == "New"


async def test_update_course_user_forbidden(
    client: AsyncClient, session: AsyncSession, normal_user_token_headers, create_user
):
    # Create course as admin first (manual DB)
    admin = await create_user("admin@up.com", is_superuser=True)
    c = Course(title="Admin Course", created_by=admin.id)
    session.add(c)
    await session.commit()

    # Try to update as normal user
    response = await client.put(
        f"/api/v1/courses/{c.id}",
        json={"title": "Hacked"},
    )
    assert response.status_code == 403


async def test_update_course_not_found(client: AsyncClient, superuser_token_headers):
    response = await client.put(
        f"/api/v1/courses/{uuid.uuid4()}",
        json={"title": "Ghost"},
    )
    assert response.status_code == 404


async def test_update_course_validation_error(
    client: AsyncClient, superuser_token_headers
):
    # Create valid course
    create_resp = await client.post("/api/v1/courses/", json={"title": "Valid"})
    cid = create_resp.json()["id"]

    # Update invalid
    response = await client.put(
        f"/api/v1/courses/{cid}",
        json={"title": "a" * 300},
    )
    assert response.status_code == 422


# --- Delete Course Tests ---


async def test_delete_course_admin_success(
    client: AsyncClient, superuser_token_headers
):
    create_resp = await client.post("/api/v1/courses/", json={"title": "To Delete"})
    cid = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/courses/{cid}")
    assert response.status_code == 204

    # Verify gone
    get_resp = await client.get(f"/api/v1/courses/{cid}")
    assert get_resp.status_code == 404


async def test_delete_course_user_forbidden(
    client: AsyncClient, session: AsyncSession, normal_user_token_headers, create_user
):
    admin = await create_user("admin@del.com", is_superuser=True)
    c = Course(title="Safe", created_by=admin.id)
    session.add(c)
    await session.commit()

    response = await client.delete(f"/api/v1/courses/{c.id}")
    assert response.status_code == 403


async def test_delete_course_not_found(client: AsyncClient, superuser_token_headers):
    response = await client.delete(f"/api/v1/courses/{uuid.uuid4()}")
    assert response.status_code == 404


# --- Enrollment Tests ---


async def test_enroll_course_success(
    client: AsyncClient, session: AsyncSession, normal_user_token_headers, create_user
):
    # Create course
    admin = await create_user("admin@enroll.com", is_superuser=True)
    c = Course(title="Enroll Me", created_by=admin.id)
    session.add(c)
    await session.commit()

    response = await client.post(f"/api/v1/courses/{c.id}/enroll")
    assert response.status_code == 201
    assert response.json()["detail"] == "Enrolled successfully"


async def test_enroll_course_already_enrolled(
    client: AsyncClient, session: AsyncSession, normal_user_token_headers, create_user
):
    admin = await create_user("admin@enroll2.com", is_superuser=True)
    c = Course(title="Enroll Twice", created_by=admin.id)
    session.add(c)
    await session.commit()

    # First enroll
    await client.post(f"/api/v1/courses/{c.id}/enroll")
    # Second enroll
    response = await client.post(f"/api/v1/courses/{c.id}/enroll")
    assert response.status_code == 400
    assert "Already enrolled" in response.json()["detail"]


async def test_enroll_course_not_found(client: AsyncClient, normal_user_token_headers):
    response = await client.post(f"/api/v1/courses/{uuid.uuid4()}/enroll")
    assert response.status_code == 404


async def test_enroll_course_unauth(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user("admin@enroll3.com", is_superuser=True)
    c = Course(title="Anon Enroll", created_by=admin.id)
    session.add(c)
    await session.commit()

    response = await client.post(f"/api/v1/courses/{c.id}/enroll")
    assert response.status_code == 401


# --- Progress Tests ---


async def test_get_progress_success(
    client: AsyncClient, session: AsyncSession, normal_user_token_headers, create_user
):
    # Setup: Admin creates course, Normal user enrolls
    admin = await create_user("admin@prog.com", is_superuser=True)
    c = Course(title="Progress Course", created_by=admin.id)
    session.add(c)
    await session.commit()

    # Enroll (client is normal user)
    await client.post(f"/api/v1/courses/{c.id}/enroll")

    response = await client.get(f"/api/v1/courses/{c.id}/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["percent"] == 0.0


async def test_get_progress_not_found(client: AsyncClient, normal_user_token_headers):
    response = await client.get(f"/api/v1/courses/{uuid.uuid4()}/progress")
    assert response.status_code == 404


async def test_get_progress_with_blocks_0_completed(
    client: AsyncClient, session: AsyncSession, normal_user_token_headers, create_user
):

    admin = await create_user("admin@blocks.com", is_superuser=True)

    c = Course(title="Blocked Course", created_by=admin.id)

    session.add(c)

    await session.commit()

    # Add blocks

    b1 = Block(course_id=c.id, title="B1", block_type=BlockType.lesson)

    session.add(b1)

    await session.commit()

    b2 = Block(course_id=c.id, title="B2", block_type=BlockType.lesson)

    session.add(b2)

    await session.commit()

    # Enroll

    await client.post(f"/api/v1/courses/{c.id}/enroll")

    response = await client.get(f"/api/v1/courses/{c.id}/progress")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2

    assert data["completed"] == 0

    assert data["percent"] == 0.0


async def test_get_progress_with_blocks_partial_completed(
    client: AsyncClient, session: AsyncSession, normal_user_token_headers, create_user
):

    # We need to know the USER ID of the 'normal_user_token_headers' user.

    # The fixture creates "normal@example.com". We can query it.

    stmt = "SELECT id FROM users WHERE email = 'normal@example.com'"

    # But direct SQL might depend on driver.

    # Better: reuse logic to find user.

    # Or just use the fact that client is logged in.

    # 1. Create Course & Blocks

    admin = await create_user("admin@partial.com", is_superuser=True)

    c = Course(title="Partial Course", created_by=admin.id)

    session.add(c)

    await session.commit()

    b1 = Block(course_id=c.id, title="B1", block_type=BlockType.lesson)

    session.add(b1)

    await session.commit()

    b2 = Block(course_id=c.id, title="B2", block_type=BlockType.lesson)

    session.add(b2)

    await session.commit()

    # 2. Enroll

    await client.post(f"/api/v1/courses/{c.id}/enroll")

    # 3. Manually mark block 1 as completed for this user
    # Find user
    from core.models.user import User
    from sqlalchemy import select

    # The normal user was created in 'normal_user_token_headers' fixture with email 'normal@example.com'
    user_res = await session.execute(
        select(User).where(User.email == "normal@example.com")
    )
    user = user_res.scalar_one()

    progress = UserBlockProgress(user_id=user.id, block_id=b1.id, is_completed=True)
    session.add(progress)
    await session.commit()

    # 4. Check progress
    response = await client.get(f"/api/v1/courses/{c.id}/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["completed"] == 1
    assert data["percent"] == 50.0
