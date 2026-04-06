"""add user role column

Revision ID: 001
Revises:
Create Date: 2026-04-06

This migration adds a 'role' column to the users table for RBAC support.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add role column to users table with default 'user' value."""
    op.add_column(
        'users',
        sa.Column('role', sa.String(20), nullable=False, server_default='user')
    )

    # Create index on role for faster queries
    op.create_index('ix_users_role', 'users', ['role'])


def downgrade() -> None:
    """Remove role column from users table."""
    op.drop_index('ix_users_role', table_name='users')
    op.drop_column('users', 'role')
