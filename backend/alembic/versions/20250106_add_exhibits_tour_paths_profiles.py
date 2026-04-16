"""add exhibits tour paths profiles

Revision ID: 20250106
Revises: 001
Create Date: 2026-04-06

This migration creates three new tables for the Digital Curation Agent:
- exhibits: Museum exhibit information with location and metadata
- tour_paths: Predefined tour routes through exhibits
- visitor_profiles: Personalized visitor preferences and history
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers
revision = '20250106'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create exhibits, tour_paths, and visitor_profiles tables."""
    # Create exhibits table
    op.create_table(
        'exhibits',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('location_x', sa.Float, nullable=True),
        sa.Column('location_y', sa.Float, nullable=True),
        sa.Column('floor', sa.Integer, nullable=True),
        sa.Column('hall', sa.String(100), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('era', sa.String(100), nullable=True),
        sa.Column('importance', sa.Integer, default=0),
        sa.Column('estimated_visit_time', sa.Integer, nullable=True),  # in minutes
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create indexes for exhibits
    op.create_index('ix_exhibits_name', 'exhibits', ['name'])
    op.create_index('ix_exhibits_category', 'exhibits', ['category'])
    op.create_index('ix_exhibits_floor', 'exhibits', ['floor'])
    op.create_index('ix_exhibits_is_active', 'exhibits', ['is_active'])
    op.create_index('ix_exhibits_document_id', 'exhibits', ['document_id'])

    # Create tour_paths table
    op.create_table(
        'tour_paths',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('theme', sa.String(100), nullable=True),
        sa.Column('estimated_duration', sa.Integer, nullable=True),  # in minutes
        sa.Column('exhibit_ids', JSON, default=list),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create indexes for tour_paths
    op.create_index('ix_tour_paths_name', 'tour_paths', ['name'])
    op.create_index('ix_tour_paths_theme', 'tour_paths', ['theme'])
    op.create_index('ix_tour_paths_is_active', 'tour_paths', ['is_active'])
    op.create_index('ix_tour_paths_created_by', 'tour_paths', ['created_by'])

    # Create visitor_profiles table
    op.create_table(
        'visitor_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('interests', JSON, default=list),
        sa.Column('knowledge_level', sa.String(20), default='beginner'),  # beginner, intermediate, expert
        sa.Column('narrative_preference', sa.String(20), default='balanced'),  # concise, balanced, detailed
        sa.Column('reflection_depth', sa.Integer, default=2),  # 1-5 scale
        sa.Column('visited_exhibit_ids', JSON, default=list),
        sa.Column('feedback_history', JSON, default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create indexes for visitor_profiles
    op.create_index('ix_visitor_profiles_user_id', 'visitor_profiles', ['user_id'])


def downgrade() -> None:
    """Drop exhibits, tour_paths, and visitor_profiles tables."""
    # Drop visitor_profiles table
    op.drop_index('ix_visitor_profiles_user_id', table_name='visitor_profiles')
    op.drop_table('visitor_profiles')

    # Drop tour_paths table
    op.drop_index('ix_tour_paths_created_by', table_name='tour_paths')
    op.drop_index('ix_tour_paths_is_active', table_name='tour_paths')
    op.drop_index('ix_tour_paths_theme', table_name='tour_paths')
    op.drop_index('ix_tour_paths_name', table_name='tour_paths')
    op.drop_table('tour_paths')

    # Drop exhibits table
    op.drop_index('ix_exhibits_document_id', table_name='exhibits')
    op.drop_index('ix_exhibits_is_active', table_name='exhibits')
    op.drop_index('ix_exhibits_floor', table_name='exhibits')
    op.drop_index('ix_exhibits_category', table_name='exhibits')
    op.drop_index('ix_exhibits_name', table_name='exhibits')
    op.drop_table('exhibits')
