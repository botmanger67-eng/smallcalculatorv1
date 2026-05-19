"""Redis cache client for enterprise-grade caching operations."""

import json
import logging
from typing import Any, Optional, Union
from datetime import timedelta
import redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class CacheConfig(BaseModel):
    """Configuration model for Redis cache client."""
    
    host: str = Field(default="localhost", description="Redis server host")
    port: int = Field(default=6379, description="Redis server port")
    db: int = Field(default=0, description="Redis database index")
    password: Optional[str] = Field(default=None, description="Redis password")
    ssl: bool = Field(default=False, description="Enable SSL connection")
    socket_timeout: float = Field(default=5.0, description="Socket timeout in seconds")
    socket_connect_timeout: float = Field(default=5.0, description="Connection timeout in seconds")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    max_connections: int = Field(default=10, description="Maximum connection pool size")
    decode_responses: bool = Field(default=True, description="Decode responses to strings")
    default_ttl: int = Field(default=300, description="Default TTL in seconds (5 minutes)")


class CacheClient:
    """Enterprise-grade Redis cache client with connection pooling and error handling."""

    def __init__(self, config: Optional[CacheConfig] = None) -> None:
        """
        Initialize the Redis cache client.

        Args:
            config: Cache configuration. If None, uses default configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        self._config = config or CacheConfig()
        self._redis_client: Optional[redis.Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Redis connection pool and client."""
        try:
            self._connection_pool = redis.ConnectionPool(
                host=self._config.host,
                port=self._config.port,
                db=self._config.db,
                password=self._config.password,
                ssl=self._config.ssl,
                socket_timeout=self._config.socket_timeout,
                socket_connect_timeout=self._config.socket_connect_timeout,
                retry_on_timeout=self._config.retry_on_timeout,
                max_connections=self._config.max_connections,
                decode_responses=self._config.decode_responses,
            )
            self._redis_client = redis.Redis(
                connection_pool=self._connection_pool,
            )
            self._redis_client.ping()
            logger.info(
                "Redis cache client initialized successfully",
                extra={
                    "host": self._config.host,
                    "port": self._config.port,
                    "db": self._config.db,
                },
            )
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(
                "Failed to initialize Redis cache client",
                extra={
                    "host": self._config.host,
                    "port": self._config.port,
                    "error": str(exc),
                },
            )
            raise RuntimeError(f"Redis initialization failed: {exc}") from exc

    def _ensure_connection(self) -> None:
        """Ensure Redis connection is active and healthy."""
        if not self._redis_client:
            raise RuntimeError("Redis client is not initialized")
        try:
            self._redis_client.ping()
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error("Redis connection lost, attempting reconnection")
            self._initialize_client()

    def _serialize(self, value: Any) -> str:
        """
        Serialize value to JSON string.

        Args:
            value: Value to serialize.

        Returns:
            JSON string representation.

        Raises:
            ValueError: If serialization fails.
        """
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Failed to serialize value: {exc}") from exc

    def _deserialize(self, value: Optional[str]) -> Any:
        """
        Deserialize JSON string to Python object.

        Args:
            value: JSON string to deserialize.

        Returns:
            Deserialized Python object or None if value is None.
        """
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(f"Failed to deserialize value: {exc}")
            return value

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if key doesn't exist.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")

        self._ensure_connection()
        try:
            value = self._redis_client.get(key)
            return self._deserialize(value)
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(f"Failed to get key '{key}': {exc}")
            raise RuntimeError(f"Redis GET operation failed: {exc}") from exc

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """
        Set a value in cache with optional TTL.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds or timedelta. Uses default TTL if None.

        Returns:
            True if successful, False otherwise.

        Raises:
            ValueError: If key is empty or serialization fails.
            RuntimeError: If Redis operation fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")

        self._ensure_connection()
        serialized_value = self._serialize(value)

        if ttl is None:
            ttl = self._config.default_ttl
        elif isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())

        try:
            return self._redis_client.setex(key, ttl, serialized_value)
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(f"Failed to set key '{key}': {exc}")
            raise RuntimeError(f"Redis SET operation failed: {exc}") from exc

    def delete(self, key: str) -> bool:
        """
        Delete a key from cache.

        Args:
            key: Cache key to delete.

        Returns:
            True if key was deleted, False if key didn't exist.

        Raises:
            ValueError: If key is empty.
            RuntimeError: If Redis operation fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")

        self._ensure_connection()
        try:
            return bool(self._redis_client.delete(key))
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(f"Failed to delete key '{key}': {exc}")
            raise RuntimeError(f"Redis DELETE operation failed: {exc}") from exc

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key to check.

        Returns:
            True if key exists, False otherwise.

        Raises:
            ValueError: If key is empty.
            RuntimeError: If Redis operation fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")

        self._ensure_connection()
        try:
            return bool(self._redis_client.exists(key))
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(f"Failed to check existence of key '{key}': {exc}")
            raise RuntimeError(f"Redis EXISTS operation failed: {exc}") from exc

    def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """
        Set TTL on an existing key.

        Args:
            key: Cache key.
            ttl: Time-to-live in seconds or timedelta.

        Returns:
            True if TTL was set, False if key doesn't exist.

        Raises:
            ValueError: If key is empty or TTL is invalid.
            RuntimeError: If Redis operation fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")

        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())

        if ttl <= 0:
            raise ValueError("TTL must be positive")

        self._ensure_connection()
        try:
            return bool(self._redis_client.expire(key, ttl))
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(f"Failed to set expiry for key '{key}': {exc}")
            raise RuntimeError(f"Redis EXPIRE operation failed: {exc}") from exc

    def ttl(self, key: str) -> int:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key.

        Returns:
            Remaining TTL in seconds. Returns -2 if key doesn't exist,
            -1 if key exists but has no TTL.

        Raises:
            ValueError: If key is empty.
            RuntimeError: If Redis operation fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")

        self._ensure_connection()
        try:
            return self._redis_client.ttl(key)
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(f"Failed to get TTL for key '{key}': {exc}")
            raise RuntimeError(f"Redis TTL operation failed: {exc}") from exc

    def clear(self) -> bool:
        """
        Clear all keys in the current database.

        Returns:
            True if successful.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        self._ensure_connection()
        try:
            self._redis_client.flushdb()
            logger.info("Cache database cleared successfully")
            return True
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.error(f"Failed to clear cache: {exc}")
            raise RuntimeError(f"Redis FLUSHDB operation failed: {exc}") from exc

    def get_or_set(
        self,
        key: str,
        fallback: callable,
        ttl: Optional[Union[int, timedelta]] = None,
    ) -> Any:
        """
        Get value from cache or compute and cache it.

        Args:
            key: Cache key.
            fallback: Callable that returns the value to cache if key doesn't exist.
            ttl: Time-to-live in seconds or timedelta.

        Returns:
            Cached or computed value.

        Raises:
            ValueError: If key is empty or fallback is not callable.
            RuntimeError: If Redis operation fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")
        if not callable(fallback):
            raise ValueError("Fallback must be callable")

        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value

        try:
            computed_value = fallback()
        except Exception as exc:
            logger.error(f"Fallback function failed for key '{key}': {exc}")
            raise RuntimeError(f"Fallback computation failed: {exc}") from exc

        self.set(key, computed_value, ttl)
        return computed_value

    def close(self) -> None:
        """Close the Redis connection pool."""
        if self._connection_pool:
            try:
                self._connection_pool.disconnect()
                logger.info("Redis connection pool closed")
            except RedisError as exc:
                logger.error(f"Error closing Redis connection pool: {exc}")
        self._redis_client = None
        self._connection_pool = None

    def __enter__(self) -> "CacheClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with cleanup."""
        self.close()

    @property
    def is_connected(self) -> bool:
        """Check if Redis client is connected."""
        if not self._redis_client:
            return False
        try:
            return self._redis_client.ping()
        except (ConnectionError, TimeoutError, RedisError):
            return False

    @property
    def config(self) -> CacheConfig:
        """Get current cache configuration."""
        return self._config