"""
Стресс-тесты для модуля тестирования (Tests & Questions & Submissions).
Охватывают 20 комплексных сценариев: валидация авто/ручных проверок, защита правильных ответов, права на оценивание.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission



@pytest.fixture
async def admin_user(create_user):
    return await create_user("test_admin@test.com", password="Password12345!", is_superuser=True, role="administrator")

async def _get_auth_headers(client: AsyncClient, user_data: dict) -> dict:
    resp = await client.post("/api/v1/auth/login", data={"username": user_data["email"], "password": user_data["password"]})
    token = resp.cookies.get("auth_user", "")
    return {"cookie": f"auth_user={token}"} if token else {}

async def _create_course_and_block(session: AsyncSession, admin_id: uuid.UUID, block_type=BlockType.auto_test):
    course = Course(title=f"Course {uuid.uuid4().hex[:4]}", created_by=admin_id)
    session.add(course)
    await session.flush()
    block = Block(course_id=course.id, title="Test Block", block_type=block_type, order_index=1, text_content="X" if block_type == BlockType.lesson else None)
    session.add(block)
    await session.commit()
    await session.refresh(course)
    await session.refresh(block)
    return course, block




@pytest.mark.anyio
async def test_admin_create_question_single(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    payload = {
        "text": "What is 2+2?", "question_type": "single_choice", "order_index": 0,
        "options": [{"text": "3", "is_correct": False}, {"text": "4", "is_correct": True}]
    }
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_admin_create_question_multiple(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    payload = {
        "text": "Select primes", "question_type": "multiple_choice", "order_index": 0,
        "options": [{"text": "2", "is_correct": True}, {"text": "4", "is_correct": False}, {"text": "5", "is_correct": True}]
    }
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_create_question_on_lesson_block_fails(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.lesson)
    payload = {"text": "Q?", "question_type": "free_text", "options": []}
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_user_cannot_create_question(client: AsyncClient, session: AsyncSession, admin_user, create_user):
    _, block = await _create_course_and_block(session, admin_user.id)
    user = await create_user("hacker_q@test.com")
    headers = await _get_auth_headers(client, {"email": "hacker_q@test.com", "password": "Password12345!"})
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json={"text": "Q", "question_type": "free_text"}, headers=headers)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_anonymous_cannot_create_question(client: AsyncClient, session: AsyncSession, admin_user):
    _, block = await _create_course_and_block(session, admin_user.id)
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json={"text": "Q", "question_type": "free_text"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_admin_updates_question(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    payload = {"text": "Old", "question_type": "free_text"}
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    q_id = resp.json()["id"]
    resp2 = await client.patch(f"/api/v1/tests/questions/{q_id}", json={"text": "New Text"}, headers=superuser_token_headers)
    assert resp2.status_code == 200
    assert resp2.json()["text"] == "New Text"


@pytest.mark.anyio
async def test_update_question_options_replacement(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    payload = {"text": "Old", "question_type": "single_choice", "options": [{"text": "A", "is_correct": True}]}
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    q_id = resp.json()["id"]
    
    resp2 = await client.patch(f"/api/v1/tests/questions/{q_id}", json={"options": [{"text": "B", "is_correct": False}]}, headers=superuser_token_headers)
    assert resp2.status_code == 200
    opts = resp2.json()["options"]
    assert len(opts) == 1
    assert opts[0]["text"] == "B"


@pytest.mark.anyio
async def test_user_cannot_update_question(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json={"text": "Old", "question_type": "free_text"}, headers=superuser_token_headers)
    q_id = resp.json()["id"]
    
    user = await create_user("hacker_q2@test.com")
    headers = await _get_auth_headers(client, {"email": "hacker_q2@test.com", "password": "Password12345!"})
    resp2 = await client.patch(f"/api/v1/tests/questions/{q_id}", json={"text": "Hacked Text"}, headers=headers)
    assert resp2.status_code in (401, 403)


@pytest.mark.anyio
async def test_admin_delete_question(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json={"text": "Drop me", "question_type": "free_text"}, headers=superuser_token_headers)
    q_id = resp.json()["id"]
    
    resp2 = await client.delete(f"/api/v1/tests/questions/{q_id}", headers=superuser_token_headers)
    assert resp2.status_code == 204


@pytest.mark.anyio
async def test_delete_nonexistent_question(client: AsyncClient, superuser_token_headers):
    resp = await client.delete(f"/api/v1/tests/questions/{uuid.uuid4()}", headers=superuser_token_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_user_list_questions_hides_correct_answers(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    payload = {"text": "Secret", "question_type": "single_choice", "options": [{"text": "A", "is_correct": True}]}
    await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    
    user = await create_user("student@test.com")
    headers = await _get_auth_headers(client, {"email": "student@test.com", "password": "Password12345!"})
    resp = await client.get(f"/api/v1/tests/blocks/{block.id}/questions", headers=headers)
    assert resp.status_code == 200
    assert "is_correct" not in resp.json()[0]["options"][0]


@pytest.mark.anyio
async def test_admin_list_questions_shows_correct_answers(client: AsyncClient, session: AsyncSession, admin_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id)
    payload = {"text": "Secret", "question_type": "single_choice", "options": [{"text": "A", "is_correct": True}]}
    await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    
    resp = await client.get(f"/api/v1/tests/blocks/{block.id}/questions", headers=superuser_token_headers)
    assert resp.status_code == 200
    assert "is_correct" in resp.json()[0]["options"][0]


@pytest.mark.anyio
async def test_submit_auto_test_success(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.auto_test)
    payload = {"text": "Math", "question_type": "single_choice", "options": [{"text": "Right", "is_correct": True}, {"text": "Wrong", "is_correct": False}]}
    q_resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    q_id = q_resp.json()["id"]
    opt_id = [o["id"] for o in q_resp.json()["options"] if o["is_correct"]][0]
    
    headers = await _get_auth_headers(client, {"email": "student@test.com", "password": "Password12345!"})
    user = await create_user("good_student@test.com")
    headers = await _get_auth_headers(client, {"email": "good_student@test.com", "password": "Password12345!"})
    
    sub = {"answers": [{"question_id": q_id, "selected_answer_id": opt_id}]}
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=sub, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["score"] == 1
    assert resp.json()["is_graded"] is True


@pytest.mark.anyio
async def test_submit_auto_test_fail(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.auto_test)
    payload = {"text": "Math", "question_type": "single_choice", "options": [{"text": "Right", "is_correct": True}, {"text": "Wrong", "is_correct": False}]}
    q_resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    q_id = q_resp.json()["id"]
    opt_bad = [o["id"] for o in q_resp.json()["options"] if not o["is_correct"]][0]
    
    user = await create_user("bad_student@test.com")
    headers = await _get_auth_headers(client, {"email": "bad_student@test.com", "password": "Password12345!"})
    
    sub = {"answers": [{"question_id": q_id, "selected_answer_id": opt_bad}]}
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=sub, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["score"] == 0


@pytest.mark.anyio
async def test_submit_manual_test_ungraded(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.manual_test)
    payload = {"text": "Tell me a story", "question_type": "free_text"}
    q_resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    q_id = q_resp.json()["id"]
    
    user = await create_user("story@test.com")
    headers = await _get_auth_headers(client, {"email": "story@test.com", "password": "Password12345!"})
    
    sub = {"answers": [{"question_id": q_id, "text_answer": "Once upon a time"}]}
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=sub, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["score"] == 0
    assert resp.json()["is_graded"] is False


@pytest.mark.anyio
async def test_admin_grades_submission(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.manual_test)
    payload = {"text": "Manual", "question_type": "free_text"}
    q_resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json=payload, headers=superuser_token_headers)
    q_id = q_resp.json()["id"]
    
    user = await create_user("manual@test.com")
    headers = await _get_auth_headers(client, {"email": "manual@test.com", "password": "Password12345!"})
    
    sub = {"answers": [{"question_id": q_id, "text_answer": "Answer"}]}
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=sub, headers=headers)
    sub_id = resp.json()["id"]
    
    admin_headers = await _get_auth_headers(client, {"email": "test_admin@test.com", "password": "Password12345!"})
    grade_resp = await client.post(f"/api/v1/tests/submissions/{sub_id}/grade", json={"score": 1, "admin_comment": "Good"}, headers=admin_headers)
    assert grade_resp.status_code == 200
    assert grade_resp.json()["score"] == 1
    assert grade_resp.json()["is_graded"] is True


@pytest.mark.anyio
async def test_user_fails_grading(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.manual_test)
    user = await create_user("hack_grade@test.com")
    headers = await _get_auth_headers(client, {"email": "hack_grade@test.com", "password": "Password12345!"})
    

    grade_resp = await client.post(f"/api/v1/tests/submissions/{uuid.uuid4()}/grade", json={"score": 10}, headers=headers)
    assert grade_resp.status_code in (401, 403, 404)


@pytest.mark.anyio
async def test_submit_nonexistent_block(client: AsyncClient, admin_user, create_user):
    user = await create_user("fake_submit@test.com")
    headers = await _get_auth_headers(client, {"email": "fake_submit@test.com", "password": "Password12345!"})
    resp = await client.post(f"/api/v1/tests/blocks/{uuid.uuid4()}/submit", json={"answers": []}, headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_own_submission(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.auto_test)
    q_resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json={"text": "Math", "question_type": "free_text"}, headers=superuser_token_headers)
    
    user = await create_user("own_sub@test.com")
    headers = await _get_auth_headers(client, {"email": "own_sub@test.com", "password": "Password12345!"})
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": [{"question_id": q_resp.json()["id"], "text_answer": "txt"}]}, headers=headers)
    sub_id = resp.json()["id"]
    
    get_resp = await client.get(f"/api/v1/tests/submissions/{sub_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == sub_id


@pytest.mark.anyio
async def test_cannot_see_others_submission(client: AsyncClient, session: AsyncSession, admin_user, create_user, superuser_token_headers):
    _, block = await _create_course_and_block(session, admin_user.id, BlockType.auto_test)
    q_resp = await client.post(f"/api/v1/tests/blocks/{block.id}/questions", json={"text": "Math", "question_type": "free_text"}, headers=superuser_token_headers)
    
    user1 = await create_user("user1@test.com")
    headers1 = await _get_auth_headers(client, {"email": "user1@test.com", "password": "Password12345!"})
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": [{"question_id": q_resp.json()["id"], "text_answer": "txt"}]}, headers=headers1)
    sub_id = resp.json()["id"]
    
    client.cookies.clear()
    user2 = await create_user("user2@test.com")
    headers2 = await _get_auth_headers(client, {"email": "user2@test.com", "password": "Password12345!"})
    
    get_resp = await client.get(f"/api/v1/tests/submissions/{sub_id}", headers=headers2)
    assert get_resp.status_code in (403, 404)
