import csv
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def _load_migration_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260808_remove_unreferenced_legacy_halls.py"
    )
    spec = importlib.util.spec_from_file_location("trusted_hall_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_minimal_schema(connection) -> None:
    connection.execute(
        sa.text(
            """
            CREATE TABLE halls (
                slug VARCHAR(100) PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                floor INTEGER,
                estimated_duration_minutes INTEGER NOT NULL,
                display_order INTEGER NOT NULL,
                is_active BOOLEAN NOT NULL,
                source_name VARCHAR(100)
            )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            CREATE TABLE exhibits (
                id VARCHAR(100) PRIMARY KEY,
                hall VARCHAR(100)
            )
            """
        )
    )


def test_trusted_hall_migration_baseline_matches_import_template():
    module = _load_migration_module()
    template_path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "museum_template"
        / "halls.csv"
    )
    with template_path.open(encoding="utf-8-sig", newline="") as handle:
        template_rows = list(csv.DictReader(handle))

    template_baseline = [
        {
            "slug": row["slug"],
            "name": row["name"],
            "description": row["description"],
            "floor": int(row["floor"]) if row["floor"].strip() else None,
            "estimated_duration_minutes": int(row["estimated_duration_minutes"]),
            "display_order": int(row["display_order"]),
        }
        for row in template_rows
    ]

    assert template_baseline == list(module.CANONICAL_HALL_BASELINE)
    assert all(
        row["source_record_id"] == f"hall-{row['slug']}"
        and row["is_active"].strip().lower() == "true"
        and row["suggested_questions"].strip() == "[]"
        for row in template_rows
    )


def test_trusted_hall_migration_replaces_unreferenced_demo_bootstrap(monkeypatch):
    module = _load_migration_module()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_minimal_schema(connection)
        connection.execute(
            sa.text(
                """
                INSERT INTO halls (
                    slug, name, description, floor,
                    estimated_duration_minutes, display_order, is_active
                ) VALUES
                    ('relic-hall', '出土文物展厅', '旧占位', 1, 30, 10, true),
                    ('site-hall', '遗址保护大厅', '旧占位', 1, 25, 20, true)
                """
            )
        )
        monkeypatch.setattr(module.op, "get_bind", lambda: connection)

        module.upgrade()

        rows = connection.execute(
            sa.text(
                "SELECT slug, name, description FROM halls ORDER BY display_order"
            )
        ).mappings().all()

    assert [row["slug"] for row in rows] == [
        hall["slug"] for hall in module.CANONICAL_HALL_BASELINE
    ]
    assert all(str(row["description"] or "").strip() for row in rows)
    with engine.connect() as connection:
        route_metadata = connection.execute(
            sa.text(
                "SELECT floor, estimated_duration_minutes FROM halls"
            )
        ).all()
    assert route_metadata == [(None, 0)] * 9


def test_trusted_hall_migration_preserves_nonempty_persisted_description(monkeypatch):
    module = _load_migration_module()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_minimal_schema(connection)
        connection.execute(
            sa.text(
                """
                INSERT INTO halls (
                    slug, name, description, floor,
                    estimated_duration_minutes, display_order, is_active
                ) VALUES (
                    'basic-exhibition-hall', '基本陈列展厅',
                    '馆方后来更新的非空简介', 1, 25, 10, true
                )
                """
            )
        )
        monkeypatch.setattr(module.op, "get_bind", lambda: connection)

        module.upgrade()

        description = connection.execute(
            sa.text(
                "SELECT description FROM halls "
                "WHERE slug = 'basic-exhibition-hall'"
            )
        ).scalar_one()

    assert description == "馆方后来更新的非空简介"


def test_trusted_hall_migration_fails_closed_on_referenced_name_conflict(monkeypatch):
    module = _load_migration_module()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_minimal_schema(connection)
        connection.execute(
            sa.text(
                """
                INSERT INTO halls (
                    slug, name, description, floor,
                    estimated_duration_minutes, display_order, is_active
                ) VALUES (
                    'site-hall', '遗址保护大厅', '不能自动删除', 1, 25, 20, true
                )
                """
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO exhibits (id, hall) VALUES ('kept-exhibit', 'site-hall')"
            )
        )
        monkeypatch.setattr(module.op, "get_bind", lambda: connection)

        with pytest.raises(RuntimeError, match="non-canonical slug 'site-hall'"):
            module.upgrade()
