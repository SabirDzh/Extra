import pytest
from httpx import AsyncClient
from core.models.block import BlockType
from Domain.Enums.course import CourseLevel, CourseAudience

@pytest.mark.anyio
async def test_create_course_with_3_stages_via_schemas(client: AsyncClient, superuser_token_headers: dict):
    # 1. Create a course using CourseCreate schema structure
    course_payload = {
        "title": "Специализированный курс с 3 этапами",
        "description": "Этот курс состоит из 3 этапов, каждый из которых включает лекцию и проверочный тест.",
        "level": CourseLevel.beginner.value,
        "audience": CourseAudience.everyone.value,
        "is_published": True
    }
    
    course_response = await client.post("/api/v1/courses/", json=course_payload, headers=superuser_token_headers)
    assert course_response.status_code == 201, f"Failed to create course: {course_response.text}"
    course_data = course_response.json()
    course_id = course_data["id"]
    
    # 2. Add blocks according to BlockCreate schema structure and sequence validation rules.
    # To have 3 stages (each stage is a pair of a lesson and a test), we create 6 blocks:
    # Stage 1: Lesson (order_index=1) + Test (order_index=2)
    # Stage 2: Lesson (order_index=3) + Test (order_index=4)
    # Stage 3: Lesson (order_index=5) + Test (order_index=6)
    
    blocks_to_create = [
        # Stage 1
        {
            "title": "Лекция 1: Введение",
            "block_type": BlockType.lesson.value,
            "order_index": 1,
            "text_content": "Приветствуем на первом этапе нашего курса. Изучите основы.",
            "video_url": None
        },
        {
            "title": "Тест 1: Основы",
            "block_type": BlockType.auto_test.value,
            "order_index": 2,
            "text_content": None,
            "video_url": None
        },
        # Stage 2
        {
            "title": "Лекция 2: Углубление",
            "block_type": BlockType.lesson.value,
            "order_index": 3,
            "text_content": "Второй этап посвящен более глубоким темам.",
            "video_url": None
        },
        {
            "title": "Тест 2: Проверка углубленных знаний",
            "block_type": BlockType.auto_test.value,
            "order_index": 4,
            "text_content": None,
            "video_url": None
        },
        # Stage 3
        {
            "title": "Лекция 3: Заключение",
            "block_type": BlockType.lesson.value,
            "order_index": 5,
            "text_content": "На финальном этапе мы подводим итоги.",
            "video_url": None
        },
        {
            "title": "Тест 3: Финальный экзамен",
            "block_type": BlockType.auto_test.value,
            "order_index": 6,
            "text_content": None,
            "video_url": None
        }
    ]
    
    created_blocks = []
    for block_payload in blocks_to_create:
        block_response = await client.post(
            f"/api/v1/courses/{course_id}/blocks/",
            json=block_payload,
            headers=superuser_token_headers
        )
        assert block_response.status_code == 201, f"Failed to create block {block_payload['title']}: {block_response.text}"
        created_blocks.append(block_response.json())
        
    # 3. Retrieve blocks for the course to verify they form 3 stages
    get_response = await client.get(
        f"/api/v1/courses/{course_id}/blocks/",
        headers=superuser_token_headers
    )
    assert get_response.status_code == 200, f"Failed to retrieve blocks: {get_response.text}"
    course_blocks_data = get_response.json()
    
    assert course_blocks_data["all_stages"] == 3, f"Expected 3 stages, but got {course_blocks_data['all_stages']}"
    assert course_blocks_data["all_blocks"] == 6, f"Expected 6 blocks total, but got {course_blocks_data['all_blocks']}"
    
    # Verify stages of each returned block
    blocks_list = course_blocks_data["blocks"]
    assert len(blocks_list) == 6
    for idx, block in enumerate(blocks_list):
        expected_stage = (idx // 2) + 1
        assert block["stage"] == expected_stage, f"Block {block['title']} at index {idx} should be stage {expected_stage}, but got {block['stage']}"


@pytest.mark.anyio
async def test_create_invalid_sequence_one_lesson_two_tests_fails(client: AsyncClient, superuser_token_headers: dict):
    # 1. Create a new course
    course_payload = {
        "title": "Курс с невалидной структурой",
        "description": "Попытка добавить 1 лекцию и 2 теста.",
        "level": CourseLevel.beginner.value,
        "audience": CourseAudience.everyone.value,
        "is_published": True
    }
    
    course_response = await client.post("/api/v1/courses/", json=course_payload, headers=superuser_token_headers)
    assert course_response.status_code == 201
    course_id = course_response.json()["id"]
    
    # 2. Add first block (Lesson, index=1) -> Should succeed
    b1_payload = {
        "title": "Лекция 1",
        "block_type": BlockType.lesson.value,
        "order_index": 1,
        "text_content": "Теория"
    }
    b1_resp = await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b1_payload, headers=superuser_token_headers)
    assert b1_resp.status_code == 201
    
    # 3. Add second block (Test, index=2) -> Should succeed
    b2_payload = {
        "title": "Тест 1",
        "block_type": BlockType.auto_test.value,
        "order_index": 2
    }
    b2_resp = await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b2_payload, headers=superuser_token_headers)
    assert b2_resp.status_code == 201
    
    # 4. Add third block (Test, index=3) -> Should fail with 400 Bad Request
    # because the sorted sequence would be: Lesson (1), Test (2), Test (3),
    # which violates the even-lesson / odd-test alternating validation.
    b3_payload = {
        "title": "Тест 2 (ошибка последовательности)",
        "block_type": BlockType.auto_test.value,
        "order_index": 3
    }
    b3_resp = await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b3_payload, headers=superuser_token_headers)
    
    assert b3_resp.status_code == 400
    assert "Нарушена последовательность этапов" in b3_resp.json()["detail"]
    assert "должен быть лекцией" in b3_resp.json()["detail"]


@pytest.mark.anyio
async def test_create_two_lessons_and_one_test_fails_if_consecutive(client: AsyncClient, superuser_token_headers: dict):
    # 1. Create a course
    course_payload = {
        "title": "Курс 2 лекции подряд",
        "description": "Попытка добавить 2 лекции подряд, а потом тест.",
        "level": CourseLevel.beginner.value,
        "audience": CourseAudience.everyone.value,
        "is_published": True
    }
    course_response = await client.post("/api/v1/courses/", json=course_payload, headers=superuser_token_headers)
    assert course_response.status_code == 201
    course_id = course_response.json()["id"]

    # 2. Add first block (Lesson, index=1) -> Should succeed
    b1_payload = {
        "title": "Лекция 1",
        "block_type": BlockType.lesson.value,
        "order_index": 1,
        "text_content": "Теория 1"
    }
    b1_resp = await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b1_payload, headers=superuser_token_headers)
    assert b1_resp.status_code == 201

    # 3. Add second block (Lesson, index=2) -> Should fail immediately because
    # sorted list would be [Lesson (1), Lesson (2)], where the second block is at odd index 1
    # which must be a test.
    b2_payload = {
        "title": "Лекция 2",
        "block_type": BlockType.lesson.value,
        "order_index": 2,
        "text_content": "Теория 2"
    }
    b2_resp = await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b2_payload, headers=superuser_token_headers)
    assert b2_resp.status_code == 400
    assert "Нарушена последовательность этапов" in b2_resp.json()["detail"]
    assert "должен быть тестом" in b2_resp.json()["detail"]


@pytest.mark.anyio
async def test_create_two_lessons_and_one_test_succeeds_if_alternating(client: AsyncClient, superuser_token_headers: dict):
    # 1. Create a course
    course_payload = {
        "title": "Курс с корректным чередованием",
        "description": "2 лекции и 1 тест, расположенные в чередующемся порядке.",
        "level": CourseLevel.beginner.value,
        "audience": CourseAudience.everyone.value,
        "is_published": True
    }
    course_response = await client.post("/api/v1/courses/", json=course_payload, headers=superuser_token_headers)
    assert course_response.status_code == 201
    course_id = course_response.json()["id"]

    # 2. Add first block (Lesson, index=1) -> Succeeds
    b1_payload = {
        "title": "Лекция 1",
        "block_type": BlockType.lesson.value,
        "order_index": 1,
        "text_content": "Теория 1"
    }
    assert (await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b1_payload, headers=superuser_token_headers)).status_code == 201

    # 3. Add second block (Test, index=2) -> Succeeds
    b2_payload = {
        "title": "Тест 1",
        "block_type": BlockType.auto_test.value,
        "order_index": 2
    }
    assert (await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b2_payload, headers=superuser_token_headers)).status_code == 201

    # 4. Add third block (Lesson, index=3) -> Succeeds (Index 2 is even, must be Lesson)
    b3_payload = {
        "title": "Лекция 2",
        "block_type": BlockType.lesson.value,
        "order_index": 3,
        "text_content": "Теория 2"
    }
    assert (await client.post(f"/api/v1/courses/{course_id}/blocks/", json=b3_payload, headers=superuser_token_headers)).status_code == 201


