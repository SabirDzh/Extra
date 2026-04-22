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
from sqlalchemy import UUID as SaUUID
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
import uuid

from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy import UUID as SaUUID

class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgUUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value

@compiles(PgUUID, "sqlite")
@compiles(SaUUID, "sqlite")
def compile_guid(type_, compiler, **kw):
    return "CHAR(36)"


DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@compiles(JSONB, "sqlite")
def compile_jsonb(type_, compiler, **kw):
    return compiler.visit_JSON(type_, **kw)


@compiles(TSVECTOR, "sqlite")
def compile_tsvector(type_, compiler, **kw):
    return "TEXT"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def async_db_engine():

    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"use_insertmanyvalues": False},
    )

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def register_custom_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "to_tsvector", 2, lambda config, text: "mock_vector", deterministic=True
        )
        dbapi_connection.create_function(
            "websearch_to_tsquery", 2, lambda config, query: "mock_query", deterministic=True
        )
        dbapi_connection.create_function(
            "ts_rank", 2, lambda vector, query: 0.0, deterministic=True
        )
        dbapi_connection.create_function(
            "similarity", 2, lambda text1, text2: 1.0, deterministic=True
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
        autocommit=False,
        autoflush=False,
        bind=async_db_engine,
        expire_on_commit=False,
    )
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def client(session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield session

    main_app.dependency_overrides[db_helper.session_getter] = override_get_db



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
        password: str = "Password12345!",
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
            "fullname": "Test User",
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
    password = "Password12345!"
    await create_user(email, password)

    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    if resp.status_code not in (200, 204):
        raise Exception(f"Failed to login in fixture: {resp.text}")

    return {}


@pytest.fixture
async def superuser_token_headers(client, create_user):
    email = "super@example.com"
    password = "Password12345!"
    await create_user(email, password, is_superuser=True, role="administrator")

    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    if resp.status_code not in (200, 204):
        raise Exception(f"Failed to login in fixture: {resp.text}")
    return {}
