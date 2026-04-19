# Risk-Driven Full-Stack Technical Debt Audit Implementation Plan
**Status:** completed

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Execute a deep, evidence-based technical debt audit across backend, frontend, and engineering workflow for the whole repository, and publish a prioritized remediation report.

**Architecture:** Use a risk-driven flow: capture runtime/static evidence first, then map root causes to architectural and process debt. Keep findings in structured artifacts, then publish one consolidated report with P0/P1/P2 priorities, quick stabilization actions, and a 2-6 week roadmap.

**Tech Stack:** Python 3.11, uv, pytest, ruff, mypy, FastAPI, Vue 3, Vite, Vitest, Docker Compose, Markdown

---

### Task 1: Initialize Audit Artifacts

**Files:**
- Create: `docs/audit/2026-04-06/evidence/README.md`
- Create: `docs/audit/2026-04-06/findings.json`
- Create: `docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md`

**Step 1: Create evidence directory**

Run: `mkdir -p docs/audit/2026-04-06/evidence`

Expected: Directory exists with no errors.

**Step 2: Write evidence README**

```markdown
# Audit Evidence Index
**Status:** completed

- Date: 2026-04-06
- Scope: full repository
- Rule: every finding must map to one evidence file or deterministic file reference

## Files
- backend-ruff.txt
- backend-mypy.txt
- backend-unit-contract.txt
- backend-e2e.txt
- frontend-build.txt
- frontend-test.txt
- infra-baseline.txt
- architecture-scan.md
- security-scan.md
```

**Step 3: Initialize findings JSON schema**

```json
{
  "metadata": {
    "date": "2026-04-06",
    "scope": "full-repo",
    "mode": "deep-audit"
  },
  "findings": []
}
```

**Step 4: Create report skeleton**

```markdown
# Technical Debt Audit Report (2026-04-06)

## Executive Summary
## Evidence Summary
## Findings by Priority
## Quick Stabilization (1-3 days)
## Structured Roadmap (2-6 weeks)
## Appendix (Commands and Logs)
```

**Step 5: Commit artifact skeleton**

```bash
git add docs/audit/2026-04-06/ docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md
git commit -m "docs: scaffold full-stack technical debt audit artifacts"
```

---

### Task 2: Capture Runtime Baseline

**Files:**
- Modify: `docs/audit/2026-04-06/evidence/infra-baseline.txt`

**Step 1: Start infrastructure**

Run: `docker-compose up -d`

Expected: PostgreSQL, Redis, Elasticsearch containers are up.

**Step 2: Capture container status**

Run: `docker-compose ps > docs/audit/2026-04-06/evidence/infra-baseline.txt`

Expected: Service status written to evidence file.

**Step 3: Verify Python dependency environment**

Run: `uv sync > docs/audit/2026-04-06/evidence/uv-sync.txt 2>&1`

Expected: Dependencies resolved/installed successfully.

**Step 4: Verify frontend dependency environment**

Run: `npm install --prefix frontend > docs/audit/2026-04-06/evidence/npm-install.txt 2>&1`

Expected: Frontend dependencies installed with no blocking errors.

**Step 5: Commit baseline evidence**

```bash
git add docs/audit/2026-04-06/evidence/infra-baseline.txt docs/audit/2026-04-06/evidence/uv-sync.txt docs/audit/2026-04-06/evidence/npm-install.txt
git commit -m "docs: record audit runtime baseline evidence"
```

---

### Task 3: Run Backend Static Quality Checks

**Files:**
- Modify: `docs/audit/2026-04-06/evidence/backend-ruff.txt`
- Modify: `docs/audit/2026-04-06/evidence/backend-mypy.txt`

**Step 1: Run backend lint**

Run: `uv run ruff check backend/ > docs/audit/2026-04-06/evidence/backend-ruff.txt 2>&1 || true`

Expected: Ruff output captured even if violations exist.

**Step 2: Run backend type check**

Run: `uv run mypy backend/ > docs/audit/2026-04-06/evidence/backend-mypy.txt 2>&1 || true`

Expected: Mypy output captured even if type errors exist.

**Step 3: Summarize static check failures in findings JSON**

Add entries per issue class (import errors, typing errors, rule violations).

**Step 4: Link static evidence in report appendix**

Add links to `backend-ruff.txt` and `backend-mypy.txt` in report appendix.

**Step 5: Commit backend static evidence**

```bash
git add docs/audit/2026-04-06/evidence/backend-ruff.txt docs/audit/2026-04-06/evidence/backend-mypy.txt docs/audit/2026-04-06/findings.json docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md
git commit -m "docs: capture backend lint and type-check debt evidence"
```

---

### Task 4: Run Backend Test Matrix

**Files:**
- Modify: `docs/audit/2026-04-06/evidence/backend-unit-contract.txt`
- Modify: `docs/audit/2026-04-06/evidence/backend-e2e.txt`

**Step 1: Execute unit + contract tests**

Run: `uv run pytest backend/tests/unit backend/tests/contract -v > docs/audit/2026-04-06/evidence/backend-unit-contract.txt 2>&1 || true`

Expected: Full output captured; pass/fail counts visible.

**Step 2: Execute e2e tests**

Run: `uv run pytest backend/tests/e2e -v > docs/audit/2026-04-06/evidence/backend-e2e.txt 2>&1 || true`

Expected: E2E output captured; infra-related failures are distinguishable.

**Step 3: Classify backend failures**

Classify each failure as one of: `code-defect`, `test-debt`, `environment-debt`.

**Step 4: Add top backend risk items to report**

Add P0/P1 candidates with evidence references.

**Step 5: Commit backend test evidence**

```bash
git add docs/audit/2026-04-06/evidence/backend-unit-contract.txt docs/audit/2026-04-06/evidence/backend-e2e.txt docs/audit/2026-04-06/findings.json docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md
git commit -m "docs: capture backend test debt evidence and risk classification"
```

---

### Task 5: Run Frontend Quality and Build Checks

**Files:**
- Modify: `docs/audit/2026-04-06/evidence/frontend-build.txt`
- Modify: `docs/audit/2026-04-06/evidence/frontend-test.txt`

**Step 1: Run production build**

Run: `npm run build --prefix frontend > docs/audit/2026-04-06/evidence/frontend-build.txt 2>&1 || true`

Expected: Build output captured with warnings/errors.

**Step 2: Run frontend tests in CI mode**

Run: `npm run test --prefix frontend -- --run > docs/audit/2026-04-06/evidence/frontend-test.txt 2>&1 || true`

Expected: Test summary captured with pass/fail counts.

**Step 3: Review API integration boundaries**

Inspect `frontend/src/api/index.js` and representative UI components for auth handling, error handling, and retry behavior.

**Step 4: Add frontend risk findings**

Add findings with explicit impact and evidence path references.

**Step 5: Commit frontend evidence**

```bash
git add docs/audit/2026-04-06/evidence/frontend-build.txt docs/audit/2026-04-06/evidence/frontend-test.txt docs/audit/2026-04-06/findings.json docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md
git commit -m "docs: capture frontend build/test debt evidence"
```

---

### Task 6: Perform Architecture Debt Scan

**Files:**
- Modify: `docs/audit/2026-04-06/evidence/architecture-scan.md`

**Step 1: Scan for boundary leakage and duplication**

Run targeted searches and capture findings:

```bash
rg "get_db_session\(" backend/app/api
rg "print\(" backend/app
rg "allow_origins=\[\"\*\"\]" backend/app
rg "TODO|FIXME|XXX" backend frontend
```

Expected: Candidate technical debt hotspots identified.

**Step 2: Review layering contracts**

Verify API -> application -> domain -> infra flow in changed/high-risk modules.

**Step 3: Record architecture findings**

Use per-item format: symptom, evidence, impact, recommendation, estimated effort.

**Step 4: Map architecture findings to P0/P1/P2**

Prioritize based on blast radius and likelihood.

**Step 5: Commit architecture scan evidence**

```bash
git add docs/audit/2026-04-06/evidence/architecture-scan.md docs/audit/2026-04-06/findings.json
git commit -m "docs: add architecture debt scan and prioritization"
```

---

### Task 7: Perform Security and Configuration Debt Scan

**Files:**
- Modify: `docs/audit/2026-04-06/evidence/security-scan.md`

**Step 1: Review security-critical backend config**

Inspect:
- `backend/app/config/settings.py`
- `backend/app/main.py`
- `backend/app/api/auth.py`
- `.env.example`

**Step 2: Validate security controls are enforced**

Check token invalidation flow, rate limiting usage, CORS policy, and secret requirements.

**Step 3: Record security/config findings**

Document each item with reproducible file references.

**Step 4: Promote production-risk items to P0/P1**

Any data exposure/auth bypass risk must be P0/P1.

**Step 5: Commit security scan evidence**

```bash
git add docs/audit/2026-04-06/evidence/security-scan.md docs/audit/2026-04-06/findings.json
git commit -m "docs: add security and configuration debt analysis"
```

---

### Task 8: Consolidate Findings and Build Priority Matrix

**Files:**
- Modify: `docs/audit/2026-04-06/findings.json`
- Modify: `docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md`

**Step 1: Normalize finding schema**

Each finding must include:

```json
{
  "id": "TD-001",
  "priority": "P1",
  "area": "backend|frontend|engineering",
  "title": "...",
  "symptom": "...",
  "evidence": ["path:line or evidence file"],
  "impact": "...",
  "recommendation": "...",
  "effort": "S|M|L"
}
```

**Step 2: Build priority matrix in report**

Add summary table by priority and functional area.

**Step 3: Add quick stabilization list (1-3 days)**

Select highest ROI risk reductions with explicit owners and order.

**Step 4: Add 2-6 week roadmap**

Group by theme (reliability, security, maintainability, test quality).

**Step 5: Commit consolidated analysis**

```bash
git add docs/audit/2026-04-06/findings.json docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md
git commit -m "docs: consolidate full-stack technical debt findings and roadmap"
```

---

### Task 9: Final Verification and Handoff

**Files:**
- Modify: `docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md`

**Step 1: Verify every P0/P1 finding has evidence and recommendation**

Checklist:
- No orphan findings
- No recommendation without impact statement
- No P0/P1 without reproducible evidence

**Step 2: Verify report acceptance criteria**

Confirm:
- backend/frontend/engineering coverage complete
- priority rationale clear
- quick and roadmap tracks included

**Step 3: Add final executive summary paragraph**

Summarize overall risk posture and recommended first-week actions.

**Step 4: Final commit**

```bash
git add docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md
git commit -m "docs: finalize deep technical debt audit report"
```

**Step 5: Optional PR preparation**

```bash
git status
git log --oneline -n 5
```

Expected: Clean branch state and clear commit history for review.

---

## Success Verification

Run these checks before declaring audit complete:

```bash
# Baseline
docker-compose ps

# Backend
uv run ruff check backend/
uv run mypy backend/
uv run pytest backend/tests/unit backend/tests/contract -v
uv run pytest backend/tests/e2e -v

# Frontend
npm run build --prefix frontend
npm run test --prefix frontend -- --run
```

Audit completion criteria:

- Report exists at `docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md`
- Evidence files exist under `docs/audit/2026-04-06/evidence/`
- Findings are structured in `docs/audit/2026-04-06/findings.json`
- P0/P1/P2 prioritization is explicit and justified
