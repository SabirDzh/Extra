import logging
import uuid
import secrets
from typing import TYPE_CHECKING, Optional

from fastapi_cache import FastAPICache
from fastapi_users import (
    BaseUserManager,
    UUIDIDMixin,
)
from fastapi_users.db import BaseUserDatabase
from mailing.send_email_confirmed import send_email_confirmed
from mailing.send_verification_email import send_verification_email
from mailing.send_password_reset_email import send_password_reset_email
from Services.notifications import send_new_user_notification

from core.config import settings
from core.models import User
from core.models.admin_role_request import AdminRoleRequest, AdminRoleRequestStatus
from core.types.user_id import UuIDMixin
from Domain.Enums.user_role import UserRole

if TYPE_CHECKING:
    from fastapi import BackgroundTasks, Request
    from fastapi_users.password import PasswordHelperProtocol

log = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.access_token.reset_password_token_secret
    verification_token_secret = settings.access_token.verification_token_secret

    def __init__(
        self,
        user_db: BaseUserDatabase[User, UuIDMixin],
        password_helper: Optional["PasswordHelperProtocol"] = None,
        background_tasks: Optional["BackgroundTasks"] = None,
    ):
        super().__init__(user_db, password_helper)
        self.background_tasks = background_tasks

    async def on_after_register(
        self,
        user: User,
        request: Optional["Request"] = None,
    ):
        if self.background_tasks:
            self.background_tasks.add_task(
                FastAPICache.clear,
                namespace=settings.cache.namespace.users_list,
            )
        else:
            await FastAPICache.clear(
                namespace=settings.cache.namespace.users_list,
            )




        await send_new_user_notification(user)




    async def on_after_forgot_password(
        self,
        user: User,
        token: str,
        request: Optional["Request"] = None,
    ):





        new_password = secrets.token_urlsafe(12)
        hashed_password = self.password_helper.hash(new_password)
        await self.user_db.update(user, {"hashed_password": hashed_password})

        self.background_tasks.add_task(
            send_password_reset_email,
            user=user,
            new_password=new_password,
        )

    async def on_after_request_verify(
        self,
        user: User,
        token: str,
        request: Optional["Request"] = None,
    ):
        log.warning(
            "Verification requested for user %r. Verification token: %r",
            user.id,
            token,
        )
        verification_link = request.url_for("verify_email").replace_query_params(
            token=token
        )
        self.background_tasks.add_task(
            send_verification_email,
            user=user,
            verification_link=str(verification_link),
        )

    async def on_after_verify(
        self,
        user: User,
        request: Optional["Request"] = None,
    ):
        log.warning(
            "User %r has been verified",
            user.id,
        )

        self.background_tasks.add_task(
            send_email_confirmed,
            user=user,
        )

    async def create(
        self,
        user_create,
        safe: bool = False,
        request: Optional["Request"] = None,
    ) -> User:
        user_dict = user_create.create_update_dict()
        requested_role = user_dict.get("role", UserRole.buyer)
        if isinstance(requested_role, str):
            requested_role = UserRole(requested_role)

        user_dict["role"] = (
            UserRole.buyer if requested_role == UserRole.admin else requested_role
        )
        user = await super().create(
            user_create.__class__(**user_dict), safe=safe, request=request
        )

        if requested_role == UserRole.admin:
            whitelist = {email.lower() for email in settings.security.admin_role_whitelist}
            if user.email.lower() in whitelist:
                user.role = UserRole.admin
            else:
                self.user_db.session.add(
                    AdminRoleRequest(
                        user_id=user.id,
                        status=AdminRoleRequestStatus.pending,
                    )
                )
            await self.user_db.session.commit()
            await self.user_db.session.refresh(user)

        return user
