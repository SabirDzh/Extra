import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseEnrollment
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission
from core.models.progress import UserBlockProgress
from core.schemas.course import CourseStatus

@pytest.fixture
async def setup_course(session: AsyncSession, create_user):
    admin = await create_user("admin_comp@test.com", is_superuser=True, role="administrator")
    course = Course(title="Comprehensive Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    return admin, course

@pytest.mark.anyio
@pytest.mark.parametrize("block_type, action, expected_status", [
    (BlockType.auto_test, "submit_correct", CourseStatus.completed),
    (BlockType.auto_test, "submit_incorrect", CourseStatus.completed),
    (BlockType.auto_test, "submit_empty", CourseStatus.completed),
    (BlockType.manual_test, "submit", CourseStatus.in_progress),
    (BlockType.manual_test, "grade_positive", CourseStatus.completed),
    (BlockType.manual_test, "grade_zero", CourseStatus.in_progress),
    (BlockType.mixed_test, "submit", CourseStatus.in_progress),
    (BlockType.mixed_test, "grade_positive", CourseStatus.completed),
])
async def test_block_status_transitions(
    client: AsyncClient, 
    session: AsyncSession, 
    setup_course, 
    create_user,
    block_type, 
    action, 
    expected_status
):
    admin, course = setup_course
    student = await create_user(f"student_{block_type.value}_{action}@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    
    block = Block(course_id=course.id, title=f"Test {block_type.value}", block_type=block_type)
    session.add(block)
    await session.flush()
    
    q = Question(block_id=block.id, text="Q", question_type=QuestionType.single_choice)
    session.add(q)
    await session.flush()
    opt = AnswerOption(question_id=q.id, text="C", is_correct=True)
    session.add(opt)
    await session.flush()
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    submission_id = None
    if action.startswith("submit") or action.startswith("grade"):
        payload = {"answers": []}
        if action == "submit_correct":
            payload = {"answers": [{"question_id": str(q.id), "selected_answer_id": str(opt.id)}]}
        
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload, cookies=cookies)
        assert resp.status_code == 200
        submission_id = resp.json()["id"]

    if action.startswith("grade"):
        admin_auth = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
        admin_cookies = {"auth_user": admin_auth.cookies.get("auth_user")}
        
        score = 85 if action == "grade_positive" else 0
        resp_grade = await client.post(
            f"/api/v1/tests/submissions/{submission_id}/grade", 
            json={"score": score, "admin_comment": "Graded"}, 
            cookies=admin_cookies
        )
        assert resp_grade.status_code == 200

    # Verify status via list API
    resp_list = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    if resp_list.status_code == 418:
        pytest.fail(f"DEBUG RESPONSE: {resp_list.json()}")
    assert resp_list.status_code == 200
    blocks_data = resp_list.json()["blocks"]
    target_block = next(b for b in blocks_data if b["id"] == str(block.id))
    assert target_block["progress"]["status"] == expected_status

@pytest.mark.anyio
async def test_lesson_block_status(client: AsyncClient, session: AsyncSession, setup_course, create_user):
    """Test binary completion for lessons."""
    admin, course = setup_course
    student = await create_user("student_lesson@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    
    block = Block(course_id=course.id, title="Lesson", block_type=BlockType.lesson, text_content="Content")
    session.add(block)
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    
    # Not started
    resp1 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert resp1.json()["blocks"][0]["progress"]["status"] == CourseStatus.not_started
    
    # Complete it (simulated via progress endpoint if exists, or manual mark)
    from crud.test_grading import _mark_block_completed
    await _mark_block_completed(session, student.id, block.id, course.id)
    await session.commit()
    
    resp2 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert resp2.json()["blocks"][0]["progress"]["status"] == CourseStatus.completed

@pytest.mark.anyio
@pytest.mark.parametrize("test_type", [BlockType.auto_test, BlockType.manual_test])
async def test_multiple_submissions_status_persistence(client: AsyncClient, session: AsyncSession, setup_course, create_user, test_type):
    """Ensure multiple submissions don't regress status."""
    admin, course = setup_course
    student = await create_user(f"student_multi_{test_type.value}@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    block = Block(course_id=course.id, title="Test", block_type=test_type)
    session.add(block)
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"fastapiusersauth": auth_resp.cookies.get("fastapiusersauth")}
    
    # Submission 1
    await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    
    # Submission 2
    await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    status = resp.json()["blocks"][0]["progress"]["status"]
    if test_type == BlockType.auto_test:
        assert status == CourseStatus.completed
    else:
        assert status == CourseStatus.in_progress
