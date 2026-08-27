"""Role-scoped visibility tests for user-facing course endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.block import Block, BlockType
from core.models.course import Course, CourseAudience, CourseEnrollment, CourseLevel
from core.models.progress import UserBlockProgress


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "Password12345!"},
    )
    assert response.status_code == 204
    return {}


async def _create_course(
    session: AsyncSession,
    creator_id: uuid.UUID,
    audience: CourseAudience,
    *,
    is_published: bool = True,
) -> Course:
    course = Course(
        title=f"{audience.value}-{uuid.uuid4().hex}",
        description="Role visibility course",
        level=CourseLevel.beginner,
        audience=audience,
        is_published=is_published,
        created_by=creator_id,
    )
    session.add(course)
    await session.commit()
    return course


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("role", "expected_audiences"),
    [
        ("installer", {"everyone", "installer"}),
        ("seller", {"everyone", "seller"}),
        ("serviceman", {"everyone", "serviceman"}),
    ],
)
async def test_list_and_search_show_only_viewer_audiences(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
    role: str,
    expected_audiences: set[str],
) -> None:
    admin = await create_user(
        f"role-visibility-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    user = await create_user(f"role-visibility-{role}-{uuid.uuid4().hex}@test.com", role=role)
    for audience in CourseAudience:
        await _create_course(session, admin.id, audience)

    cookies = await _login(client, user.email)
    list_response = await client.get("/api/v1/courses/?limit=50", cookies=cookies)
    search_response = await client.get(
        "/api/v1/courses/search?limit=50&q=Role visibility",
        cookies=cookies,
    )

    assert list_response.status_code == 200
    assert search_response.status_code == 200
    assert {course["audience"] for course in list_response.json()} == expected_audiences
    assert {course["audience"] for course in search_response.json()} == expected_audiences


@pytest.mark.anyio
async def test_audience_filter_cannot_expand_installer_access(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
) -> None:
    admin = await create_user(
        f"filter-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    installer = await create_user(f"filter-installer-{uuid.uuid4().hex}@test.com")
    await _create_course(session, admin.id, CourseAudience.seller)
    await _create_course(session, admin.id, CourseAudience.installer)

    cookies = await _login(client, installer.email)
    response = await client.get(
        "/api/v1/courses/?audience=seller&limit=50",
        cookies=cookies,
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_admin_sees_published_and_draft_courses_everywhere(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
) -> None:
    admin = await create_user(
        f"draft-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    published = await _create_course(session, admin.id, CourseAudience.everyone)
    draft = await _create_course(
        session,
        admin.id,
        CourseAudience.installer,
        is_published=False,
    )

    cookies = await _login(client, admin.email)
    list_response = await client.get("/api/v1/courses/?limit=50", cookies=cookies)
    search_response = await client.get(
        "/api/v1/courses/search?limit=50&q=Role visibility",
        cookies=cookies,
    )
    global_search_response = await client.get(
        "/api/v1/search/?q=Role visibility",
        cookies=cookies,
    )

    expected_ids = {str(published.id), str(draft.id)}
    assert {course["id"] for course in list_response.json()} == expected_ids
    assert {course["id"] for course in search_response.json()} == expected_ids
    assert {course["id"] for course in global_search_response.json()["courses"]} == expected_ids


@pytest.mark.anyio
async def test_inaccessible_and_unpublished_courses_are_not_available_by_id(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
) -> None:
    admin = await create_user(
        f"direct-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    installer = await create_user(f"direct-installer-{uuid.uuid4().hex}@test.com")
    seller_course = await _create_course(session, admin.id, CourseAudience.seller)
    draft_installer_course = await _create_course(
        session,
        admin.id,
        CourseAudience.installer,
        is_published=False,
    )
    everyone_course = await _create_course(session, admin.id, CourseAudience.everyone)

    cookies = await _login(client, installer.email)
    for path in (
        f"/api/v1/courses/{seller_course.id}",
        f"/api/v1/courses/{seller_course.id}/progress",
        f"/api/v1/courses/{draft_installer_course.id}",
    ):
        response = await client.get(path, cookies=cookies)
        assert response.status_code == 404

    enroll_response = await client.post(
        f"/api/v1/courses/{seller_course.id}/enroll",
        cookies=cookies,
    )
    assert enroll_response.status_code == 404

    visible_response = await client.get(
        f"/api/v1/courses/{everyone_course.id}",
        cookies=cookies,
    )
    assert visible_response.status_code == 200


@pytest.mark.anyio
async def test_buyer_has_no_access_to_course_router(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
) -> None:
    admin = await create_user(
        f"buyer-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    buyer = await create_user(f"buyer-{uuid.uuid4().hex}@test.com", role="buyer")
    course = await _create_course(session, admin.id, CourseAudience.everyone)
    session.add(CourseEnrollment(user_id=buyer.id, course_id=course.id))
    await session.commit()

    cookies = await _login(client, buyer.email)
    for method, path in (
        (client.get, "/api/v1/courses/"),
        (client.get, "/api/v1/courses/search"),
        (client.get, f"/api/v1/courses/{course.id}"),
        (client.post, f"/api/v1/courses/{course.id}/enroll"),
    ):
        response = await method(path, cookies=cookies)
        assert response.status_code == 403

    global_search_response = await client.get("/api/v1/search/?q=Role visibility", cookies=cookies)
    profile_response = await client.get("/api/v1/profile/courses-progress", cookies=cookies)
    assert global_search_response.status_code == 200
    assert global_search_response.json()["courses"] == []
    assert profile_response.status_code == 200
    assert profile_response.json() == []


@pytest.mark.anyio
async def test_nested_blocks_and_test_endpoints_hide_inaccessible_courses(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
) -> None:
    admin = await create_user(
        f"nested-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    installer = await create_user(f"nested-installer-{uuid.uuid4().hex}@test.com")
    seller_course = await _create_course(session, admin.id, CourseAudience.seller)
    lesson = Block(
        course_id=seller_course.id,
        title="Seller lesson",
        block_type=BlockType.lesson,
        order_index=0,
    )
    test_block = Block(
        course_id=seller_course.id,
        title="Seller test",
        block_type=BlockType.auto_test,
        order_index=1,
    )
    session.add(lesson)
    await session.flush()
    session.add(test_block)
    await session.commit()

    cookies = await _login(client, installer.email)
    for path in (
        f"/api/v1/courses/{seller_course.id}/blocks/",
        f"/api/v1/courses/{seller_course.id}/blocks/{lesson.id}",
        f"/api/v1/tests/blocks/{test_block.id}/questions",
    ):
        response = await client.get(path, cookies=cookies)
        assert response.status_code == 404

    response = await client.post(
        f"/api/v1/tests/blocks/{test_block.id}/submit",
        cookies=cookies,
        json={"answers": []},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_search_and_profile_hide_inaccessible_course_activity(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
) -> None:
    admin = await create_user(
        f"profile-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    installer = await create_user(f"profile-installer-{uuid.uuid4().hex}@test.com")
    seller_course = await _create_course(session, admin.id, CourseAudience.seller)
    everyone_course = await _create_course(session, admin.id, CourseAudience.everyone)
    session.add(CourseEnrollment(user_id=installer.id, course_id=seller_course.id))
    await session.commit()

    cookies = await _login(client, installer.email)
    search_response = await client.get(
        "/api/v1/search/?q=Role visibility",
        cookies=cookies,
    )
    progress_response = await client.get(
        "/api/v1/profile/courses-progress",
        cookies=cookies,
    )
    recent_response = await client.get(
        "/api/v1/profile/recent-courses",
        cookies=cookies,
    )

    assert search_response.status_code == 200
    assert {item["id"] for item in search_response.json()["courses"]} == {
        str(everyone_course.id)
    }
    assert progress_response.status_code == 200
    assert progress_response.json() == []
    assert recent_response.status_code == 200
    assert recent_response.json() == []


@pytest.mark.anyio
async def test_certificate_generation_requires_visible_course(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
) -> None:
    admin = await create_user(
        f"certificate-admin-{uuid.uuid4().hex}@test.com",
        is_superuser=True,
        role="administrator",
    )
    installer = await create_user(f"certificate-installer-{uuid.uuid4().hex}@test.com")
    seller_course = await _create_course(session, admin.id, CourseAudience.seller)
    lesson = Block(
        course_id=seller_course.id,
        title="Completed seller lesson",
        block_type=BlockType.lesson,
        order_index=0,
    )
    session.add(lesson)
    await session.flush()
    session.add(
        UserBlockProgress(
            user_id=installer.id,
            block_id=lesson.id,
            is_completed=True,
        )
    )
    await session.commit()

    cookies = await _login(client, installer.email)
    response = await client.post(
        f"/api/v1/certificates/courses/{seller_course.id}/generate",
        cookies=cookies,
    )

    assert response.status_code == 404

    automatic_response = await client.get("/api/v1/profile/certificates", cookies=cookies)
    assert automatic_response.status_code == 200
    assert automatic_response.json() == []
