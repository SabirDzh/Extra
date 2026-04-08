import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import Block, BlockType
from core.models.course import Course
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission, TestAnswer
from core.schemas.test import TestResultStatus

# --- Вспомогательные функции для подготовки окружения ---

async def _create_course(session: AsyncSession, user_id=None) -> Course:
    course = Course(
        title=f"QA Test Course {uuid.uuid4().hex[:6]}",
        description="Course for 50 QA test cases",
        level="beginner",
        audience="everyone",
        is_published=True,
        created_by=user_id or uuid.uuid4(),
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course

async def _create_block(session: AsyncSession, course_id: uuid.UUID, block_type=BlockType.mixed_test, title="QA Block") -> Block:
    block = Block(course_id=course_id, order_index=1, title=title, block_type=block_type)
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block

async def _get_auth_cookies(client: AsyncClient, user, password="Password12345!"):
    resp = await client.post("/api/v1/auth/login", data={"username": user.email, "password": password})
    return {"auth_user": resp.cookies.get("auth_user", "")}

# --- 1-10: Базовая логика и типы блоков ---

@pytest.mark.anyio
async def test_01_create_mixed_block_success(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin1@test.com", is_superuser=True, role="administrator")
    cookies = await _get_auth_cookies(client, admin)
    course = await _create_course(session, admin.id)
    
    resp = await client.post(
        f"/api/v1/courses/{course.id}/blocks/",
        json={"title": "Mixed Test Block", "block_type": "mixed_test", "order_index": 10},
        cookies=cookies
    )
    assert resp.status_code == 201
    assert resp.json()["block_type"] == "mixed_test"

@pytest.mark.anyio
async def test_02_create_block_invalid_type(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin2@test.com", is_superuser=True, role="administrator")
    cookies = await _get_auth_cookies(client, admin)
    course = await _create_course(session, admin.id)
    
    resp = await client.post(
        f"/api/v1/courses/{course.id}/blocks/",
        json={"title": "Invalid Block", "block_type": "super_test_123", "order_index": 1},
        cookies=cookies
    )
    assert resp.status_code == 422 # Pydantic validation error

@pytest.mark.anyio
async def test_03_submit_mixed_test_flow(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user3@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.mixed_test)
    
    # Добавляем вопрос
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
    session.add(q1)
    await session.commit()
    
    resp = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={"answers": []},
        cookies=cookies
    )
    assert resp.status_code == 200
    assert resp.json()["block_id"] == str(block.id)

@pytest.mark.anyio
async def test_04_mixed_with_free_text_is_not_graded(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user4@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.mixed_test)
    q1 = Question(block_id=block.id, text="Text Q", question_type=QuestionType.free_text)
    session.add(q1)
    await session.commit()
    
    resp = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={"answers": [{"question_id": str(q1.id), "text_answer": "Hello"}]},
        cookies=cookies
    )
    assert resp.json()["is_graded"] is False

@pytest.mark.anyio
async def test_05_mixed_always_requires_admin(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user5@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.mixed_test)
    q1 = Question(block_id=block.id, text="Choice Q", question_type=QuestionType.single_choice)
    session.add(q1)
    await session.commit()
    
    resp = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={"answers": []},
        cookies=cookies
    )
    assert resp.json()["is_graded"] is False

@pytest.mark.parametrize("role, expected_status", [("user", 403), ("admin", 200)])
@pytest.mark.anyio
async def test_06_07_access_control_submissions(client: AsyncClient, session: AsyncSession, create_user, role, expected_status):
    admin = await create_user("qa_admin6@test.com", is_superuser=True, role="administrator")
    user = await create_user("qa_user6@test.com")
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    
    # User submits
    sub = TestSubmission(user_id=user.id, block_id=block.id, max_score=1, is_graded=False)
    session.add(sub)
    await session.commit()
    
    target_user = user if role == "user" else admin
    cookies = await _get_auth_cookies(client, target_user)
    
    resp = await client.get(f"/api/v1/tests/blocks/{block.id}/submissions", cookies=cookies)
    assert resp.status_code == expected_status

@pytest.mark.anyio
async def test_08_auto_test_still_fully_auto(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user8@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.auto_test)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
    session.add(q1)
    await session.flush()
    opt = AnswerOption(question_id=q1.id, text="Correct", is_correct=True)
    session.add(opt)
    await session.commit()
    
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                             json={"answers": [{"question_id": str(q1.id), "selected_answer_id": str(opt.id)}]},
                             cookies=cookies)
    assert resp.json()["score"] == 1
    assert resp.json()["is_graded"] is True

@pytest.mark.anyio
async def test_09_manual_test_still_needs_admin(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user9@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.manual_test)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
    session.add(q1)
    await session.commit()
    
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    assert resp.json()["is_graded"] is False # manual_test is NEVER auto-graded fully if it uses manual logic

@pytest.mark.anyio
async def test_10_cascade_delete_block(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin10@test.com", is_superuser=True, role="administrator")
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
    session.add(q1)
    await session.commit()
    
    await session.delete(block)
    await session.commit()
    
    q_check = (await session.execute(select(Question).where(Question.block_id == block.id))).scalar()
    assert q_check is None

# --- 11-20: Автоматическое оценивание (Choices) ---

@pytest.mark.anyio
async def test_11_12_single_choice_logic(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user11@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
    session.add(q1)
    await session.flush()
    c_opt = AnswerOption(question_id=q1.id, text="C", is_correct=True)
    w_opt = AnswerOption(question_id=q1.id, text="W", is_correct=False)
    session.add_all([c_opt, w_opt])
    await session.commit()
    
    # Test 11: Right
    r_right = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                                json={"answers": [{"question_id": str(q1.id), "selected_answer_id": str(c_opt.id)}]}, cookies=cookies)
    assert r_right.json()["score"] == 1
    
    # Test 12: Wrong
    r_wrong = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                                json={"answers": [{"question_id": str(q1.id), "selected_answer_id": str(w_opt.id)}]}, cookies=cookies)
    assert r_wrong.json()["score"] == 0

@pytest.mark.anyio
async def test_14_15_16_multiple_choice_combinations(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user14@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q = Question(block_id=block.id, text="Multi", question_type=QuestionType.multiple_choice)
    session.add(q)
    await session.flush()
    o1 = AnswerOption(question_id=q.id, text="O1", is_correct=True)
    o2 = AnswerOption(question_id=q.id, text="O2", is_correct=True)
    o3 = AnswerOption(question_id=q.id, text="O3", is_correct=False)
    session.add_all([o1, o2, o3])
    await session.commit()
    
    # 14: Exact match (Success)
    r1 = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                           json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o1.id)}, 
                                             {"question_id": str(q.id), "selected_answer_id": str(o2.id)}]}, cookies=cookies)
    assert r1.json()["score"] == 1
    
    # 15: Partial match (Fail)
    r2 = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                           json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o1.id)}]}, cookies=cookies)
    assert r2.json()["score"] == 0
    
    # 16: Extra wrong (Fail)
    r3 = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                           json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o1.id)}, 
                                             {"question_id": str(q.id), "selected_answer_id": str(o2.id)},
                                             {"question_id": str(q.id), "selected_answer_id": str(o3.id)}]}, cookies=cookies)
    assert r3.json()["score"] == 0

@pytest.mark.anyio
async def test_18_partial_score_calculation(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user18@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q1 = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
    q2 = Question(block_id=block.id, text="Q2", question_type=QuestionType.single_choice)
    session.add_all([q1, q2])
    await session.flush()
    o1 = AnswerOption(question_id=q1.id, text="C1", is_correct=True)
    o2 = AnswerOption(question_id=q2.id, text="W2", is_correct=False)
    session.add_all([o1, o2])
    await session.commit()
    
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                             json={"answers": [{"question_id": str(q1.id), "selected_answer_id": str(o1.id)},
                                               {"question_id": str(q2.id), "selected_answer_id": str(o2.id)}]}, cookies=cookies)
    assert resp.json()["score"] == 1
    assert resp.json()["max_score"] == 2

@pytest.mark.anyio
async def test_20_max_score_updated_on_question_add(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user20@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    # 0 questions -> max_score 0
    r0 = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    assert r0.json()["max_score"] == 0
    
    # Add question
    q = Question(block_id=block.id, text="Q", question_type=QuestionType.single_choice)
    session.add(q)
    await session.commit()
    
    r1 = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    assert r1.json()["max_score"] == 1

# --- 21-30: Ручная проверка (Admin Workflow) ---

@pytest.mark.anyio
async def test_21_22_admin_grading_update_score(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user21@test.com")
    admin = await create_user("qa_admin21@test.com", is_superuser=True, role="administrator")
    cookies_admin = await _get_auth_cookies(client, admin)
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.manual_test)
    
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=0, max_score=5, is_graded=False)
    session.add(sub)
    await session.commit()
    
    resp = await client.post(f"/api/v1/tests/submissions/{sub.id}/grade", 
                             json={"score": 4, "admin_comment": "Good job"}, cookies=cookies_admin)
    assert resp.status_code == 200
    assert resp.json()["score"] == 4
    assert resp.json()["is_graded"] is True

@pytest.mark.anyio
async def test_24_admin_can_regrade(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin24@test.com", is_superuser=True, role="administrator")
    user = await create_user("qa_user24@test.com")
    cookies = await _get_auth_cookies(client, admin)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=1, is_graded=True)
    session.add(sub)
    await session.commit()
    
    await client.post(f"/api/v1/tests/submissions/{sub.id}/grade", json={"score": 5}, cookies=cookies)
    resp = await client.get(f"/api/v1/tests/submissions/{sub.id}", cookies=cookies)
    assert resp.json()["score"] == 5

@pytest.mark.anyio
async def test_27_graded_by_tracked(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin27@test.com", is_superuser=True, role="administrator")
    user = await create_user("qa_user27@test.com")
    cookies = await _get_auth_cookies(client, admin)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    sub = TestSubmission(user_id=user.id, block_id=block.id, score=0, is_graded=False)
    session.add(sub)
    await session.commit()
    
    await client.post(f"/api/v1/tests/submissions/{sub.id}/grade", json={"score": 10}, cookies=cookies)
    
    # Check in DB
    result = await session.execute(select(TestSubmission).where(TestSubmission.id == sub.id))
    assert result.scalar().graded_by == admin.id

@pytest.mark.anyio
async def test_30_pending_submissions_visibility(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin30@test.com", is_superuser=True, role="administrator")
    cookies = await _get_auth_cookies(client, admin)
    user = await create_user("qa_user30@test.com")
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.manual_test)
    
    # Ungraded
    sub = TestSubmission(user_id=user.id, block_id=block.id, is_graded=False)
    session.add(sub)
    await session.commit()
    
    resp = await client.get(f"/api/v1/tests/courses/{course.id}/pending-submissions", cookies=cookies)
    assert len(resp.json()) == 1

# --- 31-40: Граничные значения ---

@pytest.mark.anyio
async def test_31_zero_questions_submission(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user31@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    assert resp.json()["max_score"] == 0

@pytest.mark.anyio
async def test_32_large_text_answer(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user32@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q = Question(block_id=block.id, text="Q", question_type=QuestionType.free_text)
    session.add(q)
    await session.commit()
    
    large_text = "A" * 5000
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                             json={"answers": [{"question_id": str(q.id), "text_answer": large_text}]}, cookies=cookies)
    assert resp.status_code == 200

@pytest.mark.anyio
async def test_35_multiple_re_submissions_allowed(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user35@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    
    for _ in range(3):
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
        assert resp.status_code == 200

@pytest.mark.anyio
async def test_38_emojis_in_text_answer(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user38@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q = Question(block_id=block.id, text="Q", question_type=QuestionType.free_text)
    session.add(q)
    await session.commit()
    
    emoji_text = "🚀🔥 Привет мир! 🌍"
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                             json={"answers": [{"question_id": str(q.id), "text_answer": emoji_text}]}, cookies=cookies)
    assert resp.status_code == 200

@pytest.mark.anyio
async def test_40_submit_to_lesson_block_fails(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user40@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id, BlockType.lesson)
    
    resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    assert resp.status_code == 400
    assert "not a test" in resp.json()["detail"]

# --- 41-50: Детальные результаты ---

@pytest.mark.anyio
async def test_41_results_correct_status(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user41@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q = Question(block_id=block.id, text="Q", question_type=QuestionType.single_choice)
    session.add(q)
    await session.flush()
    opt = AnswerOption(question_id=q.id, text="C", is_correct=True)
    session.add(opt)
    await session.commit()
    
    await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                      json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(opt.id)}]}, cookies=cookies)
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies=cookies)
    assert resp.json()["questions"][0]["status"] == TestResultStatus.CORRECT

@pytest.mark.anyio
async def test_42_results_requires_review_status(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user42@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    q = Question(block_id=block.id, text="Q", question_type=QuestionType.free_text)
    session.add(q)
    await session.commit()
    
    await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies=cookies)
    assert resp.json()["questions"][0]["status"] == TestResultStatus.REQUIRES_REVIEW

@pytest.mark.anyio
async def test_47_always_returns_latest_submission(client: AsyncClient, session: AsyncSession, create_user):
    user = await create_user("qa_user47@test.com")
    cookies = await _get_auth_cookies(client, user)
    course = await _create_course(session)
    block = await _create_block(session, course.id)
    
    # Sub 1
    await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    # Sub 2
    await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []}, cookies=cookies)
    
    resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies=cookies)
    # Check count in DB
    subs = (await session.execute(select(TestSubmission).where(TestSubmission.user_id == user.id).order_by(TestSubmission.submitted_at.desc(), TestSubmission.id.desc()))).scalars().all()
    assert len(subs) == 2
    assert resp.json()["submission_id"] == str(subs[0].id)

@pytest.mark.anyio
async def test_50_full_integration_path(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin50@test.com", is_superuser=True, role="administrator")
    user = await create_user("qa_user50@test.com")
    cookies_user = await _get_auth_cookies(client, user)
    cookies_admin = await _get_auth_cookies(client, admin)
    
    # 1. Admin creates course & mixed block
    course = await _create_course(session, admin.id)
    block = await _create_block(session, course.id, BlockType.mixed_test)
    q1 = Question(block_id=block.id, text="Auto Q", question_type=QuestionType.single_choice)
    q2 = Question(block_id=block.id, text="Manual Q", question_type=QuestionType.free_text)
    session.add_all([q1, q2])
    await session.flush()
    opt = AnswerOption(question_id=q1.id, text="Correct", is_correct=True)
    session.add(opt)
    await session.commit()
    
    # 2. User submits
    resp_sub = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", 
                                 json={"answers": [{"question_id": str(q1.id), "selected_answer_id": str(opt.id)},
                                                   {"question_id": str(q2.id), "text_answer": "Text"}]}, cookies=cookies_user)
    sub_id = resp_sub.json()["id"]
    assert resp_sub.json()["is_graded"] is False
    
    # 3. Admin reviews & grades
    await client.post(f"/api/v1/tests/submissions/{sub_id}/grade", 
                      json={"score": 2}, cookies=cookies_admin)
    
    # 4. Check results finalized
    resp_res = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies=cookies_user)
    assert resp_res.json()["questions"][0]["status"] == TestResultStatus.CORRECT
    assert resp_res.json()["questions"][1]["status"] == TestResultStatus.CORRECT
    assert resp_res.json()["total_score"] == 2

@pytest.mark.anyio
async def test_51_truly_mixed_all_types(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("qa_admin51@test.com", is_superuser=True, role="administrator")
    user = await create_user("qa_user51@test.com")
    cookies_user = await _get_auth_cookies(client, user)
    cookies_admin = await _get_auth_cookies(client, admin)
    
    course = await _create_course(session, admin.id)
    block = await _create_block(session, course.id, BlockType.mixed_test)
    
    # Q1: Single Choice
    q1 = Question(block_id=block.id, text="Single", question_type=QuestionType.single_choice, order_index=1)
    # Q2: Multiple Choice
    q2 = Question(block_id=block.id, text="Multi", question_type=QuestionType.multiple_choice, order_index=2)
    # Q3: Free Text
    q3 = Question(block_id=block.id, text="Free", question_type=QuestionType.free_text, order_index=3)
    session.add_all([q1, q2, q3])
    await session.flush()
    
    o1_c = AnswerOption(question_id=q1.id, text="Q1_C", is_correct=True)
    o2_c1 = AnswerOption(question_id=q2.id, text="Q2_C1", is_correct=True)
    o2_c2 = AnswerOption(question_id=q2.id, text="Q2_C2", is_correct=True)
    session.add_all([o1_c, o2_c1, o2_c2])
    await session.commit()
    
    # 1. User submits all correct choice answers + some text
    resp_sub = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={
            "answers": [
                {"question_id": str(q1.id), "selected_answer_id": str(o1_c.id)},
                {"question_id": str(q2.id), "selected_answer_id": str(o2_c1.id)},
                {"question_id": str(q2.id), "selected_answer_id": str(o2_c2.id)},
                {"question_id": str(q3.id), "text_answer": "I believe the answer is..."}
            ]
        },
        cookies=cookies_user
    )
    assert resp_sub.status_code == 200
    data = resp_sub.json()
    assert data["score"] == 2 # 1 for q1, 1 for q2
    assert data["max_score"] == 3
    assert data["is_graded"] is False # Pending q3
    
    # 2. Check intermediate results
    resp_res = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies=cookies_user)
    results = resp_res.json()["questions"]
    assert results[0]["status"] == TestResultStatus.CORRECT # Q1 auto-graded
    assert results[1]["status"] == TestResultStatus.CORRECT # Q2 auto-graded
    assert results[2]["status"] == TestResultStatus.REQUIRES_REVIEW # Q3 pending
    
    # 3. Admin grades manual part
    await client.post(f"/api/v1/tests/submissions/{data['id']}/grade", 
                      json={"score": 3, "admin_comment": "Excellent work on the free text section!"}, cookies=cookies_admin)
    
    # 4. Final verification
    resp_final = await client.get(f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results", cookies=cookies_user)
    final_results = resp_final.json()["questions"]
    assert all(r["status"] == TestResultStatus.CORRECT for r in final_results)
    assert resp_final.json()["total_score"] == 3
