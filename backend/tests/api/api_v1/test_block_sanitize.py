"""
Стресс-тесты: зачистка полей урока при создании тестовых блоков.
text_content и video_url должны молча зануляться для auto_test / manual_test.
"""

import uuid

import pytest
from core.models.course import Course
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_course(session: AsyncSession) -> Course:
    course = Course(
        title=f"Block Sanitize Course {uuid.uuid4().hex[:6]}",
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


async def _post_block(
    client: AsyncClient,
    headers: dict,
    course_id: uuid.UUID,
    payload: dict,
):
    return await client.post(
        f"/api/v1/courses/{course_id}/blocks/",
        json=payload,
        headers=headers,
    )





@pytest.mark.anyio
async def test_auto_test_text_content_is_stripped(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 1: auto_test + text_content → поле молча отсекается (null в ответе).
    Никакой 422, блок создаётся.
    """
    course = await _create_course(session)
    await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Lesson 1",
            "block_type": "lesson",
            "text_content": "Lesson content",
        },
    )
    resp = await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Auto Test Block",
            "block_type": "auto_test",
            "text_content": "This should be stripped",
            "order_index": 1,
        },
    )
    assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["text_content"] is None, (
        f"text_content должен быть null, получили '{data['text_content']}'"
    )


@pytest.mark.anyio
async def test_manual_test_video_url_is_stripped(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 2: manual_test + video_url → поле молча отсекается.
    """
    course = await _create_course(session)
    await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Lesson 1",
            "block_type": "lesson",
            "text_content": "Lesson content",
        },
    )
    resp = await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Manual Test Block",
            "block_type": "manual_test",
            "video_url": "https://example.com/video.mp4",
            "order_index": 1,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["video_url"] is None, (
        f"video_url должен быть null, получили '{data['video_url']}'"
    )


@pytest.mark.anyio
async def test_auto_test_both_fields_stripped(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 3: auto_test + оба поля → оба молча отсекаются.
    """
    course = await _create_course(session)
    await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Lesson 1",
            "block_type": "lesson",
            "text_content": "Lesson content",
        },
    )
    resp = await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Full Auto Test",
            "block_type": "auto_test",
            "text_content": "some text",
            "video_url": "https://example.com/video.mp4",
            "order_index": 1,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["text_content"] is None
    assert data["video_url"] is None


@pytest.mark.anyio
async def test_auto_test_without_extra_fields_still_works(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 4: auto_test без лишних полей — создаётся нормально.
    Базовое поведение не сломано.
    """
    course = await _create_course(session)
    await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Lesson 1",
            "block_type": "lesson",
            "text_content": "Lesson content",
        },
    )
    resp = await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {"title": "Clean Auto Test", "block_type": "auto_test", "order_index": 1},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["block_type"] == "auto_test"
    assert data["text_content"] is None
    assert data["video_url"] is None


@pytest.mark.anyio
async def test_lesson_with_text_content_still_valid(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 5: lesson + text_content → создаётся нормально,
    поля НЕ отсекаются (только у тестовых блоков).
    """
    course = await _create_course(session)
    resp = await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {
            "title": "Lesson Block",
            "block_type": "lesson",
            "text_content": "Учебный материал",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["text_content"] == "Учебный материал", (
        "text_content урока не должен отсекаться"
    )


@pytest.mark.anyio
async def test_lesson_without_content_still_returns_422(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 6: lesson без text_content и video_url → 422.
    Существующая валидация урока не сломана.
    """
    course = await _create_course(session)
    resp = await _post_block(
        client,
        superuser_token_headers,
        course.id,
        {"title": "Empty Lesson", "block_type": "lesson"},
    )
    assert resp.status_code == 422, (
        f"Пустой урок должен давать 422, получили {resp.status_code}"
    )
