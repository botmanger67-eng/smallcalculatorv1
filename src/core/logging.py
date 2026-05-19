"""
Core logging configuration module for enterprise-grade logging.

Provides centralized logging setup with structured logging support,
log rotation, and configurable log levels.
"""

import json
import logging
import logging.config
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, ValidationError


class LogConfig(BaseModel):
    """Configuration model for logging settings."""

    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="json",
        description="Log format: 'json' or 'text'",
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Path to log file. If None, logs to stdout",
    )
    max_file_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum log file size in MB before rotation",
    )
    backup_count: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of backup log files to keep",
    )
    enable_console: bool = Field(
        default=True,
        description="Enable console logging",
    )
    enable_file: bool = Field(
        default=False,
        description="Enable file logging",
    )
    include_process_info: bool = Field(
        default=True,
        description="Include process ID and thread name in logs",
    )
    include_location_info: bool = Field(
        default=True,
        description="Include file name and line number in logs",
    )


class StructuredLogRecord(logging.LogRecord):
    """Custom LogRecord with structured data support."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize structured log record with extra fields."""
        super().__init__(*args, **kwargs)
        self.structured_data: Dict[str, Any] = {}


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = "%",
        validate: bool = True,
        *,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize JSON formatter.

        Args:
            fmt: Format string (unused for JSON)
            datefmt: Date format string
            style: Style for format string
            validate: Whether to validate format string
            defaults: Default values for log record
        """
        super().__init__(fmt, datefmt, style, validate, defaults=defaults)
        self._defaults = defaults or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            JSON formatted log string
        """
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(
                    traceback.format_exception(*record.exc_info)
                ),
            }

        # Add structured data if present
        if hasattr(record, "structured_data") and record.structured_data:
            log_entry["data"] = record.structured_data

        # Add process info if configured
        if hasattr(record, "processName"):
            log_entry["process"] = {
                "name": record.processName,
                "id": record.process,
            }

        if hasattr(record, "threadName"):
            log_entry["thread"] = {
                "name": record.threadName,
                "id": record.thread,
            }

        # Add location info if configured
        if hasattr(record, "pathname") and record.pathname:
            log_entry["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add any extra fields from defaults
        log_entry.update(self._defaults)

        try:
            return json.dumps(log_entry, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Fallback to string representation if JSON serialization fails
            log_entry["message"] = str(record.getMessage())
            log_entry["serialization_error"] = str(e)
            return json.dumps(log_entry, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Text formatter with consistent formatting."""

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = "%",
        validate: bool = True,
        *,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize text formatter.

        Args:
            fmt: Format string for log messages
            datefmt: Date format string
            style: Style for format string
            validate: Whether to validate format string
            defaults: Default values for log record
        """
        if fmt is None:
            fmt = (
                "%(asctime)s | %(levelname)-8s | %(name)s | "
                "%(message)s"
            )
        super().__init__(fmt, datefmt, style, validate, defaults=defaults)


class LoggerFactory:
    """Factory class for creating and configuring loggers."""

    _instances: Dict[str, logging.Logger] = {}
    _config: Optional[LogConfig] = None
    _initialized: bool = False

    @classmethod
    def initialize(cls, config: Optional[LogConfig] = None) -> None:
        """Initialize the logging system with given configuration.

        Args:
            config: Logging configuration. If None, uses default config.

        Raises:
            ValueError: If configuration is invalid
        """
        if cls._initialized:
            return

        try:
            cls._config = config or LogConfig()
            cls._validate_config(cls._config)
            cls._setup_root_logger()
            cls._initialized = True
        except (ValidationError, ValueError) as e:
            raise ValueError(f"Failed to initialize logging: {e}") from e

    @classmethod
    def _validate_config(cls, config: LogConfig) -> None:
        """Validate logging configuration.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        valid_levels = {
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
        }
        if config.log_level.upper() not in valid_levels:
            raise ValueError(
                f"Invalid log level: {config.log_level}. "
                f"Must be one of: {', '.join(sorted(valid_levels))}"
            )

        if config.log_file:
            log_path = Path(config.log_file)
            log_dir = log_path.parent
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise ValueError(
                        f"Cannot create log directory {log_dir}: {e}"
                    ) from e

    @classmethod
    def _setup_root_logger(cls) -> None:
        """Configure root logger with handlers and formatters."""
        assert cls._config is not None
        config = cls._config

        root_logger = logging.getLogger()
        root_logger.setLevel(config.log_level.upper())

        # Remove existing handlers
        root_logger.handlers.clear()

        # Create formatter
        if config.log_format == "json":
            formatter = JsonFormatter()
        else:
            formatter = TextFormatter()

        # Add console handler
        if config.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(config.log_level.upper())
            root_logger.addHandler(console_handler)

        # Add file handler with rotation
        if config.enable_file and config.log_file:
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=config.log_file,
                    maxBytes=config.max_file_size_mb * 1024 * 1024,
                    backupCount=config.backup_count,
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(config.log_level.upper())
                root_logger.addHandler(file_handler)
            except OSError as e:
                # Log to console if file handler fails
                console_handler = logging.StreamHandler(sys.stderr)
                console_handler.setFormatter(formatter)
                console_handler.setLevel(logging.ERROR)
                root_logger.addHandler(console_handler)
                root_logger.error(
                    f"Failed to create file handler: {e}",
                    extra={"structured_data": {"error": str(e)}},
                )

    @classmethod
    def get_logger(
        cls,
        name: str,
        level: Optional[str] = None,
    ) -> logging.Logger:
        """Get or create a logger with given name.

        Args:
            name: Logger name (typically __name__)
            level: Optional log level override

        Returns:
            Configured logger instance

        Raises:
            RuntimeError: If logging system not initialized
        """
        if not cls._initialized:
            cls.initialize()

        if name in cls._instances:
            logger = cls._instances[name]
        else:
            logger = logging.getLogger(name)
            cls._instances[name] = logger

        if level:
            valid_levels = {
                "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
            }
            if level.upper() in valid_levels:
                logger.setLevel(level.upper())

        return logger

    @classmethod
    def reset(cls) -> None:
        """Reset logging configuration to default state."""
        cls._instances.clear()
        cls._config = None
        cls._initialized = False

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)


def get_logger(
    name: str,
    level: Optional[str] = None,
    config: Optional[LogConfig] = None,
) -> logging.Logger:
    """Convenience function to get a configured logger.

    Args:
        name: Logger name (typically __name__)
        level: Optional log level override
        config: Optional logging configuration

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
        >>> logger.error("An error occurred", exc_info=True)
    """
    return LoggerFactory.get_logger(name, level)


def configure_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """Configure logging system with dictionary configuration.

    Args:
        config: Dictionary with logging configuration.
                If None, uses default configuration.

    Raises:
        ValueError: If configuration is invalid

    Example:
        >>> configure_logging({
        ...     "log_level": "DEBUG",
        ...     "log_format": "text",
        ...     "enable_console": True,
        ... })
    """
    try:
        if config:
            log_config = LogConfig(**config)
        else:
            log_config = LogConfig()
        LoggerFactory.initialize(log_config)
    except (ValidationError, ValueError) as e:
        raise ValueError(f"Invalid logging configuration: {e}") from e


def add_structured_data(
    logger: logging.Logger,
    data: Dict[str, Any],
) -> None:
    """Add structured data to the next log message.

    Args:
        logger: Logger instance
        data: Dictionary of structured data to include

    Example:
        >>> logger = get_logger(__name__)
        >>> add_structured_data(logger, {"user_id": 123, "action": "login"})
        >>> logger.info("User logged in")
    """
    if not isinstance(data, dict):
        raise TypeError("Structured data must be a dictionary")

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        record.structured_data = data  # type: ignore[attr-defined]
        return record

    logging.setLogRecordFactory(record_factory)


# Initialize logging with default configuration on module import
try:
    configure_logging()
except ValueError:
    # Fallback to basic logging if configuration fails
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )