"""
Custom exception classes for the application.

This module defines a hierarchy of custom exceptions used throughout the
application to provide consistent error handling and meaningful error messages.
All custom exceptions inherit from a base ApplicationException class.
"""

from typing import Any, Dict, Optional, Union


class ApplicationException(Exception):
    """
    Base exception class for all application-specific errors.
    
    All custom exceptions should inherit from this class to ensure
    consistent error handling and logging capabilities.
    
    Attributes:
        message: Human-readable error description.
        code: Optional error code for programmatic handling.
        details: Optional dictionary with additional error context.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ApplicationException.
        
        Args:
            message: Human-readable error description.
            code: Optional error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to a dictionary representation.
        
        Returns:
            Dictionary containing error information.
        """
        result: Dict[str, Any] = {
            "message": self.message,
        }
        if self.code is not None:
            result["code"] = self.code
        if self.details:
            result["details"] = self.details
        return result

    def __str__(self) -> str:
        """Return string representation of the exception."""
        parts = [self.message]
        if self.code:
            parts.append(f"[Code: {self.code}]")
        if self.details:
            parts.append(f"Details: {self.details}")
        return " | ".join(parts)


class ValidationException(ApplicationException):
    """
    Exception raised for data validation errors.
    
    Used when input data fails validation rules or constraints.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        code: Optional[str] = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ValidationException.
        
        Args:
            message: Human-readable error description.
            field: Optional name of the field that failed validation.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        self.field = field
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(message=message, code=code, details=error_details)


class AuthenticationException(ApplicationException):
    """
    Exception raised for authentication failures.
    
    Used when user authentication fails or credentials are invalid.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        code: Optional[str] = "AUTHENTICATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the AuthenticationException.
        
        Args:
            message: Human-readable error description.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        super().__init__(message=message, code=code, details=details)


class AuthorizationException(ApplicationException):
    """
    Exception raised for authorization failures.
    
    Used when a user lacks permission to perform an action.
    """

    def __init__(
        self,
        message: str = "Insufficient permissions",
        code: Optional[str] = "AUTHORIZATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the AuthorizationException.
        
        Args:
            message: Human-readable error description.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        super().__init__(message=message, code=code, details=details)


class NotFoundException(ApplicationException):
    """
    Exception raised when a requested resource is not found.
    
    Used when attempting to access or operate on a non-existent resource.
    """

    def __init__(
        self,
        resource: str,
        identifier: Optional[Union[str, int]] = None,
        message: Optional[str] = None,
        code: Optional[str] = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the NotFoundException.
        
        Args:
            resource: Name or type of the resource that was not found.
            identifier: Optional identifier of the resource.
            message: Human-readable error description. If not provided,
                    a default message will be generated.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        if message is None:
            if identifier is not None:
                message = f"{resource} with identifier '{identifier}' not found"
            else:
                message = f"{resource} not found"
        
        error_details = details or {}
        error_details["resource"] = resource
        if identifier is not None:
            error_details["identifier"] = identifier
        
        super().__init__(message=message, code=code, details=error_details)


class ConflictException(ApplicationException):
    """
    Exception raised for resource conflicts.
    
    Used when an operation conflicts with the current state of a resource.
    """

    def __init__(
        self,
        message: str,
        resource: Optional[str] = None,
        code: Optional[str] = "CONFLICT",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ConflictException.
        
        Args:
            message: Human-readable error description.
            resource: Optional name of the resource involved in the conflict.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        error_details = details or {}
        if resource:
            error_details["resource"] = resource
        super().__init__(message=message, code=code, details=error_details)


class ServiceException(ApplicationException):
    """
    Exception raised for service-level errors.
    
    Used when an external service or internal component fails.
    """

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        code: Optional[str] = "SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ServiceException.
        
        Args:
            message: Human-readable error description.
            service_name: Optional name of the service that failed.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
        super().__init__(message=message, code=code, details=error_details)


class ConfigurationException(ApplicationException):
    """
    Exception raised for configuration errors.
    
    Used when application configuration is invalid or missing.
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        code: Optional[str] = "CONFIGURATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ConfigurationException.
        
        Args:
            message: Human-readable error description.
            config_key: Optional name of the configuration key that is invalid.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key
        super().__init__(message=message, code=code, details=error_details)


class RateLimitException(ApplicationException):
    """
    Exception raised when rate limit is exceeded.
    
    Used when a client has exceeded the allowed number of requests.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        code: Optional[str] = "RATE_LIMIT_EXCEEDED",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the RateLimitException.
        
        Args:
            message: Human-readable error description.
            retry_after: Optional number of seconds to wait before retrying.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        error_details = details or {}
        if retry_after is not None:
            error_details["retry_after"] = retry_after
        super().__init__(message=message, code=code, details=error_details)


class DatabaseException(ApplicationException):
    """
    Exception raised for database-related errors.
    
    Used when database operations fail due to connection issues,
    constraint violations, or other database-level errors.
    """

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        code: Optional[str] = "DATABASE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the DatabaseException.
        
        Args:
            message: Human-readable error description.
            query: Optional SQL query or operation that caused the error.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        error_details = details or {}
        if query:
            error_details["query"] = query
        super().__init__(message=message, code=code, details=error_details)


class ExternalAPIException(ApplicationException):
    """
    Exception raised for external API call failures.
    
    Used when an external API returns an error or is unreachable.
    """

    def __init__(
        self,
        message: str,
        api_name: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        code: Optional[str] = "EXTERNAL_API_ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ExternalAPIException.
        
        Args:
            message: Human-readable error description.
            api_name: Optional name of the external API.
            status_code: Optional HTTP status code from the API response.
            response_body: Optional response body from the API.
            code: Error code for programmatic handling.
            details: Optional dictionary with additional error context.
        """
        error_details = details or {}
        if api_name:
            error_details["api_name"] = api_name
        if status_code is not None:
            error_details["status_code"] = status_code
        if response_body:
            error_details["response_body"] = response_body
        super().__init__(message=message, code=code, details=error_details)