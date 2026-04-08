#!/usr/bin/env bash
set -euo pipefail

uv sync --extra dev
npm install --prefix frontend

uv run ruff check backend/
uv run mypy backend/
uv run pytest backend/tests/unit backend/tests/contract -v
uv run bandit -r backend/ -ll || true
npm run build --prefix frontend
npm run test --prefix frontend -- --run
