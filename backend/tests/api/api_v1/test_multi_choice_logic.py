import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission, TestAnswer
from core.models.user import User



async def _create_env(session: AsyncSession, admin_id: uuid.UUID):
    course = Course(title="MultiChoice Course", created_by=admin_id, is_published=True)
    session.add(course)
    await session.flush()
    
    block = Block(course_id=course.id, title="Multi-Test", block_type=BlockType.auto_test, order_index=1)
    session.add(block)
    await session.flush()
    

    q1 = Question(block_id=block.id, text="Select A and B", question_type=QuestionType.multiple_choice, order_index=1)
    session.add(q1)
    await session.flush()
    o1a = AnswerOption(question_id=q1.id, text="A", is_correct=True, order_index=1)
    o1b = AnswerOption(question_id=q1.id, text="B", is_correct=True, order_index=2)
    o1c = AnswerOption(question_id=q1.id, text="C", is_correct=False, order_index=3)
    session.add_all([o1a, o1b, o1c])
    

    q2 = Question(block_id=block.id, text="Select X", question_type=QuestionType.single_choice, order_index=2)
    session.add(q2)
    await session.flush()
    o2x = AnswerOption(question_id=q2.id, text="X", is_correct=True, order_index=1)
    o2y = AnswerOption(question_id=q2.id, text="Y", is_correct=False, order_index=2)
    session.add_all([o2x, o2y])
    
    await session.commit()
    return course, block, q1, [o1a, o1b, o1c], q2, [o2x, o2y]



@pytest.mark.anyio
async def test_multichoice_full_match(client: AsyncClient, session: AsyncSession, create_user, superuser_token_headers):

    admin = await create_user("adm_mc@test.com", is_superuser=True, role="administrator")
    _, block, q1, o1, q2, o2 = await _create_env(session, admin.id)
    

    student_email = "student_mc1@test.com"
    await create_user(student_email)
    await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})


    payload = {
        "answers": [
            {"question_id": str(q1.id), "selected_answer_id": str(o1[0].id)},
            {"question_id": str(q1.id), "selected_answer_id": str(o1[1].id)},
            {"question_id": str(q2.id), "selected_answer_id": str(o2[0].id)}
        ]
    }
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
    assert resp.status_code == 200
    assert resp.json()["score"] == 2

@pytest.mark.anyio
async def test_multichoice_partial_match(client: AsyncClient, session: AsyncSession, create_user, superuser_token_headers):
    admin = await create_user("adm_mc2@test.com", is_superuser=True, role="administrator")
    _, block, q1, o1, q2, o2 = await _create_env(session, admin.id)
    
    student_email = "student_mc2@test.com"
    await create_user(student_email)
    await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})


    payload = {
        "answers": [
            {"question_id": str(q1.id), "selected_answer_id": str(o1[0].id)},
            {"question_id": str(q2.id), "selected_answer_id": str(o2[0].id)}
        ]
    }
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
    assert resp.status_code == 200
    assert resp.json()["score"] == 1

@pytest.mark.anyio
async def test_multichoice_over_selection(client: AsyncClient, session: AsyncSession, create_user, superuser_token_headers):
    admin = await create_user("adm_mc3@test.com", is_superuser=True, role="administrator")
    _, block, q1, o1, q2, o2 = await _create_env(session, admin.id)
    
    student_email = "student_mc3@test.com"
    await create_user(student_email)
    await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})


    payload = {
        "answers": [
            {"question_id": str(q1.id), "selected_answer_id": str(o1[0].id)},
            {"question_id": str(q1.id), "selected_answer_id": str(o1[1].id)},
            {"question_id": str(q1.id), "selected_answer_id": str(o1[2].id)},
            {"question_id": str(q2.id), "selected_answer_id": str(o2[0].id)}
        ]
    }
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
    assert resp.status_code == 200
    assert resp.json()["score"] == 1

@pytest.mark.anyio
async def test_test_results_multichoice_display(client: AsyncClient, session: AsyncSession, create_user, superuser_token_headers):
    admin = await create_user("adm_mc4@test.com", is_superuser=True, role="administrator")
    course, block, q1, o1, q2, o2 = await _create_env(session, admin.id)
    
    student_email = "student_mc4@test.com"
    await create_user(student_email)
    await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})
    

    payload = {
        "answers": [
            {"question_id": str(q1.id), "selected_answer_id": str(o1[0].id)},
            {"question_id": str(q1.id), "selected_answer_id": str(o1[1].id)}
        ]
    }
    await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
    

    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results")
    assert resp.status_code == 200
    data = resp.json()
    
    q1_res = next(r for r in data["questions"] if r["question_id"] == str(q1.id))
    assert q1_res["status"] == "Верно"
    assert "A" in q1_res["user_answer"]
    assert "B" in q1_res["user_answer"]
    assert q1_res["score"] == 1
