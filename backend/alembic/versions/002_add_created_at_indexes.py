"""add created_at indexes

Revision ID: 002
Revises: 001
Create Date: 2026-04-10

This migration adds indexes on created_at columns for chat_messages and documents.
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
