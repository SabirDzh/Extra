import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseAudience, CourseLevel
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType
from core.schemas.course import CourseStatus

@pytest.fixture
async def patch_setup(session: AsyncSession, create_user):
    admin = await create_user("admin_patch@test.com", is_superuser=True, role="administrator")
    course = Course(title="Patch Course", created_by=admin.id, is_published=True, level=CourseLevel.beginner)
    session.add(course)
    await session.flush()
    
    block = Block(course_id=course.id, title="Patch Block", block_type=BlockType.lesson, order_index=0)
    session.add(block)
    await session.flush()
    
    question = Question(block_id=block.id, text="Patch Question", question_type=QuestionType.single_choice)
    session.add(question)
    await session.flush()
    
    await session.commit()
    return admin, course, block, question

@pytest.mark.anyio
async def test_patch_course_title_only(client: AsyncClient, patch_setup):
    """1. Course Partial Update (Title): Verify only title changes."""
    admin, course, _, _ = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    new_title = "Totally New Title"
    resp = await client.patch(f"/api/v1/courses/{course.id}", json={"title": new_title}, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == new_title
    assert data["level"] == CourseLevel.beginner.value

@pytest.mark.anyio
async def test_patch_course_visibility_only(client: AsyncClient, patch_setup):
    """2. Course Partial Update (is_published): Verify only visibility changes."""
    admin, course, _, _ = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    resp = await client.patch(f"/api/v1/courses/{course.id}", json={"is_published": False}, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["is_published"] is False
    assert resp.json()["title"] == "Patch Course"

@pytest.mark.anyio
async def test_patch_block_title(client: AsyncClient, patch_setup):
    """3. Block Partial Update: Verify partial update for blocks."""
    admin, course, block, _ = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    new_title = "Updated Block Name"
    resp = await client.patch(f"/api/v1/courses/{course.id}/blocks/{block.id}", json={"title": new_title}, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["title"] == new_title

@pytest.mark.anyio
async def test_patch_question_text(client: AsyncClient, patch_setup):
    """4. Question Partial Update: Verify partial update for question text."""
    admin, _, _, question = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    new_text = "What is the meaning of life?"
    resp = await client.patch(f"/api/v1/tests/questions/{question.id}", json={"text": new_text}, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["text"] == new_text

@pytest.mark.anyio
async def test_patch_multiple_fields(client: AsyncClient, patch_setup):
    """5. Multiple Fields Update: Verify updating several fields at once."""
    admin, course, _, _ = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    payload = {"title": "Multi Patch", "level": CourseLevel.advanced.value, "audience": CourseAudience.everyone.value}
    resp = await client.patch(f"/api/v1/courses/{course.id}", json=payload, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Multi Patch"
    assert data["level"] == CourseLevel.advanced.value
    assert data["audience"] == CourseAudience.everyone.value

@pytest.mark.anyio
async def test_patch_empty_body(client: AsyncClient, patch_setup):
    """6. No Change Update: Verify sending empty body changes nothing."""
    admin, course, _, _ = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    resp = await client.patch(f"/api/v1/courses/{course.id}", json={}, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Patch Course"

@pytest.mark.anyio
async def test_patch_validation_unique_title(client: AsyncClient, patch_setup, session: AsyncSession):
    """7. Validation: Unique Title: Verify 400 when patching to a taken title."""
    admin, course, _, _ = patch_setup
    other = Course(title="Existing Title", created_by=admin.id)
    session.add(other)
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    resp = await client.patch(f"/api/v1/courses/{course.id}", json={"title": "Existing Title"}, cookies=cookies)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]

@pytest.mark.anyio
async def test_patch_permissions_admin_only(client: AsyncClient, patch_setup, create_user):
    """8. Permissions: Admin Only: Verify 403 for non-admins."""
    _, course, _, _ = patch_setup
    user = await create_user("regular_user@test.com")
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    resp = await client.patch(f"/api/v1/courses/{course.id}", json={"title": "Hack"}, cookies=cookies)
    assert resp.status_code in [401, 403]

@pytest.mark.anyio
async def test_patch_error_not_found(client: AsyncClient, patch_setup):
    """9. Error: Not Found: Verify 404 for non-existent resource."""
    admin, _, _, _ = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    fake_id = uuid.uuid4()
    resp = await client.patch(f"/api/v1/courses/{fake_id}", json={"title": "Ghost"}, cookies=cookies)
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_patch_data_integrity(client: AsyncClient, patch_setup):
    """10. Data Integrity: Verify that omitted fields are not cleared."""
    admin, course, _, _ = patch_setup
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    

    original_desc = "Some description"
    await client.patch(f"/api/v1/courses/{course.id}", json={"description": original_desc}, cookies=cookies)
    
    resp = await client.patch(f"/api/v1/courses/{course.id}", json={"title": "Integrity Check"}, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["description"] == original_desc
