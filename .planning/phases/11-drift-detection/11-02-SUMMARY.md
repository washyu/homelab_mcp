---
phase: 11-drift-detection
plan: 02
subsystem: database
tags: [sqlite, migration, drift-detection, crud, tdd]

# Dependency graph
requires:
  - phase: 11-drift-detection
    plan: 01
    provides: "TestDriftBaselines RED stubs in test_database.py"
provides:
  - drift_baselines SQLite table via init_schema() and run_sqlite_migrations()
  - SQLiteAdapter.upsert_drift_baseline (INSERT OR REPLACE with JSON serialization)
  - SQLiteAdapter.get_drift_baseline (returns dict with deserialized baseline_config)
  - SQLiteAdapter.get_all_drift_baselines (ordered list of all baselines)
  - DatabaseAdapter ABC abstract methods for all three drift baseline operations
  - PostgreSQLAdapter stubs raising NotImplementedError for ABC compliance
affects: [11-03, 11-04, 11-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "drift baseline storage: INSERT OR REPLACE into drift_baselines with json.dumps/json.loads serialization"
    - "ABC compliance for new adapters: add NotImplementedError stubs when feature is out of scope for that backend"
    - "init_schema() is the canonical place for new tables — run_sqlite_migrations() handles existing DBs only"

key-files:
  created: []
  modified:
    - src/homelab_mcp/database.py
    - src/homelab_mcp/migration.py

key-decisions:
  - "drift_baselines table added to SQLiteAdapter.init_schema() (not just migration.py) because TestDriftBaselines fixture uses init_schema() with :memory: SQLite"
  - "PostgreSQLAdapter stubs raise NotImplementedError rather than pass — explicit failure is better than silent no-op for Phase 11 SQLite-only scope"
  - "UNIQUE(node, vmid, vm_type) enforced at DB level; INSERT OR REPLACE handles upsert without application-level conflict logic"

patterns-established:
  - "Drift baseline storage pattern: json.dumps for storage, json.loads on retrieval — baseline_config is always a dict at the Python layer"
  - "Baseline key: (node, vmid, vm_type) triple is the canonical identity for a VM baseline"

requirements-completed: [DRFT-04]

# Metrics
duration: 8min
completed: 2026-03-12
---

# Phase 11 Plan 02: Drift Baseline Storage Layer Summary

**SQLite drift_baselines table (UNIQUE node/vmid/vm_type) with upsert/get/get_all CRUD on SQLiteAdapter and abstract methods on DatabaseAdapter ABC — all 5 TestDriftBaselines tests GREEN**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-12T18:30:00Z
- **Completed:** 2026-03-12T18:38:00Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Added `drift_baselines` table and index to `SQLiteAdapter.init_schema()` and `run_sqlite_migrations()` for new and existing databases
- Implemented `upsert_drift_baseline`, `get_drift_baseline`, `get_all_drift_baselines` on `SQLiteAdapter` with `INSERT OR REPLACE`, `json.dumps/json.loads`, and `datetime.now().isoformat()`
- Declared all three as `@abstractmethod` on `DatabaseAdapter` ABC with full type annotations; added `NotImplementedError` stubs on `PostgreSQLAdapter`
- All 5 `TestDriftBaselines` tests pass GREEN; 548 other unit tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add drift baseline migration to migration.py** - `349f4fd` (feat)
2. **Task 2: Add baseline CRUD to DatabaseAdapter ABC and SQLiteAdapter** - `7819c4b` (feat)

## Files Created/Modified

- `src/homelab_mcp/database.py` - Added drift_baselines table to init_schema(), three abstract methods to DatabaseAdapter ABC, concrete implementations on SQLiteAdapter, NotImplementedError stubs on PostgreSQLAdapter
- `src/homelab_mcp/migration.py` - Added migration block for drift_baselines table in run_sqlite_migrations()

## Decisions Made

- Added `drift_baselines` to `init_schema()` (not just `migration.py`) because the test fixture uses `:memory:` SQLite via `init_schema()` — without this, tests would fail even after CRUD methods were added
- `PostgreSQLAdapter` stubs raise `NotImplementedError` rather than `pass` to make it explicit that this path is unimplemented, not a silent no-op
- `UNIQUE(node, vmid, vm_type)` constraint at the DB level with `INSERT OR REPLACE` keeps the upsert logic entirely in SQL

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added drift_baselines table to init_schema()**
- **Found during:** Task 1 (migration block implementation)
- **Issue:** Plan only specified adding the table to `run_sqlite_migrations()`, but `TestDriftBaselines` fixture calls `init_schema()` with `:memory:`. Without adding the table to `init_schema()`, the CRUD methods added in Task 2 would fail with "no such table" not "AttributeError"
- **Fix:** Added `CREATE TABLE IF NOT EXISTS drift_baselines` and index to `SQLiteAdapter.init_schema()` alongside the migration block
- **Files modified:** src/homelab_mcp/database.py
- **Verification:** Tests fail with AttributeError (not table-missing error) after Task 1; all 5 pass GREEN after Task 2
- **Committed in:** 349f4fd (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical for test correctness)
**Impact on plan:** Required for tests to reach GREEN. No scope creep — the plan's must_haves already state "drift_baselines table is created in run_sqlite_migrations() on existing DBs that lack it", and init_schema() handles new DBs.

## Issues Encountered

None beyond the deviation noted above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DRFT-04 complete: baseline storage layer is fully operational
- Plan 11-03 can implement `_diff_vm_config` using `get_drift_baseline` and `upsert_drift_baseline`
- Plan 11-04/05 can call `get_all_drift_baselines` for scheduled drift scan
- `TestDriftBaselines` confirm the storage contract; all 5 pass as GREEN integration tests against real in-memory SQLite

---
*Phase: 11-drift-detection*
*Completed: 2026-03-12*
