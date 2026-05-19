"""User SQLAlchemy model for the application."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from src.database import Base
from src.models.enums import UserRole, UserStatus


class User(Base):
    """User model representing an authenticated user in the system.

    This model stores user credentials, profile information, and account status.
    Passwords are hashed using Werkzeug's security utilities before storage.

    Attributes:
        id: Unique identifier (UUID v4).
        email: User's email address (unique, used for authentication).
        username: User's display name (unique).
        password_hash: Hashed password string.
        first_name: User's first name.
        last_name: User's last name.
        role: User's role in the system (UserRole enum).
        status: Account status (UserStatus enum).
        is_active: Whether the account is active.
        is_verified: Whether the email has been verified.
        last_login_at: Timestamp of last successful login.
        created_at: Timestamp when the record was created.
        updated_at: Timestamp when the record was last updated.
    """

    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        Index("ix_users_status", "status"),
        Index("ix_users_role", "role"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
        index=True,
    )
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    username = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash = Column(
        String(255),
        nullable=False,
    )
    first_name = Column(
        String(100),
        nullable=False,
    )
    last_name = Column(
        String(100),
        nullable=False,
    )
    role = Column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.USER,
        index=True,
    )
    status = Column(
        Enum(UserStatus),
        nullable=False,
        default=UserStatus.ACTIVE,
        index=True,
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        """Return string representation of the User instance.

        Returns:
            str: Formatted string with user ID, email, and role.
        """
        return (
            f"<User(id={self.id}, email='{self.email}', "
            f"role='{self.role.value}', status='{self.status.value}')>"
        )

    @validates("email")
    def validate_email(self, key: str, value: str) -> str:
        """Validate and normalize email address.

        Args:
            key: The field name being validated.
            value: The email address to validate.

        Returns:
            str: Lowercased and stripped email address.

        Raises:
            ValueError: If email is empty, too long, or invalid format.
        """
        if not value or not value.strip():
            raise ValueError("Email address cannot be empty")

        normalized_email = value.strip().lower()

        if len(normalized_email) > 255:
            raise ValueError("Email address exceeds maximum length of 255 characters")

        if "@" not in normalized_email or "." not in normalized_email.split("@")[-1]:
            raise ValueError("Invalid email address format")

        return normalized_email

    @validates("username")
    def validate_username(self, key: str, value: str) -> str:
        """Validate username format and length.

        Args:
            key: The field name being validated.
            value: The username to validate.

        Returns:
            str: Stripped username.

        Raises:
            ValueError: If username is empty, too short/long, or contains invalid characters.
        """
        if not value or not value.strip():
            raise ValueError("Username cannot be empty")

        username = value.strip()

        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")

        if len(username) > 50:
            raise ValueError("Username exceeds maximum length of 50 characters")

        if not username.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Username can only contain letters, numbers, underscores, and hyphens"
            )

        return username

    @validates("first_name", "last_name")
    def validate_name(self, key: str, value: str) -> str:
        """Validate name fields.

        Args:
            key: The field name being validated.
            value: The name value to validate.

        Returns:
            str: Stripped and capitalized name.

        Raises:
            ValueError: If name is empty or too long.
        """
        if not value or not value.strip():
            raise ValueError(f"{key.replace('_', ' ').title()} cannot be empty")

        name = value.strip()

        if len(name) > 100:
            raise ValueError(
                f"{key.replace('_', ' ').title()} exceeds maximum length of 100 characters"
            )

        if not name.replace(" ", "").replace("-", "").isalpha():
            raise ValueError(
                f"{key.replace('_', ' ').title()} can only contain letters, spaces, and hyphens"
            )

        return name

    def set_password(self, password: str) -> None:
        """Hash and set the user's password.

        Args:
            password: Plain text password to hash and store.

        Raises:
            ValueError: If password is empty or too short.
        """
        if not password:
            raise ValueError("Password cannot be empty")

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if len(password) > 128:
            raise ValueError("Password exceeds maximum length of 128 characters")

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash.

        Args:
            password: Plain text password to verify.

        Returns:
            bool: True if password matches, False otherwise.
        """
        if not password or not self.password_hash:
            return False

        return check_password_hash(self.password_hash, password)

    def update_last_login(self) -> None:
        """Update the last_login_at timestamp to current UTC time."""
        self.last_login_at = datetime.utcnow()

    def activate(self) -> None:
        """Activate the user account."""
        self.is_active = True
        self.status = UserStatus.ACTIVE

    def deactivate(self) -> None:
        """Deactivate the user account."""
        self.is_active = False
        self.status = UserStatus.INACTIVE

    def suspend(self) -> None:
        """Suspend the user account."""
        self.is_active = False
        self.status = UserStatus.SUSPENDED

    def verify_email(self) -> None:
        """Mark the user's email as verified."""
        self.is_verified = True

    def is_admin(self) -> bool:
        """Check if the user has admin role.

        Returns:
            bool: True if user is admin, False otherwise.
        """
        return self.role == UserRole.ADMIN

    def is_moderator(self) -> bool:
        """Check if the user has moderator role.

        Returns:
            bool: True if user is moderator, False otherwise.
        """
        return self.role == UserRole.MODERATOR

    def to_dict(self) -> dict:
        """Convert user instance to dictionary representation.

        Returns:
            dict: Dictionary containing user data (excluding password hash).
        """
        return {
            "id": str(self.id),
            "email": self.email,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role": self.role.value,
            "status": self.status.value,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }