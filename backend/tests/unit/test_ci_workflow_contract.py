"""Contract tests for CI workflow configuration."""

from pathlib import Path

import yaml


def load_workflow() -> dict:
    """Load the CI workflow YAML file."""
    workflow_path = Path(".github/workflows/ci.yml")
    if not workflow_path.exists():
        raise FileNotFoundError(f"CI workflow file not found: {workflow_path}")
    content = workflow_path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


def test_ci_workflow_contains_required_quality_jobs() -> None:
    """Verify CI workflow contains all required quality jobs."""
    workflow = load_workflow()
    jobs = set(workflow["jobs"].keys())
    required = {
        "lint",
        "test-unit",
        "test-contract",
        "frontend-quality",
        "backend-coverage",
        "security-scan",
    }
    assert required.issubset(jobs), (
        f"Missing required jobs: {required - jobs}. "
        f"Current jobs: {sorted(jobs)}"
    )


def test_ci_workflow_frontend_quality_job_structure() -> None:
    """Verify frontend-quality job has required steps."""
    workflow = load_workflow()
    jobs = workflow["jobs"]

    if "frontend-quality" not in jobs:
        raise AssertionError("frontend-quality job not found")

    steps = jobs["frontend-quality"]["steps"]
    [step.get("name", step.get("uses", "")) for step in steps]

    # Check for npm ci/install step
    has_npm_install = any(
        "npm ci" in str(step) or "npm install" in str(step)
        for step in steps
    )
    assert has_npm_install, "frontend-quality job missing npm install step"

    # Check for build step
    has_build = any("build" in str(step) for step in steps)
    assert has_build, "frontend-quality job missing build step"

    # Check for test step
    has_test = any("test" in str(step).lower() for step in steps)
    assert has_test, "frontend-quality job missing test step"


def test_ci_workflow_backend_coverage_job_structure() -> None:
    """Verify backend-coverage job has pytest coverage configuration."""
    workflow = load_workflow()
    jobs = workflow["jobs"]

    if "backend-coverage" not in jobs:
        raise AssertionError("backend-coverage job not found")

    steps = jobs["backend-coverage"]["steps"]

    # Check for coverage flag in pytest command
    has_coverage = any(
        "--cov" in str(step) for step in steps
    )
    assert has_coverage, "backend-coverage job missing --cov flag in pytest"

    # Check for fail-under enforcement
    has_fail_under = any(
        "--cov-fail-under" in str(step) or "fail-under" in str(step)
        for step in steps
    )
    assert has_fail_under, (
        "backend-coverage job missing --cov-fail-under enforcement"
    )


def test_ci_workflow_security_scan_job_structure() -> None:
    """Verify security-scan job exists and has security-related steps."""
    workflow = load_workflow()
    jobs = workflow["jobs"]

    if "security-scan" not in jobs:
        raise AssertionError("security-scan job not found")

    steps = jobs["security-scan"]["steps"]

    # Check for security-related actions or commands
    step_content = str(steps).lower()
    has_security = any(
        keyword in step_content
        for keyword in ["security", "safety", "bandit", "trivy", "snyk", "pip-audit"]
    )
    assert has_security, (
        "security-scan job should use security scanning tools "
        "(e.g., bandit, safety, trivy, snyk, pip-audit)"
    )
