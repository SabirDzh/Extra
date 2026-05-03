import asyncio
import sys
from os import getenv
from pathlib import Path

# Allow direct script execution: `python actions/create_superuser.py`
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from Domain.Enums.user_role import UserRole
from core.models import User, db_helper
from fastapi_users.password import PasswordHelper
from sqlalchemy import select


default_email = getenv("DEFAULT_EMAIL", "SabirDzh@gmail.com")
default_password = getenv("DEFAULT_PASSWORD", "Sony.RichNariman111")
default_fullname = getenv("DEFAULT_FULLNAME", "Sabir Dzh")
default_is_active = True
default_is_superuser = True
default_is_verified = True
role = UserRole.admin


async def create_superuser(
    email: str = default_email,
    password: str = default_password,
    fullname: str = default_fullname,
    is_active: bool = default_is_active,
    is_superuser: bool = default_is_superuser,
    is_verified: bool = default_is_verified,
):
    password_helper = PasswordHelper()

    async with db_helper.session_factory() as session:
        existing_user = await session.scalar(select(User).where(User.email == email))

        if existing_user:
            existing_user.role = role
            existing_user.is_superuser = is_superuser
            existing_user.is_active = is_active
            existing_user.is_verified = is_verified
            if fullname and not existing_user.fullname:
                existing_user.fullname = fullname

            await session.commit()
            await session.refresh(existing_user)
            print(f"Updated existing user '{email}' to admin role.")
            return existing_user

        new_user = User(
            email=email,
            hashed_password=password_helper.hash(password),
            is_active=is_active,
            is_superuser=is_superuser,
            is_verified=is_verified,
            role=role,
            fullname=fullname,
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        print(f"Created new admin user '{email}'.")
        return new_user


if __name__ == "__main__":
    asyncio.run(create_superuser())
