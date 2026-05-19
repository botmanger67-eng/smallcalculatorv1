"""User service module implementing business logic for user management."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.models.user import User, UserStatus, UserRole
from src.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserFilter,
    UserPasswordChange,
)
from src.core.exceptions import (
    UserNotFoundException,
    UserAlreadyExistsException,
    InvalidPasswordException,
    DatabaseException,
    ValidationException,
)
from src.core.security import hash_password, verify_password, generate_password_reset_token
from src.core.config import settings

logger = logging.getLogger(__name__)


class UserService:
    """Service class for user business logic operations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize UserService with database session.

        Args:
            db_session: Async SQLAlchemy database session
        """
        self.db_session = db_session

    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user with validated data.

        Args:
            user_data: User creation schema with validated fields

        Returns:
            UserResponse with created user details

        Raises:
            UserAlreadyExistsException: If email or username already exists
            ValidationException: If user data validation fails
            DatabaseException: If database operation fails
        """
        try:
            existing_user = await self._find_user_by_email_or_username(
                email=user_data.email,
                username=user_data.username,
            )
            if existing_user:
                raise UserAlreadyExistsException(
                    detail=f"User with email '{user_data.email}' or username '{user_data.username}' already exists"
                )

            hashed_password = hash_password(user_data.password.get_secret_value())
            
            new_user = User(
                id=uuid4(),
                email=user_data.email,
                username=user_data.username,
                hashed_password=hashed_password,
                full_name=user_data.full_name,
                role=user_data.role or UserRole.USER,
                status=UserStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            self.db_session.add(new_user)
            await self.db_session.commit()
            await self.db_session.refresh(new_user)

            logger.info(f"User created successfully: {new_user.id}")
            return UserResponse.model_validate(new_user)

        except IntegrityError as exc:
            await self.db_session.rollback()
            logger.error(f"Database integrity error creating user: {exc}")
            raise UserAlreadyExistsException(
                detail="User with this email or username already exists"
            )
        except SQLAlchemyError as exc:
            await self.db_session.rollback()
            logger.error(f"Database error creating user: {exc}")
            raise DatabaseException(detail="Failed to create user in database")

    async def get_user_by_id(self, user_id: UUID) -> UserResponse:
        """Retrieve a user by their unique identifier.

        Args:
            user_id: UUID of the user to retrieve

        Returns:
            UserResponse with user details

        Raises:
            UserNotFoundException: If user with given ID doesn't exist
            DatabaseException: If database operation fails
        """
        try:
            query = select(User).where(User.id == user_id)
            result = await self.db_session.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                raise UserNotFoundException(detail=f"User with ID '{user_id}' not found")

            return UserResponse.model_validate(user)

        except SQLAlchemyError as exc:
            logger.error(f"Database error retrieving user {user_id}: {exc}")
            raise DatabaseException(detail="Failed to retrieve user from database")

    async def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Retrieve a user by their email address.

        Args:
            email: Email address of the user

        Returns:
            UserResponse if found, None otherwise

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            query = select(User).where(User.email == email)
            result = await self.db_session.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                return None

            return UserResponse.model_validate(user)

        except SQLAlchemyError as exc:
            logger.error(f"Database error retrieving user by email {email}: {exc}")
            raise DatabaseException(detail="Failed to retrieve user from database")

    async def update_user(self, user_id: UUID, update_data: UserUpdate) -> UserResponse:
        """Update user information.

        Args:
            user_id: UUID of the user to update
            update_data: User update schema with fields to update

        Returns:
            UserResponse with updated user details

        Raises:
            UserNotFoundException: If user with given ID doesn't exist
            UserAlreadyExistsException: If updated email/username conflicts with existing user
            ValidationException: If update data validation fails
            DatabaseException: If database operation fails
        """
        try:
            user = await self._get_user_entity(user_id)
            if not user:
                raise UserNotFoundException(detail=f"User with ID '{user_id}' not found")

            update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)

            if "email" in update_dict or "username" in update_dict:
                existing_user = await self._find_user_by_email_or_username(
                    email=update_dict.get("email"),
                    username=update_dict.get("username"),
                    exclude_user_id=user_id,
                )
                if existing_user:
                    raise UserAlreadyExistsException(
                        detail="Updated email or username conflicts with existing user"
                    )

            if "password" in update_dict:
                update_dict["hashed_password"] = hash_password(
                    update_dict.pop("password").get_secret_value()
                )

            update_dict["updated_at"] = datetime.now(timezone.utc)

            query = (
                update(User)
                .where(User.id == user_id)
                .values(**update_dict)
                .execution_options(synchronize_session="fetch")
            )
            await self.db_session.execute(query)
            await self.db_session.commit()

            updated_user = await self._get_user_entity(user_id)
            logger.info(f"User updated successfully: {user_id}")
            return UserResponse.model_validate(updated_user)

        except SQLAlchemyError as exc:
            await self.db_session.rollback()
            logger.error(f"Database error updating user {user_id}: {exc}")
            raise DatabaseException(detail="Failed to update user in database")

    async def delete_user(self, user_id: UUID) -> None:
        """Delete a user from the system.

        Args:
            user_id: UUID of the user to delete

        Raises:
            UserNotFoundException: If user with given ID doesn't exist
            DatabaseException: If database operation fails
        """
        try:
            user = await self._get_user_entity(user_id)
            if not user:
                raise UserNotFoundException(detail=f"User with ID '{user_id}' not found")

            query = delete(User).where(User.id == user_id)
            await self.db_session.execute(query)
            await self.db_session.commit()

            logger.info(f"User deleted successfully: {user_id}")

        except SQLAlchemyError as exc:
            await self.db_session.rollback()
            logger.error(f"Database error deleting user {user_id}: {exc}")
            raise DatabaseException(detail="Failed to delete user from database")

    async def list_users(
        self,
        filters: Optional[UserFilter] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[UserResponse]:
        """Retrieve a paginated list of users with optional filters.

        Args:
            filters: Optional filter criteria for users
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of UserResponse objects

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            query = select(User)

            if filters:
                if filters.status:
                    query = query.where(User.status == filters.status)
                if filters.role:
                    query = query.where(User.role == filters.role)
                if filters.search_term:
                    search_pattern = f"%{filters.search_term}%"
                    query = query.where(
                        User.username.ilike(search_pattern)
                        | User.email.ilike(search_pattern)
                        | User.full_name.ilike(search_pattern)
                    )
                if filters.created_after:
                    query = query.where(User.created_at >= filters.created_after)
                if filters.created_before:
                    query = query.where(User.created_at <= filters.created_before)

            query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
            result = await self.db_session.execute(query)
            users = result.scalars().all()

            return [UserResponse.model_validate(user) for user in users]

        except SQLAlchemyError as exc:
            logger.error(f"Database error listing users: {exc}")
            raise DatabaseException(detail="Failed to retrieve users from database")

    async def change_password(
        self, user_id: UUID, password_data: UserPasswordChange
    ) -> None:
        """Change user password with validation.

        Args:
            user_id: UUID of the user
            password_data: Password change schema with current and new password

        Raises:
            UserNotFoundException: If user with given ID doesn't exist
            InvalidPasswordException: If current password is incorrect
            ValidationException: If new password validation fails
            DatabaseException: If database operation fails
        """
        try:
            user = await self._get_user_entity(user_id)
            if not user:
                raise UserNotFoundException(detail=f"User with ID '{user_id}' not found")

            if not verify_password(
                password_data.current_password.get_secret_value(),
                user.hashed_password,
            ):
                raise InvalidPasswordException(detail="Current password is incorrect")

            new_hashed_password = hash_password(
                password_data.new_password.get_secret_value()
            )

            query = (
                update(User)
                .where(User.id == user_id)
                .values(
                    hashed_password=new_hashed_password,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.db_session.execute(query)
            await self.db_session.commit()

            logger.info(f"Password changed successfully for user: {user_id}")

        except SQLAlchemyError as exc:
            await self.db_session.rollback()
            logger.error(f"Database error changing password for user {user_id}: {exc}")
            raise DatabaseException(detail="Failed to change password in database")

    async def deactivate_user(self, user_id: UUID) -> UserResponse:
        """Deactivate a user account.

        Args:
            user_id: UUID of the user to deactivate

        Returns:
            UserResponse with updated user details

        Raises:
            UserNotFoundException: If user with given ID doesn't exist
            DatabaseException: If database operation fails
        """
        try:
            user = await self._get_user_entity(user_id)
            if not user:
                raise UserNotFoundException(detail=f"User with ID '{user_id}' not found")

            query = (
                update(User)
                .where(User.id == user_id)
                .values(
                    status=UserStatus.INACTIVE,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.db_session.execute(query)
            await self.db_session.commit()

            updated_user = await self._get_user_entity(user_id)
            logger.info(f"User deactivated successfully: {user_id}")
            return UserResponse.model_validate(updated_user)

        except SQLAlchemyError as exc:
            await self.db_session.rollback()
            logger.error(f"Database error deactivating user {user_id}: {exc}")
            raise DatabaseException(detail="Failed to deactivate user in database")

    async def activate_user(self, user_id: UUID) -> UserResponse:
        """Activate a previously deactivated user account.

        Args:
            user_id: UUID of the user to activate

        Returns:
            UserResponse with updated user details

        Raises:
            UserNotFoundException: If user with given ID doesn't exist
            DatabaseException: If database operation fails
        """
        try:
            user = await self._get_user_entity(user_id)
            if not user:
                raise UserNotFoundException(detail=f"User with ID '{user_id}' not found")

            query = (
                update(User)
                .where(User.id == user_id)
                .values(
                    status=UserStatus.ACTIVE,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.db_session.execute(query)
            await self.db_session.commit()

            updated_user = await self._get_user_entity(user_id)
            logger.info(f"User activated successfully: {user_id}")
            return UserResponse.model_validate(updated_user)

        except SQLAlchemyError as exc:
            await self.db_session.rollback()
            logger.error(f"Database error activating user {user_id}: {exc}")
            raise DatabaseException(detail="Failed to activate user in database")

    async def count_users(self, filters: Optional[UserFilter] = None) -> int:
        """Count users with optional filters.

        Args:
            filters: Optional filter criteria for counting users

        Returns:
            Total count of matching users

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            query = select(User)

            if filters:
                if filters.status:
                    query = query.where(User.status == filters.status)
                if filters.role:
                    query = query.where(User.role == filters.role)
                if filters.search_term:
                    search_pattern = f"%{filters.search_term}%"
                    query = query.where(
                        User.username.ilike(search_pattern)
                        | User.email.ilike(search_pattern)
                        | User.full_name.ilike(search_pattern)
                    )

            result = await self.db_session.execute(query)
            return len(result.scalars().all())

        except SQLAlchemyError as exc:
            logger.error(f"Database error counting users: {exc}")
            raise DatabaseException(detail="Failed to count users in database")

    async def _get_user_entity(self, user_id: UUID) -> Optional[User]:
        """Retrieve user entity from database.

        Args:
            user_id: UUID of the user

        Returns:
            User entity if found, None otherwise

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            query = select(User).where(User.id == user_id)
            result = await self.db_session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.error(f"Database error retrieving user entity {user_id}: {exc}")
            raise DatabaseException(detail="Failed to retrieve user entity from database")

    async def _find_user_by_email_or_username(
        self,
        email: Optional[str] = None,
        username: Optional[str] = None,
        exclude_user_id: Optional[UUID] = None,
    ) -> Optional[User]:
        """Find user by email or username, optionally excluding a specific user ID.

        Args:
            email: Email to search for
            username: Username to search for
            exclude_user_id: Optional user ID to exclude from search

        Returns:
            User entity if found, None otherwise

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            conditions = []
            if email:
                conditions.append(User.email == email)
            if username:
                conditions.append(User.username == username)

            if not conditions:
                return None

            query = select(User).where(
                conditions[0] if len(conditions) == 1 else conditions[0] | conditions[1]
            )

            if exclude_user_id:
                query = query.where(User.id != exclude_user_id)

            result = await self.db_session.execute(query)
            return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            logger.error(f"Database error finding user by email/username: {exc}")
            raise DatabaseException(
                detail="Failed to search for user in database"
            )