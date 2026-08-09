"""Add concise card copy to halls.

Revision ID: 20260809_hall_short_description
Revises: 20260809_exhibit_images
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_hall_short_description"
down_revision: str | None = "20260809_exhibit_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("halls") as batch_op:
        batch_op.add_column(
            sa.Column("short_description", sa.String(length=48), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("halls") as batch_op:
        batch_op.drop_column("short_description")
