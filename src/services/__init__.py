"""
Services package initialization.

This module provides the core service layer for the application,
implementing business logic and orchestrating data flow between
controllers and data access layers.
"""

from typing import (
    Any,
    Dict,
    List,
    Optional,
    TypeVar,
    Generic,
    Union,
    Callable,
    Awaitable,
)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime
import uuid

# Type variables for generic service patterns
T = TypeVar("T")
K = TypeVar("K")
R = TypeVar("R")

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Base exception for service layer errors."""

    def __init__(
        self,
        message: str,
        code: str = "SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize service error.

        Args:
            message: Human-readable error description
            code: Machine-readable error code
            details: Additional error context
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ServiceError):
    """Exception for data validation failures."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize validation error.

        Args:
            message: Validation error description
            field: Name of the field that failed validation
            details: Additional validation context
        """
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field, **(details or {})},
        )
        self.field = field


class NotFoundError(ServiceError):
    """Exception for resource not found scenarios."""

    def __init__(
        self,
        message: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize not found error.

        Args:
            message: Error description
            resource_type: Type of resource not found
            resource_id: Identifier of the missing resource
            details: Additional context
        """
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
                **(details or {}),
            },
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConflictError(ServiceError):
    """Exception for resource conflict scenarios."""

    def __init__(
        self,
        message: str,
        resource_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize conflict error.

        Args:
            message: Error description
            resource_type: Type of resource with conflict
            details: Additional context
        """
        super().__init__(
            message=message,
            code="CONFLICT",
            details={"resource_type": resource_type, **(details or {})},
        )
        self.resource_type = resource_type


class AuthorizationError(ServiceError):
    """Exception for authorization failures."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize authorization error.

        Args:
            message: Error description
            required_permission: Permission that was required
            details: Additional context
        """
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details={
                "required_permission": required_permission,
                **(details or {}),
            },
        )
        self.required_permission = required_permission


class ServiceOperation(Enum):
    """Enumeration of standard service operations."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    SEARCH = "search"


@dataclass
class ServiceContext:
    """Context information for service operations."""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to dictionary.

        Returns:
            Dictionary representation of the context
        """
        return {
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ServiceResult(Generic[T]):
    """Generic result wrapper for service operations."""

    success: bool
    data: Optional[T] = None
    error: Optional[ServiceError] = None
    context: Optional[ServiceContext] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        data: T,
        context: Optional[ServiceContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ServiceResult[T]":
        """
        Create a successful result.

        Args:
            data: The result data
            context: Service operation context
            metadata: Additional result metadata

        Returns:
            ServiceResult instance indicating success
        """
        return cls(
            success=True,
            data=data,
            context=context,
            metadata=metadata or {},
        )

    @classmethod
    def error_result(
        cls,
        error: ServiceError,
        context: Optional[ServiceContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ServiceResult[T]":
        """
        Create an error result.

        Args:
            error: The service error
            context: Service operation context
            metadata: Additional result metadata

        Returns:
            ServiceResult instance indicating failure
        """
        return cls(
            success=False,
            error=error,
            context=context,
            metadata=metadata or {},
        )

    def unwrap(self) -> T:
        """
        Unwrap the result, raising error if present.

        Returns:
            The result data

        Raises:
            ServiceError: If the result contains an error
        """
        if not self.success or self.error:
            raise self.error or ServiceError("Unknown error")
        return self.data  # type: ignore[return-value]


class BaseService(ABC, Generic[T, K]):
    """
    Abstract base class for all services.

    Provides common patterns for CRUD operations and service lifecycle.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize base service.

        Args:
            logger: Optional logger instance. If not provided, creates one.
        """
        self.logger = logger or logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

    @abstractmethod
    async def create(
        self,
        data: Dict[str, Any],
        context: Optional[ServiceContext] = None,
    ) -> ServiceResult[T]:
        """
        Create a new resource.

        Args:
            data: Resource creation data
            context: Service operation context

        Returns:
            ServiceResult containing the created resource
        """
        ...

    @abstractmethod
    async def get(
        self,
        id: K,
        context: Optional[ServiceContext] = None,
    ) -> ServiceResult[T]:
        """
        Retrieve a resource by identifier.

        Args:
            id: Resource identifier
            context: Service operation context

        Returns:
            ServiceResult containing the retrieved resource
        """
        ...

    @abstractmethod
    async def update(
        self,
        id: K,
        data: Dict[str, Any],
        context: Optional[ServiceContext] = None,
    ) -> ServiceResult[T]:
        """
        Update an existing resource.

        Args:
            id: Resource identifier
            data: Update data
            context: Service operation context

        Returns:
            ServiceResult containing the updated resource
        """
        ...

    @abstractmethod
    async def delete(
        self,
        id: K,
        context: Optional[ServiceContext] = None,
    ) -> ServiceResult[bool]:
        """
        Delete a resource by identifier.

        Args:
            id: Resource identifier
            context: Service operation context

        Returns:
            ServiceResult indicating deletion success
        """
        ...

    @abstractmethod
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        context: Optional[ServiceContext] = None,
    ) -> ServiceResult[List[T]]:
        """
        List resources with optional filtering and pagination.

        Args:
            filters: Optional filter criteria
            page: Page number (1-indexed)
            page_size: Number of items per page
            context: Service operation context

        Returns:
            ServiceResult containing list of resources
        """
        ...

    def _validate_context(
        self, context: Optional[ServiceContext]
    ) -> ServiceContext:
        """
        Validate and provide default context.

        Args:
            context: Optional service context

        Returns:
            Validated service context
        """
        return context or ServiceContext()

    def _log_operation(
        self,
        operation: ServiceOperation,
        resource_type: str,
        resource_id: Optional[K] = None,
        context: Optional[ServiceContext] = None,
        **kwargs: Any,
    ) -> None:
        """
        Log service operation for audit trail.

        Args:
            operation: Type of service operation
            resource_type: Type of resource being operated on
            resource_id: Optional resource identifier
            context: Service operation context
            **kwargs: Additional logging context
        """
        log_data: Dict[str, Any] = {
            "operation": operation.value,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "correlation_id": context.correlation_id if context else None,
            "user_id": context.user_id if context else None,
            "tenant_id": context.tenant_id if context else None,
            **kwargs,
        }
        self.logger.info(
            "Service operation: %s on %s",
            operation.value,
            resource_type,
            extra=log_data,
        )


class ServiceRegistry:
    """
    Registry for managing service instances.

    Implements singleton pattern for service access and dependency injection.
    """

    _instance: Optional["ServiceRegistry"] = None
    _services: Dict[str, BaseService[Any, Any]] = {}

    def __new__(cls) -> "ServiceRegistry":
        """
        Create or return singleton instance.

        Returns:
            ServiceRegistry singleton instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services = {}
        return cls._instance

    def register(
        self,
        name: str,
        service: BaseService[Any, Any],
    ) -> None:
        """
        Register a service instance.

        Args:
            name: Service identifier
            service: Service instance to register

        Raises:
            ValueError: If service name already registered
        """
        if name in self._services:
            raise ValueError(f"Service '{name}' is already registered")
        self._services[name] = service
        logger.info("Registered service: %s", name)

    def unregister(self, name: str) -> None:
        """
        Unregister a service instance.

        Args:
            name: Service identifier to remove

        Raises:
            KeyError: If service name not found
        """
        if name not in self._services:
            raise KeyError(f"Service '{name}' not found in registry")
        del self._services[name]
        logger.info("Unregistered service: %s", name)

    def get(self, name: str) -> BaseService[Any, Any]:
        """
        Retrieve a registered service.

        Args:
            name: Service identifier

        Returns:
            Registered service instance

        Raises:
            KeyError: If service name not found
        """
        if name not in self._services:
            raise KeyError(f"Service '{name}' not found in registry")
        return self._services[name]

    def get_all(self) -> Dict[str, BaseService[Any, Any]]:
        """
        Get all registered services.

        Returns:
            Dictionary of all registered services
        """
        return dict(self._services)

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        logger.info("Cleared all registered services")


# Global service registry instance
service_registry = ServiceRegistry()


def get_service(name: str) -> BaseService[Any, Any]:
    """
    Convenience function to get a registered service.

    Args:
        name: Service identifier

    Returns:
        Registered service instance

    Raises:
        KeyError: If service name not found
    """
    return service_registry.get(name)


def register_service(
    name: str,
    service: BaseService[Any, Any],
) -> None:
    """
    Convenience function to register a service.

    Args:
        name: Service identifier
        service: Service instance to register

    Raises:
        ValueError: If service name already registered
    """
    service_registry.register(name, service)


__all__: List[str] = [
    # Error classes
    "ServiceError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "AuthorizationError",
    # Enums
    "ServiceOperation",
    # Data classes
    "ServiceContext",
    "ServiceResult",
    # Abstract base
    "BaseService",
    # Registry
    "ServiceRegistry",
    "service_registry",
    # Convenience functions
    "get_service",
    "register_service",
]