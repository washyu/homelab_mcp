---
phase: 16-quality-gate
plan: 01
subsystem: testing
tags: [mypy, bandit, ruff, quality-gate, nosec, psycopg2]

# Dependency graph
requires:
  - phase: 15-preview-tool-split
    provides: completed source tree (56 tools) that this phase quality-gates
provides:
  - All three quality gates (ruff, mypy, bandit) passing cleanly against full source tree
  - psycopg2 mypy override in pyproject.toml suppressing missing-import for optional dependency
  - 9 targeted nosec annotations silencing intentional medium-severity bandit findings
affects: [CI, pre-commit, any future phase adding bandit-flagged patterns]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "[[tool.mypy.overrides]] list syntax [\"pkg\", \"pkg.*\"] required for submodule suppression"
    - "# nosec BXXX inline annotation (no colon, no bare nosec) at END of flagged line"
    - "nosec with justification comment — explains why finding is intentional, not silenced blindly"

key-files:
  created: []
  modified:
    - pyproject.toml
    - src/homelab_mcp/config.py
    - src/homelab_mcp/database.py
    - src/homelab_mcp/infrastructure_crud.py

key-decisions:
  - "Do NOT install types-psycopg2 stubs — psycopg2 is an optional soft-dependency; adding stubs for an uninstalled package creates false coverage"
  - "Use list syntax [\"psycopg2\", \"psycopg2.*\"] in mypy override — single string would not suppress submodule import errors"
  - "nosec annotations are inline (same line as flagged code) with specific B-code — not bare #nosec, not on the line above"
  - "B104 (bind 0.0.0.0): intentional homelab default, configurable via MCP_HTTP_HOST env var"
  - "B608 (SQL injection risk): set_clause built from validated column names; values always parameterized"
  - "B108 (insecure /tmp use): backup_id is UUID, service_name is validated; homelab single-operator context"

patterns-established:
  - "nosec B608 pattern: parameterized queries with dynamic column names via validated allowlist — safe pattern"
  - "nosec B108 pattern: /tmp with UUID/validated identifiers in single-operator homelab context — acceptable pattern"
  - "mypy optional-dependency override: try/except ImportError guarded imports use [[tool.mypy.overrides]] ignore_missing_imports"

requirements-completed: [QA-01]

# Metrics
duration: 8min
completed: 2026-03-13
---

# Phase 16 Plan 01: Quality Gate — mypy + bandit cleanup Summary

**psycopg2 mypy override and 9 targeted nosec annotations make all three quality gates (ruff, mypy, bandit) exit 0 cleanly, unblocking v1.2 completion**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-13T22:03:25Z
- **Completed:** 2026-03-13T22:11:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `uv run mypy src/` exits 0 (51 source files) — fixed by adding psycopg2 override to pyproject.toml
- `uv run bandit -r src/` exits 0 — 9 medium findings suppressed with targeted nosec annotations across 3 files
- `uv run ruff check src/ tests/` exits 0 — was already passing, remains passing
- `uv run pytest tests/ -m "not integration" -q` — 603 passed, 7 skipped, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix mypy — add psycopg2 override to pyproject.toml** - `920d828` (chore)
2. **Task 2: Fix bandit — add 9 targeted nosec annotations** - `a0abfe3` (fix)

## Files Created/Modified
- `pyproject.toml` - Added [[tool.mypy.overrides]] block for psycopg2 and psycopg2.*
- `src/homelab_mcp/config.py` - nosec B104 on line 17 (0.0.0.0 bind intentional)
- `src/homelab_mcp/database.py` - nosec B608 on 2 UPDATE lines (validated column names, parameterized values)
- `src/homelab_mcp/infrastructure_crud.py` - nosec B108 on 6 /tmp path lines (UUID/validated identifiers)

## Decisions Made
- Do NOT install types-psycopg2 stubs — psycopg2 is an optional soft-dependency; adding stubs for an uninstalled package creates false coverage
- Use list syntax `["psycopg2", "psycopg2.*"]` in mypy override — single string would not suppress psycopg2.extras and other submodule imports
- All bandit suppressions are targeted (specific B-code) with explanatory comments documenting the intent

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All quality gates pass cleanly — Phase 16 (v1.2 completion gate) is unblocked
- CI pipeline (ruff + mypy + bandit + pytest) will pass on next push
- Ready for any remaining Phase 16 plans or v1.2 release

---
*Phase: 16-quality-gate*
*Completed: 2026-03-13*
