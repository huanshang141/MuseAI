"""Persist the canonical source fingerprint for generated report summaries.

Revision ID: 20260716_report_summary_hash
Revises: 20260715_data_driven_tour
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_report_summary_hash"
down_revision: str | None = "20260715_data_driven_tour"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tour_reports",
        sa.Column("record_summary_source_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tour_reports", "record_summary_source_hash")
