from core.models import AdminRoleRequest, User
from core.models.admin_role_request import AdminRoleRequestStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_pending_requests(session: AsyncSession):
    stmt = (
        select(AdminRoleRequest, User)
        .join(User, User.id == AdminRoleRequest.user_id)
        .where(AdminRoleRequest.status == AdminRoleRequestStatus.pending)
        .order_by(AdminRoleRequest.requested_at.asc())
    )
    return (await session.execute(stmt)).all()


async def get_request_with_user(
    session: AsyncSession,
    request_id,
):
    stmt = (
        select(AdminRoleRequest, User)
        .join(User, User.id == AdminRoleRequest.user_id)
        .where(AdminRoleRequest.id == request_id)
    )
    return (await session.execute(stmt)).one_or_none()
