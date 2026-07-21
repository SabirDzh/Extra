import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import Block, BlockType
from core.models.course import Course, CourseEnrollment
from core.models.progress import UserBlockProgress


async def _create_admin(session: AsyncSession):
    from core.models.user import User
    from fastapi_users.password import PasswordHelper

    helper = PasswordHelper()
    admin = User(
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=helper.hash("Password12345!"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        role="administrator",
        fullname="Admin",
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def _create_user(session: AsyncSession, email: str):
    from core.models.user import User
    from fastapi_users.password import PasswordHelper

    helper = PasswordHelper()
    user = User(
        email=email,
        hashed_password=helper.hash("Password12345!"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="installer",
        fullname="User",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_course(session: AsyncSession, admin_id):
    course = Course(
        title=f"Course {uuid.uuid4().hex[:8]}",
        description="desc",
        level="beginner",
        audience="everyone",
        is_published=True,
        created_by=admin_id,
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def _add_blocks(session: AsyncSession, course_id, block_types: list[BlockType]):
    blocks = []
    for i, bt in enumerate(block_types, start=1):
        block = Block(
            course_id=course_id,
            order_index=i,
            title=f"B{i}",
            block_type=bt,
            text_content="text" if bt == BlockType.lesson else None,
        )
        session.add(block)
        await session.flush()
        blocks.append(block)
    await session.commit()
    return blocks


async def _enroll(session: AsyncSession, user_id, course_id):
    enr = CourseEnrollment(user_id=user_id, course_id=course_id)
    session.add(enr)
    await session.commit()


async def _complete_test_blocks(session: AsyncSession, user_id, blocks: list[Block]):
    for b in blocks:
        if b.block_type in {BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test}:
            session.add(UserBlockProgress(user_id=user_id, block_id=b.id, is_completed=True))
    await session.commit()


SCENARIOS = [
    (
        "lessons_and_test",
        [BlockType.lesson, BlockType.lesson, BlockType.auto_test],
        3,
        1,
    ),
    (
        "many_tests_and_lesson",
        [BlockType.auto_test, BlockType.manual_test, BlockType.mixed_test, BlockType.lesson],
        4,
        3,
    ),
    (
        "only_lessons",
        [BlockType.lesson, BlockType.lesson, BlockType.lesson],
        3,
        0,
    ),
    (
        "only_tests",
        [BlockType.auto_test, BlockType.manual_test],
        2,
        2,
    ),
    (
        "test_then_lesson",
        [BlockType.auto_test, BlockType.lesson],
        2,
        1,
    ),
    (
        "one_stage_then_lesson_without_test",
        [BlockType.lesson, BlockType.auto_test, BlockType.lesson],
        3,
        1,
    ),
]

@pytest.mark.anyio
@pytest.mark.parametrize("_name,block_types,expected_total_tests,expected_completed_tests", SCENARIOS)
async def test_profile_courses_progress_matches_courses_logic(
    auth_client: AsyncClient,
    session: AsyncSession,
    _name: str,
    block_types: list[BlockType],
    expected_total_tests: int,
    expected_completed_tests: int,
):
    admin = await _create_admin(session)
    user = await _create_user(session, f"user_{uuid.uuid4().hex[:8]}@test.com")

    course = await _create_course(session, admin.id)
    blocks = await _add_blocks(session, course.id, block_types)
    await _enroll(session, user.id, course.id)
    await _complete_test_blocks(session, user.id, blocks)

    login = await auth_client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "Password12345!"},
    )
    token = login.cookies.get("fastapiusersauth") or ""

    resp = await auth_client.get(
        "/api/v1/profile/courses-progress",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert resp.status_code == 200

    row = next((x for x in resp.json() if x["course_id"] == str(course.id)), None)
    assert row is not None

    expected_all_total = expected_total_tests
    expected_completed_stages = expected_completed_tests
    expected_percent = (
        0.0
        if expected_all_total == 0
        else round((expected_completed_stages / expected_all_total) * 100, 2)
    )
    expected_status = (
        "not_started"
        if expected_completed_stages == 0
        else ("completed" if expected_completed_stages >= expected_all_total else "in_progress")
    )

    assert row["title"] == course.title
    assert row["all_total"] == expected_all_total
    assert row["completed"] == expected_completed_stages
    assert row["percent"] == expected_percent
    assert row["status"] == expected_status

    # Course-level percent endpoint uses test blocks only.
    course_progress = await auth_client.get(
        f"/api/v1/courses/{course.id}/progress",
        cookies={"fastapiusersauth": token} if token else {},
    )
    assert course_progress.status_code == 200
    course_progress_body = course_progress.json()
    expected_course_percent = (
        0.0
        if expected_total_tests == 0
        else round((expected_completed_tests / expected_total_tests) * 100, 2)
    )
    assert course_progress_body["total"] == expected_total_tests
    assert course_progress_body["completed"] == expected_completed_tests
    assert course_progress_body["percent"] == expected_course_percent
