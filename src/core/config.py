"""
Configuration management module using pydantic settings.

This module provides a centralized configuration system for the application,
leveraging pydantic's BaseSettings for environment variable loading, validation,
and type coercion. It supports multiple environments (development, staging,
production) and provides a singleton pattern for accessing configuration
throughout the application.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Union

from pydantic import (
    BaseModel,
    BaseSettings,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    ValidationError,
    validator,
)
from pydantic.env_settings import SettingsSourceCallable


class EnvironmentType(str, Enum):
    """Enumeration of supported deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Enumeration of supported logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    url: PostgresDsn = Field(
        default=...,
        description="PostgreSQL connection string",
        env="DATABASE_URL",
    )
    pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Database connection pool size",
    )
    max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum number of connections that can be created beyond pool_size",
    )
    pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Timeout in seconds for getting a connection from the pool",
    )
    echo: bool = Field(
        default=False,
        description="Enable SQL query logging",
    )
    ssl_mode: Optional[str] = Field(
        default=None,
        description="SSL mode for database connection",
    )

    @validator("ssl_mode")
    def validate_ssl_mode(cls, value: Optional[str]) -> Optional[str]:
        """Validate SSL mode value."""
        valid_modes = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
        if value is not None and value not in valid_modes:
            raise ValueError(f"Invalid SSL mode: {value}. Must be one of {valid_modes}")
        return value


class RedisConfig(BaseModel):
    """Redis connection configuration."""

    url: RedisDsn = Field(
        default=...,
        description="Redis connection string",
        env="REDIS_URL",
    )
    socket_timeout: int = Field(
        default=5,
        ge=1,
        description="Socket timeout in seconds",
    )
    socket_connect_timeout: int = Field(
        default=5,
        ge=1,
        description="Socket connection timeout in seconds",
    )
    retry_on_timeout: bool = Field(
        default=True,
        description="Retry on timeout",
    )
    max_connections: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of connections in the pool",
    )


class SecurityConfig(BaseModel):
    """Security-related configuration."""

    secret_key: SecretStr = Field(
        default=...,
        description="Application secret key for cryptographic operations",
        env="SECRET_KEY",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_expiration_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="JWT token expiration time in minutes",
    )
    jwt_refresh_expiration_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="JWT refresh token expiration time in days",
    )
    bcrypt_rounds: int = Field(
        default=12,
        ge=4,
        le=31,
        description="Number of bcrypt hashing rounds",
    )
    allowed_hosts: List[str] = Field(
        default=["*"],
        description="List of allowed hosts for CORS",
    )
    cors_origins: List[str] = Field(
        default=["*"],
        description="List of allowed CORS origins",
    )

    @validator("allowed_hosts", "cors_origins", pre=True)
    def parse_list(cls, value: Union[str, List[str]]) -> List[str]:
        """Parse list from string or return as-is."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [host.strip() for host in value.split(",")]
        return value


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level",
        env="LOG_LEVEL",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )
    date_format: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        description="Date format for log messages",
    )
    json_format: bool = Field(
        default=False,
        description="Enable JSON log format for structured logging",
    )
    file_path: Optional[Path] = Field(
        default=None,
        description="Path to log file. If None, logs to stdout",
    )
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum log file size in MB before rotation",
    )
    backup_count: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of backup log files to keep",
    )


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""

    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking",
        env="SENTRY_DSN",
    )
    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics endpoint",
    )
    metrics_port: int = Field(
        default=9090,
        ge=1024,
        le=65535,
        description="Port for Prometheus metrics server",
    )
    health_check_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Health check interval in seconds",
    )


class AppConfig(BaseSettings):
    """
    Main application configuration class.

    This class uses pydantic's BaseSettings to automatically load configuration
    from environment variables, .env files, and default values. It provides
    a centralized configuration management system with validation and type safety.

    Configuration is loaded in the following order (later sources override earlier ones):
    1. Default values
    2. .env file
    3. Environment variables
    """

    # Application metadata
    app_name: str = Field(
        default="FastAPI Application",
        description="Application name",
        env="APP_NAME",
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version",
        env="APP_VERSION",
    )
    app_description: str = Field(
        default="",
        description="Application description",
        env="APP_DESCRIPTION",
    )

    # Environment
    environment: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Deployment environment",
        env="ENVIRONMENT",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
        env="DEBUG",
    )

    # Server configuration
    host: str = Field(
        default="0.0.0.0",
        description="Server host",
        env="HOST",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port",
        env="PORT",
    )
    workers: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Number of worker processes",
        env="WORKERS",
    )
    reload: bool = Field(
        default=False,
        description="Enable auto-reload for development",
        env="RELOAD",
    )

    # Sub-configurations
    database: DatabaseConfig = Field(
        default=...,
        description="Database configuration",
    )
    redis: RedisConfig = Field(
        default=...,
        description="Redis configuration",
    )
    security: SecurityConfig = Field(
        default=...,
        description="Security configuration",
    )
    logging: LoggingConfig = Field(
        default=LoggingConfig(),
        description="Logging configuration",
    )
    monitoring: MonitoringConfig = Field(
        default=MonitoringConfig(),
        description="Monitoring configuration",
    )

    # Feature flags
    feature_flags: Dict[str, bool] = Field(
        default={},
        description="Feature flags for enabling/disabling features",
        env="FEATURE_FLAGS",
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
        env="RATE_LIMIT_ENABLED",
    )
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of requests per window",
        env="RATE_LIMIT_REQUESTS",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Rate limit window in seconds",
        env="RATE_LIMIT_WINDOW_SECONDS",
    )

    # Cache configuration
    cache_enabled: bool = Field(
        default=True,
        description="Enable caching",
        env="CACHE_ENABLED",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        ge=1,
        le=86400,
        description="Default cache TTL in seconds",
        env="CACHE_TTL_SECONDS",
    )

    # File upload configuration
    max_upload_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum file upload size in MB",
        env="MAX_UPLOAD_SIZE_MB",
    )
    allowed_upload_extensions: Set[str] = Field(
        default={".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx", ".txt"},
        description="Allowed file extensions for upload",
        env="ALLOWED_UPLOAD_EXTENSIONS",
    )

    # Singleton instance
    _instance: ClassVar[Optional[AppConfig]] = None

    class Config:
        """Pydantic configuration for AppConfig."""

        env_file: str = ".env"
        env_file_encoding: str = "utf-8"
        case_sensitive: bool = False
        validate_assignment: bool = True
        arbitrary_types_allowed: bool = True

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            """Customize the order of settings sources."""
            return (
                init_settings,
                env_settings,
                file_secret_settings,
            )

    @validator("environment", pre=True)
    def validate_environment(cls, value: Union[str, EnvironmentType]) -> EnvironmentType:
        """Validate and convert environment value."""
        if isinstance(value, EnvironmentType):
            return value
        try:
            return EnvironmentType(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid environment: {value}. Must be one of "
                f"{[e.value for e in EnvironmentType]}"
            )

    @validator("debug")
    def validate_debug(cls, value: bool, values: Dict[str, Any]) -> bool:
        """Validate debug mode based on environment."""
        environment = values.get("environment")
        if environment == EnvironmentType.PRODUCTION and value:
            raise ValueError("Debug mode cannot be enabled in production environment")
        return value

    @validator("allowed_upload_extensions", pre=True)
    def parse_extensions(cls, value: Union[str, Set[str]]) -> Set[str]:
        """Parse file extensions from string or return as-is."""
        if isinstance(value, str):
            try:
                return set(json.loads(value))
            except json.JSONDecodeError:
                return {ext.strip().lower() for ext in value.split(",")}
        return value

    @validator("feature_flags", pre=True)
    def parse_feature_flags(cls, value: Union[str, Dict[str, bool]]) -> Dict[str, bool]:
        """Parse feature flags from JSON string or return as-is."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("FEATURE_FLAGS must be a valid JSON object")
        return value

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == EnvironmentType.DEVELOPMENT

    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment == EnvironmentType.STAGING

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == EnvironmentType.PRODUCTION

    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == EnvironmentType.TESTING

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return self.feature_flags.get(feature_name, False)

    def get_database_url(self) -> str:
        """Get the database URL as a string."""
        return str(self.database.url)

    def get_redis_url(self) -> str:
        """Get the Redis URL as a string."""
        return str(self.redis.url)

    def get_secret_key(self) -> str:
        """Get the secret key as a string."""
        return self.security.secret_key.get_secret_value()

    def dict(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Override dict to handle SecretStr serialization."""
        kwargs.setdefault("exclude_none", True)
        return super().dict(*args, **kwargs)

    def json(self, *args: Any, **kwargs: Any) -> str:
        """Override json to handle SecretStr serialization."""
        kwargs.setdefault("exclude_none", True)
        return super().json(*args, **kwargs)


def get_settings() -> AppConfig:
    """
    Get the application settings singleton.

    This function implements the singleton pattern for configuration access.
    It ensures that configuration is loaded only once and reused throughout
    the application lifecycle.

    Returns:
        AppConfig: The application configuration instance.

    Raises:
        ConfigurationError: If configuration loading fails.
    """
    if AppConfig._instance is None:
        try:
            AppConfig._instance = AppConfig()
        except ValidationError as e:
            raise ConfigurationError(
                f"Failed to load configuration: {e}"
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Unexpected error loading configuration: {e}"
            ) from e
    return AppConfig._instance


def reload_settings() -> AppConfig:
    """
    Force reload the application settings.

    This function clears the singleton instance and reloads configuration
    from environment variables and .env file. Useful for testing or
    configuration changes.

    Returns:
        AppConfig: The newly loaded application configuration instance.

    Raises:
        ConfigurationError: If configuration loading fails.
    """
    AppConfig._instance = None
    return get_settings()


class ConfigurationError(Exception):
    """
    Custom exception for configuration-related errors.

    This exception is raised when there are issues loading or validating
    the application configuration.
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """
        Initialize the ConfigurationError.

        Args:
            message: Human-readable error description.
            original_error: The original exception that caused this error, if any.
        """
        self.original_error = original_error
        super().__init__(message)


# Export commonly used types and functions
__all__ = [
    "AppConfig",
    "ConfigurationError",
    "DatabaseConfig",
    "EnvironmentType",
    "LogLevel",
    "LoggingConfig",
    "MonitoringConfig",
    "RedisConfig",
    "SecurityConfig",
    "get_settings",
    "reload_settings",
]