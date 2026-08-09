"""Add server-only trusted hall chat history.

Revision ID: 20260809_trusted_hall_chat_history
Revises: 20260809_hall_short_description
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_trusted_hall_chat_history"
down_revision: str | None = "20260809_hall_short_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = postgresql.JSON(astext_type=sa.Text())
    op.add_column(
        "tour_sessions",
        sa.Column(
            "trusted_hall_chat_history",
            json_type,
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("tour_sessions", "trusted_hall_chat_history")
