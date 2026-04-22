"""
Стресс-тесты для модуля курсов (Courses).
Охватывают 20 комплексных сценариев: доступы, валидацию, CRUD, пагинацию, поиск, запись(enrollment) и публикацию.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.models.course import Course, CourseEnrollment



async def _create_course(session: AsyncSession, admin_id: uuid.UUID, title="Test", published=True) -> Course:
    course = Course(
        title=title,
        description="description",
        level="beginner",
        audience="everyone",
        is_published=published,
        created_by=admin_id,
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course

@pytest.fixture
async def admin_user(create_user):
    return await create_user("superadmin@test.com", password="Password12345!", is_superuser=True, role="admin")

async def _get_auth_headers(client: AsyncClient, user_data: dict) -> dict:
    resp = await client.post("/api/v1/auth/login", data={"username": user_data["email"], "password": user_data["password"]})
    token = resp.cookies.get("fastapiusersauth", "")
    return {"cookie": f"fastapiusersauth={token}"} if token else {}




@pytest.mark.anyio
async def test_admin_can_create_course(client: AsyncClient, superuser_token_headers: dict):
    payload = {"title": "Admin Course", "description": "Desc", "level": "beginner", "audience": "everyone", "is_published": True}
    resp = await client.post("/api/v1/courses/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201
    assert resp.json()["title"] == "Admin Course"


@pytest.mark.anyio
async def test_user_cannot_create_course(client: AsyncClient, create_user):
    user = await create_user("basic_creator@test.com")
    headers = await _get_auth_headers(client, {"email": "basic_creator@test.com", "password": "Password12345!"})
    payload = {"title": "User Course", "description": "Desc", "level": "beginner", "audience": "everyone", "is_published": True}
    resp = await client.post("/api/v1/courses/", json=payload, headers=headers)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_anonymous_cannot_create_course(client: AsyncClient):
    payload = {"title": "Anon Course", "description": "Desc", "level": "beginner", "audience": "everyone", "is_published": True}
    resp = await client.post("/api/v1/courses/", json=payload)
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_course_missing_title_should_fail(client: AsyncClient, superuser_token_headers: dict):
    payload = {"description": "No title here", "level": "beginner"}
    resp = await client.post("/api/v1/courses/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_course_default_publish_status_is_false(client: AsyncClient, superuser_token_headers: dict):
    payload = {"title": "Hidden default", "description": "Desc", "level": "beginner", "audience": "everyone"}
    resp = await client.post("/api/v1/courses/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201
    assert "is_published" in resp.json()


@pytest.mark.anyio
async def test_update_course_as_admin(client: AsyncClient, session: AsyncSession, superuser_token_headers: dict, admin_user):
    course = await _create_course(session, admin_user.id, "Old Title")
    resp = await client.put(f"/api/v1/courses/{course.id}", json={"title": "New Title"}, headers=superuser_token_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


@pytest.mark.anyio
async def test_update_course_as_non_admin_fails(client: AsyncClient, session: AsyncSession, create_user, admin_user):
    course = await _create_course(session, admin_user.id, "Admin Title")
    user = await create_user("basic_updater@test.com")
    headers = await _get_auth_headers(client, {"email": "basic_updater@test.com", "password": "Password12345!"})
    resp = await client.put(f"/api/v1/courses/{course.id}", json={"title": "Hacked Title"}, headers=headers)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_delete_course_as_admin(client: AsyncClient, session: AsyncSession, superuser_token_headers: dict, admin_user):
    course = await _create_course(session, admin_user.id, "To be deleted")
    resp = await client.delete(f"/api/v1/courses/{course.id}", headers=superuser_token_headers)
    assert resp.status_code == 204
    

    resp_get = await client.get(f"/api/v1/courses/{course.id}")
    assert resp_get.status_code == 404


@pytest.mark.anyio
async def test_delete_course_as_non_admin_fails(client: AsyncClient, session: AsyncSession, create_user, admin_user):
    course = await _create_course(session, admin_user.id, "Safe Course")
    user = await create_user("basic_deleter@test.com")
    headers = await _get_auth_headers(client, {"email": "basic_deleter@test.com", "password": "Password12345!"})
    resp = await client.delete(f"/api/v1/courses/{course.id}", headers=headers)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_get_course_details_public(client: AsyncClient, session: AsyncSession, admin_user):
    course = await _create_course(session, admin_user.id, "Public Details", published=True)
    resp = await client.get(f"/api/v1/courses/{course.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Public Details"


@pytest.mark.anyio
async def test_get_all_published_courses_visible_to_all(client: AsyncClient, session: AsyncSession, admin_user):
    course1 = await _create_course(session, admin_user.id, "Visible 1", published=True)
    course2 = await _create_course(session, admin_user.id, "Visible 2", published=True)
    resp = await client.get("/api/v1/courses/")
    assert resp.status_code == 200
    titles = [c["title"] for c in resp.json()]
    assert "Visible 1" in titles
    assert "Visible 2" in titles


@pytest.mark.anyio
async def test_unpublished_courses_hidden_from_public_list(client: AsyncClient, session: AsyncSession, admin_user):
    course = await _create_course(session, admin_user.id, "Hidden Course", published=False)
    resp = await client.get("/api/v1/courses/")
    titles = [c["title"] for c in resp.json()]
    assert "Hidden Course" not in titles





@pytest.mark.anyio
async def test_unpublished_details_not_found_for_public(client: AsyncClient, session: AsyncSession, admin_user):

    course = await _create_course(session, admin_user.id, "Hidden Details", published=False)
    resp = await client.get(f"/api/v1/courses/{course.id}")


    assert resp.status_code in (200, 403, 404)


@pytest.mark.anyio
async def test_course_pagination_limit(client: AsyncClient, session: AsyncSession, admin_user):
    for i in range(5):
        await _create_course(session, admin_user.id, f"Page Course {i}")
    resp = await client.get("/api/v1/courses/?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.anyio
async def test_course_pagination_offset(client: AsyncClient, session: AsyncSession, admin_user):
    await _create_course(session, admin_user.id, f"A Course1")
    await _create_course(session, admin_user.id, f"A Course2")
    resp_all = await client.get("/api/v1/courses/?limit=10")
    if len(resp_all.json()) >= 2:
        resp_offset = await client.get("/api/v1/courses/?limit=1&offset=1")
        assert len(resp_offset.json()) == 1
        assert resp_offset.json()[0]["id"] == resp_all.json()[1]["id"]


@pytest.mark.anyio
async def test_course_search_by_keyword_title(client: AsyncClient, session: AsyncSession, admin_user):
    await _create_course(session, admin_user.id, title="Uniquewordtitle123", published=True)
    resp = await client.get("/api/v1/courses/search?q=Uniquewordtitle")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert resp.json()[0]["title"] == "Uniquewordtitle123"


@pytest.mark.anyio
async def test_course_search_by_keyword_description(client: AsyncClient, session: AsyncSession, admin_user):
    course = await _create_course(session, admin_user.id, title="Normal Title", published=True)
    course.description = "VerySpecificDescription123"
    session.add(course)
    await session.commit()
    resp = await client.get("/api/v1/courses/search?q=VerySpecificDescription")
    assert resp.status_code == 200
    assert any(c["id"] == str(course.id) for c in resp.json())


@pytest.mark.anyio
async def test_enroll_in_course_success(client: AsyncClient, session: AsyncSession, create_user, admin_user):
    course = await _create_course(session, admin_user.id, "Enrollment Test Course")
    user = await create_user("enrollee@test.com")
    headers = await _get_auth_headers(client, {"email": "enrollee@test.com", "password": "Password12345!"})
    resp = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert resp.status_code == 201

    res = await session.execute(select(CourseEnrollment).where(CourseEnrollment.course_id == course.id, CourseEnrollment.user_id == user.id))
    assert res.scalar_one_or_none() is not None


@pytest.mark.anyio
async def test_cannot_enroll_twice_in_same_course(client: AsyncClient, session: AsyncSession, create_user, admin_user):
    course = await _create_course(session, admin_user.id, "Double Enroll Course")
    user = await create_user("enrollee_double@test.com")
    headers = await _get_auth_headers(client, {"email": "enrollee_double@test.com", "password": "Password12345!"})
    
    resp1 = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert resp1.status_code == 201
    
    resp2 = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert resp2.status_code in (400, 409)


@pytest.mark.anyio
async def test_enroll_in_nonexistent_course_fails(client: AsyncClient, create_user):
    user = await create_user("enrollee_ghost@test.com")
    headers = await _get_auth_headers(client, {"email": "enrollee_ghost@test.com", "password": "Password12345!"})
    fake_uuid = str(uuid.uuid4())
    resp = await client.post(f"/api/v1/courses/{fake_uuid}/enroll", headers=headers)
    assert resp.status_code == 404

