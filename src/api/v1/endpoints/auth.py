"""
Authentication endpoints for the API v1.

This module provides endpoints for user authentication, including login,
logout, token refresh, and password management.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    get_password_hash,
)
from src.db.models.user import User
from src.schemas.auth import (
    TokenResponse,
    LoginRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LogoutResponse,
)
from src.schemas.user import UserResponse
from src.services.auth_service import AuthService
from src.services.user_service import UserService
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    UserNotFoundError,
    PasswordMismatchError,
    AccountLockedError,
    EmailNotVerifiedError,
)
from src.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and return tokens",
    description="Validates user credentials and returns access and refresh tokens.",
)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Authenticate a user with email and password.

    Args:
        login_data: Login credentials containing email and password.
        db: Database session dependency.

    Returns:
        TokenResponse containing access and refresh tokens.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 423: If account is locked.
        HTTPException 403: If email is not verified.
    """
    try:
        auth_service = AuthService(db)
        user_service = UserService(db)

        # Validate user credentials
        user = await user_service.get_by_email(login_data.email)
        if not user:
            logger.warning(f"Login attempt with non-existent email: {login_data.email}")
            raise AuthenticationError("Invalid email or password")

        # Check if account is locked
        if user.is_locked:
            logger.warning(f"Login attempt on locked account: {user.email}")
            raise AccountLockedError("Account is locked due to multiple failed attempts")

        # Check if email is verified
        if not user.is_email_verified:
            logger.warning(f"Login attempt with unverified email: {user.email}")
            raise EmailNotVerifiedError("Email not verified")

        # Verify password
        if not verify_password(login_data.password, user.hashed_password):
            await auth_service.increment_failed_attempts(user)
            logger.warning(f"Failed login attempt for user: {user.email}")
            raise AuthenticationError("Invalid email or password")

        # Reset failed attempts on successful login
        await auth_service.reset_failed_attempts(user)

        # Generate tokens
        access_token = create_access_token(
            subject=user.id,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token = create_refresh_token(
            subject=user.id,
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )

        # Store refresh token in database
        await auth_service.store_refresh_token(user.id, refresh_token)

        logger.info(f"Successful login for user: {user.email}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.from_orm(user),
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AccountLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(e),
        )
    except EmailNotVerifiedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Validates refresh token and returns new access and refresh tokens.",
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Refresh the access token using a valid refresh token.

    Args:
        refresh_data: Refresh token data.
        db: Database session dependency.

    Returns:
        TokenResponse containing new access and refresh tokens.

    Raises:
        HTTPException 401: If refresh token is invalid or expired.
    """
    try:
        auth_service = AuthService(db)

        # Validate refresh token
        payload = decode_token(refresh_data.refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Invalid token payload")

        # Verify refresh token exists in database
        stored_token = await auth_service.get_refresh_token(user_id, refresh_data.refresh_token)
        if not stored_token:
            raise InvalidTokenError("Refresh token not found or revoked")

        # Revoke old refresh token
        await auth_service.revoke_refresh_token(stored_token)

        # Generate new tokens
        access_token = create_access_token(
            subject=user_id,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        new_refresh_token = create_refresh_token(
            subject=user_id,
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )

        # Store new refresh token
        await auth_service.store_refresh_token(user_id, new_refresh_token)

        # Get user details
        user_service = UserService(db)
        user = await user_service.get_by_id(user_id)

        logger.info(f"Token refreshed for user ID: {user_id}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.from_orm(user) if user else None,
        )

    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Revokes the current refresh token and invalidates the session.",
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Logout the current user by revoking their refresh tokens.

    Args:
        request: The HTTP request object.
        current_user: The authenticated user.
        db: Database session dependency.

    Returns:
        LogoutResponse indicating success.

    Raises:
        HTTPException 401: If user is not authenticated.
    """
    try:
        auth_service = AuthService(db)

        # Revoke all refresh tokens for the user
        await auth_service.revoke_all_user_tokens(current_user.id)

        # Log the logout event
        logger.info(f"User logged out: {current_user.email}")

        return LogoutResponse(
            message="Successfully logged out",
            success=True,
        )

    except Exception as e:
        logger.error(f"Unexpected error during logout: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change user password",
    description="Changes the password for the authenticated user.",
)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Change the password for the authenticated user.

    Args:
        password_data: Contains current and new passwords.
        current_user: The authenticated user.
        db: Database session dependency.

    Returns:
        Success message.

    Raises:
        HTTPException 400: If current password is incorrect.
        HTTPException 401: If user is not authenticated.
    """
    try:
        auth_service = AuthService(db)

        # Verify current password
        if not verify_password(password_data.current_password, current_user.hashed_password):
            raise PasswordMismatchError("Current password is incorrect")

        # Validate new password strength
        if len(password_data.new_password) < settings.MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long",
            )

        # Update password
        new_hashed_password = get_password_hash(password_data.new_password)
        await auth_service.update_password(current_user.id, new_hashed_password)

        # Revoke all existing tokens except current session
        await auth_service.revoke_all_user_tokens(current_user.id)

        logger.info(f"Password changed for user: {current_user.email}")

        return {
            "message": "Password changed successfully",
            "success": True,
        }

    except PasswordMismatchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during password change: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Sends a password reset link to the user's email.",
)
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Initiate password reset process by sending reset link to email.

    Args:
        forgot_data: Contains the user's email address.
        db: Database session dependency.

    Returns:
        Success message (always returns success to prevent email enumeration).
    """
    try:
        auth_service = AuthService(db)
        user_service = UserService(db)

        # Find user by email
        user = await user_service.get_by_email(forgot_data.email)

        if user:
            # Generate password reset token
            reset_token = create_access_token(
                subject=user.id,
                expires_delta=timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS),
                token_type="password_reset",
            )

            # Store reset token
            await auth_service.store_password_reset_token(user.id, reset_token)

            # Send password reset email (implementation depends on email service)
            # await email_service.send_password_reset_email(user.email, reset_token)

            logger.info(f"Password reset requested for user: {user.email}")

        # Always return success to prevent email enumeration
        return {
            "message": "If the email exists, a password reset link has been sent",
            "success": True,
        }

    except Exception as e:
        logger.error(f"Unexpected error during forgot password: {str(e)}", exc_info=True)
        # Return generic success to prevent information leakage
        return {
            "message": "If the email exists, a password reset link has been sent",
            "success": True,
        }


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Resets the user's password using a valid reset token.",
)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Reset user password using a valid reset token.

    Args:
        reset_data: Contains reset token and new password.
        db: Database session dependency.

    Returns:
        Success message.

    Raises:
        HTTPException 400: If reset token is invalid or expired.
    """
    try:
        auth_service = AuthService(db)

        # Validate reset token
        payload = decode_token(reset_data.token)
        if payload.get("type") != "password_reset":
            raise InvalidTokenError("Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Invalid token payload")

        # Verify reset token exists in database
        stored_token = await auth_service.get_password_reset_token(user_id, reset_data.token)
        if not stored_token:
            raise InvalidTokenError("Reset token not found or already used")

        # Validate new password strength
        if len(reset_data.new_password) < settings.MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long",
            )

        # Update password
        new_hashed_password = get_password_hash(reset_data.new_password)
        await auth_service.update_password(user_id, new_hashed_password)

        # Revoke reset token
        await auth_service.revoke_password_reset_token(stored_token)

        # Revoke all existing tokens
        await auth_service.revoke_all_user_tokens(user_id)

        logger.info(f"Password reset completed for user ID: {user_id}")

        return {
            "message": "Password reset successfully",
            "success": True,
        }

    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during password reset: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Returns the profile of the currently authenticated user.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get the profile of the currently authenticated user.

    Args:
        current_user: The authenticated user from the dependency.

    Returns:
        UserResponse containing user profile data.

    Raises:
        HTTPException 401: If user is not authenticated.
    """
    try:
        return UserResponse.from_orm(current_user)

    except Exception as e:
        logger.error(f"Unexpected error fetching user profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )