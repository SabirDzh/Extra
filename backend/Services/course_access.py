"""Centralized access rules for role-targeted course content."""

from dataclasses import dataclass
from typing import Final

from Domain.Enums.course import CourseAudience
from Domain.Enums.user_role import UserRole
from core.models.course import Course
from sqlalchemy import false
from sqlalchemy.sql import Select


ROLE_AUDIENCES: Final[dict[UserRole, CourseAudience]] = {
    UserRole.installer: CourseAudience.installer,
    UserRole.seller: CourseAudience.seller,
    UserRole.serviceman: CourseAudience.serviceman,
}
PROFESSIONAL_ROLES: Final[tuple[UserRole, ...]] = tuple(ROLE_AUDIENCES)


@dataclass(frozen=True, slots=True)
class CourseAccessPolicy:
    """Describe the courses visible to one viewer role.

    Attributes:
        audiences: Allowed course audiences. ``None`` represents unrestricted
            admin access; an empty set intentionally permits no courses.
        published_only: Whether unpublished courses must be excluded.
    """

    audiences: frozenset[CourseAudience] | None
    published_only: bool


def apply_course_access_policy(
    statement: Select,
    policy: CourseAccessPolicy,
) -> Select:
    """Constrain a query joined with ``Course`` to the viewer's visibility.

    Args:
        statement: SQLAlchemy statement that selects or joins ``Course``.
        policy: Resolved visibility rule for the requesting user.

    Returns:
        The statement with publication and audience restrictions applied.
    """
    if policy.published_only:
        statement = statement.where(Course.is_published.is_(True))

    if policy.audiences is None:
        return statement
    if not policy.audiences:
        return statement.where(false())

    return statement.where(Course.audience.in_(tuple(policy.audiences)))


def get_course_access_policy(
    role: UserRole | None,
    *,
    include_unpublished_for_admin: bool = False,
) -> CourseAccessPolicy:
    """Resolve the only supported visibility rule for a user role.

    Professional users can see their own audience and universal courses.
    Buyers and anonymous users receive an empty policy, while administrators
    can inspect every audience and may explicitly include drafts.

    Args:
        role: Current authenticated role, if available.
        include_unpublished_for_admin: Enables draft visibility for a direct
            administrative management operation.

    Returns:
        Immutable policy that callers apply before retrieving course data.
    """
    if role == UserRole.admin:
        return CourseAccessPolicy(
            audiences=None,
            published_only=not include_unpublished_for_admin,
        )

    own_audience = ROLE_AUDIENCES.get(role)
    if own_audience is None:
        return CourseAccessPolicy(audiences=frozenset(), published_only=True)

    return CourseAccessPolicy(
        audiences=frozenset({CourseAudience.everyone, own_audience}),
        published_only=True,
    )


def get_course_notification_roles(audience: CourseAudience) -> tuple[UserRole, ...]:
    """Return professional roles that are allowed to view a new course.

    Args:
        audience: Audience selected for the published course.

    Returns:
        Professional roles that should receive a new-course notification.
        Legacy buyer-only courses deliberately return no recipients.
    """
    return tuple(
        role
        for role in PROFESSIONAL_ROLES
        if audience in (get_course_access_policy(role).audiences or frozenset())
    )
