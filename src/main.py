"""
Main entry point for the FastAPI application.

This module initializes and configures the FastAPI application instance,
sets up middleware, exception handlers, and includes all route routers.
It serves as the primary entry point for running the application server.
"""

import logging
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import settings
from src.api.v1.router import api_router
from src.core.exceptions import (
    ApplicationError,
    NotFoundError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
)
from src.core.logging import setup_logging

# Initialize logging configuration
setup_logging()

# Create logger instance
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    This factory function initializes the FastAPI app with all necessary
    configuration, middleware, exception handlers, and route inclusion.

    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=f"{settings.API_V1_STR}/redoc" if settings.ENVIRONMENT != "production" else None,
        debug=settings.DEBUG,
    )

    # Set up CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Set up trusted host middleware
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

    # Include API router
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # Register exception handlers
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(ApplicationError, application_exception_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(Exception, general_exception_handler)

    # Register startup and shutdown events
    application.add_event_handler("startup", startup_event)
    application.add_event_handler("shutdown", shutdown_event)

    return application


async def startup_event() -> None:
    """
    Perform startup tasks when the application starts.

    This function initializes connections to external services,
    sets up database connections, and performs any other necessary
    initialization tasks.
    """
    logger.info("Starting application initialization")
    try:
        # Initialize database connection pool
        from src.db.session import init_db
        await init_db()

        # Initialize cache connection
        from src.cache.redis import init_redis
        await init_redis()

        logger.info("Application startup completed successfully")
    except Exception as exception:
        logger.error(f"Failed to initialize application: {str(exception)}")
        raise


async def shutdown_event() -> None:
    """
    Perform cleanup tasks when the application shuts down.

    This function closes connections to external services,
    releases resources, and performs any other necessary cleanup.
    """
    logger.info("Starting application shutdown")
    try:
        # Close database connection pool
        from src.db.session import close_db
        await close_db()

        # Close cache connection
        from src.cache.redis import close_redis
        await close_redis()

        logger.info("Application shutdown completed successfully")
    except Exception as exception:
        logger.error(f"Error during application shutdown: {str(exception)}")


async def validation_exception_handler(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors.

    Args:
        request: The incoming HTTP request.
        exception: The validation error that occurred.

    Returns:
        JSONResponse: A JSON response with error details.
    """
    logger.warning(
        f"Validation error for request {request.method} {request.url.path}: {exception.errors()}"
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exception.errors(),
            "body": exception.body,
        },
    )


async def application_exception_handler(
    request: Request, exception: ApplicationError
) -> JSONResponse:
    """
    Handle custom application exceptions.

    Args:
        request: The incoming HTTP request.
        exception: The application error that occurred.

    Returns:
        JSONResponse: A JSON response with error details.
    """
    logger.error(
        f"Application error for request {request.method} {request.url.path}: {str(exception)}"
    )

    status_code_map: Dict[type, int] = {
        NotFoundError: status.HTTP_404_NOT_FOUND,
        ValidationError: status.HTTP_400_BAD_REQUEST,
        AuthenticationError: status.HTTP_401_UNAUTHORIZED,
        AuthorizationError: status.HTTP_403_FORBIDDEN,
    }

    http_status = status_code_map.get(type(exception), status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JSONResponse(
        status_code=http_status,
        content={
            "detail": str(exception),
            "error_code": exception.error_code if hasattr(exception, "error_code") else None,
        },
    )


async def http_exception_handler(
    request: Request, exception: StarletteHTTPException
) -> JSONResponse:
    """
    Handle HTTP exceptions.

    Args:
        request: The incoming HTTP request.
        exception: The HTTP exception that occurred.

    Returns:
        JSONResponse: A JSON response with error details.
    """
    logger.warning(
        f"HTTP exception for request {request.method} {request.url.path}: {exception.detail}"
    )
    return JSONResponse(
        status_code=exception.status_code,
        content={"detail": exception.detail},
    )


async def general_exception_handler(
    request: Request, exception: Exception
) -> JSONResponse:
    """
    Handle unhandled exceptions.

    Args:
        request: The incoming HTTP request.
        exception: The unhandled exception that occurred.

    Returns:
        JSONResponse: A JSON response with error details.
    """
    logger.error(
        f"Unhandled exception for request {request.method} {request.url.path}: {str(exception)}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred",
            "error_id": str(id(exception)),
        },
    )


# Create the application instance
app = create_application()


@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    Perform a health check on the application.

    Returns:
        Dict[str, Any]: A dictionary containing health status information.
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["root"])
async def root() -> Dict[str, str]:
    """
    Root endpoint that provides basic API information.

    Returns:
        Dict[str, str]: A dictionary with API name and version.
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "documentation": f"{settings.API_V1_STR}/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=settings.WORKERS,
    )