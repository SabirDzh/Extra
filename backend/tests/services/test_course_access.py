"""Tests for the single source of truth of course visibility."""

import pytest
from pydantic import ValidationError

from Domain.Enums.course import CourseAudience
from Domain.Enums.user_role import UserRole
from Services.course_access import (
    get_course_access_policy,
    get_course_notification_roles,
)
from core.schemas.course import CourseCreate, CourseUpdate


@pytest.mark.parametrize(
    ("role", "audiences"),
    [
        (
            UserRole.installer,
            {CourseAudience.everyone, CourseAudience.installer},
        ),
        (
            UserRole.seller,
            {CourseAudience.everyone, CourseAudience.seller},
        ),
        (
            UserRole.serviceman,
            {CourseAudience.everyone, CourseAudience.serviceman},
        ),
        (UserRole.buyer, set()),
        (None, set()),
    ],
)
def test_course_access_policy_for_professional_roles(
    role: UserRole | None,
    audiences: set[CourseAudience],
) -> None:
    policy = get_course_access_policy(role)

    assert policy.audiences == frozenset(audiences)
    assert policy.published_only is True


def test_admin_policy_allows_all_published_audiences() -> None:
    policy = get_course_access_policy(UserRole.admin)

    assert policy.audiences is None
    assert policy.published_only is True


def test_admin_direct_policy_allows_unpublished_courses() -> None:
    policy = get_course_access_policy(
        UserRole.admin,
        include_unpublished_for_admin=True,
    )

    assert policy.audiences is None
    assert policy.published_only is False


@pytest.mark.parametrize(
    ("audience", "roles"),
    [
        (CourseAudience.installer, (UserRole.installer,)),
        (CourseAudience.seller, (UserRole.seller,)),
        (CourseAudience.serviceman, (UserRole.serviceman,)),
        (
            CourseAudience.everyone,
            (UserRole.installer, UserRole.seller, UserRole.serviceman),
        ),
        (CourseAudience.buyer, ()),
    ],
)
def test_course_notification_roles_match_course_access(
    audience: CourseAudience,
    roles: tuple[UserRole, ...],
) -> None:
    assert get_course_notification_roles(audience) == roles


@pytest.mark.parametrize("schema", [CourseCreate, CourseUpdate])
def test_course_input_rejects_buyer_audience(schema: type[CourseCreate | CourseUpdate]) -> None:
    with pytest.raises(ValidationError):
        schema(audience=CourseAudience.buyer, title="Course")
