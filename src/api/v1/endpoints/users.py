"""User management API endpoints.

This module provides RESTful endpoints for user management operations including
CRUD operations, authentication, and profile management.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import (
    get_current_active_user,
    get_current_user,
    require_admin,
    require_permission,
)
from src.api.v1.dependencies.database import get_db_session
from src.api.v1.schemas.users import (
    UserCreate,
    UserFilter,
    UserProfileUpdate,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)
from src.core.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    ResourceNotFoundError,
    UserInactiveError,
)
from src.core.logging import get_logger
from src.models.user import User, UserRole, UserStatus
from src.services.user_service import UserService

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    response_model=List[UserResponse],
    summary="List users",
    description="Retrieve a paginated list of users with optional filtering.",
)
async def list_users(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    email: Optional[str] = Query(default=None, description="Filter by email"),
    role: Optional[UserRole] = Query(default=None, description="Filter by role"),
    status: Optional[UserStatus] = Query(default=None, description="Filter by status"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search in name or email"),
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> List[UserResponse]:
    """Retrieve a paginated list of users.

    Args:
        page: Page number for pagination.
        page_size: Number of items per page.
        email: Optional email filter.
        role: Optional role filter.
        status: Optional status filter.
        is_active: Optional active status filter.
        search: Optional search string for name or email.
        db_session: Database session dependency.
        current_user: Authenticated admin user.

    Returns:
        List of user responses.

    Raises:
        HTTPException: If database error occurs.
    """
    try:
        user_filter = UserFilter(
            email=email,
            role=role,
            status=status,
            is_active=is_active,
            search=search,
        )
        user_service = UserService(db_session)
        users = await user_service.list_users(
            page=page,
            page_size=page_size,
            filter_params=user_filter,
        )
        return [UserResponse.from_orm(user) for user in users]
    except Exception as exception:
        logger.error(f"Failed to list users: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        ) from exception


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user account.",
)
async def create_user(
    user_data: UserCreate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_permission("users:create")),
) -> UserResponse:
    """Create a new user.

    Args:
        user_data: User creation data.
        db_session: Database session dependency.
        current_user: Authenticated user with create permission.

    Returns:
        Created user response.

    Raises:
        HTTPException: If email already exists or validation fails.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.create_user(user_data)
        logger.info(f"User created: {user.email}")
        return UserResponse.from_orm(user)
    except DuplicateEmailError as exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exception),
        ) from exception
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to create user: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        ) from exception


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Retrieve the currently authenticated user's profile.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Get current user profile.

    Args:
        current_user: Currently authenticated active user.

    Returns:
        Current user's profile.

    Raises:
        HTTPException: If user is inactive.
    """
    return UserResponse.from_orm(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
    description="Update the currently authenticated user's profile.",
)
async def update_current_user_profile(
    profile_data: UserProfileUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Update current user profile.

    Args:
        profile_data: Profile update data.
        db_session: Database session dependency.
        current_user: Currently authenticated active user.

    Returns:
        Updated user profile.

    Raises:
        HTTPException: If update fails or email conflict.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.update_user(
            user_id=current_user.id,
            update_data=profile_data,
        )
        logger.info(f"User profile updated: {user.email}")
        return UserResponse.from_orm(user)
    except DuplicateEmailError as exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exception),
        ) from exception
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to update profile: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
        ) from exception


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Retrieve a specific user by their ID.",
)
async def get_user(
    user_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_permission("users:read")),
) -> UserResponse:
    """Get user by ID.

    Args:
        user_id: UUID of the user to retrieve.
        db_session: Database session dependency.
        current_user: Authenticated user with read permission.

    Returns:
        User response.

    Raises:
        HTTPException: If user not found.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.get_user_by_id(user_id)
        return UserResponse.from_orm(user)
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to get user {user_id}: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user",
        ) from exception


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update a specific user's details.",
)
async def update_user(
    user_id: UUID,
    update_data: UserProfileUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_permission("users:update")),
) -> UserResponse:
    """Update user details.

    Args:
        user_id: UUID of the user to update.
        update_data: User update data.
        db_session: Database session dependency.
        current_user: Authenticated user with update permission.

    Returns:
        Updated user response.

    Raises:
        HTTPException: If user not found or update fails.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.update_user(
            user_id=user_id,
            update_data=update_data,
        )
        logger.info(f"User updated: {user.email}")
        return UserResponse.from_orm(user)
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except DuplicateEmailError as exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to update user {user_id}: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        ) from exception


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
    summary="Update user role",
    description="Update a user's role. Requires admin privileges.",
)
async def update_user_role(
    user_id: UUID,
    role_data: UserRoleUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    """Update user role.

    Args:
        user_id: UUID of the user.
        role_data: New role data.
        db_session: Database session dependency.
        current_user: Authenticated admin user.

    Returns:
        Updated user response.

    Raises:
        HTTPException: If user not found or role update fails.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.update_user_role(
            user_id=user_id,
            new_role=role_data.role,
        )
        logger.info(f"User role updated: {user.email} -> {role_data.role}")
        return UserResponse.from_orm(user)
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to update user role {user_id}: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role",
        ) from exception


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    summary="Update user status",
    description="Update a user's status. Requires admin privileges.",
)
async def update_user_status(
    user_id: UUID,
    status_data: UserStatusUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    """Update user status.

    Args:
        user_id: UUID of the user.
        status_data: New status data.
        db_session: Database session dependency.
        current_user: Authenticated admin user.

    Returns:
        Updated user response.

    Raises:
        HTTPException: If user not found or status update fails.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.update_user_status(
            user_id=user_id,
            new_status=status_data.status,
        )
        logger.info(f"User status updated: {user.email} -> {status_data.status}")
        return UserResponse.from_orm(user)
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to update user status {user_id}: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status",
        ) from exception


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete a user account. Requires admin privileges.",
)
async def delete_user(
    user_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> None:
    """Delete a user.

    Args:
        user_id: UUID of the user to delete.
        db_session: Database session dependency.
        current_user: Authenticated admin user.

    Raises:
        HTTPException: If user not found or deletion fails.
    """
    try:
        user_service = UserService(db_session)
        await user_service.delete_user(user_id)
        logger.info(f"User deleted: {user_id}")
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to delete user {user_id}: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        ) from exception


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Activate user",
    description="Activate a deactivated user account. Requires admin privileges.",
)
async def activate_user(
    user_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    """Activate a user account.

    Args:
        user_id: UUID of the user to activate.
        db_session: Database session dependency.
        current_user: Authenticated admin user.

    Returns:
        Activated user response.

    Raises:
        HTTPException: If user not found or activation fails.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.activate_user(user_id)
        logger.info(f"User activated: {user.email}")
        return UserResponse.from_orm(user)
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except UserInactiveError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to activate user {user_id}: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user",
        ) from exception


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate user",
    description="Deactivate an active user account. Requires admin privileges.",
)
async def deactivate_user(
    user_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    """Deactivate a user account.

    Args:
        user_id: UUID of the user to deactivate.
        db_session: Database session dependency.
        current_user: Authenticated admin user.

    Returns:
        Deactivated user response.

    Raises:
        HTTPException: If user not found or deactivation fails.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.deactivate_user(user_id)
        logger.info(f"User deactivated: {user.email}")
        return UserResponse.from_orm(user)
    except ResourceNotFoundError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except UserInactiveError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    except Exception as exception:
        logger.error(f"Failed to deactivate user {user_id}: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user",
        ) from exception