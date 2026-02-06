import uuid
from typing import AsyncGenerator

import pytest
from core.models import Base, User
from core.models.db_helper import db_helper
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from main import main_app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Use in-memory SQLite for tests
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def async_db_engine():
    # Re-create engine per test to ensure clean state
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def session(async_db_engine) -> AsyncGenerator[AsyncSession, None]:
    TestingSessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, bind=async_db_engine
    )
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def client(session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield session

    main_app.dependency_overrides[db_helper.session_getter] = override_get_db

    # Initialize FastAPICache with InMemoryBackend for tests with UNIQUE prefix
    # This ensures that even if backend state persists (unlikely but possible), keys won't collide
    FastAPICache.init(
        InMemoryBackend(), prefix=f"test-cache-{uuid.uuid4()}", enable=False
    )

    async with AsyncClient(
        transport=ASGITransport(app=main_app), base_url="http://test"
    ) as ac:
        yield ac

    main_app.dependency_overrides.clear()


@pytest.fixture
async def create_user(session):
    async def _create_user(
        email: str,
        password: str = "password12345",
        is_superuser: bool = False,
        role: str = "user",
    ):
        password_helper = PasswordHelper()
        user_dict = {
            "email": email,
            "hashed_password": password_helper.hash(password),
            "is_active": True,
            "is_superuser": is_superuser,
            "is_verified": True,
            "role": role,
            "username": {"first_name": "Test", "last_name": "User"},
        }
        user = User(**user_dict)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    return _create_user


@pytest.fixture
async def normal_user_token_headers(client, create_user):
    email = "normal@example.com"
    password = "password12345"
    await create_user(email, password)

    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    if resp.status_code not in (200, 204):
        raise Exception(f"Failed to login in fixture: {resp.text}")

    # Cookie based auth puts token in cookie jar, which httpx client handles automatically.
    # But if we need explicit headers (which we assume in tests), we might need to extract it.
    # However, since we return 'Authorization' header dict, we need to decide.
    # If the app uses ONLY cookies, then headers might not work unless we manually set cookie header.
    # But `client` persists cookies.
    # Let's return empty headers if cookies are managed by client, OR check if we need to return specific headers.

    # Since the tests use `headers=normal_user_token_headers`, passing empty dict or None might be fine
    # IF the client retained the cookies.
    # Let's return None or empty dict and rely on client cookies.
    return {}


@pytest.fixture
async def superuser_token_headers(client, create_user):
    email = "super@example.com"
    password = "password12345"
    await create_user(email, password, is_superuser=True, role="administrator")

    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    if resp.status_code not in (200, 204):
        raise Exception(f"Failed to login in fixture: {resp.text}")
    return {}
