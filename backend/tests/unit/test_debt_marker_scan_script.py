from pathlib import Path


def test_debt_marker_scan_script_excludes_lockfiles() -> None:
    path = Path("scripts/run_debt_marker_scan.sh")
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    assert "TODO|FIXME|XXX" in content
    assert "-g '!**/package-lock.json'" in content
    assert "-g '!**/pnpm-lock.yaml'" in content
    assert "-g '!**/yarn.lock'" in content
