"""Add tour_sessions, tour_events, tour_reports tables and display_order to exhibits

Revision ID: 20260415_add_tour_tables
Revises: 20250408_add_prompts
Create Date: 2026-04-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260415_add_tour_tables'
down_revision: str | None = '20250408_add_prompts'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'tour_sessions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('guest_id', sa.String(64), nullable=True),
        sa.Column('session_token', sa.String(64), nullable=False),
        sa.Column('interest_type', sa.String(1), nullable=False),
        sa.Column('persona', sa.String(1), nullable=False),
        sa.Column('assumption', sa.String(1), nullable=False),
        sa.Column('current_hall', sa.String(50), nullable=True),
        sa.Column('current_exhibit_id', sa.String(36), nullable=True),
        sa.Column('visited_halls', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('visited_exhibit_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='onboarding'),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['current_exhibit_id'], ['exhibits.id'], ondelete='SET NULL'),
        sa.CheckConstraint("user_id IS NOT NULL OR guest_id IS NOT NULL", name="ck_tour_session_owner"),
    )
    op.create_index('ix_tour_sessions_user_id', 'tour_sessions', ['user_id'])
    op.create_index('ix_tour_sessions_guest_id', 'tour_sessions', ['guest_id'])
    op.create_index('ix_tour_sessions_session_token', 'tour_sessions', ['session_token'])
    op.create_index('ix_tour_sessions_status', 'tour_sessions', ['status'])

    op.create_table(
        'tour_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tour_session_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(30), nullable=False),
        sa.Column('exhibit_id', sa.String(36), nullable=True),
        sa.Column('hall', sa.String(50), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tour_session_id'], ['tour_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exhibit_id'], ['exhibits.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_tour_events_tour_session_id', 'tour_events', ['tour_session_id'])
    op.create_index('ix_tour_events_event_type', 'tour_events', ['event_type'])
    op.create_index('ix_tour_events_session_type', 'tour_events', ['tour_session_id', 'event_type'])

    op.create_table(
        'tour_reports',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tour_session_id', sa.String(36), nullable=False),
        sa.Column('total_duration_minutes', sa.Float(), nullable=False),
        sa.Column('most_viewed_exhibit_id', sa.String(36), nullable=True),
        sa.Column('most_viewed_exhibit_duration', sa.Integer(), nullable=True),
        sa.Column('longest_hall', sa.String(50), nullable=True),
        sa.Column('longest_hall_duration', sa.Integer(), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('total_exhibits_viewed', sa.Integer(), nullable=False),
        sa.Column('ceramic_questions', sa.Integer(), nullable=False),
        sa.Column('identity_tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('radar_scores', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('one_liner', sa.Text(), nullable=False),
        sa.Column('report_theme', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tour_session_id'], ['tour_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['most_viewed_exhibit_id'], ['exhibits.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('tour_session_id'),
    )
    op.create_index('ix_tour_reports_tour_session_id', 'tour_reports', ['tour_session_id'])

    op.add_column('exhibits', sa.Column('display_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('exhibits', 'display_order')
    op.drop_index('ix_tour_reports_tour_session_id', table_name='tour_reports')
    op.drop_table('tour_reports')
    op.drop_index('ix_tour_events_session_type', table_name='tour_events')
    op.drop_index('ix_tour_events_event_type', table_name='tour_events')
    op.drop_index('ix_tour_events_tour_session_id', table_name='tour_events')
    op.drop_table('tour_events')
    op.drop_index('ix_tour_sessions_status', table_name='tour_sessions')
    op.drop_index('ix_tour_sessions_session_token', table_name='tour_sessions')
    op.drop_index('ix_tour_sessions_guest_id', table_name='tour_sessions')
    op.drop_index('ix_tour_sessions_user_id', table_name='tour_sessions')
    op.drop_table('tour_sessions')
