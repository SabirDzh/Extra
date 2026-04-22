"""
Стресс-тесты для Шага 5: автоматическое вычисление статуса курса.
- not_started: пользователь не записан или записан, но нет пройденных блоков
- in_progress: пройден хотя бы один блок, но не все
- completed: пройдены все блоки (enrollment.completed_at устанавливается автоматически)
"""

import uuid

import pytest
from core.models.block import Block, BlockType
from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession





async def _create_course(session: AsyncSession, title: str = "Status Test Course") -> Course:
    course = Course(
        title=title,
        description="",
        level="beginner",
        audience="everyone",
        is_published=True,
        created_by=uuid.uuid4(),
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def _add_block(session: AsyncSession, course_id: uuid.UUID, title: str = "Block") -> Block:
    block = Block(
        course_id=course_id,
        order_index=0,
        title=title,
        block_type=BlockType.auto_test,
    )
    session.add(block)
    await session.flush()
    await session.refresh(block)
    await session.commit()
    return block


async def _enroll(session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID) -> None:
    enrollment = CourseEnrollment(user_id=user_id, course_id=course_id)
    session.add(enrollment)
    await session.commit()


async def _complete_block(session: AsyncSession, user_id: uuid.UUID, block: Block) -> None:
    progress = UserBlockProgress(
        user_id=user_id, block_id=block.id, is_completed=True
    )
    session.add(progress)
    await session.commit()





@pytest.mark.anyio
async def test_status_not_started_for_anonymous(
    client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 1: Анонимный пользователь — статус всегда not_started.
    """
    course = await _create_course(session, "Anon Status Course")
    await _add_block(session, course.id, "Block 1")

    resp = await client.get(f"/api/v1/courses/{course.id}")
    assert resp.status_code == 200
    assert resp.json()["progress"]["status"] == "not_started"


@pytest.mark.anyio
async def test_status_not_started_when_enrolled_but_no_blocks_done(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 2: Пользователь записан, но не прошёл ни одного блока → not_started.
    """
    user = await create_user("enrolled_noblock@test.com")
    course = await _create_course(session, "No Blocks Done Course")
    await _add_block(session, course.id)
    await _enroll(session, user.id, course.id)

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "enrolled_noblock@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth", "")

    resp2 = await client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    assert resp2.json()["progress"]["status"] == "not_started"


@pytest.mark.anyio
async def test_status_in_progress_when_partial_blocks_done(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 3: Пройден 1 из 3 блоков → in_progress.
    """
    user = await create_user("partial_status@test.com")
    course = await _create_course(session, "Partial Status Course")
    blocks = []
    for i in range(3):
        b = await _add_block(session, course.id, f"Block {i}")
        blocks.append(b)
    await _enroll(session, user.id, course.id)
    await _complete_block(session, user.id, blocks[0])

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "partial_status@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth", "")

    resp2 = await client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]
    assert progress["status"] == "in_progress", (
        f"Ожидали 'in_progress', получили '{progress['status']}'"
    )
    assert progress["completed"] == 1
    assert progress["total"] == 3


@pytest.mark.anyio
async def test_status_completed_when_all_blocks_done(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 4: Пройдены все блоки → status="completed".
    enrollment.completed_at должен устанавливаться автоматически.
    """
    user = await create_user("all_done@test.com")
    course = await _create_course(session, "All Done Course")
    blocks = []
    for i in range(3):
        b = await _add_block(session, course.id, f"Block {i}")
        blocks.append(b)
    await _enroll(session, user.id, course.id)
    for block in blocks:
        await _complete_block(session, user.id, block)


    from crud.course import update_course_completion_status
    await update_course_completion_status(session, user.id, course.id)

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "all_done@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth", "")

    resp2 = await client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]
    assert progress["status"] == "completed", (
        f"Ожидали 'completed', получили '{progress['status']}'"
    )
    assert progress["completed"] == 3
    assert progress["percent"] == 100.0


@pytest.mark.anyio
async def test_status_in_list_endpoint(
    client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 5: Поле status присутствует у каждого курса в листинге.
    Анонимный пользователь → все статусы not_started.
    """
    for i in range(3):
        await _create_course(session, f"List Status Course {i}")

    resp = await client.get("/api/v1/courses/")
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) >= 3
    for course in courses:
        assert "status" in course["progress"], f"status отсутствует у {course['id']}"
        assert course["progress"]["status"] == "not_started"


@pytest.mark.anyio
async def test_course_without_blocks_status_is_not_started(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 6: Курс без блоков — статус not_started для записанного пользователя.
    Нет деления на ноль, нет ложного completed.
    """
    user = await create_user("no_blocks_enrolled@test.com")
    course = await _create_course(session, "No Blocks Enrolled Course")

    await _enroll(session, user.id, course.id)

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "no_blocks_enrolled@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth", "")

    resp2 = await client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]

    assert progress["status"] in ("not_started", "in_progress")
    assert progress["total"] == 0
    assert progress["completed"] == 0
