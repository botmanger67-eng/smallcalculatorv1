"""Pytest configuration and fixtures for the test suite."""

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from _pytest.config import Config
from _pytest.fixtures import FixtureRequest
from _pytest.monkeypatch import MonkeyPatch
from _pytest.tmpdir import TempPathFactory

from src.config import AppConfig, DatabaseConfig, LoggingConfig, SecurityConfig
from src.database import DatabaseManager
from src.models import User, Product, Order
from src.security import SecurityManager
from src.services import AuthService, ProductService, OrderService


# ---------------------------------------------------------------------------
# Global test configuration
# ---------------------------------------------------------------------------

def pytest_configure(config: Config) -> None:
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires external services)."
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow (may take longer than usual)."
    )
    config.addinivalue_line(
        "markers",
        "security: mark test as security-related test."
    )


def pytest_collection_modifyitems(items: List[pytest.Item]) -> None:
    """Modify test items after collection (e.g., skip slow tests unless requested)."""
    for item in items:
        if "slow" in item.keywords and not item.config.getoption("--runslow"):
            item.add_marker(pytest.mark.skip(reason="need --runslow option to run"))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="Run slow tests."
    )
    parser.addoption(
        "--db-url",
        action="store",
        default="sqlite:///:memory:",
        help="Database URL for integration tests."
    )


# ---------------------------------------------------------------------------
# Fixtures for configuration
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_config() -> AppConfig:
    """Provide a default application configuration for testing."""
    return AppConfig(
        debug=True,
        testing=True,
        secret_key="test-secret-key-not-for-production",
        database=DatabaseConfig(
            url=os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:"),
            pool_size=5,
            max_overflow=10,
            echo=False,
        ),
        logging=LoggingConfig(
            level="DEBUG",
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        ),
        security=SecurityConfig(
            jwt_secret="test-jwt-secret",
            jwt_algorithm="HS256",
            access_token_expire_minutes=30,
            refresh_token_expire_minutes=1440,
            bcrypt_rounds=4,  # Low rounds for speed in tests
        ),
    )


@pytest.fixture(scope="session")
def security_config(app_config: AppConfig) -> SecurityConfig:
    """Extract security configuration from app config."""
    return app_config.security


@pytest.fixture(scope="session")
def database_config(app_config: AppConfig) -> DatabaseConfig:
    """Extract database configuration from app config."""
    return app_config.database


# ---------------------------------------------------------------------------
# Fixtures for temporary files and directories
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_dir(tmp_path_factory: TempPathFactory) -> Generator[Path, None, None]:
    """Create a temporary directory for test file operations."""
    temp_path = tmp_path_factory.mktemp("test_data")
    yield temp_path
    # Cleanup is handled automatically by pytest


@pytest.fixture(scope="function")
def temp_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary file for test operations."""
    file_path = temp_dir / "test_file.tmp"
    file_path.touch()
    yield file_path
    if file_path.exists():
        file_path.unlink()


@pytest.fixture(scope="function")
def temp_json_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary JSON file with sample data."""
    file_path = temp_dir / "test_data.json"
    sample_data = {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ],
        "products": [
            {"id": 101, "name": "Widget", "price": 9.99},
            {"id": 102, "name": "Gadget", "price": 24.99},
        ],
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2)
    yield file_path
    if file_path.exists():
        file_path.unlink()


# ---------------------------------------------------------------------------
# Fixtures for database
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def db_manager(app_config: AppConfig) -> AsyncGenerator[DatabaseManager, None]:
    """Create and initialize a database manager for testing."""
    manager = DatabaseManager(app_config.database)
    try:
        await manager.initialize()
        yield manager
    except Exception as exc:
        pytest.fail(f"Failed to initialize database manager: {exc}")
    finally:
        await manager.close()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_manager: DatabaseManager) -> AsyncGenerator[Any, None]:
    """Provide a database session for test operations."""
    async with db_manager.session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def populated_db(db_manager: DatabaseManager) -> AsyncGenerator[DatabaseManager, None]:
    """Provide a database manager with pre-populated test data."""
    async with db_manager.session() as session:
        # Create sample users
        users = [
            User(username="alice", email="alice@example.com", is_active=True),
            User(username="bob", email="bob@example.com", is_active=True),
            User(username="charlie", email="charlie@example.com", is_active=False),
        ]
        for user in users:
            session.add(user)
        
        # Create sample products
        products = [
            Product(name="Widget", price=9.99, stock=100),
            Product(name="Gadget", price=24.99, stock=50),
            Product(name="Doohickey", price=14.99, stock=0),
        ]
        for product in products:
            session.add(product)
        
        await session.commit()
    
    yield db_manager


# ---------------------------------------------------------------------------
# Fixtures for security and authentication
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def security_manager(security_config: SecurityConfig) -> SecurityManager:
    """Create a security manager instance for testing."""
    return SecurityManager(security_config)


@pytest.fixture(scope="function")
def auth_service(security_manager: SecurityManager, db_manager: DatabaseManager) -> AuthService:
    """Create an authentication service for testing."""
    return AuthService(security_manager, db_manager)


@pytest.fixture(scope="function")
def valid_access_token(security_manager: SecurityManager) -> str:
    """Generate a valid JWT access token for testing."""
    payload = {"sub": "test-user-id", "username": "testuser", "role": "user"}
    return security_manager.create_access_token(payload)


@pytest.fixture(scope="function")
def expired_access_token(security_manager: SecurityManager) -> str:
    """Generate an expired JWT access token for testing."""
    payload = {"sub": "test-user-id", "username": "testuser", "role": "user"}
    return security_manager.create_access_token(payload, expires_delta=-1)


@pytest.fixture(scope="function")
def invalid_token() -> str:
    """Provide an obviously invalid token string."""
    return "invalid.token.here"


# ---------------------------------------------------------------------------
# Fixtures for services
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def product_service(db_manager: DatabaseManager) -> ProductService:
    """Create a product service for testing."""
    return ProductService(db_manager)


@pytest.fixture(scope="function")
def order_service(db_manager: DatabaseManager, product_service: ProductService) -> OrderService:
    """Create an order service for testing."""
    return OrderService(db_manager, product_service)


# ---------------------------------------------------------------------------
# Fixtures for mock objects
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_db_session() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture(scope="function")
def mock_security_manager() -> MagicMock:
    """Create a mock security manager."""
    manager = MagicMock()
    manager.create_access_token = MagicMock(return_value="mock-access-token")
    manager.create_refresh_token = MagicMock(return_value="mock-refresh-token")
    manager.verify_token = MagicMock(return_value={"sub": "mock-user-id"})
    manager.hash_password = MagicMock(return_value="hashed-password")
    manager.verify_password = MagicMock(return_value=True)
    return manager


@pytest.fixture(scope="function")
def mock_auth_service() -> MagicMock:
    """Create a mock authentication service."""
    service = MagicMock()
    service.register_user = AsyncMock(return_value={"id": "mock-user-id", "username": "testuser"})
    service.authenticate_user = AsyncMock(return_value={"access_token": "mock-token", "token_type": "bearer"})
    service.refresh_token = AsyncMock(return_value={"access_token": "new-mock-token", "token_type": "bearer"})
    service.get_current_user = AsyncMock(return_value={"id": "mock-user-id", "username": "testuser"})
    return service


@pytest.fixture(scope="function")
def mock_product_service() -> MagicMock:
    """Create a mock product service."""
    service = MagicMock()
    service.create_product = AsyncMock(return_value={"id": 1, "name": "Test Product", "price": 19.99})
    service.get_product = AsyncMock(return_value={"id": 1, "name": "Test Product", "price": 19.99})
    service.get_all_products = AsyncMock(return_value=[
        {"id": 1, "name": "Product A", "price": 9.99},
        {"id": 2, "name": "Product B", "price": 29.99},
    ])
    service.update_product = AsyncMock(return_value={"id": 1, "name": "Updated Product", "price": 24.99})
    service.delete_product = AsyncMock(return_value=True)
    return service


@pytest.fixture(scope="function")
def mock_order_service() -> MagicMock:
    """Create a mock order service."""
    service = MagicMock()
    service.create_order = AsyncMock(return_value={"id": 1001, "user_id": "user1", "total": 59.97})
    service.get_order = AsyncMock(return_value={"id": 1001, "user_id": "user1", "total": 59.97})
    service.get_user_orders = AsyncMock(return_value=[
        {"id": 1001, "total": 59.97},
        {"id": 1002, "total": 34.99},
    ])
    service.cancel_order = AsyncMock(return_value=True)
    return service


# ---------------------------------------------------------------------------
# Fixtures for HTTP client (if using FastAPI or similar)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def async_client() -> AsyncMock:
    """Create a mock async HTTP client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"data": "mock"}))
    client.post = AsyncMock(return_value=MagicMock(status_code=201, json=lambda: {"id": "new-resource"}))
    client.put = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"updated": True}))
    client.delete = AsyncMock(return_value=MagicMock(status_code=204))
    return client


# ---------------------------------------------------------------------------
# Fixtures for environment variables
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_env_vars(monkeypatch: MonkeyPatch) -> Dict[str, str]:
    """Set mock environment variables for testing."""
    env_vars = {
        "APP_ENV": "testing",
        "DATABASE_URL": "sqlite:///:memory:",
        "JWT_SECRET": "test-jwt-secret",
        "API_KEY": "test-api-key-12345",
        "LOG_LEVEL": "DEBUG",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


# ---------------------------------------------------------------------------
# Fixtures for test data factories
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def sample_user_data() -> Dict[str, Any]:
    """Provide sample user data for testing."""
    return {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "role": "user",
    }


@pytest.fixture(scope="function")
def sample_product_data() -> Dict[str, Any]:
    """Provide sample product data for testing."""
    return {
        "name": "Test Widget",
        "description": "A widget for testing purposes",
        "price": 19.99,
        "stock": 100,
        "category": "widgets",
        "sku": "WIDGET-001",
        "is_active": True,
    }


@pytest.fixture(scope="function")
def sample_order_data() -> Dict[str, Any]:
    """Provide sample order data for testing."""
    return {
        "user_id": "user-123",
        "items": [
            {"product_id": 1, "quantity": 2, "unit_price": 19.99},
            {"product_id": 2, "quantity": 1, "unit_price": 29.99},
        ],
        "shipping_address": {
            "street": "123 Test St",
            "city": "Testville",
            "state": "TS",
            "zip": "12345",
            "country": "Testland",
        },
        "payment_method": "credit_card",
    }


# ---------------------------------------------------------------------------
# Fixtures for async event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Fixtures for patching external dependencies
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def patch_external_api() -> Generator[MagicMock, None, None]:
    """Patch external API calls for testing."""
    with patch("src.services.external_api.ExternalAPIClient") as mock:
        mock_instance = mock.return_value
        mock_instance.fetch_data = AsyncMock(return_value={"status": "ok", "data": []})
        mock_instance.send_notification = AsyncMock(return_value=True)
        yield mock_instance


@pytest.fixture(scope="function")
def patch_redis_cache() -> Generator[MagicMock, None, None]:
    """Patch Redis cache for testing."""
    with patch("src.cache.redis_client.RedisClient") as mock:
        mock_instance = mock.return_value
        mock_instance.get = AsyncMock(return_value=None)
        mock_instance.set = AsyncMock(return_value=True)
        mock_instance.delete = AsyncMock(return_value=True)
        mock_instance.exists = AsyncMock(return_value=False)
        yield mock_instance


# ---------------------------------------------------------------------------
# Fixtures for error scenarios
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_connection_error() -> Exception:
    """Provide a database connection error for testing error handling."""
    return ConnectionError("Failed to connect to database")


@pytest.fixture(scope="function")
def authentication_error() -> Exception:
    """Provide an authentication error for testing."""
    return PermissionError("Invalid credentials")


@pytest.fixture(scope="function")
def validation_error() -> Exception:
    """Provide a validation error for testing."""
    return ValueError("Invalid input data")


# ---------------------------------------------------------------------------
# Cleanup fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function", autouse=True)
def cleanup_temp_files() -> Generator[None, None, None]:
    """Automatically clean up temporary files after each test."""
    yield
    # Additional cleanup logic can be added here if needed
    pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_session() -> Generator[None, None, None]:
    """Perform cleanup operations at the end of the test session."""
    yield
    # Clean up any session-level resources
    temp_dir = Path(tempfile.gettempdir()) / "pytest_session_cleanup"
    if temp_dir.exists():
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)