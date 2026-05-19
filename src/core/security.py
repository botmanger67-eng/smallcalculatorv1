"""Security utilities for JWT token management and password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import settings

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The hashed password to compare against.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
        raise TypeError("Both plain_password and hashed_password must be strings.")
    if not plain_password or not hashed_password:
        raise ValueError("Both plain_password and hashed_password must be non-empty.")
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        raise RuntimeError(f"Password verification failed: {e}") from e


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for the given password.

    Args:
        password: The plain text password to hash.

    Returns:
        The hashed password as a string.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    try:
        return pwd_context.hash(password)
    except Exception as e:
        raise RuntimeError(f"Password hashing failed: {e}") from e


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: A dictionary containing claims to encode in the token.
        expires_delta: Optional custom expiration time delta.
                       Defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        The encoded JWT access token as a string.
    """
    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary.")
    if not data:
        raise ValueError("Data dictionary must not be empty.")

    to_encode = data.copy()
    if expires_delta is not None:
        if not isinstance(expires_delta, timedelta):
            raise TypeError("expires_delta must be a timedelta or None.")
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return encoded_jwt
    except Exception as e:
        raise RuntimeError(f"Failed to create access token: {e}") from e


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string to decode.

    Returns:
        The decoded payload as a dictionary.

    Raises:
        ValueError: If the token is invalid or expired.
    """
    if not isinstance(token, str) or not token:
        raise ValueError("Token must be a non-empty string.")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error decoding token: {e}") from e


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token with a longer expiration.

    Args:
        data: A dictionary containing claims to encode in the token.
        expires_delta: Optional custom expiration time delta.
                       Defaults to settings.REFRESH_TOKEN_EXPIRE_DAYS.

    Returns:
        The encoded JWT refresh token as a string.
    """
    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary.")
    if not data:
        raise ValueError("Data dictionary must not be empty.")

    to_encode = data.copy()
    if expires_delta is not None:
        if not isinstance(expires_delta, timedelta):
            raise TypeError("expires_delta must be a timedelta or None.")
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode.update({"exp": expire})
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return encoded_jwt
    except Exception as e:
        raise RuntimeError(f"Failed to create refresh token: {e}") from e