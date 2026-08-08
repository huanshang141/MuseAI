"""Replace demo hall bootstrap with the trusted nine-hall baseline.

Revision ID: 20260808_remove_legacy_halls
Revises: 20260716_report_summary_hash
Create Date: 2026-08-08

The historical halls-table migration inserted ``relic-hall`` and ``site-hall``
as demo rows. Published migrations stay immutable, so this forward-only cleanup
removes those rows only when no exhibit references them, inserts a missing
canonical hall, and fills only an empty canonical description. Existing
non-empty museum content is never overwritten.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_remove_legacy_halls"
down_revision: str | None = "20260716_report_summary_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CANONICAL_HALL_BASELINE = (
    {
        "slug": "basic-exhibition-hall",
        "name": "基本陈列展厅",
        "description": "以半坡遗址考古发现与研究成果为主线，系统呈现半坡文化的生活形态、生产方式与社会结构。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 10,
    },
    {
        "slug": "site-protection-hall",
        "name": "遗址保护大厅",
        "description": "强调原址呈现与保护展示，可观察墓葬、地面圆形房屋、烧制作坊、灶具灶台等关键遗存。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 20,
    },
    {
        "slug": "kiln-hall",
        "name": "陶窑展厅",
        "description": "以“陶器如何被制作出来”为核心叙事，解释制坯、装饰、干燥、入窑烧成等生产流程。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 30,
    },
    {
        "slug": "prehistoric-workshop",
        "name": "史前工坊",
        "description": "把制陶、材料、手作等史前生活知识转化为可参与的互动学习体验。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 40,
    },
    {
        "slug": "banpo-girl-sculpture",
        "name": "半坡姑娘雕塑",
        "description": "以“半坡姑娘”为代表形象进行艺术化再现，是观众合影点和半坡人形象记忆入口。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 50,
    },
    {
        "slug": "education-center",
        "name": "教研中心",
        "description": "面向青少年和公众教育活动，适合承载研学课程、主题课堂与研究型活动。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 60,
    },
    {
        "slug": "peony-garden",
        "name": "牡丹园",
        "description": "以牡丹为核心的园林休憩区域，适合在观展间隙停留并体验季节性自然景观。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 70,
    },
    {
        "slug": "temporary-hall-1",
        "name": "临展厅一",
        "description": "承载阶段性专题展览，主题和展品随当期策展内容变化。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 80,
    },
    {
        "slug": "temporary-hall-2",
        "name": "临展厅二",
        "description": "与临展厅一共同承担轮换展出，需要按馆方最新展览清单更新内容。",
        "floor": None,
        "estimated_duration_minutes": 0,
        "display_order": 90,
    },
)


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM halls
            WHERE slug IN ('relic-hall', 'site-hall')
              AND NOT EXISTS (
                  SELECT 1 FROM exhibits WHERE exhibits.hall = halls.slug
              )
            """
        )
    )

    existing = {
        row["slug"]: row
        for row in connection.execute(
            sa.text(
                "SELECT slug, name, description, source_name FROM halls"
            )
        ).mappings()
    }
    for hall in CANONICAL_HALL_BASELINE:
        current = existing.get(hall["slug"])
        if current is not None:
            if current["name"] != hall["name"]:
                raise RuntimeError(
                    "canonical hall slug "
                    f"'{hall['slug']}' is bound to unexpected name "
                    f"'{current['name']}'; resolve it before upgrading"
                )
            if not str(current["description"] or "").strip():
                connection.execute(
                    sa.text(
                        "UPDATE halls SET description = :description "
                        "WHERE slug = :slug AND "
                        "(description IS NULL OR TRIM(description) = '')"
                    ),
                    {
                        "slug": hall["slug"],
                        "description": hall["description"],
                    },
                )
            if not str(current["source_name"] or "").strip():
                connection.execute(
                    sa.text(
                        "UPDATE halls SET floor = NULL, "
                        "estimated_duration_minutes = 0 WHERE slug = :slug"
                    ),
                    {"slug": hall["slug"]},
                )
            continue

        conflicting_slug = connection.execute(
            sa.text(
                "SELECT slug FROM halls "
                "WHERE name = :name AND slug <> :slug LIMIT 1"
            ),
            {"name": hall["name"], "slug": hall["slug"]},
        ).scalar_one_or_none()
        if conflicting_slug is not None:
            raise RuntimeError(
                f"trusted hall name '{hall['name']}' is already bound to "
                f"non-canonical slug '{conflicting_slug}'; resolve it before upgrading"
            )

        connection.execute(
            sa.text(
                """
                INSERT INTO halls (
                    slug, name, description, floor,
                    estimated_duration_minutes, display_order, is_active
                ) VALUES (
                    :slug, :name, :description, :floor,
                    :estimated_duration_minutes, :display_order, true
                )
                """
            ),
            hall,
        )


def downgrade() -> None:
    # Do not recreate demo data during a downgrade.
    pass
