"""
Tests covering grading and test submission bugs:
- GradeSubmission schema type mismatch (int vs float)
- No enrollment check before test submission
- Question type validation (single_choice with 0 options)
- Block title cannot be updated for test blocks
- get_course filter_type makes course invisible
- No pagination on list_submissions
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
    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    token = resp.cookies.get("fastapiusersauth", "")
    return {"fastapiusersauth": token} if token else {}


# ============================================================
# GradeSubmission schema: score should be float, validated
# ============================================================

class TestGradeSubmissionSchema:
    @pytest.mark.anyio
    async def test_grade_with_integer_score(self, client: AsyncClient, session: AsyncSession, create_user):
        admin = await create_user("gs_int_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("gs_int_user@test.com")
        course = Course(title="GS Int Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="MT", block_type=BlockType.manual_test, order_index=0)
        session.add(block)
        await session.flush()
        q = Question(block_id=block.id, text="Q", question_type=QuestionType.free_text)
        session.add(q)
        await session.commit()

        sub = TestSubmission(user_id=user.id, block_id=block.id, max_score=5, is_graded=False)
        session.add(sub)
        await session.commit()

        admin_h = await _login(client, "gs_int_admin@test.com")
        resp = await client.post(
            f"/api/v1/tests/submissions/{sub.id}/grade",
            json={"score": 3},
            cookies=admin_h,
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == 3.0

    @pytest.mark.anyio
    async def test_grade_with_float_score(self, client: AsyncClient, session: AsyncSession, create_user):
        admin = await create_user("gs_flt_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("gs_flt_user@test.com")
        course = Course(title="GS Flt Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="MT", block_type=BlockType.manual_test, order_index=0)
        session.add(block)
        await session.flush()
        q = Question(block_id=block.id, text="Q", question_type=QuestionType.free_text)
        session.add(q)
        await session.commit()

        sub = TestSubmission(user_id=user.id, block_id=block.id, max_score=5, is_graded=False)
        session.add(sub)
        await session.commit()

        admin_h = await _login(client, "gs_flt_admin@test.com")
        resp = await client.post(
            f"/api/v1/tests/submissions/{sub.id}/grade",
            json={"score": 3.7},
            cookies=admin_h,
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == 3.7


# ============================================================
# No enrollment check before test submission
# ============================================================

class TestEnrollmentCheckOnSubmit:
    @pytest.mark.anyio
    async def test_unenrolled_user_can_submit_test(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("noenroll_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("noenroll_user@test.com")
        course = Course(title="NoEnroll Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=0)
        session.add(block)
        await session.flush()
        q = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
        session.add(q)
        await session.flush()
        o = AnswerOption(question_id=q.id, text="C", is_correct=True)
        session.add(o)
        await session.commit()

        user_h = await _login(client, "noenroll_user@test.com")
        resp = await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]},
            cookies=user_h,
        )
        assert resp.status_code == 200, "Currently no enrollment check"

    @pytest.mark.anyio
    async def test_enrolled_user_can_submit_test(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("enroll_ok_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("enroll_ok_user@test.com")
        course = Course(title="Enroll OK Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=0)
        session.add(block)
        await session.flush()
        q = Question(block_id=block.id, text="Q1", question_type=QuestionType.single_choice)
        session.add(q)
        await session.flush()
        o = AnswerOption(question_id=q.id, text="C", is_correct=True)
        session.add(o)
        await session.commit()

        enrollment = CourseEnrollment(user_id=user.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()

        user_h = await _login(client, "enroll_ok_user@test.com")
        resp = await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]},
            cookies=user_h,
        )
        assert resp.status_code == 200


# ============================================================
# Question type validation: single_choice with 0 options
# ============================================================

class TestQuestionTypeValidation:
    @pytest.mark.anyio
    async def test_single_choice_with_zero_options_created(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("qtv_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="QTV Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=0)
        session.add(block)
        await session.commit()

        admin_h = await _login(client, "qtv_admin@test.com")
        resp = await client.post(
            f"/api/v1/tests/blocks/{block.id}/questions",
            json={
                "text": "Single choice with no options",
                "question_type": "single_choice",
                "order_index": 0,
                "options": [],
            },
            cookies=admin_h,
        )
        assert resp.status_code == 201, "Currently accepts single_choice with 0 options"

    @pytest.mark.anyio
    async def test_multiple_choice_with_zero_options_created(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("qtv_mc_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="QTV MC Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=0)
        session.add(block)
        await session.commit()

        admin_h = await _login(client, "qtv_mc_admin@test.com")
        resp = await client.post(
            f"/api/v1/tests/blocks/{block.id}/questions",
            json={
                "text": "MC with no options",
                "question_type": "multiple_choice",
                "order_index": 0,
                "options": [],
            },
            cookies=admin_h,
        )
        assert resp.status_code == 201, "Currently accepts multiple_choice with 0 options"

    @pytest.mark.anyio
    async def test_single_choice_with_no_correct_option(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("qtv_nocorrect_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="QTV NoCorrect Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="T1", block_type=BlockType.auto_test, order_index=0)
        session.add(block)
        await session.commit()

        admin_h = await _login(client, "qtv_nocorrect_admin@test.com")
        resp = await client.post(
            f"/api/v1/tests/blocks/{block.id}/questions",
            json={
                "text": "SC no correct",
                "question_type": "single_choice",
                "order_index": 0,
                "options": [
                    {"text": "A", "is_correct": False, "order_index": 0},
                    {"text": "B", "is_correct": False, "order_index": 1},
                ],
            },
            cookies=admin_h,
        )
        assert resp.status_code == 201, "Currently accepts single_choice with no correct option"


# ============================================================
# Block title update silently dropped for test blocks
# ============================================================

class TestBlockTitleUpdate:
    @pytest.mark.anyio
    async def test_update_test_block_title_silently_ignored(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("btu_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="BTU Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="Original Title", block_type=BlockType.auto_test, order_index=0)
        session.add(block)
        await session.commit()

        admin_h = await _login(client, "btu_admin@test.com")
        resp = await client.patch(
            f"/api/v1/courses/{course.id}/blocks/{block.id}",
            json={"title": "New Test Title"},
            cookies=admin_h,
        )
        assert resp.status_code == 200

        await session.refresh(block)
        assert block.title == "Original Title", "Test block title was silently dropped"

    @pytest.mark.anyio
    async def test_update_lesson_block_title_changes_course_title(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("btu_lesson_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="Original Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="Original Course", block_type=BlockType.lesson, order_index=0)
        session.add(block)
        await session.commit()

        admin_h = await _login(client, "btu_lesson_admin@test.com")
        resp = await client.patch(
            f"/api/v1/courses/{course.id}/blocks/{block.id}",
            json={"title": "Updated Course"},
            cookies=admin_h,
        )
        assert resp.status_code == 200

        await session.refresh(course)
        assert course.title == "Updated Course"


# ============================================================
# get_course with filter_type makes course invisible
# ============================================================

class TestCourseFilterTypeDetail:
    @pytest.mark.anyio
    async def test_get_course_with_non_matching_filter_returns_error(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("cft_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="CFT Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.commit()

        resp = await client.get(f"/api/v1/courses/{course.id}?filter_type=completed")
        assert resp.status_code in (401, 404), (
            "Course returns 401/404 when filter_type doesn't match"
        )

    @pytest.mark.anyio
    async def test_get_course_without_filter_returns_ok(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("cft2_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="CFT2 Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.commit()

        resp = await client.get(f"/api/v1/courses/{course.id}")
        assert resp.status_code in (200, 401)


# ============================================================
# No pagination on list_submissions
# ============================================================

class TestSubmissionsPagination:
    @pytest.mark.anyio
    async def test_list_submissions_returns_all_without_pagination(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("sp_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("sp_user@test.com")
        course = Course(title="SP Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        block = Block(course_id=course.id, title="T1", block_type=BlockType.manual_test, order_index=0)
        session.add(block)
        await session.flush()
        await session.commit()

        for i in range(5):
            sub = TestSubmission(user_id=user.id, block_id=block.id, max_score=1, is_graded=False)
            session.add(sub)
            await session.flush()
        await session.commit()

        admin_h = await _login(client, "sp_admin@test.com")
        resp = await client.get(f"/api/v1/tests/blocks/{block.id}/submissions", cookies=admin_h)
        assert resp.status_code == 200
        assert len(resp.json()) == 5, "Returns all submissions without pagination"
