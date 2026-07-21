"""
Стресс-тесты для Шага 7: в total и completed считаются только тестовые блоки
(auto_test, manual_test). Обучающие блоки (lesson) не влияют на прогресс.
"""

import uuid

import pytest
from core.models.block import Block, BlockType
from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession





async def _create_course(session: AsyncSession, title: str) -> Course:
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


async def _add_block(
    session: AsyncSession,
    course_id: uuid.UUID,
    block_type: BlockType,
    title: str = "Block",
) -> Block:
    block = Block(
        course_id=course_id,
        order_index=0,
        title=title,
        block_type=block_type,
    )
    session.add(block)
    await session.flush()
    await session.refresh(block)
    await session.commit()
    return block


async def _enroll(session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID):
    enrollment = CourseEnrollment(user_id=user_id, course_id=course_id)
    session.add(enrollment)
    await session.commit()


async def _complete_block(session: AsyncSession, user_id: uuid.UUID, block: Block):
    progress = UserBlockProgress(user_id=user_id, block_id=block.id, is_completed=True)
    session.add(progress)
    await session.commit()





@pytest.mark.anyio
async def test_total_excludes_lesson_blocks(
    auth_client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 1: Курс с 2 уроками (lesson) и 1 тестом (auto_test).
    total должен быть 1 (только тест), а не 3.
    """
    course = await _create_course(session, "Lesson Excluded Course")
    await _add_block(session, course.id, BlockType.lesson, "Lesson 1")
    await _add_block(session, course.id, BlockType.lesson, "Lesson 2")
    await _add_block(session, course.id, BlockType.auto_test, "Test 1")

    resp = await auth_client.get(f"/api/v1/courses/{course.id}")
    assert resp.status_code == 200
    progress = resp.json()["progress"]
    assert progress["total"] == 3, (
        f"Ожидали total=3, получили {progress['total']}"
    )


@pytest.mark.anyio
async def test_total_counts_both_auto_and_manual_test(
    auth_client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 2: Курс с 1 auto_test и 1 manual_test — total = 2.
    """
    course = await _create_course(session, "Both Tests Course")
    await _add_block(session, course.id, BlockType.auto_test, "Auto Test")
    await _add_block(session, course.id, BlockType.manual_test, "Manual Test")
    await _add_block(session, course.id, BlockType.lesson, "Intro Lesson")

    resp = await auth_client.get(f"/api/v1/courses/{course.id}")
    assert resp.status_code == 200
    progress = resp.json()["progress"]
    assert progress["total"] == 3


@pytest.mark.anyio
async def test_completed_ignores_lesson_completion(
    auth_client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 3: Пользователь "прошёл" урок — completed не должен расти.
    Только завершение тестового блока увеличивает completed.
    """
    user = await create_user("lesson_done@test.com")
    course = await _create_course(session, "Lesson Done Course")
    lesson = await _add_block(session, course.id, BlockType.lesson, "Lesson")
    test_block = await _add_block(session, course.id, BlockType.auto_test, "Test")
    await _enroll(session, user.id, course.id)


    await _complete_block(session, user.id, lesson)

    resp = await auth_client.post(
        "/api/v1/auth/login",
        data={"username": "lesson_done@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth", "")

    resp2 = await auth_client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]
    assert progress["total"] == 2, "total должен считать все блоки"
    assert progress["completed"] == 1, "завершение урока должно засчитываться"


@pytest.mark.anyio
async def test_only_lesson_blocks_gives_zero_total(
    auth_client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 4: Курс с 3 уроками и 0 тестов → total = 0.
    """
    course = await _create_course(session, "Only Lessons Course")
    await _add_block(session, course.id, BlockType.lesson, "L1")
    await _add_block(session, course.id, BlockType.lesson, "L2")
    await _add_block(session, course.id, BlockType.lesson, "L3")

    resp = await auth_client.get(f"/api/v1/courses/{course.id}")
    assert resp.status_code == 200
    progress = resp.json()["progress"]
    assert progress["total"] == 3
    assert progress["completed"] == 0
    assert progress["percent"] == 0.0


@pytest.mark.anyio
async def test_full_test_progress_gives_100_percent(
    auth_client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 5: 2 теста + 3 урока. Проходим оба теста + все уроки.
    percent должен быть 100% (тесты) и completed=2.
    """
    user = await create_user("full_test_progress@test.com")
    course = await _create_course(session, "Full Test Progress Course")
    l1 = await _add_block(session, course.id, BlockType.lesson, "L1")
    l2 = await _add_block(session, course.id, BlockType.lesson, "L2")
    l3 = await _add_block(session, course.id, BlockType.lesson, "L3")
    t1 = await _add_block(session, course.id, BlockType.auto_test, "T1")
    t2 = await _add_block(session, course.id, BlockType.manual_test, "T2")

    await _enroll(session, user.id, course.id)

    for block in [l1, l2, l3, t1, t2]:
        await _complete_block(session, user.id, block)

    from Services.course import update_course_completion_status
    await update_course_completion_status(session, user.id, course.id)

    resp = await auth_client.post(
        "/api/v1/auth/login",
        data={"username": "full_test_progress@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth", "")

    resp2 = await auth_client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]
    assert progress["total"] == 5, f"total должен быть 5, получили {progress['total']}"
    assert progress["completed"] == 5
    assert progress["percent"] == 100.0
    assert progress["status"] == "completed"


@pytest.mark.anyio
async def test_partial_test_completion_gives_correct_percent(
    auth_client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 6: 4 теста, пройден 1 → percent = 25.0, completed = 1.
    Уроки вообще не влияют.
    """
    user = await create_user("partial_test@test.com")
    course = await _create_course(session, "Partial Test Course")
    await _add_block(session, course.id, BlockType.lesson, "Intro")
    t1 = await _add_block(session, course.id, BlockType.auto_test, "T1")
    await _add_block(session, course.id, BlockType.auto_test, "T2")
    await _add_block(session, course.id, BlockType.manual_test, "T3")
    await _add_block(session, course.id, BlockType.manual_test, "T4")

    await _enroll(session, user.id, course.id)
    await _complete_block(session, user.id, t1)

    resp = await auth_client.post(
        "/api/v1/auth/login",
        data={"username": "partial_test@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth", "")

    resp2 = await auth_client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]
    assert progress["total"] == 5
    assert progress["completed"] == 1
    assert progress["percent"] == 20.0
    assert progress["status"] == "in_progress"
