"""
API package initialization module.

This module initializes the API package, providing centralized configuration,
error handling, and utility functions for all API endpoints.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type, Union

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from src.config import settings
from src.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError as AppValidationError,
)

logger = logging.getLogger(__name__)

# Package metadata
__version__ = "1.0.0"
__author__ = "Enterprise Engineering Team"
__description__ = "Enterprise-grade REST API package"

# Public API exports
__all__: List[str] = [
    "create_app",
    "APIResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "api_router",
    "handle_exception",
    "validate_request",
]


class APIResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool = True
    data: Optional[Any] = None
    message: str = "Operation completed successfully"
    error: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": 1, "name": "example"},
                "message": "Resource retrieved successfully",
                "error": None,
                "metadata": {"timestamp": "2024-01-01T00:00:00Z"},
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""

    success: bool = False
    data: Optional[Any] = None
    message: str = "An error occurred"
    error: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": False,
                "data": None,
                "message": "Validation failed",
                "error": {
                    "code": "VALIDATION_ERROR",
                    "details": {"field": "email", "reason": "Invalid format"},
                },
                "metadata": {"timestamp": "2024-01-01T00:00:00Z"},
            }
        }


class PaginatedResponse(BaseModel):
    """Standard paginated response wrapper."""

    success: bool = True
    data: List[Any]
    message: str = "Resources retrieved successfully"
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {
        "page": 1,
        "page_size": 20,
        "total_items": 0,
        "total_pages": 0,
        "has_next": False,
        "has_previous": False,
    }

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [{"id": 1, "name": "example"}],
                "message": "Resources retrieved successfully",
                "error": None,
                "metadata": {
                    "page": 1,
                    "page_size": 20,
                    "total_items": 100,
                    "total_pages": 5,
                    "has_next": True,
                    "has_previous": False,
                },
            }
        }


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Returns:
        FastAPI: Configured application instance with middleware, exception handlers,
                 and route registration.

    Raises:
        RuntimeError: If application initialization fails.
    """
    try:
        app = FastAPI(
            title=settings.APP_NAME,
            version=__version__,
            description=__description__,
            docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
            redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
            openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        )

        # Configure CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
        )

        # Register exception handlers
        app.add_exception_handler(AppException, handle_app_exception)
        app.add_exception_handler(RequestValidationError, handle_validation_error)
        app.add_exception_handler(HTTPException, handle_http_exception)
        app.add_exception_handler(Exception, handle_generic_exception)

        # Register middleware
        app.middleware("http")(request_id_middleware)
        app.middleware("http")(logging_middleware)

        # Include routers
        from src.api.v1 import router as v1_router
        app.include_router(v1_router, prefix="/api/v1")

        # Health check endpoint
        @app.get("/health", tags=["health"])
        async def health_check() -> Dict[str, Any]:
            """
            Health check endpoint for monitoring and load balancers.

            Returns:
                Dict[str, Any]: Health status information.
            """
            return {
                "status": "healthy",
                "version": __version__,
                "environment": settings.ENVIRONMENT,
            }

        logger.info(f"Application '{settings.APP_NAME}' initialized successfully")
        return app

    except Exception as exc:
        logger.error(f"Failed to initialize application: {exc}")
        raise RuntimeError(f"Application initialization failed: {exc}") from exc


async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle custom application exceptions.

    Args:
        request: The incoming HTTP request.
        exc: The application exception instance.

    Returns:
        JSONResponse: Standardized error response.
    """
    logger.error(f"Application exception: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            message=exc.message,
            error={
                "code": exc.code,
                "details": exc.details,
            },
        ).model_dump(),
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle FastAPI request validation errors.

    Args:
        request: The incoming HTTP request.
        exc: The validation error instance.

    Returns:
        JSONResponse: Standardized validation error response.
    """
    errors = exc.errors()
    logger.warning(f"Validation error: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            message="Request validation failed",
            error={
                "code": "VALIDATION_ERROR",
                "details": [
                    {
                        "field": error.get("loc", ["unknown"])[-1],
                        "message": error.get("msg", "Invalid value"),
                        "type": error.get("type", "unknown"),
                    }
                    for error in errors
                ],
            },
        ).model_dump(),
    )


async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions.

    Args:
        request: The incoming HTTP request.
        exc: The HTTP exception instance.

    Returns:
        JSONResponse: Standardized HTTP error response.
    """
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            message=str(exc.detail),
            error={
                "code": f"HTTP_{exc.status_code}",
                "details": exc.detail,
            },
        ).model_dump(),
        headers=exc.headers,
    )


async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unhandled exceptions.

    Args:
        request: The incoming HTTP request.
        exc: The unhandled exception instance.

    Returns:
        JSONResponse: Standardized internal server error response.
    """
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="An unexpected error occurred",
            error={
                "code": "INTERNAL_SERVER_ERROR",
                "details": "Please try again later or contact support",
            },
        ).model_dump(),
    )


async def request_id_middleware(request: Request, call_next: Any) -> Response:
    """
    Middleware to add request ID to each request.

    Args:
        request: The incoming HTTP request.
        call_next: The next middleware or route handler.

    Returns:
        Response: The HTTP response with request ID header.
    """
    import uuid

    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


async def logging_middleware(request: Request, call_next: Any) -> Response:
    """
    Middleware to log request/response information.

    Args:
        request: The incoming HTTP request.
        call_next: The next middleware or route handler.

    Returns:
        Response: The HTTP response.
    """
    import time

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"Status: {response.status_code} "
        f"Duration: {process_time:.3f}s "
        f"RequestID: {request.state.request_id}"
    )

    return response


def validate_request(
    model: Type[BaseModel],
    data: Dict[str, Any],
    strict: bool = True,
) -> BaseModel:
    """
    Validate request data against a Pydantic model.

    Args:
        model: The Pydantic model class to validate against.
        data: The data dictionary to validate.
        strict: Whether to use strict validation mode.

    Returns:
        BaseModel: The validated model instance.

    Raises:
        AppValidationError: If validation fails.
    """
    try:
        if strict:
            return model.model_validate(data, strict=True)
        return model.model_validate(data)
    except ValidationError as exc:
        logger.warning(f"Request validation failed: {exc.errors()}")
        raise AppValidationError(
            message="Request validation failed",
            details=[
                {
                    "field": error.get("loc", ["unknown"])[-1],
                    "message": error.get("msg", "Invalid value"),
                    "type": error.get("type", "unknown"),
                }
                for error in exc.errors()
            ],
        ) from exc


def api_router() -> None:
    """
    Placeholder for API router configuration.

    This function is intended to be overridden by specific API version modules
    to register their routes with the main application.
    """
    pass