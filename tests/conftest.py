"""
Test configuration and fixtures for the application test suite.

This module provides shared fixtures and configuration for all test modules,
ensuring consistent test setup and teardown across the entire test suite.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.core.database import Base, get_db
from app.main import create_application
from app.models.user import User
from app.models.organization import Organization
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService
from app.services.user_service import UserService


# ---------------------------------------------------------------------------
# Environment Configuration
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _setup_test_environment() -> Generator[None, None, None]:
    """
    Configure environment variables for testing.
    
    Sets up a clean test environment with isolated database and storage
    configurations. Restores original environment variables after tests.
    """
    original_env = dict(os.environ)
    test_env_vars = {
        "DATABASE_URL": "sqlite+aiosqlite:///./test.db",
        "TESTING": "true",
        "LOG_LEVEL": "CRITICAL",
        "SECRET_KEY": "test-secret-key-not-for-production",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "STORAGE_PATH": tempfile.mkdtemp(),
    }
    
    try:
        os.environ.update(test_env_vars)
        yield
    finally:
        os.environ.clear()
        os.environ.update(original_env)


# ---------------------------------------------------------------------------
# Settings Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def settings() -> Settings:
    """
    Provide application settings for testing.
    
    Returns:
        Settings: Application configuration instance with test values.
    """
    return get_settings()


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create an async SQLAlchemy engine for testing.
    
    Yields:
        AsyncEngine: Database engine configured for test database.
    """
    settings_instance = get_settings()
    engine = create_async_engine(
        settings_instance.database_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"check_same_thread": False} if "sqlite" in settings_instance.database_url else {},
    )
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def async_session(
    async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a new database session for each test.
    
    Args:
        async_engine: The async database engine.
    
    Yields:
        AsyncSession: Database session with transaction rollback on cleanup.
    """
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# ---------------------------------------------------------------------------
# Application Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_app(async_engine: AsyncEngine):
    """
    Create a FastAPI test application instance.
    
    Args:
        async_engine: The async database engine.
    
    Returns:
        FastAPI: Configured application for testing.
    """
    app = create_application()
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session_factory = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest_asyncio.fixture
async def async_client(test_app):
    """
    Provide an async HTTP client for testing endpoints.
    
    Args:
        test_app: The FastAPI test application.
    
    Yields:
        AsyncClient: HTTP client for making test requests.
    """
    from httpx import AsyncClient, ASGITransport
    
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Service Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def auth_service(async_session: AsyncSession) -> AuthService:
    """
    Provide an AuthService instance for testing.
    
    Args:
        async_session: Database session.
    
    Returns:
        AuthService: Authentication service with test dependencies.
    """
    return AuthService(db=async_session)


@pytest_asyncio.fixture
async def user_service(async_session: AsyncSession) -> UserService:
    """
    Provide a UserService instance for testing.
    
    Args:
        async_session: Database session.
    
    Returns:
        UserService: User management service with test dependencies.
    """
    return UserService(db=async_session)


# ---------------------------------------------------------------------------
# Model Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_organization(
    async_session: AsyncSession,
    faker,
) -> Organization:
    """
    Create a test organization in the database.
    
    Args:
        async_session: Database session.
        faker: Faker instance for generating test data.
    
    Returns:
        Organization: Created organization instance.
    """
    organization = Organization(
        name=faker.company(),
        description=faker.catch_phrase(),
        is_active=True,
    )
    async_session.add(organization)
    await async_session.commit()
    await async_session.refresh(organization)
    return organization


@pytest_asyncio.fixture
async def test_user(
    async_session: AsyncSession,
    test_organization: Organization,
    faker,
) -> User:
    """
    Create a test user in the database.
    
    Args:
        async_session: Database session.
        test_organization: Parent organization for the user.
        faker: Faker instance for generating test data.
    
    Returns:
        User: Created user instance with hashed password.
    """
    from app.core.security import get_password_hash
    
    user_data = {
        "email": faker.email(),
        "username": faker.user_name(),
        "hashed_password": get_password_hash("test_password123"),
        "full_name": faker.name(),
        "is_active": True,
        "is_superuser": False,
        "organization_id": test_organization.id,
    }
    
    user = User(**user_data)
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_superuser(
    async_session: AsyncSession,
    test_organization: Organization,
    faker,
) -> User:
    """
    Create a test superuser in the database.
    
    Args:
        async_session: Database session.
        test_organization: Parent organization for the superuser.
        faker: Faker instance for generating test data.
    
    Returns:
        User: Created superuser instance with admin privileges.
    """
    from app.core.security import get_password_hash
    
    superuser_data = {
        "email": faker.email(),
        "username": faker.user_name(),
        "hashed_password": get_password_hash("admin_password123"),
        "full_name": faker.name(),
        "is_active": True,
        "is_superuser": True,
        "organization_id": test_organization.id,
    }
    
    superuser = User(**superuser_data)
    async_session.add(superuser)
    await async_session.commit()
    await async_session.refresh(superuser)
    return superuser


# ---------------------------------------------------------------------------
# Authentication Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def auth_headers(
    async_client,
    test_user: User,
) -> Dict[str, str]:
    """
    Generate authentication headers for a test user.
    
    Args:
        async_client: HTTP client for making requests.
        test_user: User to authenticate.
    
    Returns:
        Dict[str, str]: Headers with Bearer token.
    """
    login_data = {
        "username": test_user.email,
        "password": "test_password123",
    }
    
    response = await async_client.post("/api/v1/auth/login", data=login_data)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def superuser_headers(
    async_client,
    test_superuser: User,
) -> Dict[str, str]:
    """
    Generate authentication headers for a test superuser.
    
    Args:
        async_client: HTTP client for making requests.
        test_superuser: Superuser to authenticate.
    
    Returns:
        Dict[str, str]: Headers with Bearer token.
    """
    login_data = {
        "username": test_superuser.email,
        "password": "admin_password123",
    }
    
    response = await async_client.post("/api/v1/auth/login", data=login_data)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Mock Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_external_service() -> MagicMock:
    """
    Create a mock for external service calls.
    
    Returns:
        MagicMock: Configured mock for external service.
    """
    mock = MagicMock()
    mock.some_method = AsyncMock(return_value={"status": "success"})
    return mock


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """
    Create a mock Redis client for testing caching.
    
    Returns:
        MagicMock: Mocked Redis client with common methods.
    """
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=False)
    return mock


# ---------------------------------------------------------------------------
# Utility Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for file storage tests.
    
    Yields:
        Path: Path to temporary directory.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def faker():
    """
    Provide a Faker instance for generating test data.
    
    Returns:
        Faker: Configured Faker instance.
    """
    from faker import Faker
    return Faker()


@pytest.fixture(autouse=True)
def _mock_external_calls(mock_external_service: MagicMock) -> Generator[None, None, None]:
    """
    Automatically mock external service calls for all tests.
    
    Args:
        mock_external_service: Mock for external services.
    """
    with patch("app.services.external_service.ExternalService", return_value=mock_external_service):
        yield


# ---------------------------------------------------------------------------
# Cleanup Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_files() -> Generator[None, None, None]:
    """
    Clean up test files after all tests complete.
    
    Removes temporary test database and storage directories.
    """
    yield
    
    test_db_path = Path("./test.db")
    if test_db_path.exists():
        test_db_path.unlink()
    
    test_db_wal_path = Path("./test.db-wal")
    if test_db_wal_path.exists():
        test_db_wal_path.unlink()
    
    test_db_shm_path = Path("./test.db-shm")
    if test_db_shm_path.exists():
        test_db_shm_path.unlink()