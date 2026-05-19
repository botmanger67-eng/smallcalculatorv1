"""Database session and engine setup module.

This module provides database connectivity and session management
using SQLAlchemy with async support. It implements connection pooling,
session lifecycle management, and proper error handling for production use.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncGenerator, AsyncIterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import settings
from src.core.exceptions import DatabaseConnectionError, DatabaseSessionError

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration dataclass.

    Attributes:
        url: Database connection URL.
        pool_size: Number of connections to maintain in pool.
        max_overflow: Maximum overflow connections beyond pool_size.
        pool_timeout: Timeout in seconds for acquiring connection from pool.
        pool_recycle: Recycle connections after this many seconds.
        echo: Enable SQL echo for debugging.
        connect_args: Additional connection arguments.
    """

    url: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    connect_args: dict = field(default_factory=dict)


class DatabaseManager:
    """Manages database engine and session lifecycle.

    This class provides a centralized manager for database connections,
    handling engine creation, session factories, and proper cleanup.

    Attributes:
        config: Database configuration instance.
        engine: SQLAlchemy async engine instance.
        sync_engine: SQLAlchemy sync engine instance (for migrations).
        async_session_factory: Async session factory.
        sync_session_factory: Sync session factory.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        """Initialize database manager with optional configuration.

        Args:
            config: Database configuration. If None, loads from settings.
        """
        self.config = config or self._load_config_from_settings()
        self.engine: Optional[AsyncEngine] = None
        self.sync_engine: Optional[Engine] = None
        self.async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self.sync_session_factory: Optional[sessionmaker[Session]] = None
        self._initialized: bool = False

    def _load_config_from_settings(self) -> DatabaseConfig:
        """Load database configuration from application settings.

        Returns:
            DatabaseConfig instance populated from settings.

        Raises:
            DatabaseConnectionError: If required settings are missing.
        """
        try:
            return DatabaseConfig(
                url=settings.DATABASE_URL,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_timeout=settings.DATABASE_POOL_TIMEOUT,
                pool_recycle=settings.DATABASE_POOL_RECYCLE,
                echo=settings.DATABASE_ECHO,
            )
        except AttributeError as error:
            raise DatabaseConnectionError(
                f"Missing database configuration: {error}"
            ) from error

    def initialize(self) -> None:
        """Initialize database engines and session factories.

        Creates both async and sync engines with connection pooling
        and configures session factories.

        Raises:
            DatabaseConnectionError: If initialization fails.
        """
        if self._initialized:
            logger.warning("Database manager already initialized")
            return

        try:
            # Create async engine
            self.engine = create_async_engine(
                self.config.url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=self.config.echo,
                connect_args=self.config.connect_args,
            )

            # Create sync engine for migrations and sync operations
            sync_url = self.config.url.replace("+asyncpg", "").replace(
                "+aiosqlite", ""
            )
            self.sync_engine = create_engine(
                sync_url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=self.config.echo,
            )

            # Configure event listeners for connection pooling
            self._configure_engine_events()

            # Create session factories
            self.async_session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            self.sync_session_factory = sessionmaker(
                self.sync_engine,
                class_=Session,
                expire_on_commit=False,
            )

            self._initialized = True
            logger.info(
                "Database manager initialized successfully with pool_size=%s",
                self.config.pool_size,
            )

        except SQLAlchemyError as error:
            raise DatabaseConnectionError(
                f"Failed to initialize database: {error}"
            ) from error

    def _configure_engine_events(self) -> None:
        """Configure SQLAlchemy engine event listeners.

        Sets up connection pool monitoring and error handling.
        """
        if self.engine is None:
            return

        @event.listens_for(self.engine.sync_engine, "connect")
        def receive_connect(dbapi_connection, connection_record) -> None:  # type: ignore
            """Handle new database connections."""
            logger.debug("New database connection established")

        @event.listens_for(self.engine.sync_engine, "checkout")
        def receive_checkout(
            dbapi_connection, connection_record, connection_proxy
        ) -> None:  # type: ignore
            """Handle connection checkout from pool."""
            logger.debug("Database connection checked out from pool")

        @event.listens_for(self.engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record) -> None:  # type: ignore
            """Handle connection checkin to pool."""
            logger.debug("Database connection checked in to pool")

    async def get_async_session(self) -> AsyncSession:
        """Get an async database session.

        Returns:
            AsyncSession instance.

        Raises:
            DatabaseSessionError: If session creation fails.
        """
        if not self._initialized or self.async_session_factory is None:
            raise DatabaseSessionError("Database manager not initialized")

        try:
            session = self.async_session_factory()
            return session
        except SQLAlchemyError as error:
            raise DatabaseSessionError(
                f"Failed to create async session: {error}"
            ) from error

    def get_sync_session(self) -> Session:
        """Get a sync database session.

        Returns:
            Session instance.

        Raises:
            DatabaseSessionError: If session creation fails.
        """
        if not self._initialized or self.sync_session_factory is None:
            raise DatabaseSessionError("Database manager not initialized")

        try:
            session = self.sync_session_factory()
            return session
        except SQLAlchemyError as error:
            raise DatabaseSessionError(
                f"Failed to create sync session: {error}"
            ) from error

    @asynccontextmanager
    async def async_session_context(self) -> AsyncIterator[AsyncSession]:
        """Context manager for async database sessions.

        Provides automatic session lifecycle management with
        proper commit/rollback handling.

        Yields:
            AsyncSession instance.

        Raises:
            DatabaseSessionError: If session operations fail.
        """
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as error:
            await session.rollback()
            raise DatabaseSessionError(
                f"Async session error: {error}"
            ) from error
        finally:
            await session.close()

    @asynccontextmanager
    async def sync_session_context(self) -> AsyncIterator[Session]:
        """Context manager for sync database sessions.

        Provides automatic session lifecycle management with
        proper commit/rollback handling.

        Yields:
            Session instance.

        Raises:
            DatabaseSessionError: If session operations fail.
        """
        session = self.get_sync_session()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as error:
            session.rollback()
            raise DatabaseSessionError(
                f"Sync session error: {error}"
            ) from error
        finally:
            session.close()

    async def check_connection(self) -> bool:
        """Check database connectivity.

        Performs a simple query to verify database connection.

        Returns:
            True if connection is healthy, False otherwise.
        """
        if not self._initialized or self.engine is None:
            return False

        try:
            async with self.engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
            return True
        except SQLAlchemyError as error:
            logger.error("Database connection check failed: %s", error)
            return False

    async def close(self) -> None:
        """Close database connections and cleanup resources.

        Disposes of all engine connections and resets state.
        """
        if not self._initialized:
            return

        try:
            if self.engine is not None:
                await self.engine.dispose()
                logger.debug("Async engine disposed")

            if self.sync_engine is not None:
                self.sync_engine.dispose()
                logger.debug("Sync engine disposed")

            self.engine = None
            self.sync_engine = None
            self.async_session_factory = None
            self.sync_session_factory = None
            self._initialized = False
            logger.info("Database manager closed successfully")

        except SQLAlchemyError as error:
            logger.error("Error closing database connections: %s", error)
            raise DatabaseConnectionError(
                f"Failed to close database connections: {error}"
            ) from error


# Global database manager instance
db_manager: DatabaseManager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Provides a database session for dependency injection.

    Yields:
        AsyncSession instance.

    Raises:
        DatabaseSessionError: If session creation fails.
    """
    if not db_manager._initialized:
        db_manager.initialize()

    async with db_manager.async_session_context() as session:
        yield session


def init_db() -> None:
    """Initialize the global database manager.

    Should be called during application startup.
    """
    db_manager.initialize()


async def close_db() -> None:
    """Close the global database manager.

    Should be called during application shutdown.
    """
    await db_manager.close()


async def verify_database_connection() -> bool:
    """Verify database connectivity.

    Returns:
        True if database is reachable, False otherwise.
    """
    return await db_manager.check_connection()