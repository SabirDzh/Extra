"""
Tests covering certificate PDF generation, profile certificates endpoint,
ensure_completed_certificates, and edge cases in the certification flow.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import Block, BlockType
from core.models.certificates import Certificate
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


async def _setup_auto_test_course(session: AsyncSession, admin_id: uuid.UUID, test_count: int = 1):
    course = Course(title=f"PDF Course {uuid.uuid4().hex[:6]}", created_by=admin_id, is_published=True)
    session.add(course)
    await session.flush()
    blocks = []
    questions = []
    options = []
    for i in range(test_count):
        b = Block(course_id=course.id, title=f"Test {i}", block_type=BlockType.auto_test, order_index=i)
        session.add(b)
        blocks.append(b)
        q = Question(block_id=b.id, text=f"Q {i}", question_type=QuestionType.single_choice, order_index=0)
        session.add(q)
        questions.append(q)
        o = AnswerOption(question_id=q.id, text="Correct", is_correct=True, order_index=0)
        session.add(o)
        options.append(o)
    await session.flush()
    await session.commit()
    return course, blocks, questions, options


# ============================================================
# PDF generation
# ============================================================

class TestCertificatePDF:
    @pytest.mark.anyio
    async def test_pdf_returns_valid_content_type(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("pdf_admin@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _setup_auto_test_course(session, admin.id, 1)
        enrollment = CourseEnrollment(user_id=admin.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()
        headers = await _login(client, "pdf_admin@test.com")

        b = blocks[0]
        q = (await session.execute(select(Question).where(Question.block_id == b.id))).scalar_one()
        o = (await session.execute(select(AnswerOption).where(AnswerOption.question_id == q.id))).scalar_one()
        await client.post(
            f"/api/v1/tests/blocks/{b.id}/submit",
            json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]},
            cookies=headers,
        )
        gen = await client.post(
            f"/api/v1/certificates/courses/{course.id}/generate", cookies=headers
        )
        cert_number = gen.json()["certificate_number"]

        resp = await client.get(f"/api/v1/certificates/{cert_number}/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    @pytest.mark.anyio
    async def test_pdf_filename_contains_certificate_number(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("pdf_fn_admin@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _setup_auto_test_course(session, admin.id, 1)
        enrollment = CourseEnrollment(user_id=admin.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()
        headers = await _login(client, "pdf_fn_admin@test.com")

        b = blocks[0]
        q = (await session.execute(select(Question).where(Question.block_id == b.id))).scalar_one()
        o = (await session.execute(select(AnswerOption).where(AnswerOption.question_id == q.id))).scalar_one()
        await client.post(
            f"/api/v1/tests/blocks/{b.id}/submit",
            json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]},
            cookies=headers,
        )
        gen = await client.post(
            f"/api/v1/certificates/courses/{course.id}/generate", cookies=headers
        )
        cert_number = gen.json()["certificate_number"]

        resp = await client.get(f"/api/v1/certificates/{cert_number}/download")
        assert cert_number in resp.headers.get("content-disposition", "")


# ============================================================
# ensure_completed_certificates from profile
# ============================================================

class TestProfileCertificatesAutoGeneration:
    @pytest.mark.anyio
    async def test_profile_certificates_auto_generates(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("pc_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("pc_user@test.com")
        course, blocks, _, _ = await _setup_auto_test_course(session, admin.id, 1)
        enrollment = CourseEnrollment(user_id=user.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()

        user_h = await _login(client, "pc_user@test.com")
        b = blocks[0]
        q = (await session.execute(select(Question).where(Question.block_id == b.id))).scalar_one()
        o = (await session.execute(select(AnswerOption).where(AnswerOption.question_id == q.id))).scalar_one()
        await client.post(
            f"/api/v1/tests/blocks/{b.id}/submit",
            json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]},
            cookies=user_h,
        )

        resp = await client.get("/api/v1/profile/certificates", cookies=user_h)
        assert resp.status_code == 200
        certs = resp.json()
        assert len(certs) >= 1
        assert "download_url" in certs[0]
        assert "certificate_number" in certs[0]

    @pytest.mark.anyio
    async def test_profile_certificates_empty_when_not_completed(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("pc_empty_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("pc_empty_user@test.com")
        course = Course(title="Empty Cert Course", created_by=admin.id, is_published=True)
        session.add(course)
        await session.flush()
        enrollment = CourseEnrollment(user_id=user.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()

        user_h = await _login(client, "pc_empty_user@test.com")
        resp = await client.get("/api/v1/profile/certificates", cookies=user_h)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    @pytest.mark.anyio
    async def test_profile_certificates_contains_course_title(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("pc_title_admin@test.com", is_superuser=True, role="administrator")
        user = await create_user("pc_title_user@test.com")
        course, blocks, _, _ = await _setup_auto_test_course(session, admin.id, 1)
        enrollment = CourseEnrollment(user_id=user.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()

        user_h = await _login(client, "pc_title_user@test.com")
        b = blocks[0]
        q = (await session.execute(select(Question).where(Question.block_id == b.id))).scalar_one()
        o = (await session.execute(select(AnswerOption).where(AnswerOption.question_id == q.id))).scalar_one()
        await client.post(
            f"/api/v1/tests/blocks/{b.id}/submit",
            json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]},
            cookies=user_h,
        )

        resp = await client.get("/api/v1/profile/certificates", cookies=user_h)
        assert resp.json()[0]["course_title"] == course.title


# ============================================================
# Certificate edge cases
# ============================================================

class TestCertificateEdgeCases:
    @pytest.mark.anyio
    async def test_generate_cert_nonexistent_course(
        self, client: AsyncClient, create_user
    ):
        admin = await create_user("edge_admin@test.com", is_superuser=True, role="administrator")
        headers = await _login(client, "edge_admin@test.com")
        resp = await client.post(
            f"/api/v1/certificates/courses/{uuid.uuid4()}/generate", cookies=headers
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_certificate_nonexistent_course(
        self, client: AsyncClient, create_user
    ):
        admin = await create_user("edge2_admin@test.com", is_superuser=True, role="administrator")
        headers = await _login(client, "edge2_admin@test.com")
        resp = await client.get(
            f"/api/v1/certificates/courses/{uuid.uuid4()}/certificate", cookies=headers
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_download_nonexistent_certificate_number(
        self, client: AsyncClient
    ):
        resp = await client.get(
            "/api/v1/certificates/00000000-0000-0000-0000-000000000000/download"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_generate_cert_course_with_zero_blocks(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("edge3_admin@test.com", is_superuser=True, role="administrator")
        course = Course(title="Zero Blocks", created_by=admin.id, is_published=True)
        session.add(course)
        await session.commit()
        enrollment = CourseEnrollment(user_id=admin.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()

        headers = await _login(client, "edge3_admin@test.com")
        resp = await client.post(
            f"/api/v1/certificates/courses/{course.id}/generate", cookies=headers
        )
        assert resp.status_code == 400
        assert "no blocks" in resp.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_generate_cert_idempotent(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("edge4_admin@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _setup_auto_test_course(session, admin.id, 1)
        enrollment = CourseEnrollment(user_id=admin.id, course_id=course.id)
        session.add(enrollment)
        await session.commit()
        headers = await _login(client, "edge4_admin@test.com")

        b = blocks[0]
        q = (await session.execute(select(Question).where(Question.block_id == b.id))).scalar_one()
        o = (await session.execute(select(AnswerOption).where(AnswerOption.question_id == q.id))).scalar_one()
        await client.post(
            f"/api/v1/tests/blocks/{b.id}/submit",
            json={"answers": [{"question_id": str(q.id), "selected_answer_id": str(o.id)}]},
            cookies=headers,
        )

        r1 = await client.post(
            f"/api/v1/certificates/courses/{course.id}/generate", cookies=headers
        )
        r2 = await client.post(
            f"/api/v1/certificates/courses/{course.id}/generate", cookies=headers
        )
        assert r1.json()["id"] == r2.json()["id"]

    @pytest.mark.anyio
    async def test_anonymous_cannot_generate_certificate(
        self, client: AsyncClient, session: AsyncSession, create_user
    ):
        admin = await create_user("edge5_admin@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _setup_auto_test_course(session, admin.id, 1)

        resp = await client.post(
            f"/api/v1/certificates/courses/{course.id}/generate"
        )
        assert resp.status_code in (401, 403)
