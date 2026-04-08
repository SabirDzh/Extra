"""
Стресс-тесты для модуля детальных результатов тестов.
Охватывает 20 сценариев (краевые случаи, авторизация, различные типы заданий, перепроверки).
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from core.models.block import Block, BlockType
from core.models.course import Course
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission, TestAnswer
from core.schemas.test import TestResultStatus

async def _create_course(session: AsyncSession) -> Course:
    course = Course(
        title=f"Course {uuid.uuid4().hex[:6]}",
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

async def _create_block(session: AsyncSession, course_id: uuid.UUID, block_type=BlockType.auto_test) -> Block:
    block = Block(course_id=course_id, order_index=1, title="Test Block", block_type=block_type)
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block

async def _create_base_env(session: AsyncSession):
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice, order_index=1)
    q2 = Question(block_id=block.id, text="Q2", question_type=QuestionType.single_choice, order_index=2)
    session.add_all([q1, q2])
    await session.flush()
    
    o1_c = AnswerOption(question_id=q1.id, text="Right1", is_correct=True, order_index=1)
    o1_w = AnswerOption(question_id=q1.id, text="Wrong1", is_correct=False, order_index=2)
    o2_c = AnswerOption(question_id=q2.id, text="Right2", is_correct=True, order_index=1)
    o2_w = AnswerOption(question_id=q2.id, text="Wrong2", is_correct=False, order_index=2)
    session.add_all([o1_c, o1_w, o2_c, o2_w])
    await session.commit()
    
    return course, block, q1, q2, o1_c, o1_w, o2_c, o2_w

async def _get_auth_token(client: AsyncClient, user, password="Password12345!"):
    resp = await client.post("/api/v1/auth/login", data={"username": user.email, "password": password})
    return resp.cookies.get("auth_user", "")

@pytest.fixture
async def base_env(session: AsyncSession):
    return await _create_base_env(session)


# --- 1-6: Базовые проверки доступности и валидации (HTTP Ошибки) ---

@pytest.mark.anyio
async def test_1_unauthorized_missing_token(client: AsyncClient, base_env):
    course, block, *_ = base_env
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results")
    assert resp.status_code == 401

@pytest.mark.anyio
async def test_2_unauthorized_invalid_token(client: AsyncClient, base_env):
    course, block, *_ = base_env
    resp = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results",
        cookies={"auth_user": "invalid_fake_token"}
    )
    assert resp.status_code == 401

@pytest.mark.anyio
async def test_3_nonexistent_course(client: AsyncClient, create_user, base_env):
    _, block, *_ = base_env
    user = await create_user("u3@test.com")
    token = await _get_auth_token(client, user)
    
    resp = await client.get(
        f"/api/v1/courses/{uuid.uuid4()}/blocks/{block.id}/test-results",
        cookies={"auth_user": token}
    )
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_4_nonexistent_block(client: AsyncClient, create_user, base_env):
    course, *_ = base_env
    user = await create_user("u4@test.com")
    token = await _get_auth_token(client, user)
    
    resp = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{uuid.uuid4()}/test-results",
        cookies={"auth_user": token}
    )
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_5_not_a_test_block(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, *_ = base_env
    lesson_block = await _create_block(session, course.id, BlockType.lesson)
    user = await create_user("u5@test.com")
    token = await _get_auth_token(client, user)
    
    resp = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{lesson_block.id}/test-results",
        cookies={"auth_user": token}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Block is not a test block"

@pytest.mark.anyio
async def test_6_no_submission_yet(client: AsyncClient, create_user, base_env):
    course, block, *_ = base_env
    user = await create_user("u6@test.com")
    token = await _get_auth_token(client, user)
    
    resp = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results",
        cookies={"auth_user": token}
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# --- 7-10: Логика Auto Test ---

@pytest.mark.anyio
async def test_7_auto_test_all_correct(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, q2, o1_c, _, o2_c, _ = base_env
    user = await create_user("u7@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=2, max_score=2, is_graded=True)
    session.add(sub)
    await session.flush()
    session.add_all([
        TestAnswer(submission_id=sub.id, question_id=q1.id, selected_answer_id=o1_c.id),
        TestAnswer(submission_id=sub.id, question_id=q2.id, selected_answer_id=o2_c.id),
    ])
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_score"] == 2
    for q in data["questions"]:
        assert q["status"] == TestResultStatus.CORRECT
        assert q["score"] == 1

@pytest.mark.anyio
async def test_8_auto_test_all_wrong(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, q2, _, o1_w, _, o2_w = base_env
    user = await create_user("u8@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=0, max_score=2, is_graded=True)
    session.add(sub)
    await session.flush()
    session.add_all([
        TestAnswer(submission_id=sub.id, question_id=q1.id, selected_answer_id=o1_w.id),
        TestAnswer(submission_id=sub.id, question_id=q2.id, selected_answer_id=o2_w.id),
    ])
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_score"] == 0
    for q in data["questions"]:
        assert q["status"] == TestResultStatus.INCORRECT
        assert q["score"] == 0

@pytest.mark.anyio
async def test_9_auto_test_partial(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, q2, o1_c, _, _, o2_w = base_env
    user = await create_user("u9@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=1, max_score=2, is_graded=True)
    session.add(sub)
    await session.flush()
    session.add_all([
        TestAnswer(submission_id=sub.id, question_id=q1.id, selected_answer_id=o1_c.id),
        TestAnswer(submission_id=sub.id, question_id=q2.id, selected_answer_id=o2_w.id),
    ])
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    assert resp.status_code == 200
    data = resp.json()
    qts = {q["question_id"]: q for q in data["questions"]}
    assert qts[str(q1.id)]["status"] == TestResultStatus.CORRECT
    assert qts[str(q2.id)]["status"] == TestResultStatus.INCORRECT

@pytest.mark.anyio
async def test_10_multiple_submissions_returns_latest(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, q2, o1_c, o1_w, o2_c, o2_w = base_env
    user = await create_user("u10@test.com")
    token = await _get_auth_token(client, user)
    
    # Submission 1 (Old) - All correct
    sub1 = TestSubmission(user_id=user.id, block_id=block.id, score=2, max_score=2, is_graded=True, submitted_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    session.add(sub1)
    await session.flush()
    session.add_all([
        TestAnswer(submission_id=sub1.id, question_id=q1.id, selected_answer_id=o1_c.id),
        TestAnswer(submission_id=sub1.id, question_id=q2.id, selected_answer_id=o2_c.id),
    ])
    
    # Submission 2 (Latest) - All wrong
    sub2 = TestSubmission(user_id=user.id, block_id=block.id, score=0, max_score=2, is_graded=True, submitted_at=datetime.now(timezone.utc))
    session.add(sub2)
    await session.flush()
    session.add_all([
        TestAnswer(submission_id=sub2.id, question_id=q1.id, selected_answer_id=o1_w.id),
        TestAnswer(submission_id=sub2.id, question_id=q2.id, selected_answer_id=o2_w.id),
    ])
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["submission_id"] == str(sub2.id)
    assert data["total_score"] == 0
    assert data["questions"][0]["status"] == TestResultStatus.INCORRECT


# --- 11-13: Логика Manual Test ---

@pytest.mark.anyio
async def test_11_manual_test_ungraded(client: AsyncClient, session: AsyncSession, create_user):
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.manual_test)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.free_text, order_index=1)
    session.add(q1)
    await session.flush()
    
    user = await create_user("u11@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=None, max_score=1, is_graded=False)
    session.add(sub)
    await session.flush()
    session.add(TestAnswer(submission_id=sub.id, question_id=q1.id, text_answer="My free text answer"))
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    data = resp.json()
    assert data["questions"][0]["status"] == TestResultStatus.REQUIRES_REVIEW
    assert data["questions"][0]["score"] == 0

@pytest.mark.anyio
async def test_12_manual_test_graded_zero(client: AsyncClient, session: AsyncSession, create_user):
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.manual_test)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.free_text, order_index=1)
    session.add(q1)
    await session.flush()
    
    user = await create_user("u12@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=0, max_score=1, is_graded=True)
    session.add(sub)
    await session.flush()
    session.add(TestAnswer(submission_id=sub.id, question_id=q1.id, text_answer="Wrong answer"))
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    data = resp.json()
    assert data["questions"][0]["status"] == TestResultStatus.INCORRECT

@pytest.mark.anyio
async def test_13_manual_test_graded_full(client: AsyncClient, session: AsyncSession, create_user):
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.manual_test)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.free_text, order_index=1)
    session.add(q1)
    await session.flush()
    
    user = await create_user("u13@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=1, max_score=1, is_graded=True)
    session.add(sub)
    await session.flush()
    session.add(TestAnswer(submission_id=sub.id, question_id=q1.id, text_answer="Great answer"))
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    data = resp.json()
    assert data["questions"][0]["status"] == TestResultStatus.CORRECT
    assert data["questions"][0]["score"] == 1


# --- 14-20: Краевые случаи и нюансы ответов ---

@pytest.mark.anyio
async def test_14_unanswered_questions_marked_wrong(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, _, o1_c, _, _, _ = base_env
    user = await create_user("u14@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=1, max_score=2, is_graded=True)
    session.add(sub)
    await session.flush()
    # То есть отвечаем на 1 вопрос, а 2-й пропускаем
    session.add(TestAnswer(submission_id=sub.id, question_id=q1.id, selected_answer_id=o1_c.id))
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    data = resp.json()
    assert len(data["questions"]) == 2
    
    q2_result = next(q for q in data["questions"] if q["question_id"] != str(q1.id))
    assert q2_result["status"] == TestResultStatus.INCORRECT
    assert q2_result["user_answer"] is None

@pytest.mark.anyio
async def test_15_multiple_answers_text_concatenation(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, _, _, _, _, _ = base_env
    q1.question_type = QuestionType.multiple_choice
    await session.flush()
    
    # Добавляем для первого вопроса ещё один "правильный" вариант ответа
    o_extra = AnswerOption(question_id=q1.id, text="AnotherRight", is_correct=True, order_index=3)
    session.add(o_extra)
    await session.commit()
    
    user = await create_user("u15@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=0, max_score=2, is_graded=True)
    session.add(sub)
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    data = resp.json()
    
    q1_res = next(q for q in data["questions"] if q["question_id"] == str(q1.id))
    # Оба правильных ответа должны быть перечислены через запятую
    assert "Right1" in q1_res["correct_answer"]
    assert "AnotherRight" in q1_res["correct_answer"]

@pytest.mark.anyio
async def test_16_user_answer_is_text(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, _, _, _, _, _ = base_env
    q1.question_type = QuestionType.free_text
    o1_c = AnswerOption(question_id=q1.id, text="Expected text", is_correct=True)
    session.add(o1_c)
    await session.flush()
    
    user = await create_user("u16@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=0, max_score=2, is_graded=True)
    session.add(sub)
    await session.flush()
    # Ответ дан текстом
    session.add(TestAnswer(submission_id=sub.id, question_id=q1.id, text_answer="User Input Text"))
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    data = resp.json()
    
    q1_res = next(q for q in data["questions"] if q["question_id"] == str(q1.id))
    assert q1_res["user_answer"] == "User Input Text"
    assert "Expected text" in q1_res["correct_answer"]

@pytest.mark.anyio
async def test_17_different_user_submission_hidden(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, q1, _, o1_c, _, _, _ = base_env
    # User 1 submits
    user1 = await create_user("u17_1@test.com")
    sub1 = TestSubmission(user_id=user1.id, block_id=block.id, score=2, max_score=2, is_graded=True)
    session.add(sub1)
    await session.flush()
    session.add(TestAnswer(submission_id=sub1.id, question_id=q1.id, selected_answer_id=o1_c.id))
    await session.commit()
    
    # User 2 logs in but has NO submissions
    user2 = await create_user("u17_2@test.com")
    token2 = await _get_auth_token(client, user2)
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token2})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

@pytest.mark.anyio
async def test_18_course_mismatch(client: AsyncClient, session: AsyncSession, create_user, base_env):
    # block belongs to base_env course
    _, block, *_ = base_env
    # create another course completely
    course_fake = await _create_course(session)
    
    user = await create_user("u18@test.com")
    token = await _get_auth_token(client, user)
    
    resp = await client.get(f"/api/v1/courses/{course_fake.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    # Because _get_block_or_404 checks block.course_id == course_id, it returns 404
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_19_no_answers_empty_test_handled_gracefully(client: AsyncClient, session: AsyncSession, create_user):
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.auto_test)
    # Block has NO questions
    
    user = await create_user("u19@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=0, max_score=0, is_graded=True)
    session.add(sub)
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_score"] == 0
    assert len(data["questions"]) == 0

@pytest.mark.anyio
async def test_20_deleted_block_prevents_getting_results(client: AsyncClient, session: AsyncSession, create_user, base_env):
    course, block, *_ = base_env
    user = await create_user("u20@test.com")
    token = await _get_auth_token(client, user)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=1, max_score=2, is_graded=True)
    session.add(sub)
    await session.commit()
    
    # Delete block
    await session.delete(block)
    await session.commit()
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies={"auth_user": token})
    assert resp.status_code == 404

