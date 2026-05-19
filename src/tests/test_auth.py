"""
Unit tests for authentication endpoints.

This module contains comprehensive tests for the authentication system,
including user registration, login, token refresh, password reset,
and session management. Tests are designed to verify both success
and failure scenarios with proper error handling.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth import AuthService
from app.services.user import UserService

# Test constants
TEST_EMAIL: str = "testuser@example.com"
TEST_PASSWORD: str = "SecureP@ssw0rd123!"
TEST_NEW_PASSWORD: str = "NewSecureP@ssw0rd456!"
TEST_INVALID_EMAIL: str = "invalid-email"
TEST_WEAK_PASSWORD: str = "weak"
TEST_RESET_TOKEN: str = "test-reset-token-12345"

# Password hashing context for tests
pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture(scope="module")
def test_app() -> FastAPI:
    """Create test application instance."""
    return app


@pytest.fixture(scope="module")
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """Create test client for API requests."""
    with TestClient(test_app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    from app.db.session import SessionLocal

    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create a test user in the database."""
    user_service: UserService = UserService(db_session)
    auth_service: AuthService = AuthService(db_session)

    # Clean up any existing test user
    existing_user: Optional[User] = user_service.get_by_email(TEST_EMAIL)
    if existing_user:
        user_service.delete(existing_user.id)

    # Create test user
    user: User = user_service.create(
        email=TEST_EMAIL,
        password=TEST_PASSWORD,
        is_active=True,
        is_verified=True,
    )
    return user


@pytest.fixture(scope="function")
def auth_headers(test_user: User) -> Dict[str, str]:
    """Generate authentication headers for test user."""
    access_token: str = create_access_token(
        data={"sub": test_user.email, "user_id": str(test_user.id)}
    )
    return {"Authorization": f"Bearer {access_token}"}


class TestAuthRegistration:
    """Test user registration endpoint."""

    def test_register_success(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test successful user registration."""
        unique_email: str = f"test_{uuid.uuid4().hex[:8]}@example.com"
        payload: Dict[str, str] = {
            "email": unique_email,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 201
        data: Dict[str, Any] = response.json()
        assert data["email"] == unique_email
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data

    def test_register_duplicate_email(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test registration with existing email."""
        payload: Dict[str, str] = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 409
        data: Dict[str, Any] = response.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower()

    def test_register_invalid_email(
        self, client: TestClient
    ) -> None:
        """Test registration with invalid email format."""
        payload: Dict[str, str] = {
            "email": TEST_INVALID_EMAIL,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 422
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_register_weak_password(
        self, client: TestClient
    ) -> None:
        """Test registration with weak password."""
        payload: Dict[str, str] = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": TEST_WEAK_PASSWORD,
            "confirm_password": TEST_WEAK_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 422
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_register_password_mismatch(
        self, client: TestClient
    ) -> None:
        """Test registration with mismatched passwords."""
        payload: Dict[str, str] = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": TEST_PASSWORD,
            "confirm_password": TEST_NEW_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 422
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_register_missing_fields(
        self, client: TestClient
    ) -> None:
        """Test registration with missing required fields."""
        payload: Dict[str, str] = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 422
        data: Dict[str, Any] = response.json()
        assert "detail" in data


class TestAuthLogin:
    """Test user login endpoint."""

    def test_login_success(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test successful login."""
        payload: Dict[str, str] = {
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/login",
            data=payload,
        )

        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test login with incorrect password."""
        payload: Dict[str, str] = {
            "username": TEST_EMAIL,
            "password": "WrongPassword123!",
        }

        response = client.post(
            "/api/v1/auth/login",
            data=payload,
        )

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_login_nonexistent_user(
        self, client: TestClient
    ) -> None:
        """Test login with non-existent email."""
        payload: Dict[str, str] = {
            "username": f"nonexistent_{uuid.uuid4().hex[:8]}@example.com",
            "password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/login",
            data=payload,
        )

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_login_inactive_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test login with inactive user account."""
        user_service: UserService = UserService(db_session)
        inactive_email: str = f"inactive_{uuid.uuid4().hex[:8]}@example.com"
        user: User = user_service.create(
            email=inactive_email,
            password=TEST_PASSWORD,
            is_active=False,
        )

        payload: Dict[str, str] = {
            "username": inactive_email,
            "password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/login",
            data=payload,
        )

        assert response.status_code == 403
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_login_rate_limiting(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test rate limiting on login endpoint."""
        payload: Dict[str, str] = {
            "username": TEST_EMAIL,
            "password": "WrongPassword123!",
        }

        # Attempt multiple failed logins
        for _ in range(5):
            response = client.post(
                "/api/v1/auth/login",
                data=payload,
            )

        # Check if rate limited
        assert response.status_code in [401, 429]


class TestAuthTokenRefresh:
    """Test token refresh endpoint."""

    def test_refresh_token_success(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test successful token refresh."""
        refresh_token: str = create_refresh_token(
            data={"sub": test_user.email, "user_id": str(test_user.id)}
        )

        payload: Dict[str, str] = {
            "refresh_token": refresh_token,
        }

        response = client.post(
            "/api/v1/auth/refresh",
            json=payload,
        )

        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_token_invalid(
        self, client: TestClient
    ) -> None:
        """Test refresh with invalid token."""
        payload: Dict[str, str] = {
            "refresh_token": "invalid-token-12345",
        }

        response = client.post(
            "/api/v1/auth/refresh",
            json=payload,
        )

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_refresh_token_expired(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test refresh with expired token."""
        expired_token: str = create_refresh_token(
            data={"sub": test_user.email, "user_id": str(test_user.id)},
            expires_delta=timedelta(seconds=-1),
        )

        payload: Dict[str, str] = {
            "refresh_token": expired_token,
        }

        response = client.post(
            "/api/v1/auth/refresh",
            json=payload,
        )

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_refresh_token_revoked(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test refresh with revoked token."""
        auth_service: AuthService = AuthService(db_session)
        refresh_token: str = create_refresh_token(
            data={"sub": test_user.email, "user_id": str(test_user.id)}
        )

        # Revoke the token
        auth_service.revoke_refresh_token(refresh_token)

        payload: Dict[str, str] = {
            "refresh_token": refresh_token,
        }

        response = client.post(
            "/api/v1/auth/refresh",
            json=payload,
        )

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data


class TestAuthPasswordReset:
    """Test password reset endpoints."""

    def test_password_reset_request_success(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test successful password reset request."""
        payload: Dict[str, str] = {
            "email": TEST_EMAIL,
        }

        response = client.post(
            "/api/v1/auth/password-reset-request",
            json=payload,
        )

        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert "message" in data
        assert "reset_token" in data

    def test_password_reset_request_nonexistent(
        self, client: TestClient
    ) -> None:
        """Test password reset request for non-existent email."""
        payload: Dict[str, str] = {
            "email": f"nonexistent_{uuid.uuid4().hex[:8]}@example.com",
        }

        response = client.post(
            "/api/v1/auth/password-reset-request",
            json=payload,
        )

        assert response.status_code == 404
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_password_reset_confirm_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successful password reset confirmation."""
        auth_service: AuthService = AuthService(db_session)
        reset_token: str = auth_service.create_password_reset_token(TEST_EMAIL)

        payload: Dict[str, str] = {
            "token": reset_token,
            "new_password": TEST_NEW_PASSWORD,
            "confirm_password": TEST_NEW_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/password-reset-confirm",
            json=payload,
        )

        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert "message" in data

        # Verify new password works
        login_payload: Dict[str, str] = {
            "username": TEST_EMAIL,
            "password": TEST_NEW_PASSWORD,
        }
        login_response = client.post(
            "/api/v1/auth/login",
            data=login_payload,
        )
        assert login_response.status_code == 200

    def test_password_reset_confirm_invalid_token(
        self, client: TestClient
    ) -> None:
        """Test password reset with invalid token."""
        payload: Dict[str, str] = {
            "token": "invalid-reset-token",
            "new_password": TEST_NEW_PASSWORD,
            "confirm_password": TEST_NEW_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/password-reset-confirm",
            json=payload,
        )

        assert response.status_code == 400
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_password_reset_confirm_expired_token(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test password reset with expired token."""
        auth_service: AuthService = AuthService(db_session)
        reset_token: str = auth_service.create_password_reset_token(
            TEST_EMAIL, expires_in=timedelta(seconds=-1)
        )

        payload: Dict[str, str] = {
            "token": reset_token,
            "new_password": TEST_NEW_PASSWORD,
            "confirm_password": TEST_NEW_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/password-reset-confirm",
            json=payload,
        )

        assert response.status_code == 400
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_password_reset_confirm_weak_password(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test password reset with weak new password."""
        auth_service: AuthService = AuthService(db_session)
        reset_token: str = auth_service.create_password_reset_token(TEST_EMAIL)

        payload: Dict[str, str] = {
            "token": reset_token,
            "new_password": TEST_WEAK_PASSWORD,
            "confirm_password": TEST_WEAK_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/password-reset-confirm",
            json=payload,
        )

        assert response.status_code == 422
        data: Dict[str, Any] = response.json()
        assert "detail" in data


class TestAuthLogout:
    """Test user logout endpoint."""

    def test_logout_success(
        self, client: TestClient, auth_headers: Dict[str, str]
    ) -> None:
        """Test successful logout."""
        response = client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert "message" in data

    def test_logout_without_token(
        self, client: TestClient
    ) -> None:
        """Test logout without authentication."""
        response = client.post("/api/v1/auth/logout")

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_logout_invalid_token(
        self, client: TestClient
    ) -> None:
        """Test logout with invalid token."""
        headers: Dict[str, str] = {
            "Authorization": "Bearer invalid-token-12345"
        }
        response = client.post(
            "/api/v1/auth/logout",
            headers=headers,
        )

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data


class TestAuthProfile:
    """Test user profile endpoint."""

    def test_get_profile_success(
        self, client: TestClient, auth_headers: Dict[str, str], test_user: User
    ) -> None:
        """Test successful profile retrieval."""
        response = client.get(
            "/api/v1/auth/profile",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert data["email"] == TEST_EMAIL
        assert "id" in data
        assert "created_at" in data

    def test_get_profile_unauthorized(
        self, client: TestClient
    ) -> None:
        """Test profile retrieval without authentication."""
        response = client.get("/api/v1/auth/profile")

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_update_profile_success(
        self, client: TestClient, auth_headers: Dict[str, str], test_user: User
    ) -> None:
        """Test successful profile update."""
        payload: Dict[str, str] = {
            "full_name": "Updated Test User",
            "phone": "+1234567890",
        }

        response = client.put(
            "/api/v1/auth/profile",
            headers=auth_headers,
            json=payload,
        )

        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert data["full_name"] == "Updated Test User"
        assert data["phone"] == "+1234567890"


class TestAuthSecurity:
    """Test authentication security features."""

    def test_brute_force_protection(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test brute force protection on login."""
        payload: Dict[str, str] = {
            "username": TEST_EMAIL,
            "password": "WrongPassword123!",
        }

        # Attempt multiple rapid logins
        for _ in range(10):
            response = client.post(
                "/api/v1/auth/login",
                data=payload,
            )

        # Should be rate limited
        assert response.status_code == 429

    def test_token_expiry(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test access token expiry."""
        # Create an expired token
        expired_token: str = create_access_token(
            data={"sub": test_user.email, "user_id": str(test_user.id)},
            expires_delta=timedelta(seconds=-1),
        )

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {expired_token}"
        }

        response = client.get(
            "/api/v1/auth/profile",
            headers=headers,
        )

        assert response.status_code == 401
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_sql_injection_prevention(
        self, client: TestClient
    ) -> None:
        """Test SQL injection prevention in login."""
        malicious_inputs: list[str] = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users; --",
            "admin' --",
        ]

        for malicious_input in malicious_inputs:
            payload: Dict[str, str] = {
                "username": malicious_input,
                "password": TEST_PASSWORD,
            }

            response = client.post(
                "/api/v1/auth/login",
                data=payload,
            )

            # Should not return success for SQL injection attempts
            assert response.status_code != 200

    def test_xss_prevention(
        self, client: TestClient, auth_headers: Dict[str, str]
    ) -> None:
        """Test XSS prevention in profile update."""
        xss_payload: str = "<script>alert('XSS')</script>"
        payload: Dict[str, str] = {
            "full_name": xss_payload,
        }

        response = client.put(
            "/api/v1/auth/profile",
            headers=auth_headers,
            json=payload,
        )

        # Should sanitize or reject XSS payload
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data: Dict[str, Any] = response.json()
            assert "<script>" not in data.get("full_name", "")


class TestAuthEdgeCases:
    """Test authentication edge cases."""

    def test_concurrent_sessions(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test multiple concurrent sessions for same user."""
        # Create multiple tokens for same user
        tokens: list[str] = []
        for _ in range(3):
            token: str = create_access_token(
                data={
                    "sub": test_user.email,
                    "user_id": str(test_user.id),
                }
            )
            tokens.append(token)

        # All tokens should be valid
        for token in tokens:
            headers: Dict[str, str] = {
                "Authorization": f"Bearer {token}"
            }
            response = client.get(
                "/api/v1/auth/profile",
                headers=headers,
            )
            assert response.status_code == 200

    def test_special_characters_in_password(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test registration with special characters in password."""
        special_password: str = "P@ssw0rd!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        unique_email: str = f"special_{uuid.uuid4().hex[:8]}@example.com"

        payload: Dict[str, str] = {
            "email": unique_email,
            "password": special_password,
            "confirm_password": special_password,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 201

        # Verify login with special characters
        login_payload: Dict[str, str] = {
            "username": unique_email,
            "password": special_password,
        }
        login_response = client.post(
            "/api/v1/auth/login",
            data=login_payload,
        )
        assert login_response.status_code == 200

    def test_unicode_email(
        self, client: TestClient
    ) -> None:
        """Test registration with unicode email."""
        unicode_email: str = "test@üñîçødé.com"
        payload: Dict[str, str] = {
            "email": unicode_email,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        # Should handle unicode properly
        assert response.status_code in [201, 422]

    def test_empty_request_body(
        self, client: TestClient
    ) -> None:
        """Test endpoints with empty request body."""
        endpoints: list[tuple[str, str]] = [
            ("POST", "/api/v1/auth/register"),
            ("POST", "/api/v1/auth/login"),
            ("POST", "/api/v1/auth/refresh"),
            ("POST", "/api/v1/auth/password-reset-request"),
            ("POST", "/api/v1/auth/password-reset-confirm"),
        ]

        for method, endpoint in endpoints:
            if method == "POST":
                response = client.post(endpoint, json={})
            else:
                response = client.get(endpoint)

            assert response.status_code == 422


class TestAuthServiceIntegration:
    """Test AuthService integration with database."""

    def test_password_hashing(self, db_session: Session) -> None:
        """Test password hashing and verification."""
        auth_service: AuthService = AuthService(db_session)
        hashed_password: str = auth_service.hash_password(TEST_PASSWORD)

        assert hashed_password != TEST_PASSWORD
        assert auth_service.verify_password(TEST_PASSWORD, hashed_password)
        assert not auth_service.verify_password(
            "WrongPassword123!", hashed_password
        )

    def test_token_blacklisting(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test token blacklisting after logout."""
        auth_service: AuthService = AuthService(db_session)

        # Create and use a token
        token: str = create_access_token(
            data={"sub": test_user.email, "user_id": str(test_user.id)}
        )

        # Blacklist the token
        auth_service.blacklist_token(token)

        # Try to use blacklisted token
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {token}"
        }
        response = client.get(
            "/api/v1/auth/profile",
            headers=headers,
        )

        assert response.status_code == 401

    def test_password_reset_token_validation(
        self, db_session: Session, test_user: User
    ) -> None:
        """Test password reset token creation and validation."""
        auth_service: AuthService = AuthService(db_session)

        # Create reset token
        reset_token: str = auth_service.create_password_reset_token(TEST_EMAIL)
        assert reset_token is not None

        # Validate reset token
        validated_email: Optional[str] = auth_service.validate_reset_token(
            reset_token
        )
        assert validated_email == TEST_EMAIL

        # Validate invalid token
        invalid_result: Optional[str] = auth_service.validate_reset_token(
            "invalid-token"
        )
        assert invalid_result is None


class TestAuthErrorHandling:
    """Test authentication error handling scenarios."""

    def test_database_connection_error(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error handling when database connection fails."""
        def mock_get_db() -> Generator:
            raise Exception("Database connection failed")
            yield None  # type: ignore

        monkeypatch.setattr(
            "app.api.v1.endpoints.auth.get_db",
            mock_get_db,
        )

        payload: Dict[str, str] = {
            "email": f"error_{uuid.uuid4().hex[:8]}@example.com",
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert response.status_code == 500
        data: Dict[str, Any] = response.json()
        assert "detail" in data

    def test_malformed_request_body(
        self, client: TestClient
    ) -> None:
        """Test handling of malformed request bodies."""
        response = client.post(
            "/api/v1/auth/register",
            data="not-json-data",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_invalid_content_type(
        self, client: TestClient
    ) -> None:
        """Test handling of invalid content type."""
        response = client.post(
            "/api/v1/auth/login",
            data="username=test&password=test",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 415


if __name__ == "__main__":
    pytest.main(["-v", "--cov=app", "--cov-report=term-missing", __file__])