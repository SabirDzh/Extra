import argparse
import asyncio
import secrets
import string
import sys
from pathlib import Path

# Allow direct script execution: `python actions/reset_user_password.py ...`
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.models import User, db_helper
from fastapi_users.password import PasswordHelper
from sqlalchemy import select


ALPHABET = string.ascii_letters + string.digits + "@#$%*_-"


def generate_password(length: int = 14) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


async def reset_user_password(email: str, new_password: str | None = None) -> None:
    password_helper = PasswordHelper()
    password = new_password or generate_password()

    async with db_helper.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if not user:
            print(f"User with email '{email}' not found.")
            return

        user.hashed_password = password_helper.hash(password)
        await session.commit()

    print(f"Password updated for: {email}")
    print(f"New password: {password}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset user password by email (CLI only)."
    )
    parser.add_argument("email", help="User email")
    parser.add_argument(
        "--password",
        dest="password",
        default=None,
        help="Set custom password (if omitted, random one will be generated)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(reset_user_password(args.email, args.password))
