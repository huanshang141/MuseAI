from pathlib import Path


def test_verify_local_quality_script_exists() -> None:
    assert Path("scripts/verify_local_quality.sh").exists()


def test_verify_local_quality_script_contains_required_commands() -> None:
    content = Path("scripts/verify_local_quality.sh").read_text(encoding="utf-8")
    assert "uv sync --extra dev" in content
    assert "uv run ruff check backend/" in content
    assert "uv run mypy backend/" in content
    assert "uv run pytest backend/tests/unit backend/tests/contract -v" in content
    assert "npm run build --prefix frontend" in content
    assert "npm run test --prefix frontend -- --run" in content
