import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseEnrollment
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption
from core.models.progress import UserBlockProgress

@pytest.mark.anyio
async def test_empty_questions_block(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test 1: Block with zero questions should be marked completed on submission."""
    admin = await create_user("stress1@test.com", is_superuser=True, role="administrator")
    course = Course(title="Stress Course 1", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    
    b1 = Block(course_id=course.id, title="Empty Test", block_type=BlockType.auto_test)
    session.add(b1)
    await session.commit()
    
    student_email = "student_s1@test.com"
    student = await create_user(student_email)
    enrollment = CourseEnrollment(user_id=student.id, course_id=course.id)
    session.add(enrollment)
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    

    payload = {"answers": []}
    resp = await client.post(f"/api/v1/tests/blocks/{b1.id}/submit", json=payload, cookies=cookies)
    assert resp.status_code == 200
    

    stmt = select(UserBlockProgress).where(UserBlockProgress.user_id == student.id, UserBlockProgress.block_id == b1.id)
    progress = (await session.execute(stmt)).scalar_one_or_none()
    assert progress is not None
    assert progress.is_completed is True

@pytest.mark.anyio
async def test_empty_answers_submission(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test 2: Submitting empty answers to a block WITH questions should mark it completed."""
    admin = await create_user("stress2@test.com", is_superuser=True, role="administrator")
    course = Course(title="Stress Course 2", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    
    b = Block(course_id=course.id, title="Test", block_type=BlockType.auto_test)
    session.add(b)
    await session.flush()
    q = Question(block_id=b.id, text="Q", question_type=QuestionType.single_choice)
    session.add(q)
    await session.commit()
    
    student = await create_user("student_s2@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": "student_s2@test.com", "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    
    resp = await client.post(f"/api/v1/tests/blocks/{b.id}/submit", json={"answers": []}, cookies=cookies)
    assert resp.status_code == 200
    
    stmt = select(UserBlockProgress).where(UserBlockProgress.user_id == student.id, UserBlockProgress.block_id == b.id)
    progress = (await session.execute(stmt)).scalar_one_or_none()
    assert progress is not None
    assert progress.is_completed is True

@pytest.mark.anyio
async def test_incorrect_answers_submission(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test 3: Submitting incorrect answers should mark the block as completed."""
    admin = await create_user("stress3@test.com", is_superuser=True, role="administrator")
    course = Course(title="Stress Course 3", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    
    b = Block(course_id=course.id, title="Test", block_type=BlockType.auto_test)
    session.add(b)
    await session.flush()
    q = Question(block_id=b.id, text="Q", question_type=QuestionType.single_choice)
    session.add(q)
    await session.flush()
    o_correct = AnswerOption(question_id=q.id, text="Correct", is_correct=True)
    o_wrong = AnswerOption(question_id=q.id, text="Wrong", is_correct=False)
    session.add(o_correct)
    session.add(o_wrong)
    await session.commit()
    
    student = await create_user("student_s3@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": "student_s3@test.com", "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    

    payload = {"answers": [{"question_id": str(q.id), "selected_answer_id": str(o_wrong.id)}]}
    resp = await client.post(f"/api/v1/tests/blocks/{b.id}/submit", json=payload, cookies=cookies)
    assert resp.status_code == 200
    
    stmt = select(UserBlockProgress).where(UserBlockProgress.user_id == student.id, UserBlockProgress.block_id == b.id)
    progress = (await session.execute(stmt)).scalar_one_or_none()
    assert progress is not None
    assert progress.is_completed is True, "Block should be completed even with wrong answers"

@pytest.mark.anyio
async def test_invalid_block_id_submission(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test 4: Submitting to non-existent block ID should return 404."""
    student = await create_user("student_s4@test.com")
    auth_resp = await client.post("/api/v1/auth/login", data={"username": "student_s4@test.com", "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    
    random_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/tests/blocks/{random_id}/submit", json={"answers": []}, cookies=cookies)
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_multiple_submissions_consistency(client: AsyncClient, session: AsyncSession, create_user):
    """Stress Test 5: Multiple submissions should maintain completion and not error."""
    admin = await create_user("stress5@test.com", is_superuser=True, role="administrator")
    course = Course(title="Stress Course 5", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    
    b = Block(course_id=course.id, title="Test", block_type=BlockType.auto_test)
    session.add(b)
    await session.commit()
    
    student = await create_user("student_s5@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": "student_s5@test.com", "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    

    await client.post(f"/api/v1/tests/blocks/{b.id}/submit", json={"answers": []}, cookies=cookies)
    

    resp = await client.post(f"/api/v1/tests/blocks/{b.id}/submit", json={"answers": []}, cookies=cookies)
    assert resp.status_code == 200
    
    stmt = select(UserBlockProgress).where(UserBlockProgress.user_id == student.id, UserBlockProgress.block_id == b.id)
    progress = (await session.execute(stmt)).scalars().all()
    assert len(progress) == 1, "There should be only 1 progress record"
    assert progress[0].is_completed is True
