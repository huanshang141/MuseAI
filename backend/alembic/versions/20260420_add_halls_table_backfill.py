"""Add halls table and backfill exhibit hall values to slug identifiers.

Revision ID: 20260420_add_halls_table_backfill
Revises: 20260415_add_tour_tables
Create Date: 2026-04-20
"""

from __future__ import annotations

import hashlib
import re

import sqlalchemy as sa
from alembic import op

revision = "20260420_add_halls_table_backfill"
down_revision = "20260415_add_tour_tables"
branch_labels = None
depends_on = None


LEGACY_HALLS = {
    "relic-hall": {
        "name": "出土文物展厅",
        "description": "陈列半坡遗址出土的陶器、石器、骨器等文物，展示6000年前半坡人的生存技术和精神世界。",
        "estimated_duration_minutes": 30,
        "display_order": 10,
    },
    "site-hall": {
        "name": "遗址保护大厅",
        "description": "保留半坡遗址的居住区、制陶区和墓葬区原貌，展示圆形和方形半地穴式房屋结构。",
        "estimated_duration_minutes": 25,
        "display_order": 20,
    },
}


def _slugify(value: str) -> str:
    stripped = value.strip().lower()
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", stripped).strip("-")
    if ascii_slug:
        return ascii_slug
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()[:8]
    return f"hall-{digest}"


def _allocate_slug(raw_name: str, slug_name_map: dict[str, str]) -> str:
    for existing_slug, existing_name in slug_name_map.items():
        if existing_name == raw_name:
            return existing_slug

    base = _slugify(raw_name)
    candidate = base
    suffix = 2
    while candidate in slug_name_map and slug_name_map[candidate] != raw_name:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "halls" not in inspector.get_table_names():
        op.create_table(
            "halls",
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("floor", sa.Integer(), nullable=True),
            sa.Column("estimated_duration_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("slug"),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_halls_floor", "halls", ["floor"])
        op.create_index("ix_halls_display_order", "halls", ["display_order"])
        op.create_index("ix_halls_is_active", "halls", ["is_active"])

    hall_rows = conn.execute(sa.text("SELECT slug, name FROM halls")).fetchall()
    slug_name_map: dict[str, str] = {row[0]: row[1] for row in hall_rows}

    for slug, data in LEGACY_HALLS.items():
        if slug not in slug_name_map:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO halls (slug, name, description, floor, estimated_duration_minutes, display_order, is_active)
                    VALUES (:slug, :name, :description, :floor, :estimated_duration_minutes, :display_order, :is_active)
                    """
                ),
                {
                    "slug": slug,
                    "name": data["name"],
                    "description": data["description"],
                    "floor": None,
                    "estimated_duration_minutes": data["estimated_duration_minutes"],
                    "display_order": data["display_order"],
                    "is_active": True,
                },
            )
            slug_name_map[slug] = data["name"]

    inspector = sa.inspect(conn)
    if "exhibits" not in inspector.get_table_names():
        return

    raw_halls = conn.execute(
        sa.text("SELECT DISTINCT hall FROM exhibits WHERE hall IS NOT NULL AND TRIM(hall) <> ''")
    ).fetchall()

    for row in raw_halls:
        raw_hall = row[0]
        if raw_hall in LEGACY_HALLS:
            target_slug = raw_hall
        else:
            target_slug = _allocate_slug(raw_hall, slug_name_map)

        if target_slug not in slug_name_map:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO halls (slug, name, description, floor, estimated_duration_minutes, display_order, is_active)
                    VALUES (:slug, :name, :description, :floor, :estimated_duration_minutes, :display_order, :is_active)
                    """
                ),
                {
                    "slug": target_slug,
                    "name": raw_hall,
                    "description": None,
                    "floor": None,
                    "estimated_duration_minutes": 30,
                    "display_order": 1000,
                    "is_active": True,
                },
            )
            slug_name_map[target_slug] = raw_hall

        if raw_hall != target_slug:
            conn.execute(
                sa.text("UPDATE exhibits SET hall = :target_slug WHERE hall = :raw_hall"),
                {"target_slug": target_slug, "raw_hall": raw_hall},
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "halls" in inspector.get_table_names():
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("halls")}
        if "ix_halls_is_active" in existing_indexes:
            op.drop_index("ix_halls_is_active", table_name="halls")
        if "ix_halls_display_order" in existing_indexes:
            op.drop_index("ix_halls_display_order", table_name="halls")
        if "ix_halls_floor" in existing_indexes:
            op.drop_index("ix_halls_floor", table_name="halls")
        op.drop_table("halls")
