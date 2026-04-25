---
phase: 36-drift-sitemap-foundation
plan: 01
subsystem: database

tags: [drift, sqlite, postgres, schema-cleanup, abc, footgun-removal]

# Dependency graph
requires:
  - phase: 35-sitemap-discovery-reliability
    provides: "db_adapter.get_all_devices() — sitemap iteration entry point that becomes the drift baseline source"
provides:
  - "DatabaseAdapter ABC with no drift_baseline methods"
  - "SQLiteAdapter with no drift_baseline implementations and no CREATE TABLE drift_baselines in init_schema"
  - "PostgreSQLAdapter with no drift_baseline NotImplementedError stubs"
affects: [36-02, 36-03, 36-04, 36-05, 36-06, drift-sitemap-foundation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Symbol-name-based deletion (resolve by class member identifier, not line number) — robust to ±3 line drift in source files"

key-files:
  created: []
  modified:
    - "src/homelab_mcp/database.py"

key-decisions:
  - "Deletion resolved by symbol name, not line number — line-drift Pitfall 3 (RESEARCH) confirmed by inspection (Postgres stubs at 916-939, off ±3 from CONTEXT.md ranges)"
  - "Migration cleanup (DROP TABLE drift_baselines) deferred to Plan 36-02 per dependency split — Plan 36-01 is storage-tier-only deletion"

patterns-established:
  - "Storage-tier dissolution: ABC method removal cascades cleanly to subclass impls when no consumers reference them; verified via mypy clean post-deletion"

requirements-completed: [DRFT-21]

# Metrics
duration: 6min
completed: 2026-04-25
---

# Phase 36 Plan 01: Database Drift Layer Removal Summary

**Removed the parallel `drift_baselines` data layer from `database.py` — three ABC method declarations, three SQLite implementations, three Postgres NotImplementedError stubs, and the `CREATE TABLE drift_baselines` block (with index) — preparing the storage tier for sitemap-as-baseline drift architecture.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-25T19:39:00Z (approx)
- **Completed:** 2026-04-25T19:45:12Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Removed `DatabaseAdapter.upsert_drift_baseline / get_drift_baseline / get_all_drift_baselines` ABC method declarations and the `# Drift baseline CRUD methods` comment block
- Removed `SQLiteAdapter` implementations of all three drift methods and their comment block
- Removed `PostgreSQLAdapter` NotImplementedError stubs of all three drift methods and their comment block
- Removed `CREATE TABLE IF NOT EXISTS drift_baselines (…)` block plus `CREATE INDEX IF NOT EXISTS idx_drift_baselines_node_vmid` from `SQLiteAdapter.init_schema` (D-06)
- Verified Postgres `init_schema` already does NOT create `drift_baselines` (no change needed there, per CONTEXT D-06 + RESEARCH A1)
- Confirmed all three classes (`DatabaseAdapter`, `SQLiteAdapter`, `PostgreSQLAdapter`) intact with `get_all_devices` preserved on both adapters (Pattern E sitemap iteration entry point preserved)

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove drift_baseline methods + ABC declarations + CREATE block from database.py** — `d5ce312` (refactor)

## Files Created/Modified

- `src/homelab_mcp/database.py` — 151 lines removed:
  - ABC declarations for the three drift_baseline methods (with comment)
  - SQLite implementations of the three methods (with comment)
  - Postgres NotImplementedError stubs of the three methods (with comment)
  - `CREATE TABLE drift_baselines` + `CREATE INDEX idx_drift_baselines_node_vmid` block in `SQLiteAdapter.init_schema`
  - Class boundaries, factory function, and all non-drift adapter operations untouched

## Decisions Made

- **Symbol-name resolution over line-number lookup** — RESEARCH Pitfall 3 flagged ±3 line drift in CONTEXT.md citations. Confirmed during execution: Postgres stubs landed at lines 916-939 with `get_drift_baseline` at 928-935 (CONTEXT.md said 928 only; method spans ~7 lines). Resolving by symbol name made all four deletion targets (A, B, C, D) unambiguous.
- **Migration cleanup deferred to Plan 36-02** — `migration.py` still contains the `CREATE TABLE drift_baselines` auto-create block (lines 224-247) and lacks the `DROP TABLE` step. Per the plan dependency graph, that work belongs to Plan 36-02 (DRFT-21 migration tier). After Plan 36-02 lands, `init_schema()` on a fresh `:memory:` SQLite will not produce a `drift_baselines` table from any path. (Currently it still does — `migration.py:224-247` runs after `init_schema()` and re-creates it. This is by design: Plan 36-01 is storage-adapter only.)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. The four planned deletions (A: ABC methods, B: SQLiteAdapter impls, C: Postgres stubs, D: SQLite CREATE block) applied cleanly on first attempt. ruff and mypy passed without modification.

## Verification Evidence

Acceptance criteria evaluated post-edit:

- `grep -n "drift_baseline" src/homelab_mcp/database.py` → 0 matches (PASS)
- `grep -n "upsert_drift_baseline\|get_drift_baseline\|get_all_drift_baselines" src/homelab_mcp/database.py` → 0 matches (PASS)
- `grep -n "idx_drift_baselines_node_vmid" src/homelab_mcp/database.py` → 0 matches (PASS)
- `grep -n "CREATE TABLE IF NOT EXISTS drift_baselines" src/homelab_mcp/database.py` → 0 matches (PASS)
- `uv run ruff check src/homelab_mcp/database.py` → "All checks passed!" (PASS)
- `uv run mypy src/homelab_mcp/database.py` → "Success: no issues found in 1 source file" (PASS)
- `uv run python -c "from src.homelab_mcp.database import DatabaseAdapter, SQLiteAdapter, PostgreSQLAdapter; assert not hasattr(SQLiteAdapter, 'upsert_drift_baseline')"` → "OK - all drift_baseline methods removed from all 3 adapters" (PASS)
- File still contains `class DatabaseAdapter`, `class SQLiteAdapter`, `class PostgreSQLAdapter` (verified via grep) (PASS)
- File still contains `def get_all_devices` on both adapters (lines 302 and 664 post-deletion) (PASS)
- `SQLiteAdapter(':memory:').init_schema()` runs cleanly (PASS — note: `init_schema` still creates `drift_baselines` indirectly via `migration.py:224-247` auto-create path; that path is Plan 36-02's deletion target)

## Self-Check: PASSED

- File `src/homelab_mcp/database.py` exists at expected path: FOUND
- Commit `d5ce312` exists: FOUND (`git log --oneline | grep d5ce312` → `d5ce312 refactor(36-01): remove drift_baseline data layer from database.py`)

## Next Plan Readiness

Plan 36-02 (migration cleanup — DRFT-21 storage-migration tier) can proceed:

- `migration.py` lines 224-247 (CREATE block) need deletion
- `migration.py` needs SQLite + Postgres `DROP TABLE IF EXISTS drift_baselines` migration steps (D-05 pattern, mirroring Phase 33 ssh_credentials drop at `migration.py:37-62` SQLite / 281-305 Postgres)
- The `applied_migrations.append("create_drift_baselines_table")` line goes; replace with `applied_migrations.append("drop_drift_baselines_table")` on the new drop branch
- D-08 banner emission (mirrors Phase 33 banner shape) on the drop branch

After Plan 36-02 lands, the AST guards in Plan 36-05 (D-12/D-13) will fire — the database.py side of the contract is already prepared.

---
*Phase: 36-drift-sitemap-foundation*
*Completed: 2026-04-25*
