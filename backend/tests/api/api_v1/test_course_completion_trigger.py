import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseEnrollment
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption
from core.models.user import User

@pytest.mark.anyio
async def test_course_completion_triggers_after_test_submission(
    client: AsyncClient, 
    session: AsyncSession, 
    create_user, 
    superuser_token_headers
):

    admin = await create_user("adm_trigger@test.com", is_superuser=True, role="administrator")
    
    course = Course(title="Trigger Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    

    b1 = Block(course_id=course.id, title="Test 1", block_type=BlockType.auto_test, order_index=1)
    session.add(b1)
    await session.flush()
    q1 = Question(block_id=b1.id, text="Q1", question_type=QuestionType.single_choice)
    session.add(q1)
    await session.flush()
    o1 = AnswerOption(question_id=q1.id, text="Correct", is_correct=True)
    session.add(o1)
    

    b2 = Block(course_id=course.id, title="Test 2", block_type=BlockType.auto_test, order_index=2)
    session.add(b2)
    await session.flush()
    q2 = Question(block_id=b2.id, text="Q2", question_type=QuestionType.single_choice)
    session.add(q2)
    await session.flush()
    o2 = AnswerOption(question_id=q2.id, text="Correct", is_correct=True)
    session.add(o2)
    
    await session.commit()
    

    student_email = "student_trigger@test.com"
    student = await create_user(student_email)
    

    enrollment = CourseEnrollment(user_id=student.id, course_id=course.id)
    session.add(enrollment)
    await session.commit()
    

    auth_resp = await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})
    token = auth_resp.cookies.get("fastapiusersauth")
    cookies = {"fastapiusersauth": token}
    

    payload1 = {
        "answers": [{"question_id": str(q1.id), "selected_answer_id": str(o1.id)}]
    }
    resp1 = await client.post(f"/api/v1/tests/blocks/{b1.id}/submit", json=payload1, cookies=cookies)
    assert resp1.status_code == 200
    

    await session.refresh(enrollment)
    assert enrollment.completed_at is None
    

    payload2 = {
        "answers": [{"question_id": str(q2.id), "selected_answer_id": str(o2.id)}]
    }
    resp2 = await client.post(f"/api/v1/tests/blocks/{b2.id}/submit", json=payload2, cookies=cookies)
    assert resp2.status_code == 200
    


    await session.refresh(enrollment)
    assert enrollment.completed_at is not None, "Course should be marked as completed after last test!"

@pytest.mark.anyio
async def test_manual_lesson_completion_triggers_course_completion(
    client: AsyncClient, 
    session: AsyncSession, 
    create_user, 
):

    admin = await create_user("adm_manual@test.com", is_superuser=True, role="administrator")
    course = Course(title="Manual Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    



    
    b_test = Block(course_id=course.id, title="Test", block_type=BlockType.auto_test)
    session.add(b_test)
    await session.flush()
    q = Question(block_id=b_test.id, text="Q", question_type=QuestionType.single_choice)
    session.add(q)
    await session.flush()
    o = AnswerOption(question_id=q.id, text="C", is_correct=True)
    session.add(o)
    
    await session.commit()
    
    student_email = "student_manual@test.com"
    student = await create_user(student_email)
    enrollment = CourseEnrollment(user_id=student.id, course_id=course.id)
    session.add(enrollment)
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    

    payload = {"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]}
    await client.post(f"/api/v1/tests/blocks/{b_test.id}/submit", json=payload, cookies=cookies)
    
    await session.refresh(enrollment)
    assert enrollment.completed_at is not None
