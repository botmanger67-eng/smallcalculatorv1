"""User repository module for database operations."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from loguru import logger

from src.models.user import User
from src.schemas.user import UserCreate, UserUpdate
from src.core.exceptions import (
    DatabaseError,
    NotFoundError,
    DuplicateEntryError,
    ValidationError
)


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize UserRepository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user in the database.

        Args:
            user_data: User creation schema with validated data

        Returns:
            Created User instance

        Raises:
            DuplicateEntryError: If user with same email exists
            DatabaseError: If database operation fails
            ValidationError: If user data validation fails
        """
        try:
            existing_user = await self.get_by_email(user_data.email)
            if existing_user:
                raise DuplicateEntryError(
                    f"User with email {user_data.email} already exists"
                )

            user = User(
                email=user_data.email,
                username=user_data.username,
                hashed_password=user_data.password,
                is_active=user_data.is_active if hasattr(user_data, 'is_active') else True,
                is_verified=user_data.is_verified if hasattr(user_data, 'is_verified') else False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

            logger.info(f"Created user with ID: {user.id}")
            return user

        except IntegrityError as exc:
            await self.session.rollback()
            logger.error(f"Integrity error creating user: {exc}")
            raise DuplicateEntryError(
                f"User with email {user_data.email} already exists"
            ) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.error(f"Database error creating user: {exc}")
            raise DatabaseError(f"Failed to create user: {exc}") from exc

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Retrieve a user by their ID.

        Args:
            user_id: UUID of the user to retrieve

        Returns:
            User instance if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(User).where(User.id == user_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.error(f"Database error retrieving user by ID {user_id}: {exc}")
            raise DatabaseError(f"Failed to retrieve user: {exc}") from exc

    async def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by their email address.

        Args:
            email: Email address to search for

        Returns:
            User instance if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(User).where(User.email == email)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.error(f"Database error retrieving user by email {email}: {exc}")
            raise DatabaseError(f"Failed to retrieve user by email: {exc}") from exc

    async def get_by_username(self, username: str) -> Optional[User]:
        """Retrieve a user by their username.

        Args:
            username: Username to search for

        Returns:
            User instance if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(User).where(User.username == username)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.error(f"Database error retrieving user by username {username}: {exc}")
            raise DatabaseError(f"Failed to retrieve user by username: {exc}") from exc

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[User]:
        """Retrieve all users with pagination and optional filters.

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            filters: Optional dictionary of filter conditions

        Returns:
            List of User instances

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(User)

            if filters:
                for key, value in filters.items():
                    if hasattr(User, key):
                        query = query.where(getattr(User, key) == value)

            query = query.offset(skip).limit(limit)
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            logger.error(f"Database error retrieving users: {exc}")
            raise DatabaseError(f"Failed to retrieve users: {exc}") from exc

    async def update(self, user_id: UUID, update_data: UserUpdate) -> User:
        """Update an existing user.

        Args:
            user_id: UUID of the user to update
            update_data: User update schema with fields to update

        Returns:
            Updated User instance

        Raises:
            NotFoundError: If user not found
            DuplicateEntryError: If email/username already exists
            DatabaseError: If database operation fails
        """
        try:
            user = await self.get_by_id(user_id)
            if not user:
                raise NotFoundError(f"User with ID {user_id} not found")

            update_dict = update_data.dict(exclude_unset=True)
            if not update_dict:
                return user

            # Check for duplicate email if email is being updated
            if 'email' in update_dict and update_dict['email'] != user.email:
                existing = await self.get_by_email(update_dict['email'])
                if existing:
                    raise DuplicateEntryError(
                        f"User with email {update_dict['email']} already exists"
                    )

            # Check for duplicate username if username is being updated
            if 'username' in update_dict and update_dict['username'] != user.username:
                existing = await self.get_by_username(update_dict['username'])
                if existing:
                    raise DuplicateEntryError(
                        f"User with username {update_dict['username']} already exists"
                    )

            update_dict['updated_at'] = datetime.utcnow()

            query = (
                update(User)
                .where(User.id == user_id)
                .values(**update_dict)
                .execution_options(synchronize_session="fetch")
            )
            await self.session.execute(query)
            await self.session.commit()

            updated_user = await self.get_by_id(user_id)
            logger.info(f"Updated user with ID: {user_id}")
            return updated_user

        except (NotFoundError, DuplicateEntryError):
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            logger.error(f"Integrity error updating user {user_id}: {exc}")
            raise DuplicateEntryError("Email or username already exists") from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.error(f"Database error updating user {user_id}: {exc}")
            raise DatabaseError(f"Failed to update user: {exc}") from exc

    async def delete(self, user_id: UUID) -> None:
        """Delete a user from the database.

        Args:
            user_id: UUID of the user to delete

        Raises:
            NotFoundError: If user not found
            DatabaseError: If database operation fails
        """
        try:
            user = await self.get_by_id(user_id)
            if not user:
                raise NotFoundError(f"User with ID {user_id} not found")

            query = delete(User).where(User.id == user_id)
            await self.session.execute(query)
            await self.session.commit()

            logger.info(f"Deleted user with ID: {user_id}")
        except NotFoundError:
            raise
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.error(f"Database error deleting user {user_id}: {exc}")
            raise DatabaseError(f"Failed to delete user: {exc}") from exc

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count users with optional filters.

        Args:
            filters: Optional dictionary of filter conditions

        Returns:
            Count of users matching filters

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(User)

            if filters:
                for key, value in filters.items():
                    if hasattr(User, key):
                        query = query.where(getattr(User, key) == value)

            result = await self.session.execute(query)
            return len(result.scalars().all())
        except SQLAlchemyError as exc:
            logger.error(f"Database error counting users: {exc}")
            raise DatabaseError(f"Failed to count users: {exc}") from exc

    async def exists(self, user_id: UUID) -> bool:
        """Check if a user exists by ID.

        Args:
            user_id: UUID to check

        Returns:
            True if user exists, False otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            user = await self.get_by_id(user_id)
            return user is not None
        except SQLAlchemyError as exc:
            logger.error(f"Database error checking user existence {user_id}: {exc}")
            raise DatabaseError(f"Failed to check user existence: {exc}") from exc

    async def update_last_login(self, user_id: UUID) -> None:
        """Update the last login timestamp for a user.

        Args:
            user_id: UUID of the user

        Raises:
            NotFoundError: If user not found
            DatabaseError: If database operation fails
        """
        try:
            user = await self.get_by_id(user_id)
            if not user:
                raise NotFoundError(f"User with ID {user_id} not found")

            query = (
                update(User)
                .where(User.id == user_id)
                .values(
                    last_login=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            await self.session.execute(query)
            await self.session.commit()

            logger.info(f"Updated last login for user ID: {user_id}")
        except NotFoundError:
            raise
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.error(f"Database error updating last login for user {user_id}: {exc}")
            raise DatabaseError(f"Failed to update last login: {exc}") from exc

    async def search(
        self,
        query_string: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Search users by email or username.

        Args:
            query_string: Search query string
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching User instances

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            search_pattern = f"%{query_string}%"
            query = (
                select(User)
                .where(
                    and_(
                        User.is_active == True,
                        (
                            User.email.ilike(search_pattern) |
                            User.username.ilike(search_pattern)
                        )
                    )
                )
                .offset(skip)
                .limit(limit)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            logger.error(f"Database error searching users: {exc}")
            raise DatabaseError(f"Failed to search users: {exc}") from exc

    async def bulk_create(self, users_data: List[UserCreate]) -> List[User]:
        """Create multiple users in a single transaction.

        Args:
            users_data: List of user creation schemas

        Returns:
            List of created User instances

        Raises:
            DuplicateEntryError: If any user data conflicts
            DatabaseError: If database operation fails
        """
        try:
            created_users = []
            for user_data in users_data:
                user = User(
                    email=user_data.email,
                    username=user_data.username,
                    hashed_password=user_data.password,
                    is_active=True,
                    is_verified=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.session.add(user)
                created_users.append(user)

            await self.session.commit()
            for user in created_users:
                await self.session.refresh(user)

            logger.info(f"Bulk created {len(created_users)} users")
            return created_users

        except IntegrityError as exc:
            await self.session.rollback()
            logger.error(f"Integrity error in bulk user creation: {exc}")
            raise DuplicateEntryError("Duplicate email or username in bulk creation") from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.error(f"Database error in bulk user creation: {exc}")
            raise DatabaseError(f"Failed to bulk create users: {exc}") from exc