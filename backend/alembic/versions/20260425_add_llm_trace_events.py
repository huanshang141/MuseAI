"""Add llm_trace_events table

Revision ID: 20260425_add_llm_trace_events
Revises: 20260420_add_halls_table_backfill
Create Date: 2026-04-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260425_add_llm_trace_events"
down_revision: str | None = "20260420_add_halls_table_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_trace_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("call_id", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("endpoint_method", sa.String(10), nullable=True),
        sa.Column("endpoint_path", sa.String(255), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=True),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("session_type", sa.String(20), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("request_payload_masked", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_payload_masked", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_readable", sa.Text(), nullable=True),
        sa.Column("response_readable", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_type", sa.String(128), nullable=True),
        sa.Column("error_message_masked", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id", name="uq_llm_traces_call_id"),
    )
    op.create_index("ix_llm_traces_created_at", "llm_trace_events", [sa.text("created_at DESC")])
    op.create_index("ix_llm_traces_trace_id", "llm_trace_events", ["trace_id"])
    op.create_index("ix_llm_traces_request_id", "llm_trace_events", ["request_id"])
    op.create_index("ix_llm_traces_source_status", "llm_trace_events", ["source", "status"])
    op.create_index("ix_llm_traces_model", "llm_trace_events", ["model"])
    op.create_index("ix_llm_traces_session_id", "llm_trace_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_traces_session_id", table_name="llm_trace_events")
    op.drop_index("ix_llm_traces_model", table_name="llm_trace_events")
    op.drop_index("ix_llm_traces_source_status", table_name="llm_trace_events")
    op.drop_index("ix_llm_traces_request_id", table_name="llm_trace_events")
    op.drop_index("ix_llm_traces_trace_id", table_name="llm_trace_events")
    op.drop_index("ix_llm_traces_created_at", table_name="llm_trace_events")
    op.drop_table("llm_trace_events")
