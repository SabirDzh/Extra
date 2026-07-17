import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course, CourseEnrollment
from core.models.block import Block, BlockType
from core.models.progress import UserBlockProgress
from Services.test_grading import _mark_block_completed

@pytest.fixture
async def multi_stage_course(session: AsyncSession, create_user):
    admin = await create_user("admin_unlock@test.com", is_superuser=True, role="administrator")
    course = Course(title="Unlock Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    

    b0 = Block(course_id=course.id, title="L1", block_type=BlockType.lesson, order_index=0)
    session.add(b0)
    await session.flush()
    
    b1 = Block(course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=1)
    session.add(b1)
    await session.flush()
    

    b2 = Block(course_id=course.id, title="L2", block_type=BlockType.lesson, order_index=2)
    session.add(b2)
    await session.flush()
    
    b3 = Block(course_id=course.id, title="T2", block_type=BlockType.auto_test, order_index=3)
    session.add(b3)
    await session.flush()
    
    await session.commit()
    return admin, course, [b0, b1, b2, b3]

@pytest.mark.anyio
async def test_progressive_unlocking_stages(client: AsyncClient, session: AsyncSession, multi_stage_course, create_user):
    """Test that blocks from future stages are hidden."""
    admin, course, blocks = multi_stage_course
    student = await create_user("student_unlock@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    

    resp1 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    visible_ids = [b["id"] for b in resp1.json()["blocks"]]
    assert len(visible_ids) == 2
    assert str(blocks[0].id) in visible_ids
    assert str(blocks[1].id) in visible_ids
    assert str(blocks[2].id) not in visible_ids
    

    await _mark_block_completed(session, student.id, blocks[0].id, course.id)
    await session.commit()
    resp2 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert len(resp2.json()["blocks"]) == 2
    

    await _mark_block_completed(session, student.id, blocks[1].id, course.id)
    await session.commit()
    resp3 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert len(resp3.json()["blocks"]) == 2
    visible_ids_3 = [b["id"] for b in resp3.json()["blocks"]]
    assert str(blocks[2].id) in visible_ids_3
    assert str(blocks[3].id) in visible_ids_3
    assert str(blocks[0].id) not in visible_ids_3
    assert str(blocks[1].id) not in visible_ids_3

@pytest.mark.anyio
async def test_admin_sees_all_blocks(client: AsyncClient, session: AsyncSession, multi_stage_course):
    """Admin should see all blocks regardless of progress."""
    admin, course, blocks = multi_stage_course
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert len(resp.json()["blocks"]) == 4

@pytest.mark.anyio
async def test_block_access_content_security(client: AsyncClient, session: AsyncSession, multi_stage_course, create_user):
    """TODO: If there is a direct GET /blocks/{id} endpoint, it should 403 if locked."""

    admin, course, blocks = multi_stage_course
    student = await create_user("student_sec@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    

    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{blocks[2].id}", cookies=cookies)





    pass

@pytest.mark.anyio
async def test_stage_logic_with_odd_number_of_blocks(client: AsyncClient, session: AsyncSession, create_user):
    """Test stage calculation for course with 3 blocks."""
    admin = await create_user("adm_odd@test.com", is_superuser=True, role="administrator")
    course = Course(title="Odd Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()
    b0 = Block(course_id=course.id, title="B0", block_type=BlockType.lesson, order_index=0)
    session.add(b0)
    await session.flush()
    b1 = Block(course_id=course.id, title="B1", block_type=BlockType.auto_test, order_index=1)
    session.add(b1)
    await session.flush()
    b2 = Block(course_id=course.id, title="B2", block_type=BlockType.auto_test, order_index=2)
    session.add(b2)
    await session.flush()
    await session.commit()
    
    student = await create_user("student_odd@test.com")
    session.add(CourseEnrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    
    auth_resp = await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})
    cookies = {"auth_user": auth_resp.cookies.get("auth_user")}
    

    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert len(resp.json()["blocks"]) == 2
    
    await _mark_block_completed(session, student.id, b0.id, course.id)
    await _mark_block_completed(session, student.id, b1.id, course.id)
    await session.commit()
    
    resp2 = await client.get(f"/api/v1/courses/{course.id}/blocks/", cookies=cookies)
    assert len(resp2.json()["blocks"]) == 1
