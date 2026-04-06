"""
Стресс-тесты для Шага 1: поле progress всегда возвращается как объект,
completed=0 по умолчанию, total = общее количество блоков курса.
"""

import uuid

import pytest
from core.models.block import Block, BlockType
from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ─── Helpers ───────────────────────────────────────────────────────────────────


async def _create_course(session: AsyncSession, title: str = "Test Course") -> Course:
    course = Course(
        title=title,
        description="desc",
        level="beginner",
        is_published=True,
        created_by=uuid.uuid4(),
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def _add_blocks(
    session: AsyncSession,
    course_id: uuid.UUID,
    count: int,
    block_type: BlockType = BlockType.auto_test,
) -> list[Block]:
    """Create blocks. Defaults to auto_test since progress counts only test blocks."""
    blocks = []
    for i in range(count):
        block = Block(
            course_id=course_id,
            order_index=i,
            title=f"Block {i}",
            block_type=block_type,
        )
        session.add(block)
        await session.flush()
        await session.refresh(block)
        blocks.append(block)
    await session.commit()
    return blocks



async def _enroll(session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID) -> None:
    enrollment = CourseEnrollment(user_id=user_id, course_id=course_id)
    session.add(enrollment)
    await session.commit()


async def _complete_blocks(
    session: AsyncSession, user_id: uuid.UUID, blocks: list[Block]
) -> None:
    for block in blocks:
        progress = UserBlockProgress(
            user_id=user_id, block_id=block.id, is_completed=True
        )
        session.add(progress)
    await session.commit()


# ─── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_anonymous_user_gets_zero_progress_not_null(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 1: Анонимный пользователь должен получить progress с completed=0,
    а не null. Проверяет что поле progress НИКОГДА не null.
    """
    course = await _create_course(session, "Anon Course")
    await _add_blocks(session, course.id, 5)

    resp = await client.get("/api/v1/courses/")
    assert resp.status_code == 200

    courses = resp.json()
    matching = [c for c in courses if c["id"] == str(course.id)]
    assert len(matching) == 1

    progress = matching[0]["progress"]
    assert progress is not None, "progress не должен быть null!"
    assert progress["completed"] == 0
    assert progress["total"] == 5
    assert progress["percent"] == 0.0


@pytest.mark.anyio
async def test_enrolled_but_no_blocks_completed(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 2: Пользователь записан на курс, но не завершил ни одного блока.
    progress.completed должен быть 0, progress.total = кол-во блоков.
    """
    user = await create_user("enrolled_zero@test.com")
    course = await _create_course(session, "Enrolled Zero Course")
    await _add_blocks(session, course.id, 3)
    await _enroll(session, user.id, course.id)

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "enrolled_zero@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth") or ""

    resp2 = await client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]
    assert progress is not None
    assert progress["completed"] == 0
    assert progress["total"] == 3
    assert progress["percent"] == 0.0


@pytest.mark.anyio
async def test_course_with_zero_blocks_returns_zero_total(
    client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 3: Курс без блоков — total=0, completed=0, percent=0.0.
    Не должно быть деления на ноль или падения.
    """
    course = await _create_course(session, "Empty Blocks Course")
    # No blocks added

    resp = await client.get(f"/api/v1/courses/{course.id}")
    assert resp.status_code == 200

    progress = resp.json()["progress"]
    assert progress is not None
    assert progress["completed"] == 0
    assert progress["total"] == 0
    assert progress["percent"] == 0.0


@pytest.mark.anyio
async def test_progress_total_reflects_actual_block_count(
    client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 4: total в progress должен точно отражать количество блоков
    курса. Создаём резные курсы с разным количеством блоков (0, 1, 10, 100).
    """
    test_data = [
        ("Zero Blocks", 0),
        ("One Block", 1),
        ("Ten Blocks", 10),
        ("Hundred Blocks", 100),
    ]

    created = []
    for title, block_count in test_data:
        course = await _create_course(session, title)
        await _add_blocks(session, course.id, block_count)
        created.append((course.id, block_count))

    resp = await client.get("/api/v1/courses/?limit=100")
    assert resp.status_code == 200

    courses_map = {c["id"]: c for c in resp.json()}

    for course_id, expected_total in created:
        assert str(course_id) in courses_map, f"Курс {course_id} не найден в ответе"
        progress = courses_map[str(course_id)]["progress"]
        assert progress is not None
        assert progress["total"] == expected_total, (
            f"Ожидали total={expected_total}, получили {progress['total']}"
        )
        assert progress["completed"] == 0
        assert progress["percent"] == 0.0


@pytest.mark.anyio
async def test_list_courses_all_have_progress_field(
    client: AsyncClient,
    session: AsyncSession,
):
    """
    Стресс-тест 5: При запросе списка курсов (GET /api/v1/courses/) — у КАЖДОГО
    курса должно быть поле progress (не null), даже если нет auth-пользователя.
    """
    for i in range(5):
        course = await _create_course(session, f"List Course {i}")
        await _add_blocks(session, course.id, i + 1)

    resp = await client.get("/api/v1/courses/?limit=50")
    assert resp.status_code == 200

    courses = resp.json()
    assert len(courses) >= 5

    for course in courses:
        assert "progress" in course, f"Курс {course['id']} не имеет поля progress!"
        assert course["progress"] is not None, (
            f"Курс {course['id']} имеет progress=null!"
        )
        assert "completed" in course["progress"]
        assert "total" in course["progress"]
        assert "percent" in course["progress"]
        assert course["progress"]["completed"] == 0
        assert course["progress"]["percent"] == 0.0


@pytest.mark.anyio
async def test_enrolled_user_sees_correct_partial_progress(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    """
    Стресс-тест 6: Пользователь завершил часть блоков — percent и completed
    должны точно совпадать с реальными данными. Проверяет корректность формулы.
    """
    user = await create_user("partial_progress@test.com")
    course = await _create_course(session, "Partial Progress Course")
    blocks = await _add_blocks(session, course.id, 10)
    await _enroll(session, user.id, course.id)

    # Complete 4 out of 10 blocks
    await _complete_blocks(session, user.id, blocks[:4])

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "partial_progress@test.com", "password": "Password12345!"},
    )
    token = resp.cookies.get("fastapiusersauth") or ""

    resp2 = await client.get(
        f"/api/v1/courses/{course.id}",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp2.status_code == 200
    progress = resp2.json()["progress"]
    assert progress is not None
    assert progress["completed"] == 4
    assert progress["total"] == 10
    assert progress["percent"] == 40.0
