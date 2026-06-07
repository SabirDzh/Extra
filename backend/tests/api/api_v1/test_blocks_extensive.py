"""
Стресс-тесты для модуля блоков (Blocks).
Охватывают 20 комплексных сценариев: создание разных типов блоков, валидацию Pydantic, безопасность и поведение списков.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course
from core.models.block import Block, BlockType



@pytest.fixture
async def admin_user(create_user):
    return await create_user("block_admin@test.com", password="Password12345!", is_superuser=True, role="admin")

async def _get_auth_headers(client: AsyncClient, user_data: dict) -> dict:
    resp = await client.post("/api/v1/auth/login", data={"username": user_data["email"], "password": user_data["password"]})
    token = resp.cookies.get("fastapiusersauth", "")
    return {"cookie": f"fastapiusersauth={token}"} if token else {}

async def _create_course(session: AsyncSession, admin_id: uuid.UUID) -> Course:
    course = Course(
        title=f"Block Test Course {uuid.uuid4().hex[:4]}",
        description="description",
        level="beginner",
        audience="everyone",
        is_published=True,
        created_by=admin_id,
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course

async def _create_block(session: AsyncSession, course_id: uuid.UUID, block_type=BlockType.lesson, title="A block") -> Block:
    block = Block(
        course_id=course_id,
        title=title,
        block_type=block_type,
        text_content="some content" if block_type == BlockType.lesson else None,
        order_index=1
    )
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block




@pytest.mark.anyio
async def test_admin_create_lesson_block(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    payload = {"title": "Lesson 1", "block_type": "lesson", "text_content": "Text", "order_index": 1}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201
    assert resp.json()["title"] == course.title


@pytest.mark.anyio
async def test_admin_create_test_block(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    payload = {"title": "Test 1", "block_type": "auto_test", "order_index": 1}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201
    assert resp.json()["block_type"] == "auto_test"


@pytest.mark.anyio
async def test_create_test_block_strips_text_content(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    payload = {"title": "Test STRIP", "block_type": "auto_test", "text_content": "Should be gone", "order_index": 1}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201
    assert resp.json()["text_content"] is None


@pytest.mark.anyio
async def test_user_cannot_create_block(client: AsyncClient, session: AsyncSession, admin_user, create_user):
    course = await _create_course(session, admin_user.id)
    user = await create_user("hacker@test.com")
    headers = await _get_auth_headers(client, {"email": "hacker@test.com", "password": "Password12345!"})
    payload = {"title": "Hack block", "block_type": "lesson", "order_index": 1}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload, headers=headers)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_anonymous_cannot_create_block(client: AsyncClient, session: AsyncSession, admin_user):
    course = await _create_course(session, admin_user.id)
    payload = {"title": "Anon block", "block_type": "lesson", "order_index": 1}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload)
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_block_nonexistent_course(client: AsyncClient, superuser_token_headers):
    fake_url = f"/api/v1/courses/{uuid.uuid4()}/blocks/"
    payload = {"title": "Orphan", "block_type": "lesson", "text_content": "Required", "order_index": 1}
    resp = await client.post(fake_url, json=payload, headers=superuser_token_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_create_block_missing_title(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    payload = {"block_type": "lesson", "order_index": 1}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_block_invalid_type(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    payload = {"title": "Invalid Type", "block_type": "something_else", "order_index": 1}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_block_str_coercion(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    payload = {"title": "12345", "block_type": "lesson", "text_content": "Content"}
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201
    assert resp.json()["title"] == course.title


@pytest.mark.anyio
async def test_admin_update_block(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    block = await _create_block(session, course.id, title="Old")
    payload = {"title": "New", "text_content": "updated content"}
    resp = await client.patch(f"/api/v1/courses/{course.id}/blocks/{block.id}", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"
    assert resp.json()["text_content"] == "updated content"
    await session.refresh(course)
    assert course.title == "New"


@pytest.mark.anyio
async def test_user_update_block_fails(client: AsyncClient, session: AsyncSession, admin_user, create_user):
    course = await _create_course(session, admin_user.id)
    block = await _create_block(session, course.id, title="Safe")
    user = await create_user("hacker2@test.com")
    headers = await _get_auth_headers(client, {"email": "hacker2@test.com", "password": "Password12345!"})
    resp = await client.patch(f"/api/v1/courses/{course.id}/blocks/{block.id}", json={"title": "Hacked"}, headers=headers)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_update_nonexistent_block(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    resp = await client.patch(f"/api/v1/courses/{course.id}/blocks/{uuid.uuid4()}", json={"title": "Ghost"}, headers=superuser_token_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_admin_delete_block(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    block = await _create_block(session, course.id)
    resp = await client.delete(f"/api/v1/courses/{course.id}/blocks/{block.id}", headers=superuser_token_headers)
    assert resp.status_code == 204
    

    resp_get = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}")
    assert resp_get.status_code == 404


@pytest.mark.anyio
async def test_user_delete_block_fails(client: AsyncClient, session: AsyncSession, admin_user, create_user):
    course = await _create_course(session, admin_user.id)
    block = await _create_block(session, course.id)
    user = await create_user("hacker3@test.com")
    headers = await _get_auth_headers(client, {"email": "hacker3@test.com", "password": "Password12345!"})
    resp = await client.delete(f"/api/v1/courses/{course.id}/blocks/{block.id}", headers=headers)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_delete_nonexistent_block(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    resp = await client.delete(f"/api/v1/courses/{course.id}/blocks/{uuid.uuid4()}", headers=superuser_token_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_blocks_for_course(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    await _create_block(session, course.id, title="1")
    await _create_block(session, course.id, title="2")
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/", headers=superuser_token_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["blocks"]) == 2

    assert "current_block_id" in data
    assert "next_block_id" in data["blocks"][0]
    

    assert data["blocks"][0]["order_index"] == 1
    

    assert data["all_stages"] == 1

    assert data["blocks"][0]["stage"] == 1
    assert data["blocks"][1]["stage"] == 1
    

    assert data["all_blocks"] == 2
    assert "all_blocks" not in data["blocks"][0]


@pytest.mark.anyio
async def test_get_blocks_nonexistent_course(client: AsyncClient, superuser_token_headers):
    resp = await client.get(f"/api/v1/courses/{uuid.uuid4()}/blocks/", headers=superuser_token_headers)

    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_block_details(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    course = await _create_course(session, admin_user.id)
    block = await _create_block(session, course.id, title="Specific")
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}", headers=superuser_token_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Specific"


@pytest.mark.anyio
async def test_auth_user_complete_block_manual(client: AsyncClient, session: AsyncSession, admin_user, create_user):
    course = await _create_course(session, admin_user.id)
    block = await _create_block(session, course.id, block_type=BlockType.lesson)
    user = await create_user("completer@test.com")
    headers = await _get_auth_headers(client, {"email": "completer@test.com", "password": "Password12345!"})

    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/{block.id}/complete", headers=headers)
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_anon_user_complete_block_fails(client: AsyncClient, session: AsyncSession, admin_user):
    course = await _create_course(session, admin_user.id)
    block = await _create_block(session, course.id)
    resp = await client.post(f"/api/v1/courses/{course.id}/blocks/{block.id}/complete")
    assert resp.status_code == 401
