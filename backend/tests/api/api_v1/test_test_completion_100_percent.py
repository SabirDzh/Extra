import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import Block, BlockType
from core.models.certificates import Certificate
from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress
from core.models.test import AnswerOption, Question, QuestionType, TestSubmission


async def _login(client: AsyncClient, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "Password12345!"},
    )
    token = response.cookies.get("auth_user") or ""
    return {"auth_user": token}


async def _create_test_course(
    session: AsyncSession,
    admin_id: uuid.UUID,
    title: str,
    block_type: BlockType = BlockType.auto_test,
):
    course = Course(
        title=title,
        created_by=admin_id,
        is_published=True,
        audience="everyone",
    )
    session.add(course)
    await session.flush()

    block = Block(
        course_id=course.id,
        title="Test block",
        block_type=block_type,
        order_index=0,
    )
    session.add(block)
    await session.flush()

    question = Question(
        block_id=block.id,
        text="Question",
        question_type=QuestionType.single_choice,
        order_index=0,
    )
    session.add(question)
    await session.flush()

    correct = AnswerOption(
        question_id=question.id,
        text="Correct",
        is_correct=True,
        order_index=0,
    )
    wrong = AnswerOption(
        question_id=question.id,
        text="Wrong",
        is_correct=False,
        order_index=1,
    )
    session.add_all([correct, wrong])
    await session.commit()
    return course, block, question, correct, wrong


async def _enroll(session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID):
    session.add(CourseEnrollment(user_id=user_id, course_id=course_id))
    await session.commit()


@pytest.mark.anyio
async def test_failed_test_does_not_complete_block_or_course_or_certificate(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    admin = await create_user(
        "completion_failed_admin@test.com",
        is_superuser=True,
        role="administrator",
    )
    user = await create_user("completion_failed_user@test.com")
    course, block, question, correct, wrong = await _create_test_course(
        session, admin.id, "Failed completion course"
    )
    await _enroll(session, user.id, course.id)
    cookies = await _login(client, user.email)

    response = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={
            "answers": [
                {
                    "question_id": str(question.id),
                    "selected_answer_id": str(wrong.id),
                }
            ]
        },
        cookies=cookies,
    )

    assert response.status_code == 200
    assert response.json()["score"] == 0.0
    progress = (
        await session.execute(
            select(UserBlockProgress).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id == block.id,
            )
        )
    ).scalar_one_or_none()
    assert progress is None or progress.is_completed is False

    course_response = await client.get(
        f"/api/v1/courses/{course.id}/progress",
        cookies=cookies,
    )
    assert course_response.status_code == 200
    assert course_response.json()["completed"] == 0
    assert course_response.json()["percent"] == 0.0

    certificate_response = await client.post(
        f"/api/v1/certificates/courses/{course.id}/generate",
        cookies=cookies,
    )
    assert certificate_response.status_code == 400
    assert await session.scalar(
        select(Certificate.id).where(
            Certificate.user_id == user.id,
            Certificate.course_id == course.id,
        )
    ) is None


@pytest.mark.anyio
async def test_stale_test_progress_flag_does_not_count_without_perfect_submission(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    admin = await create_user(
        "completion_stale_admin@test.com",
        is_superuser=True,
        role="administrator",
    )
    user = await create_user("completion_stale_user@test.com")
    course, block, _, _, _ = await _create_test_course(
        session, admin.id, "Stale completion course"
    )
    await _enroll(session, user.id, course.id)
    session.add(
        UserBlockProgress(
            user_id=user.id,
            block_id=block.id,
            is_completed=True,
        )
    )
    await session.commit()
    cookies = await _login(client, user.email)

    course_response = await client.get(
        f"/api/v1/courses/{course.id}/progress",
        cookies=cookies,
    )
    assert course_response.status_code == 200
    assert course_response.json()["completed"] == 0
    assert course_response.json()["percent"] == 0.0

    certificate_response = await client.post(
        f"/api/v1/certificates/courses/{course.id}/generate",
        cookies=cookies,
    )
    assert certificate_response.status_code == 400


@pytest.mark.anyio
async def test_exactly_100_percent_completes_block_course_and_certificate(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    admin = await create_user(
        "completion_success_admin@test.com",
        is_superuser=True,
        role="administrator",
    )
    user = await create_user("completion_success_user@test.com")
    course, block, question, correct, _ = await _create_test_course(
        session, admin.id, "Successful completion course"
    )
    await _enroll(session, user.id, course.id)
    cookies = await _login(client, user.email)

    response = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={
            "answers": [
                {
                    "question_id": str(question.id),
                    "selected_answer_id": str(correct.id),
                }
            ]
        },
        cookies=cookies,
    )

    assert response.status_code == 200
    assert response.json()["score"] == response.json()["max_score"]
    progress = (
        await session.execute(
            select(UserBlockProgress).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id == block.id,
            )
        )
    ).scalar_one()
    assert progress.is_completed is True

    course_response = await client.get(
        f"/api/v1/courses/{course.id}/progress",
        cookies=cookies,
    )
    assert course_response.status_code == 200
    assert course_response.json()["completed"] == 1
    assert course_response.json()["percent"] == 100.0

    certificate_response = await client.post(
        f"/api/v1/certificates/courses/{course.id}/generate",
        cookies=cookies,
    )
    assert certificate_response.status_code == 201


@pytest.mark.anyio
async def test_later_failed_attempt_does_not_erase_previous_perfect_completion(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    admin = await create_user(
        "completion_retry_admin@test.com",
        is_superuser=True,
        role="administrator",
    )
    user = await create_user("completion_retry_user@test.com")
    course, block, question, correct, wrong = await _create_test_course(
        session, admin.id, "Retry completion course"
    )
    await _enroll(session, user.id, course.id)
    cookies = await _login(client, user.email)

    for option in (correct, wrong):
        response = await client.post(
            f"/api/v1/tests/blocks/{block.id}/submit",
            json={
                "answers": [
                    {
                        "question_id": str(question.id),
                        "selected_answer_id": str(option.id),
                    }
                ]
            },
            cookies=cookies,
        )
        assert response.status_code == 200

    course_response = await client.get(
        f"/api/v1/courses/{course.id}/progress",
        cookies=cookies,
    )
    assert course_response.json()["completed"] == 1
    assert course_response.json()["percent"] == 100.0


@pytest.mark.anyio
async def test_manual_test_requires_exact_max_score(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    admin = await create_user(
        "completion_manual_admin@test.com",
        is_superuser=True,
        role="administrator",
    )
    user = await create_user("completion_manual_user@test.com")
    course, block, question, _, _ = await _create_test_course(
        session,
        admin.id,
        "Manual completion course",
        block_type=BlockType.manual_test,
    )
    await _enroll(session, user.id, course.id)
    user_cookies = await _login(client, user.email)
    admin_cookies = await _login(client, admin.email)

    submitted = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={
            "answers": [
                {
                    "question_id": str(question.id),
                    "text_answer": "Answer",
                }
            ]
        },
        cookies=user_cookies,
    )
    assert submitted.status_code == 200
    submission_id = submitted.json()["id"]

    partial = await client.post(
        f"/api/v1/tests/submissions/{submission_id}/grade",
        json={"score": 0},
        cookies=admin_cookies,
    )
    assert partial.status_code == 200
    assert (
        await session.execute(
            select(UserBlockProgress).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id == block.id,
                UserBlockProgress.is_completed.is_(True),
            )
        )
    ).scalar_one_or_none() is None

    full = await client.post(
        f"/api/v1/tests/submissions/{submission_id}/grade",
        json={"score": 1},
        cookies=admin_cookies,
    )
    assert full.status_code == 200
    progress = (
        await session.execute(
            select(UserBlockProgress).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id == block.id,
            )
        )
    ).scalar_one()
    assert progress.is_completed is True

    enrollment = await session.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user.id,
            CourseEnrollment.course_id == course.id,
        )
    )
    assert enrollment is not None
    assert enrollment.completed_at is not None

    downgraded = await client.post(
        f"/api/v1/tests/submissions/{submission_id}/grade",
        json={"score": 0},
        cookies=admin_cookies,
    )
    assert downgraded.status_code == 200

    await session.refresh(progress)
    await session.refresh(enrollment)
    assert progress.is_completed is False
    assert enrollment.completed_at is None

    course_response = await client.get(
        f"/api/v1/courses/{course.id}/progress",
        cookies=user_cookies,
    )
    assert course_response.status_code == 200
    assert course_response.json()["completed"] == 0
    assert course_response.json()["percent"] == 0.0

    certificate_response = await client.post(
        f"/api/v1/certificates/courses/{course.id}/generate",
        cookies=user_cookies,
    )
    assert certificate_response.status_code == 400
