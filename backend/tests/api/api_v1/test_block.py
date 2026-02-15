import uuid

import pytest
from core.models.block import Block, BlockType
from core.models.course import Course
from core.models.progress import UserBlockProgress
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.anyio

# --- Helpers ---


async def create_course_db(session, user_id, title="Test Course"):
    c = Course(title=title, created_by=user_id, is_published=True)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def create_block_db(
    session, course_id, title="B1", btype=BlockType.lesson, text="Content"
):
    b = Block(course_id=course_id, title=title, block_type=btype, text_content=text)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b


# --- Create Block Tests ---


async def test_create_block_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@block.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)

    # Authenticate as admin
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@block.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={
            "title": "New Lesson",
            "block_type": "lesson",
            "text_content": "Some text",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Lesson"
    assert data["course_id"] == str(c.id)


async def test_create_block_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user("admin@b.com", is_superuser=True, role="administrator")
    user = await create_user("user@b.com", is_superuser=False)
    c = await create_course_db(session, admin.id)

    # Login as user
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@b.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={"title": "Hacked", "block_type": "lesson", "text_content": "x"},
    )
    assert response.status_code == 403


async def test_create_block_unauth(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user("admin@un.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, admin.id)

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={"title": "Anon", "block_type": "lesson", "text_content": "x"},
    )
    assert response.status_code == 401


async def test_create_block_course_not_found(client: AsyncClient, create_user):
    await create_user("admin@nf.com", is_superuser=True, role="administrator")
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@nf.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{uuid.uuid4()}/blocks/",
        json={"title": "Ghost", "block_type": "lesson", "text_content": "x"},
    )
    assert response.status_code == 404


async def test_create_lesson_block_no_content(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@val.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@val.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={"title": "Empty", "block_type": "lesson"},  # Missing content
    )
    assert response.status_code == 422
    assert "Lesson block must have text_content or video_url" in response.text


async def test_create_lesson_block_text_only(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@txt.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@txt.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={"title": "Text", "block_type": "lesson", "text_content": "Ok"},
    )
    assert response.status_code == 201


async def test_create_lesson_block_video_url_only(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@vid.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@vid.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={"title": "Vid", "block_type": "lesson", "video_url": "http://vid.com"},
    )
    assert response.status_code == 201


async def test_create_test_block_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@testb.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@testb.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={"title": "Quiz", "block_type": "auto_test"},
    )
    assert response.status_code == 201


async def test_create_block_invalid_type(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@inv.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@inv.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/",
        json={"title": "Bad", "block_type": "magic", "text_content": "x"},
    )
    assert response.status_code == 422


# --- List Blocks Tests ---


async def test_list_blocks_empty(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@list.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)

    response = await client.get(f"/api/v1/courses/{c.id}/blocks/")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_blocks_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@list2.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b1 = await create_block_db(session, c.id, "B1")

    response = await client.get(f"/api/v1/courses/{c.id}/blocks/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(b1.id)


async def test_list_blocks_ordering(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@ord.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)

    # Create unordered via DB, but assign index
    b2 = Block(
        course_id=c.id,
        title="B2",
        block_type=BlockType.lesson,
        text_content="x",
        order_index=2,
    )
    session.add(b2)
    await session.commit()
    b1 = Block(
        course_id=c.id,
        title="B1",
        block_type=BlockType.lesson,
        text_content="x",
        order_index=1,
    )
    session.add(b1)
    await session.commit()

    response = await client.get(f"/api/v1/courses/{c.id}/blocks/")
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "B1"
    assert data[1]["title"] == "B2"


async def test_list_blocks_course_not_found(client: AsyncClient):
    response = await client.get(f"/api/v1/courses/{uuid.uuid4()}/blocks/")
    assert response.status_code == 404


# --- Get Block Tests ---


async def test_get_block_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@get.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)

    response = await client.get(f"/api/v1/courses/{c.id}/blocks/{b.id}")
    assert response.status_code == 200
    assert response.json()["title"] == "B1"


async def test_get_block_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@gnf.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)

    response = await client.get(f"/api/v1/courses/{c.id}/blocks/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_get_block_course_mismatch(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@mis.com", is_superuser=True, role="administrator")
    c1 = await create_course_db(session, user.id, "C1")
    c2 = await create_course_db(session, user.id, "C2")
    b = await create_block_db(session, c1.id)

    # Try accessing block b (which is in C1) via C2 URL
    response = await client.get(f"/api/v1/courses/{c2.id}/blocks/{b.id}")
    assert response.status_code == 404  # Should be 404 based on _get_block_or_404 logic


# --- Update Block Tests ---


async def test_update_block_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@up.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@up.com", "password": "Password12345!"},
    )

    response = await client.put(
        f"/api/v1/courses/{c.id}/blocks/{b.id}",
        json={"title": "Updated", "text_content": "New"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


async def test_update_block_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user("admin@fup.com", is_superuser=True, role="administrator")
    user = await create_user("user@fup.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@fup.com", "password": "Password12345!"},
    )

    response = await client.put(
        f"/api/v1/courses/{c.id}/blocks/{b.id}", json={"title": "Hacked"}
    )
    assert response.status_code == 403


async def test_update_block_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@upnf.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@upnf.com", "password": "Password12345!"},
    )

    response = await client.put(
        f"/api/v1/courses/{c.id}/blocks/{uuid.uuid4()}", json={"title": "Ghost"}
    )
    assert response.status_code == 404


async def test_update_block_course_mismatch(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@upmis.com", is_superuser=True, role="administrator")
    c1 = await create_course_db(session, user.id)
    c2 = await create_course_db(session, user.id)
    b = await create_block_db(session, c1.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@upmis.com", "password": "Password12345!"},
    )

    response = await client.put(
        f"/api/v1/courses/{c2.id}/blocks/{b.id}", json={"title": "Wrong Course"}
    )
    assert response.status_code == 404


# --- Delete Block Tests ---


async def test_delete_block_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@del.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@del.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/courses/{c.id}/blocks/{b.id}")
    assert response.status_code == 204

    # Verify gone
    resp = await client.get(f"/api/v1/courses/{c.id}/blocks/{b.id}")
    assert resp.status_code == 404


async def test_delete_block_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user("admin@del2.com", is_superuser=True, role="administrator")
    user = await create_user("user@del2.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@del2.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/courses/{c.id}/blocks/{b.id}")
    assert response.status_code == 403


async def test_delete_block_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@del3.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@del3.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/courses/{c.id}/blocks/{uuid.uuid4()}")
    assert response.status_code == 404


# --- Completion Tests ---


async def test_mark_complete_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("user@comp.com", is_superuser=False)
    admin = await create_user("admin@comp.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@comp.com", "password": "Password12345!"},
    )

    response = await client.post(f"/api/v1/courses/{c.id}/blocks/{b.id}/complete")
    assert response.status_code == 201

    # Verify DB
    # We can check via course progress
    await client.post(
        f"/api/v1/courses/{c.id}/enroll"
    )  # Should enroll first usually? Logic doesn't check enrollment but it's cleaner.
    # Actually mark_complete logic just checks UserBlockProgress.
    # Enroll logic is separate.

    # Check progress
    prog_resp = await client.get(f"/api/v1/courses/{c.id}/progress")
    assert prog_resp.json()["completed"] == 1


async def test_mark_complete_already_completed(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("user@comp2.com", is_superuser=False)
    admin = await create_user(
        "admin@comp2.com", is_superuser=True, role="administrator"
    )
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@comp2.com", "password": "Password12345!"},
    )

    await client.post(f"/api/v1/courses/{c.id}/blocks/{b.id}/complete")
    response = await client.post(f"/api/v1/courses/{c.id}/blocks/{b.id}/complete")
    assert response.status_code == 201  # Idempotent


async def test_mark_complete_block_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("user@comp3.com", is_superuser=False)
    admin = await create_user(
        "admin@comp3.com", is_superuser=True, role="administrator"
    )
    c = await create_course_db(session, admin.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@comp3.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/{uuid.uuid4()}/complete"
    )
    assert response.status_code == 404


async def test_mark_complete_unauth(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@comp4.com", is_superuser=True, role="administrator"
    )
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    response = await client.post(f"/api/v1/courses/{c.id}/blocks/{b.id}/complete")
    assert response.status_code == 401


# --- Upload Video Tests ---


async def test_upload_video_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@upl.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@upl.com", "password": "Password12345!"},
    )

    files = {"file": ("test.mp4", b"video content", "video/mp4")}
    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/{b.id}/upload-video", files=files
    )
    assert response.status_code == 201
    assert response.json()["video_url"] is not None
    # Cleanup file? Tests use in-memory mostly, but os.makedirs creates real dirs.
    # Ideally should mock settings.UPLOAD_DIR or cleanup.
    # For now, it will create files in `uploads/videos` relative to CWD.


async def test_upload_video_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("user@upl.com", is_superuser=False)
    admin = await create_user("admin@upl2.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@upl.com", "password": "Password12345!"},
    )

    files = {"file": ("test.mp4", b"x", "video/mp4")}
    response = await client.post(
        f"/api/v1/courses/{c.id}/blocks/{b.id}/upload-video", files=files
    )
    assert response.status_code == 403


async def test_delete_block_course_mismatch(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user(
        "admin@delmis.com", is_superuser=True, role="administrator"
    )
    c1 = await create_course_db(session, user.id, "C1")
    c2 = await create_course_db(session, user.id, "C2")
    b = await create_block_db(session, c1.id)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@delmis.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/courses/{c2.id}/blocks/{b.id}")
    assert response.status_code == 404
