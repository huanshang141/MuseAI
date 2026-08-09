"""Add external and uploaded image references to exhibits.

Revision ID: 20260809_exhibit_images
Revises: 20260808_remove_legacy_halls
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_exhibit_images"
down_revision: str | None = "20260808_remove_legacy_halls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("exhibits") as batch_op:
        batch_op.add_column(sa.Column("image_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("image_path", sa.String(length=512), nullable=True))
        batch_op.create_check_constraint(
            "ck_exhibits_image_url_https",
            "image_url IS NULL OR image_url LIKE 'https://%'",
        )


def downgrade() -> None:
    with op.batch_alter_table("exhibits") as batch_op:
        batch_op.drop_constraint(
            "ck_exhibits_image_url_https",
            type_="check",
        )
        batch_op.drop_column("image_path")
        batch_op.drop_column("image_url")
