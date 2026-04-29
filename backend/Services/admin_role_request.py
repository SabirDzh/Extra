import uuid
from datetime import datetime, timezone

from core.config import settings
from core.models.admin_role_request import AdminRoleRequestStatus
from core.schemas.user import AdminRoleRequestRead
from Repository import admin_role_request as repo
from Domain.Enums.user_role import UserRole


async def list_pending_admin_role_requests(session):
    rows = await repo.list_pending_requests(session)
    return [
        AdminRoleRequestRead(
            id=request.id,
            user_id=owner.id,
            user_email=owner.email,
            user_fullname=owner.fullname,
            status=request.status.value,
            requested_at=request.requested_at.isoformat(),
            reviewed_at=request.reviewed_at.isoformat() if request.reviewed_at else None,
            reviewed_by=request.reviewed_by,
        )
        for request, owner in rows
    ]


async def review_admin_role_request(
    session,
    request_id: uuid.UUID,
    approve: bool,
    reviewer_id: uuid.UUID,
):
    row = await repo.get_request_with_user(session, request_id)
    if not row:
        return None, "not_found"

    request_obj, owner = row
    if request_obj.status != AdminRoleRequestStatus.pending:
        return None, "already_reviewed"

    if approve:
        whitelist = {email.lower() for email in settings.security.admin_role_whitelist}
        if whitelist and owner.email.lower() not in whitelist:
            return None, "not_whitelisted"
        owner.role = UserRole.admin
        request_obj.status = AdminRoleRequestStatus.approved
    else:
        request_obj.status = AdminRoleRequestStatus.rejected

    request_obj.reviewed_at = datetime.now(timezone.utc)
    request_obj.reviewed_by = reviewer_id
    session.add(owner)
    session.add(request_obj)
    await session.commit()
    await session.refresh(request_obj)
    await session.refresh(owner)

    return (
        AdminRoleRequestRead(
            id=request_obj.id,
            user_id=owner.id,
            user_email=owner.email,
            user_fullname=owner.fullname,
            status=request_obj.status.value,
            requested_at=request_obj.requested_at.isoformat(),
            reviewed_at=(
                request_obj.reviewed_at.isoformat() if request_obj.reviewed_at else None
            ),
            reviewed_by=request_obj.reviewed_by,
        ),
        None,
    )


__all__ = ["list_pending_admin_role_requests", "review_admin_role_request"]
