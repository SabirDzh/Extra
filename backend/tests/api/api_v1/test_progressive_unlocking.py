import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course
from core.models.block import Block, BlockType
from core.models.progress import UserBlockProgress



async def _create_multi_stage_env(session: AsyncSession, admin_id: uuid.UUID):
    course = Course(id=uuid.uuid4(), title="Progessive Course", created_by=admin_id, is_published=True)
    session.add(course)
    await session.flush()
    

    b1 = Block(id=uuid.uuid4(), course_id=course.id, title="L1", block_type=BlockType.lesson, order_index=1)
    b2 = Block(id=uuid.uuid4(), course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=2)

    b3 = Block(id=uuid.uuid4(), course_id=course.id, title="L2", block_type=BlockType.lesson, order_index=3)
    b4 = Block(id=uuid.uuid4(), course_id=course.id, title="T2", block_type=BlockType.auto_test, order_index=4)

    b5 = Block(id=uuid.uuid4(), course_id=course.id, title="L3", block_type=BlockType.lesson, order_index=5)
    b6 = Block(id=uuid.uuid4(), course_id=course.id, title="T3", block_type=BlockType.auto_test, order_index=6)
    
    session.add_all([b1, b2, b3, b4, b5, b6])
    await session.commit()
    return course, [b1, b2, b3, b4, b5, b6]

@pytest.mark.anyio
async def test_unlocking_anonymous(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("adm_up1@test.com", is_superuser=True, role="administrator")
    course, blocks = await _create_multi_stage_env(session, admin.id)

    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
    assert resp.status_code == 401


@pytest.mark.anyio

async def test_unlocking_partial_progress(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("adm_up2@test.com", is_superuser=True, role="administrator")
    course, blocks = await _create_multi_stage_env(session, admin.id)
    
    student_email = "student_up2@test.com"
    student = await create_user(student_email)
    await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})


    p1 = UserBlockProgress(user_id=student.id, block_id=blocks[0].id, is_completed=True)
    p2 = UserBlockProgress(user_id=student.id, block_id=blocks[1].id, is_completed=True)
    session.add_all([p1, p2])
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
    assert resp.status_code == 200
    data = resp.json()
    

    assert len(data["blocks"]) == 2
    assert data["blocks"][0]["title"] == "L2"
    assert data["blocks"][1]["title"] == "T2"
    assert len(data["completed_blocks"]) == 2
    assert data["completed_blocks"][0]["title"] == "L1"
    assert data["completed_blocks"][1]["title"] == "T1"
    assert data["current_block_id"] == str(blocks[3].id)

@pytest.mark.anyio
async def test_unlocking_single_block_completed(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("adm_up3@test.com", is_superuser=True, role="administrator")
    course, blocks = await _create_multi_stage_env(session, admin.id)
    
    student_email = "student_up3@test.com"
    student = await create_user(student_email)
    await client.post("/api/v1/auth/login", data={"username": student_email, "password": "Password12345!"})


    p1 = UserBlockProgress(user_id=student.id, block_id=blocks[0].id, is_completed=True)
    session.add(p1)
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
    assert resp.status_code == 200
    data = resp.json()
    

    assert len(data["blocks"]) == 2
