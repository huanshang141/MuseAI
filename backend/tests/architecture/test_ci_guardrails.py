"""CI guardrails tests — B1 batch verification.

These tests verify that the CI guardrails (mypy, ruff, layer rules, pytest
configuration) are correctly configured and enforced. They follow TDD: each
test is written BEFORE the fix is applied, so they should FAIL initially
(RED phase) and PASS after the fix (GREEN phase).
"""

import subprocess
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    with open(PYPROJECT_PATH, "rb") as f:
        return tomllib.load(f)


# ---------- Task 1: B1-1 — mypy configuration ----------


class TestMypyConfig:
    """Verify mypy configuration fixes the duplicate-module-path blocker."""

    def test_mypy_has_explicit_package_bases(self):
        pyproject = _load_pyproject()
        mypy_config = pyproject.get("tool", {}).get("mypy", {})
        assert mypy_config.get("explicit_package_bases") is True, (
            "mypy config must set explicit_package_bases = true to avoid "
            "duplicate-module-path errors"
        )

    def test_mypy_has_mypy_path_backend(self):
        pyproject = _load_pyproject()
        mypy_config = pyproject.get("tool", {}).get("mypy", {})
        assert mypy_config.get("mypy_path") == "backend", (
            "mypy config must set mypy_path = 'backend' so there is a single "
            "canonical package root (app.*)"
        )

    def test_mypy_has_namespace_packages(self):
        pyproject = _load_pyproject()
        mypy_config = pyproject.get("tool", {}).get("mypy", {})
        assert mypy_config.get("namespace_packages") is True, (
            "mypy config must set namespace_packages = true so the backend/ "
            "directory (no __init__.py) can be a valid source root"
        )

    def test_mypy_excludes_performance_and_alembic(self):
        pyproject = _load_pyproject()
        mypy_config = pyproject.get("tool", {}).get("mypy", {})
        exclude = mypy_config.get("exclude", [])
        assert any("tests" in p for p in exclude), (
            "mypy exclude must contain test directory pattern"
        )
        assert any("alembic" in p for p in exclude), (
            "mypy exclude must contain alembic pattern"
        )
        assert any("scripts" in p for p in exclude), (
            "mypy exclude must contain scripts pattern"
        )

    def test_mypy_passes_on_backend(self):
        result = subprocess.run(
            ["uv", "run", "mypy", "backend/"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"mypy must pass with exit code 0. Got:\n{result.stdout}\n{result.stderr}"
        )

    def test_mypy_traverses_tree(self):
        result = subprocess.run(
            ["uv", "run", "mypy", "backend/"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert "Source file found twice" not in result.stdout, (
            "mypy must not report duplicate-module-path errors"
        )
        assert "Success" in result.stdout, (
            "mypy must report successful completion"
        )


# ---------- Task 3: B1-3 — ruff compliance ----------


class TestRuffCompliance:
    """Verify ruff check passes with zero errors after B1-3 fixes."""

    def test_ruff_check_passes(self):
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "backend/"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"ruff check must pass with exit code 0. Got:\n{result.stdout}\n{result.stderr}"
        )

    def test_ruff_no_errors(self):
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "backend/"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert "Found 0 errors" in result.stdout or "All checks passed" in result.stdout, (
            f"ruff must report 0 errors. Got:\n{result.stdout}"
        )

    def test_ruff_per_file_ignores_configured(self):
        pyproject = _load_pyproject()
        per_file_ignores = (
            pyproject.get("tool", {}).get("ruff", {}).get("lint", {}).get("per-file-ignores", {})
        )
        assert any("performance" in k for k in per_file_ignores), (
            "ruff per-file-ignores must have an entry for performance test scripts (E402)"
        )

    def test_no_unused_import_in_alembic_002(self):
        migration_file = (
            PROJECT_ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "002_add_created_at_indexes.py"
        )
        content = migration_file.read_text()
        assert "import sqlalchemy as sa" not in content, (
            "002_add_created_at_indexes.py must not have unused 'import sqlalchemy as sa'"
        )

    def test_no_b023_in_test_no_main_runtime_imports(self):
        result = subprocess.run(
            [
                "uv", "run", "ruff", "check",
                "backend/tests/architecture/test_no_main_runtime_imports.py",
                "--select", "B023",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"B023 must be fixed in test_no_main_runtime_imports.py. Got:\n{result.stdout}"
        )

    def test_no_b023_in_test_parallel_indexing(self):
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "backend/tests/unit/test_parallel_indexing.py", "--select", "B023"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"B023 must be fixed in test_parallel_indexing.py. Got:\n{result.stdout}"
        )

    def test_no_b007_in_start_mock_services(self):
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "backend/tests/performance/start_mock_services.py", "--select", "B007"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"B007 must be fixed in start_mock_services.py. Got:\n{result.stdout}"
        )


# ---------- Task 4: B1-4 — pytest warning elimination ----------


class TestPytestWarnings:
    """Verify pytest collection warnings are eliminated after B1-4 fixes."""

    def test_no_collect_ignore_glob_in_pyproject(self):
        pyproject = _load_pyproject()
        pytest_config = pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {})
        assert "collect_ignore_glob" not in pytest_config, (
            "collect_ignore_glob must be removed from pyproject.toml [tool.pytest.ini_options] "
            "because pytest 9 no longer reads it from there"
        )

    def test_backend_conftest_exists(self):
        conftest_path = PROJECT_ROOT / "backend" / "conftest.py"
        assert conftest_path.exists(), (
            "backend/conftest.py must exist to house collect_ignore_glob"
        )

    def test_backend_conftest_has_collect_ignore_glob(self):
        conftest_path = PROJECT_ROOT / "backend" / "conftest.py"
        content = conftest_path.read_text()
        assert "collect_ignore_glob" in content, (
            "backend/conftest.py must define collect_ignore_glob"
        )

    def test_no_testconfig_class_name(self):
        config_path = PROJECT_ROOT / "backend" / "tests" / "performance" / "config.py"
        content = config_path.read_text()
        assert "class TestConfig" not in content, (
            "TestConfig class must be renamed to PerfTestConfig to avoid "
            "pytest collection warning"
        )

    def test_perftestconfig_class_exists(self):
        config_path = PROJECT_ROOT / "backend" / "tests" / "performance" / "config.py"
        content = config_path.read_text()
        assert "class PerfTestConfig" in content, (
            "PerfTestConfig class must exist in performance config"
        )

    def test_no_testconfig_references_in_performance_tests(self):
        result = subprocess.run(
            ["grep", "-r", "\\bTestConfig\\b", "backend/tests/performance/"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        lines = [
            line for line in result.stdout.strip().split("\n")
            if line and "PerfTestConfig" not in line
        ]
        assert len(lines) == 0, (
            f"No references to TestConfig should remain in performance tests. "
            f"Found:\n{chr(10).join(lines)}"
        )

    def test_pytest_collect_no_warnings(self):
        result = subprocess.run(
            ["uv", "run", "pytest", "backend/tests", "--collect-only"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        output = result.stdout + result.stderr
        assert "PytestConfigWarning" not in output, (
            "pytest collection must not produce PytestConfigWarning"
        )
        assert "PytestCollectionWarning" not in output, (
            "pytest collection must not produce PytestCollectionWarning"
        )
