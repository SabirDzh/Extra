import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseEnrollment
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission
from core.models.progress import UserBlockProgress

@pytest.fixture
async def math_setup(session: AsyncSession, create_user):
    admin = await create_user("admin_math@test.com", is_superuser=True, role="administrator")
    course = Course(title="Math Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    return admin, course

@pytest.mark.anyio
async def test_auto_grading_fractional_scores(client: AsyncClient, session: AsyncSession, math_setup, create_user):
    """Verify that auto-grading correctly calculates and stores absolute scores."""
    admin, course = math_setup
    block = Block(course_id=course.id, title="3-Question Test", block_type=BlockType.auto_test)
    session.add(block)
    await session.flush()
    

    qs = []
    opts = []
    for i in range(3):
        q = Question(block_id=block.id, text=f"Q{i}", question_type=QuestionType.single_choice)
        session.add(q)
        await session.flush()
        opt = AnswerOption(question_id=q.id, text="C", is_correct=True)
        session.add(opt)
        await session.flush()
        qs.append(q)
        opts.append(opt)
    await session.commit()
    
    student = await create_user("student_math_1@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    

    payload = {
        "answers": [
            {"question_id": str(qs[0].id), "selected_answer_id": str(opts[0].id)},
            {"question_id": str(qs[1].id), "selected_answer_id": str(opts[1].id)},

        ]
    }
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload, cookies=cookies)
    assert resp.status_code == 200
    
    data = resp.json()

    assert data["score"] == 2
    assert data["max_score"] == 3

@pytest.mark.anyio
async def test_course_progress_percentage_calculation(client: AsyncClient, session: AsyncSession, math_setup, create_user):
    """Verify that course progress percentage counts only tests, not lessons."""
    admin, course = math_setup
    

    tests = [
        Block(course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=0),
        Block(course_id=course.id, title="T2", block_type=BlockType.auto_test, order_index=1),
    ]
    lessons = [Block(course_id=course.id, title=f"L{i}", block_type=BlockType.lesson, order_index=i+2) for i in range(5)]
    for t in tests:
        session.add(t)
        await session.flush()
    for l in lessons:
        session.add(l)
        await session.flush()
    await session.commit()
    
    student = await create_user("student_prog@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    

    resp0 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert resp0.json()["progress"]["percent"] == 0.0
    

    from crud.test_grading import _mark_block_completed
    await _mark_block_completed(session, student.id, tests[0].id, course.id)
    await session.commit()
    
    resp1 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert resp1.json()["progress"]["percent"] == 50.0
    

    for l in lessons:
        await _mark_block_completed(session, student.id, l.id, course.id)
    await session.commit()
    
    resp2 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert resp2.json()["progress"]["percent"] == 50.0
    

    await _mark_block_completed(session, student.id, tests[1].id, course.id)
    await session.commit()
    
    resp3 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert resp3.json()["progress"]["percent"] == 100.0

@pytest.mark.anyio
async def test_multi_select_partial_grading_zero(client: AsyncClient, session: AsyncSession, math_setup, create_user):
    """Verify that multiple choice requires ALL correct answers for 1.0 point, else 0.0 (current business logic)."""
    admin, course = math_setup
    block = Block(course_id=course.id, title="Multi Test", block_type=BlockType.auto_test)
    session.add(block)
    await session.flush()
    
    q = Question(block_id=block.id, text="Multi", question_type=QuestionType.multiple_choice)
    session.add(q)
    await session.flush()
    o1 = AnswerOption(question_id=q.id, text="A", is_correct=True)
    o2 = AnswerOption(question_id=q.id, text="B", is_correct=True)
    o3 = AnswerOption(question_id=q.id, text="C", is_correct=False)
    session.add(o1)
    await session.flush()
    session.add(o2)
    await session.flush()
    session.add(o3)
    await session.flush()
    await session.commit()
    
    student = await create_user("student_multi_math@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    

    payload_partial = {"answers": [{"question_id": str(q.id), "selected_answer_id": str(o1.id)}]}
    resp_partial = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload_partial, cookies=cookies)
    assert resp_partial.json()["score"] == 0.0
    

    payload_wrong = {
        "answers": [
            {"question_id": str(q.id), "selected_answer_id": str(o1.id)},
            {"question_id": str(q.id), "selected_answer_id": str(o2.id)},
            {"question_id": str(q.id), "selected_answer_id": str(o3.id)},
        ]
    }
    resp_wrong = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload_wrong, cookies=cookies)
    assert resp_wrong.json()["score"] == 0.0
    

    payload_correct = {
        "answers": [
            {"question_id": str(q.id), "selected_answer_id": str(o1.id)},
            {"question_id": str(q.id), "selected_answer_id": str(o2.id)},
        ]
    }
    resp_correct = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload_correct, cookies=cookies)
    assert resp_correct.json()["score"] == 1.0
