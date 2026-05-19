"""FastAPI dependencies for database sessions and current user authentication."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.database import async_session_factory
from src.models.user import User

security_scheme = HTTPBearer()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for dependency injection.

    Yields:
        AsyncSession: SQLAlchemy async session that is closed after use.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as exc:
            await session.rollback()
            raise exc
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Authenticate and retrieve the current user from JWT token.

    Args:
        credentials: Bearer token credentials from the request.
        db: Database session for user lookup.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: If token is invalid, expired, or user not found.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """Optionally authenticate and retrieve the current user.

    Unlike get_current_user, this dependency does not raise an error
    if no token is provided. Useful for endpoints that work for both
    authenticated and unauthenticated users.

    Args:
        credentials: Optional Bearer token credentials.
        db: Database session for user lookup.

    Returns:
        Optional[User]: The authenticated user or None if no token.
    """
    if credentials is None:
        return None

    try:
        user = await get_current_user(credentials=credentials, db=db)
        return user
    except HTTPException:
        return None