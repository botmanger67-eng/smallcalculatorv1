"""Initial migration.

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Optional, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Optional[str] = None
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    """Create initial database schema."""
    try:
        # Create users table
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_users_email"),
            sa.UniqueConstraint("username", name="uq_users_username"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_username", "users", ["username"], unique=True)

        # Create roles table
        op.create_table(
            "roles",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("is_system_role", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_roles_name"),
        )
        op.create_index("ix_roles_name", "roles", ["name"], unique=True)

        # Create user_roles junction table
        op.create_table(
            "user_roles",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_user_roles_user_id"),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE", name="fk_user_roles_role_id"),
            sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
        )
        op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
        op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

        # Create permissions table
        op.create_table(
            "permissions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("resource", sa.String(length=100), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_permissions_name"),
            sa.UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),
        )
        op.create_index("ix_permissions_name", "permissions", ["name"], unique=True)

        # Create role_permissions junction table
        op.create_table(
            "role_permissions",
            sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE", name="fk_role_permissions_role_id"),
            sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE", name="fk_role_permissions_permission_id"),
            sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
        )
        op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
        op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

        # Create audit_log table
        op.create_table(
            "audit_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("resource", sa.String(length=100), nullable=False),
            sa.Column("resource_id", sa.String(length=100), nullable=True),
            sa.Column("details", postgresql.JSONB(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL", name="fk_audit_logs_user_id"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

        # Create sessions table
        op.create_table(
            "sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("token", sa.String(length=500), nullable=False),
            sa.Column("refresh_token", sa.String(length=500), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_sessions_user_id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token", name="uq_sessions_token"),
        )
        op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
        op.create_index("ix_sessions_token", "sessions", ["token"], unique=True)
        op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

        # Create settings table
        op.create_table(
            "settings",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column("value", postgresql.JSONB(), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key", name="uq_settings_key"),
        )
        op.create_index("ix_settings_key", "settings", ["key"], unique=True)

    except Exception as exc:
        raise RuntimeError(f"Failed to create initial schema: {exc}") from exc


def downgrade() -> None:
    """Drop initial database schema."""
    try:
        # Drop tables in reverse order to respect foreign key constraints
        op.drop_table("settings")
        op.drop_table("sessions")
        op.drop_table("audit_logs")
        op.drop_table("role_permissions")
        op.drop_table("permissions")
        op.drop_table("user_roles")
        op.drop_table("roles")
        op.drop_table("users")
    except Exception as exc:
        raise RuntimeError(f"Failed to drop initial schema: {exc}") from exc