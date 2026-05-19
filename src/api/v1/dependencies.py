"""API-specific dependencies for v1 endpoints.

This module provides dependency injection functions for FastAPI endpoints,
including authentication, authorization, database sessions, and rate limiting.
"""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
)
from src.core.logging import get_logger
from src.db.session import get_async_session
from src.models.user import User
from src.repositories.user import UserRepository
from src.services.auth import AuthService
from src.services.rate_limiter import RateLimiter

logger = get_logger(__name__)

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """Dependency to get the currently authenticated user.

    Args:
        credentials: Bearer token credentials from the request.
        db: Database session.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: If authentication fails with 401 status code.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        auth_service = AuthService(db)
        token = credentials.credentials
        user = await auth_service.validate_token(token)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        return user

    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable",
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to get the current active user.

    Args:
        current_user: The authenticated user.

    Returns:
        The active user.

    Raises:
        HTTPException: If user is not active with 403 status code.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Dependency to get the current superuser.

    Args:
        current_user: The authenticated active user.

    Returns:
        The superuser.

    Raises:
        HTTPException: If user is not a superuser with 403 status code.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """Dependency to get a user by their ID.

    Args:
        user_id: UUID of the user.
        db: Database session.

    Returns:
        The user.

    Raises:
        HTTPException: If user is not found with 404 status code.
    """
    user_repository = UserRepository(db)
    user = await user_repository.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    return user


async def verify_resource_ownership(
    resource_user_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Dependency to verify that the current user owns the resource.

    Args:
        resource_user_id: UUID of the resource owner.
        current_user: The authenticated active user.

    Raises:
        HTTPException: If user does not own the resource with 403 status code.
    """
    if current_user.id != resource_user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )


async def get_pagination_params(
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Dependency to get and validate pagination parameters.

    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        Dictionary with validated pagination parameters.

    Raises:
        HTTPException: If parameters are invalid with 422 status code.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Page number must be greater than 0",
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Page size must be between 1 and 100",
        )

    return {
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
        "limit": page_size,
    }


async def get_rate_limiter(
    request: Request,
    rate_limiter: RateLimiter = Depends(),
) -> None:
    """Dependency to apply rate limiting to endpoints.

    Args:
        request: The incoming request.
        rate_limiter: Rate limiter service instance.

    Raises:
        HTTPException: If rate limit is exceeded with 429 status code.
    """
    try:
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        is_allowed = await rate_limiter.check_rate_limit(
            key=f"{client_ip}:{endpoint}",
            max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )

        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(settings.RATE_LIMIT_WINDOW_SECONDS)},
            )

    except RateLimitError as e:
        logger.warning(f"Rate limit error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    except Exception as e:
        logger.error(f"Unexpected rate limiter error: {str(e)}")
        # Allow request to proceed if rate limiter fails
        pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get a database session with automatic cleanup.

    Yields:
        Database session.

    Raises:
        HTTPException: If database connection fails with 503 status code.
    """
    try:
        async with get_async_session() as session:
            yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )


async def validate_api_key(
    request: Request,
    api_key: Optional[str] = None,
) -> str:
    """Dependency to validate API key for external service access.

    Args:
        request: The incoming request.
        api_key: Optional API key from query parameter.

    Returns:
        Validated API key.

    Raises:
        HTTPException: If API key is invalid with 401 status code.
    """
    # Check header first, then query parameter
    header_key = request.headers.get("X-API-Key")
    api_key = header_key or api_key

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
        )

    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return api_key


async def get_request_id(
    request: Request,
) -> str:
    """Dependency to get or generate a request ID for tracing.

    Args:
        request: The incoming request.

    Returns:
        Request ID string.
    """
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())

    return request_id


async def get_user_agent(
    request: Request,
) -> Optional[str]:
    """Dependency to extract user agent from request.

    Args:
        request: The incoming request.

    Returns:
        User agent string or None.
    """
    return request.headers.get("User-Agent")


async def get_content_type(
    request: Request,
) -> Optional[str]:
    """Dependency to extract content type from request.

    Args:
        request: The incoming request.

    Returns:
        Content type string or None.
    """
    return request.headers.get("Content-Type")