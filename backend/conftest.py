"""Backend-root pytest conftest.

pytest 9 no longer reads `collect_ignore_glob` from pyproject.toml; declare
it here instead. Performance tests under backend/tests/performance/ run
standalone (sys.path manipulation, live servers) and are excluded from the
default `pytest backend/tests` invocation.
"""
collect_ignore_glob = ["tests/performance/*"]
