"""Add data-driven mini-program session and museum source fields.

Revision ID: 20260715_data_driven_tour
Revises: 20260610_add_report_record_summary
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_data_driven_tour"
down_revision: str | None = "20260610_add_report_record_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = postgresql.JSON(astext_type=sa.Text())
    op.add_column("tour_sessions", sa.Column("tour_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tour_sessions", sa.Column("questionnaire", json_type, nullable=False, server_default="{}"))
    op.add_column("tour_sessions", sa.Column("resume_state", json_type, nullable=False, server_default="{}"))
    op.add_column("tour_sessions", sa.Column("hall_chat_history", json_type, nullable=False, server_default="{}"))
    op.add_column("tour_sessions", sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"))
    op.alter_column(
        "tour_sessions", "interest_type", existing_type=sa.String(length=1), type_=sa.String(length=10)
    )
    op.alter_column(
        "tour_sessions", "persona", existing_type=sa.String(length=1), type_=sa.String(length=10)
    )
    op.alter_column(
        "tour_sessions", "current_hall", existing_type=sa.String(length=50), type_=sa.String(length=100)
    )
    op.alter_column(
        "tour_events", "hall", existing_type=sa.String(length=50), type_=sa.String(length=100)
    )
    op.alter_column(
        "tour_reports", "longest_hall", existing_type=sa.String(length=50), type_=sa.String(length=100)
    )

    for table in ("halls", "exhibits"):
        op.add_column(table, sa.Column("suggested_questions", json_type, nullable=False, server_default="[]"))
        op.add_column(table, sa.Column("source_name", sa.String(length=100), nullable=True))
        op.add_column(table, sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_exhibits_source_record", "exhibits", ["source_name", "source_record_id"]
    )
    op.create_unique_constraint(
        "uq_halls_source_record", "halls", ["source_name", "source_record_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_halls_source_record", "halls", type_="unique")
    op.drop_constraint("uq_exhibits_source_record", "exhibits", type_="unique")
    for table in ("exhibits", "halls"):
        op.drop_column(table, "source_record_id")
        op.drop_column(table, "source_name")
        op.drop_column(table, "suggested_questions")
    op.drop_column("tour_sessions", "state_version")
    op.drop_column("tour_sessions", "hall_chat_history")
    op.drop_column("tour_sessions", "resume_state")
    op.drop_column("tour_sessions", "questionnaire")
    op.drop_column("tour_sessions", "tour_started_at")
    op.alter_column(
        "tour_sessions", "persona", existing_type=sa.String(length=10), type_=sa.String(length=1)
    )
    op.alter_column(
        "tour_sessions", "interest_type", existing_type=sa.String(length=10), type_=sa.String(length=1)
    )
    op.alter_column(
        "tour_reports", "longest_hall", existing_type=sa.String(length=100), type_=sa.String(length=50)
    )
    op.alter_column(
        "tour_events", "hall", existing_type=sa.String(length=100), type_=sa.String(length=50)
    )
    op.alter_column(
        "tour_sessions", "current_hall", existing_type=sa.String(length=100), type_=sa.String(length=50)
    )
