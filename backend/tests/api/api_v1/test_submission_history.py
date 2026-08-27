"""
Tests for GET /courses/{course_id}/blocks/{block_id}/submission-history

- 5 failure tests (4xx)
- 5 success tests (200)
- 5 edge-case / mixed tests
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import Block, BlockType
from core.models.course import Course, CourseEnrollment
from core.models.test import (
    AnswerOption,
    Question,
    QuestionType,
    TestSubmission,
)


async def _login(client: AsyncClient, email: str, password: str = "Password12345!") -> dict:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    token = resp.cookies.get("fastapiusersauth", "")
    return {"fastapiusersauth": token} if token else {}


async def _create_course_with_block(
    session: AsyncSession,
    admin_id: uuid.UUID,
    block_type: BlockType = BlockType.auto_test,
    question_type: QuestionType = QuestionType.single_choice,
    question_count: int = 1,
):
    course = Course(
        title=f"SH Course {uuid.uuid4().hex[:6]}",
        created_by=admin_id,
        is_published=True,
    )
    session.add(course)
    await session.flush()

    block = Block(
        course_id=course.id,
        title="Test Block",
        block_type=block_type,
        order_index=0,
    )
    session.add(block)
    await session.flush()

    questions = []
    options = []
    for i in range(question_count):
        q = Question(
            block_id=block.id,
            text=f"Q{i}",
            question_type=question_type,
            order_index=i,
        )
        session.add(q)
        await session.flush()
        questions.append(q)

        o = AnswerOption(
            question_id=q.id, text="Correct", is_correct=True, order_index=0
        )
        session.add(o)
        await session.flush()
        options.append(o)

        if question_type == QuestionType.multiple_choice:
            o2 = AnswerOption(
                question_id=q.id, text="Wrong", is_correct=False, order_index=1
            )
            session.add(o2)
            await session.flush()

    await session.commit()
    return course, block, questions, options


async def _enroll(session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID):
    session.add(CourseEnrollment(user_id=user_id, course_id=course_id))
    await session.commit()


async def _submit(
    client: AsyncClient, block_id: uuid.UUID, questions, options, cookies: dict
):
    answers = []
    for q, o in zip(questions, options):
        answers.append({"question_id": str(q.id), "selected_answer_id": str(o.id)})
    return await client.post(
        f"/api/v1/tests/blocks/{block_id}/submit",
        json={"answers": answers},
        cookies=cookies,
    )


# ============================================================
# FAILURE TESTS (5)
# ============================================================


class TestSubmissionHistoryFailures:

    @pytest.mark.anyio
    async def test_nonexistent_course_returns_403_or_404(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        await create_user("sh_fail1@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_fail1u@test.com")
        headers = await _login(client, "sh_fail1u@test.com")

        fake_course_id = uuid.uuid4()
        fake_block_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/courses/{fake_course_id}/blocks/{fake_block_id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code in (403, 404)

    @pytest.mark.anyio
    async def test_nonexistent_block_returns_404(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_fail2@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_fail2u@test.com")
        course = Course(title="SH Fail2", created_by=admin.id, is_published=True)
        session.add(course)
        await session.commit()
        await _enroll(session, user.id, course.id)

        headers = await _login(client, "sh_fail2u@test.com")
        fake_block_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{fake_block_id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_lesson_block_returns_400(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_fail3@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_fail3u@test.com")
        course = Course(title="SH Fail3", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(
            course_id=course.id, title="Lesson", block_type=BlockType.lesson, order_index=0
        )
        session.add(block)
        await session.commit()
        await _enroll(session, user.id, course.id)

        headers = await _login(client, "sh_fail3u@test.com")
        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_no_submissions_returns_404(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_fail4@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_fail4u@test.com")
        course, block, _, _ = await _create_course_with_block(session, admin.id)
        await _enroll(session, user.id, course.id)

        headers = await _login(client, "sh_fail4u@test.com")
        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_anonymous_user_gets_401(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_fail5@test.com", is_superuser=True, role="administrator")
        course, block, _, _ = await _create_course_with_block(session, admin.id)

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
        )
        assert resp.status_code == 401


# ============================================================
# SUCCESS TESTS (5)
# ============================================================


class TestSubmissionHistorySuccess:

    @pytest.mark.anyio
    async def test_single_correct_submission(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_ok1@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_ok1u@test.com")
        course, block, questions, options = await _create_course_with_block(session, admin.id)
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_ok1u@test.com")

        await _submit(client, block.id, questions, options, headers)

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_attempts"] == 1
        assert data["block_id"] == str(block.id)
        assert len(data["submissions"]) == 1
        sub = data["submissions"][0]
        assert sub["score"] is not None
        assert sub["score"] > 0

    @pytest.mark.anyio
    async def test_multiple_submissions_ordered_desc(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_ok2@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_ok2u@test.com")
        course, block, questions, options = await _create_course_with_block(session, admin.id)
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_ok2u@test.com")

        for _ in range(3):
            await _submit(client, block.id, questions, options, headers)

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_attempts"] == 3
        timestamps = [s["submitted_at"] for s in data["submissions"]]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.anyio
    async def test_free_text_question_shows_requires_review(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_ok3@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_ok3u@test.com")
        course, block, questions, _ = await _create_course_with_block(
            session, admin.id, question_type=QuestionType.free_text
        )
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_ok3u@test.com")

        resp = await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={
                "answers": [
                    {"question_id": str(questions[0].id), "text_answer": "My answer"}
                ]
            },
            cookies=headers,
        )
        assert resp.status_code == 200

        hist = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert hist.status_code == 200
        q_result = hist.json()["submissions"][0]["questions"][0]
        assert q_result["status"] == "Требует проверки"
        assert q_result["user_answer"] == "My answer"

    @pytest.mark.anyio
    async def test_manual_test_block_shows_not_graded(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_ok5@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_ok5u@test.com")
        course, block, questions, options = await _create_course_with_block(
            session, admin.id, block_type=BlockType.manual_test
        )
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_ok5u@test.com")
        await _submit(client, block.id, questions, options, headers)

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 200
        sub = resp.json()["submissions"][0]
        assert sub["is_graded"] is False

    @pytest.mark.anyio
    async def test_history_includes_question_results(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_ok4@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_ok4u@test.com")
        course, block, questions, options = await _create_course_with_block(
            session, admin.id, question_count=2
        )
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_ok4u@test.com")
        await _submit(client, block.id, questions, options, headers)

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 200
        qs = resp.json()["submissions"][0]["questions"]
        assert len(qs) == 2
        assert all(q["status"] == "Верно" for q in qs)


# ============================================================
# EDGE CASE TESTS (5)
# ============================================================


class TestSubmissionHistoryEdgeCases:

    @pytest.mark.anyio
    async def test_wrong_answer_shows_incorrect(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_edge1@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_edge1u@test.com")
        course, block, questions, _ = await _create_course_with_block(session, admin.id)
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_edge1u@test.com")

        wrong_opt = AnswerOption(
            question_id=questions[0].id, text="Wrong", is_correct=False, order_index=1
        )
        session.add(wrong_opt)
        await session.commit()

        await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={
                "answers": [
                    {
                        "question_id": str(questions[0].id),
                        "selected_answer_id": str(wrong_opt.id),
                    }
                ]
            },
            cookies=headers,
        )

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        q_result = resp.json()["submissions"][0]["questions"][0]
        assert q_result["status"] == "Неверно"
        assert q_result["score"] == 0

    @pytest.mark.anyio
    async def test_free_text_answer_recorded_correctly(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_edge2@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_edge2u@test.com")
        course, block, questions, _ = await _create_course_with_block(
            session, admin.id, block_type=BlockType.manual_test,
            question_type=QuestionType.free_text,
        )
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_edge2u@test.com")

        await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={
                "answers": [
                    {"question_id": str(questions[0].id), "text_answer": "My text answer"}
                ]
            },
            cookies=headers,
        )

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 200
        sub = resp.json()["submissions"][0]
        assert sub["is_graded"] is False
        q_result = sub["questions"][0]
        assert q_result["user_answer"] == "My text answer"
        assert q_result["status"] == "Требует проверки"

    @pytest.mark.anyio
    async def test_multiple_questions_all_answered(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_edge3@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_edge3u@test.com")
        course, block, questions, options = await _create_course_with_block(
            session, admin.id, question_count=3
        )
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_edge3u@test.com")
        await _submit(client, block.id, questions, options, headers)

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["submissions"][0]["questions"]) == 3

    @pytest.mark.anyio
    async def test_mixed_test_block_history(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_edge4@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_edge4u@test.com")
        course, block, _, _ = await _create_course_with_block(
            session, admin.id, block_type=BlockType.mixed_test
        )

        q_text = Question(
            block_id=block.id,
            text="Free Q",
            question_type=QuestionType.free_text,
            order_index=1,
        )
        session.add(q_text)
        await session.commit()

        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_edge4u@test.com")

        q_auto = (await session.execute(
            select(Question).where(Question.block_id == block.id, Question.order_index == 0)
        )).scalar_one()
        o_auto = (await session.execute(
            select(AnswerOption).where(AnswerOption.question_id == q_auto.id)
        )).scalar_one()

        await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={
                "answers": [
                    {"question_id": str(q_auto.id), "selected_answer_id": str(o_auto.id)},
                    {"question_id": str(q_text.id), "text_answer": "My free text"},
                ]
            },
            cookies=headers,
        )

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        assert resp.status_code == 200
        qs = resp.json()["submissions"][0]["questions"]
        auto_q = next(q for q in qs if q["question_id"] == str(q_auto.id))
        free_q = next(q for q in qs if q["question_id"] == str(q_text.id))
        assert auto_q["status"] == "Верно"
        assert free_q["status"] == "Требует проверки"

    @pytest.mark.anyio
    async def test_each_submission_independent_results(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sh_edge5@test.com", is_superuser=True, role="administrator")
        user = await create_user("sh_edge5u@test.com")
        course, block, questions, options = await _create_course_with_block(session, admin.id)
        await _enroll(session, user.id, course.id)
        headers = await _login(client, "sh_edge5u@test.com")

        await _submit(client, block.id, questions, options, headers)

        wrong_opt = AnswerOption(
            question_id=questions[0].id, text="Wrong", is_correct=False, order_index=1
        )
        session.add(wrong_opt)
        await session.commit()
        await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={
                "answers": [
                    {
                        "question_id": str(questions[0].id),
                        "selected_answer_id": str(wrong_opt.id),
                    }
                ]
            },
            cookies=headers,
        )

        resp = await client.get(
            f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history",
            cookies=headers,
        )
        subs = resp.json()["submissions"]
        assert len(subs) == 2
        scores = [s["score"] for s in subs]
        assert set(scores) == {0.0, 1.0}
        assert subs[0]["submitted_at"] >= subs[1]["submitted_at"]
