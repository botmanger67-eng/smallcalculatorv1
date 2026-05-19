"""
User Pydantic schemas for request/response validation and serialization.

This module defines Pydantic models for user-related data structures,
including creation, update, login, and response schemas with full
type validation and error handling.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from pydantic.functional_validators import field_validator


class UserBase(BaseModel):
    """Base schema with common user attributes."""
    
    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"]
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique username",
        examples=["john_doe"]
    )
    is_active: bool = Field(
        default=True,
        description="Whether the user account is active"
    )
    is_verified: bool = Field(
        default=False,
        description="Whether the user email is verified"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """Validate username format."""
        if not value.isalnum() and "_" not in value:
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return value.strip().lower()


class UserCreate(UserBase):
    """Schema for creating a new user."""
    
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (will be hashed)",
        examples=["SecurePass123!"]
    )
    confirm_password: str = Field(
        ...,
        description="Password confirmation",
        examples=["SecurePass123!"]
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Validate password meets security requirements."""
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit")
        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in value):
            raise ValueError("Password must contain at least one special character")
        return value

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info) -> str:
        """Ensure password and confirmation match."""
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    
    email: Optional[EmailStr] = Field(
        default=None,
        description="New email address"
    )
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="New username"
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="New password"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Update active status"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: Optional[str]) -> Optional[str]:
        """Validate username if provided."""
        if value is not None:
            if not value.isalnum() and "_" not in value:
                raise ValueError("Username must contain only alphanumeric characters and underscores")
            return value.strip().lower()
        return value

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: Optional[str]) -> Optional[str]:
        """Validate password if provided."""
        if value is not None:
            if not any(char.isupper() for char in value):
                raise ValueError("Password must contain at least one uppercase letter")
            if not any(char.islower() for char in value):
                raise ValueError("Password must contain at least one lowercase letter")
            if not any(char.isdigit() for char in value):
                raise ValueError("Password must contain at least one digit")
            if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in value):
                raise ValueError("Password must contain at least one special character")
        return value


class UserLogin(BaseModel):
    """Schema for user login request."""
    
    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"]
    )
    password: str = Field(
        ...,
        description="User password",
        examples=["SecurePass123!"]
    )


class UserResponse(UserBase):
    """Schema for user response (excludes sensitive data)."""
    
    id: UUID = Field(
        ...,
        description="Unique user identifier"
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp"
    )
    last_login: Optional[datetime] = Field(
        default=None,
        description="Last successful login timestamp"
    )
    roles: List[str] = Field(
        default=[],
        description="User roles/permissions"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "username": "john_doe",
                "is_active": True,
                "is_verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "last_login": "2024-01-01T00:00:00Z",
                "roles": ["user"]
            }
        }
    )


class UserListResponse(BaseModel):
    """Schema for paginated user list response."""
    
    items: List[UserResponse] = Field(
        ...,
        description="List of users"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of users"
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number"
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page"
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages"
    )

    @field_validator("total_pages")
    @classmethod
    def calculate_total_pages(cls, value: int, info) -> int:
        """Validate total_pages consistency."""
        if "total" in info.data and "page_size" in info.data:
            expected = (info.data["total"] + info.data["page_size"] - 1) // info.data["page_size"]
            if value != expected:
                raise ValueError(f"total_pages must be {expected}")
        return value


class UserPasswordChange(BaseModel):
    """Schema for changing user password."""
    
    current_password: str = Field(
        ...,
        description="Current password for verification"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )
    confirm_new_password: str = Field(
        ...,
        description="Confirm new password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        """Validate new password meets security requirements."""
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit")
        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in value):
            raise ValueError("Password must contain at least one special character")
        return value

    @field_validator("confirm_new_password")
    @classmethod
    def new_passwords_match(cls, value: str, info) -> str:
        """Ensure new password and confirmation match."""
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return value


class UserPasswordReset(BaseModel):
    """Schema for password reset request."""
    
    email: EmailStr = Field(
        ...,
        description="Email address for password reset"
    )


class UserPasswordResetConfirm(BaseModel):
    """Schema for confirming password reset."""
    
    token: str = Field(
        ...,
        description="Password reset token"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )
    confirm_new_password: str = Field(
        ...,
        description="Confirm new password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        """Validate new password meets security requirements."""
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit")
        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in value):
            raise ValueError("Password must contain at least one special character")
        return value

    @field_validator("confirm_new_password")
    @classmethod
    def new_passwords_match(cls, value: str, info) -> str:
        """Ensure new password and confirmation match."""
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return value


class UserEmailVerification(BaseModel):
    """Schema for email verification."""
    
    token: str = Field(
        ...,
        description="Email verification token"
    )


class UserProfileResponse(BaseModel):
    """Schema for user profile response with additional details."""
    
    id: UUID = Field(
        ...,
        description="Unique user identifier"
    )
    email: EmailStr = Field(
        ...,
        description="User email address"
    )
    username: str = Field(
        ...,
        description="Unique username"
    )
    is_active: bool = Field(
        ...,
        description="Whether the user account is active"
    )
    is_verified: bool = Field(
        ...,
        description="Whether the user email is verified"
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp"
    )
    last_login: Optional[datetime] = Field(
        default=None,
        description="Last successful login timestamp"
    )
    roles: List[str] = Field(
        default=[],
        description="User roles/permissions"
    )
    profile_picture_url: Optional[str] = Field(
        default=None,
        description="URL to user profile picture"
    )
    bio: Optional[str] = Field(
        default=None,
        max_length=500,
        description="User biography"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "username": "john_doe",
                "is_active": True,
                "is_verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "last_login": "2024-01-01T00:00:00Z",
                "roles": ["user"],
                "profile_picture_url": "https://example.com/profile.jpg",
                "bio": "Software developer and tech enthusiast"
            }
        }
    )