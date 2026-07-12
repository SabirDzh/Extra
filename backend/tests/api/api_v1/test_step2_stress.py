import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseEnrollment
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission

@pytest.mark.anyio
async def test_admin_grade_normalization(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test: Admin grades are stored as absolute points."""
    admin = await create_user("adm_s2@test.com", is_superuser=True, role="administrator")
    course = Course(title="S2 Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    
    b = Block(course_id=course.id, title="Manual Test", block_type=BlockType.manual_test)
    session.add(b)
    await session.commit()
    
    student = await create_user("student_s2_1@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.flush()
    sub = TestSubmission(user_id=student.id, block_id=b.id, max_score=100, is_graded=False)
    session.add(sub)
    await session.commit()
    submission_id = str(sub.id)
    
    admin_auth = await client.post("/api/v1/auth/login", data={"username": "adm_s2@test.com", "password": "Password12345!"})
    admin_cookies = {"fastapiusersauth": admin_auth.cookies.get("fastapiusersauth")}
    
    grade_payload = {"score": 85, "admin_comment": "Good job"}
    resp_grade = await client.post(f"/api/v1/tests/submissions/{submission_id}/grade", json=grade_payload, cookies=admin_cookies)
    assert resp_grade.status_code == 200
    
    data = resp_grade.json()
    assert data["score"] == 85
    

    session.expire_all()
    stmt = select(TestSubmission).where(TestSubmission.id == uuid.UUID(submission_id))
    submission = (await session.execute(stmt)).scalar_one()
    assert submission.score == 85

@pytest.mark.anyio
async def test_admin_grade_boundaries(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test: Admin grades 0 and 100 as absolute points."""
    admin = await create_user("adm_s2_bound@test.com", is_superuser=True, role="administrator")
    course = Course(title="S2 Bounds", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    b = Block(course_id=course.id, title="Test", block_type=BlockType.manual_test)
    session.add(b)
    await session.commit()
    
    student = await create_user("std_bound@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.flush()
    
    sub1 = TestSubmission(user_id=student.id, block_id=b.id, max_score=100, is_graded=False)
    session.add(sub1)
    await session.flush()
    sub2 = TestSubmission(user_id=student.id, block_id=b.id, max_score=100, is_graded=False)
    session.add(sub2)
    await session.commit()
    
    admin_auth = await client.post("/api/v1/auth/login", data={"username": "adm_s2_bound@test.com", "password": "Password12345!"})
    admin_cookies = {"fastapiusersauth": admin_auth.cookies.get("fastapiusersauth")}
    
    await client.post(f"/api/v1/tests/submissions/{sub1.id}/grade", json={"score": 0}, cookies=admin_cookies)
    

    await client.post(f"/api/v1/tests/submissions/{sub2.id}/grade", json={"score": 100}, cookies=admin_cookies)
    

    sub1_id = sub1.id
    sub2_id = sub2.id
    session.expire_all()
    sub1 = (await session.execute(select(TestSubmission).where(TestSubmission.id == sub1_id))).scalar_one()
    assert sub1.score == 0.0
    
    sub2 = (await session.execute(select(TestSubmission).where(TestSubmission.id == sub2_id))).scalar_one()
    assert sub2.score == 100.0

@pytest.mark.anyio
async def test_auto_grade_normalization(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test: Auto-test with 1/2 correct answers should show 1/2 points."""
    admin = await create_user("adm_s2_auto@test.com", is_superuser=True, role="administrator")
    course = Course(title="S2 Auto", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    
    b = Block(course_id=course.id, title="Auto Test", block_type=BlockType.auto_test)
    session.add(b)
    await session.flush()
    
    q1 = Question(block_id=b.id, text="Q1", question_type=QuestionType.single_choice, order_index=1)
    q2 = Question(block_id=b.id, text="Q2", question_type=QuestionType.single_choice, order_index=2)
    session.add_all([q1, q2])
    await session.flush()
    
    o1 = AnswerOption(question_id=q1.id, text="C", is_correct=True)
    o2 = AnswerOption(question_id=q2.id, text="C", is_correct=True)
    session.add_all([o1, o2])
    await session.commit()
    
    student = await create_user("std_auto_s2@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": "std_auto_s2@test.com", "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    

    payload = {"answers": [{"question_id": str(q1.id), "selected_answer_id": str(o1.id)}]}
    resp = await client.post(f"/api/v1/tests/blocks/{b.id}/submit", json=payload, cookies=cookies)
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["score"] == 1
    assert data["max_score"] == 2

@pytest.mark.anyio
async def test_submission_read_float_schema(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test: Ensure API response correctly handles float scores."""
    student = await create_user("std_schema@test.com")
    auth_resp = await client.post("/api/v1/auth/login", data={"username": "std_schema@test.com", "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    

    admin = await create_user("adm_schema@test.com", role="administrator")
    b = Block(course_id=uuid.uuid4(), title="B", block_type=BlockType.auto_test)

    course = Course(title="Schema Course", created_by=admin.id)
    session.add(course)
    await session.flush()
    block = Block(course_id=course.id, title="Test", block_type=BlockType.auto_test)
    session.add(block)
    await session.flush()
    
    sub = TestSubmission(user_id=student.id, block_id=block.id, score=0.777, max_score=1.0, is_graded=True)
    session.add(sub)
    await session.commit()
    
    resp = await client.get(f"/api/v1/tests/submissions/{sub.id}", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["score"] == 0.777
