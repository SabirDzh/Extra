import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course
from core.models.block import Block, BlockType


async def _create_course_and_blocks(session: AsyncSession):
    course = Course(
        title=f"Question Block Type Test {uuid.uuid4().hex[:6]}",
        description="",
        level="beginner",
        audience="everyone",
        is_published=True,
        created_by=uuid.uuid4(),
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)

    lesson_block = Block(
        course_id=course.id,
        title="Lesson Block",
        block_type=BlockType.lesson,
        text_content="content",
        order_index=1
    )
    session.add(lesson_block)
    await session.flush()
    await session.refresh(lesson_block)

    test_block = Block(
        course_id=course.id,
        title="Test Block",
        block_type=BlockType.auto_test,
        order_index=2
    )
    session.add(test_block)
    await session.flush()
    await session.refresh(test_block)
    
    await session.commit()
    return course, lesson_block, test_block



@pytest.mark.anyio
async def test_cannot_add_question_to_lesson_block(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    course, lesson_block, _ = await _create_course_and_blocks(session)
    
    payload = {
        "text": "Valid question?",
        "question_type": "single_choice",
        "order_index": 0,
        "options": [
            {"text": "A", "is_correct": True, "order_index": 0},
            {"text": "B", "is_correct": False, "order_index": 1}
        ]
    }
    
    response = await client.post(
        f"/api/v1/tests/blocks/{lesson_block.id}/questions",
        json=payload,
        headers=superuser_token_headers
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Questions can only be added to test blocks"


@pytest.mark.anyio
async def test_can_add_question_to_test_block(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict,
):
    course, _, test_block = await _create_course_and_blocks(session)
    
    payload = {
        "text": "Valid question?",
        "question_type": "single_choice",
        "order_index": 0,
        "options": [
            {"text": "A", "is_correct": True, "order_index": 0},
            {"text": "B", "is_correct": False, "order_index": 1}
        ]
    }
    
    response = await client.post(
        f"/api/v1/tests/blocks/{test_block.id}/questions",
        json=payload,
        headers=superuser_token_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Valid question?"
    assert len(data["options"]) == 2
