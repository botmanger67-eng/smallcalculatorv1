"""Alembic environment configuration for database migrations.

This module configures the Alembic migration environment, including:
- Database connection setup
- Migration context configuration
- Autogenerate support for schema changes
- Transaction management
"""

import asyncio
from logging.config import fileConfig
from typing import Any, AsyncGenerator, Optional

from alembic import context
from sqlalchemy import engine_from_config, pool, Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncConnection
from sqlalchemy.engine import Connection

# Import your application's metadata
# Replace with your actual models metadata import
from app.models import Base  # type: ignore[import-untyped]

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata

# Database URL configuration
# Supports both sync and async connections
DATABASE_URL: str = config.get_main_option("sqlalchemy.url", "")
ASYNC_DATABASE_URL: str = config.get_main_option(
    "sqlalchemy.async_url",
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    if DATABASE_URL.startswith("postgresql://")
    else DATABASE_URL,
)


def get_sync_engine() -> Engine:
    """Create a synchronous SQLAlchemy engine from configuration.

    Returns:
        Engine: Configured synchronous database engine.

    Raises:
        ValueError: If database URL is not configured.
    """
    if not DATABASE_URL:
        raise ValueError(
            "Database URL not configured. "
            "Set 'sqlalchemy.url' in alembic.ini or environment."
        )

    return engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )


def get_async_engine() -> AsyncEngine:
    """Create an asynchronous SQLAlchemy engine.

    Returns:
        AsyncEngine: Configured asynchronous database engine.

    Raises:
        ValueError: If async database URL is not configured.
    """
    if not ASYNC_DATABASE_URL:
        raise ValueError(
            "Async database URL not configured. "
            "Set 'sqlalchemy.async_url' in alembic.ini or environment."
        )

    return create_async_engine(
        ASYNC_DATABASE_URL,
        poolclass=pool.NullPool,
        future=True,
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url: str = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    connectable: Optional[Connection] = None

    try:
        connectable = get_sync_engine().connect()

        with connectable:
            context.configure(
                connection=connectable,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()

    except Exception as exc:
        raise RuntimeError(
            f"Failed to run migrations online: {exc}"
        ) from exc
    finally:
        if connectable is not None:
            connectable.close()


async def run_async_migrations() -> None:
    """Run migrations asynchronously.

    This function handles async database connections for migrations
    when using async database drivers like asyncpg.
    """
    connectable: Optional[AsyncConnection] = None

    try:
        async_engine: AsyncEngine = get_async_engine()
        async with async_engine.connect() as connectable:
            await connectable.run_sync(do_run_migrations)

    except Exception as exc:
        raise RuntimeError(
            f"Failed to run async migrations: {exc}"
        ) from exc
    finally:
        if connectable is not None:
            await connectable.close()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations with the given connection.

    Args:
        connection: SQLAlchemy connection to use for migrations.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations() -> None:
    """Main entry point for running migrations.

    Determines whether to run in offline, online sync, or online async mode
    based on configuration.
    """
    is_async: bool = config.get_main_option("async_mode", "false").lower() == "true"

    if context.is_offline_mode():
        run_migrations_offline()
    elif is_async:
        asyncio.run(run_async_migrations())
    else:
        run_migrations_online()


# Entry point for Alembic
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations()