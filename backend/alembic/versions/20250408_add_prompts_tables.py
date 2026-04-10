"""Add prompts and prompt_versions tables

Revision ID: 20250408_add_prompts
Revises: 20250106
Create Date: 2026-04-08

This migration creates two new tables for the Prompt Management System:
- prompts: Store prompt templates with variables and metadata
- prompt_versions: Track version history of prompt content changes

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20250408_add_prompts'
down_revision: str | None = '20250106'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create prompts and prompt_versions tables."""
    # Create prompts table
    op.create_table(
        'prompts',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_prompts_key', 'prompts', ['key'])
    op.create_index('ix_prompts_category', 'prompts', ['category'])
    op.create_index('ix_prompts_is_active', 'prompts', ['is_active'])

    # Create prompt_versions table
    op.create_table(
        'prompt_versions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('prompt_id', sa.String(36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('changed_by', sa.String(36), nullable=True),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prompt_id', 'version', name='uq_prompt_version'),
    )
    op.create_index('ix_prompt_versions_prompt_id', 'prompt_versions', ['prompt_id'])


def downgrade() -> None:
    """Drop prompts and prompt_versions tables."""
    op.drop_index('ix_prompt_versions_prompt_id', table_name='prompt_versions')
    op.drop_table('prompt_versions')
    op.drop_index('ix_prompts_is_active', table_name='prompts')
    op.drop_index('ix_prompts_category', table_name='prompts')
    op.drop_index('ix_prompts_key', table_name='prompts')
    op.drop_table('prompts')
