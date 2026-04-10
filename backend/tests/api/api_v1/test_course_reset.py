import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseEnrollment
from core.models.block import Block, BlockType
from core.models.test import TestSubmission
from core.models.progress import UserBlockProgress

@pytest.mark.anyio
async def test_admin_resets_user_progress(client: AsyncClient, session: AsyncSession, create_user):
    # 1. Setup Admin and User
    admin = await create_user("admin_reset@test.com", is_superuser=True, role="administrator")
    user = await create_user("student_reset@test.com")
    
    # 2. Setup Course and Block
    course = Course(title="Reset Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    
    block = Block(course_id=course.id, title="Test Block", block_type=BlockType.auto_test, order_index=0)
    session.add(block)
    await session.flush()
    
    # 3. Enroll User
    enrollment = CourseEnrollment(user_id=user.id, course_id=course.id)
    session.add(enrollment)
    await session.flush()
    
    # 4. Create Fake Progress and Submission
    progress = UserBlockProgress(user_id=user.id, block_id=block.id, is_completed=True)
    session.add(progress)
    submission = TestSubmission(user_id=user.id, block_id=block.id, score=1.0, max_score=1.0, is_graded=True)
    session.add(submission)
    await session.commit()
    
    # 5. Admin Login
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    # 6. Call Reset Endpoint
    resp = await client.post(f"/api/v1/courses/{course.id}/users/{user.id}/reset", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Progress reset successfully"
    
    # 7. Verify Cleanup
    # Check Submission
    stmt_sub = select(TestSubmission).where(TestSubmission.user_id == user.id, TestSubmission.block_id == block.id)
    res_sub = await session.execute(stmt_sub)
    assert res_sub.scalar_one_or_none() is None
    
    # Check Progress
    stmt_prog = select(UserBlockProgress).where(UserBlockProgress.user_id == user.id, UserBlockProgress.block_id == block.id)
    res_prog = await session.execute(stmt_prog)
    assert res_prog.scalar_one_or_none() is None
    
    # Check Enrollment status
    stmt_enroll = select(CourseEnrollment).where(CourseEnrollment.user_id == user.id, CourseEnrollment.course_id == course.id)
    res_enroll = await session.execute(stmt_enroll)
    final_enrollment = res_enroll.scalar_one()
    assert final_enrollment.completed_at is None

@pytest.mark.anyio
async def test_reset_unauthorized_fails(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("admin_fail@test.com", is_superuser=True, role="administrator")
    user = await create_user("student_fail@test.com")
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    # Regular user tries to reset their own or someone else's progress
    resp = await client.post(f"/api/v1/courses/{uuid.uuid4()}/users/{user.id}/reset", cookies=cookies)
    assert resp.status_code in [401, 403]
