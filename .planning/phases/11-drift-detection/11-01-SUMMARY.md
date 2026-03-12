---
phase: 11-drift-detection
plan: 01
subsystem: testing
tags: [pytest, tdd, drift-detection, sqlite, asyncio]

# Dependency graph
requires: []
provides:
  - Failing test stubs for DRFT-01 (scan_drift structured report)
  - Failing test stubs for DRFT-02 (state drift including SSH probe path)
  - Failing test stubs for DRFT-03 (_diff_vm_config pure function)
  - Failing test stubs for DRFT-04 (SQLiteAdapter drift baseline CRUD)
  - Failing test stubs for DRFT-05 (update_baseline_after_mutation)
affects: [11-02, 11-03, 11-04, 11-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Wave-0 TDD scaffolding: all tests fail at import/attribute level establishing RED state before any production code exists

key-files:
  created:
    - tests/test_drift_detection.py
  modified:
    - tests/test_database.py

key-decisions:
  - "Module-level import in test_drift_detection.py causes ImportError (not AttributeError) at collection time — this is valid RED state for TDD Wave 0 scaffolding"
  - "TestDriftBaselines uses real in-memory SQLite adapter (not mocked) so tests go GREEN automatically once schema migration runs"
  - "test_ssh_probe_unreachable patches homelab_mcp.drift_detection.asyncssh.connect and get_proxmox_vm_status to isolate SSH probe failure path"

patterns-established:
  - "Wave-0 stubs: module-level imports that fail immediately establish RED state without requiring stub implementations"
  - "TestDriftBaselines adapter fixture uses :memory: SQLite with init_schema() to match existing test_database.py pattern"

requirements-completed: [DRFT-01, DRFT-02, DRFT-03, DRFT-04, DRFT-05]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 11 Plan 01: Drift Detection Test Scaffolds Summary

**Wave-0 TDD stubs for all 5 drift detection requirements: 10 tests in test_drift_detection.py (DRFT-01/02/03/05) and 5 tests in TestDriftBaselines (DRFT-04), all failing in RED state before any production code exists**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T18:25:16Z
- **Completed:** 2026-03-12T18:27:52Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Created `tests/test_drift_detection.py` with 4 test classes covering all DRFT-01/02/03/05 requirements including the SSH probe unreachable path
- Appended `TestDriftBaselines` class (5 tests) to `tests/test_database.py` covering SQLiteAdapter drift baseline CRUD (DRFT-04)
- All 15 new tests are in RED state: test_drift_detection.py fails with `ModuleNotFoundError`, TestDriftBaselines fails with `AttributeError` — production code not yet implemented
- All previously passing tests remain passing (13 passed, 3 skipped)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/test_drift_detection.py stub** - `45e55c0` (test)
2. **Task 2: Add TestDriftBaselines to tests/test_database.py** - `43c19a4` (test)

## Files Created/Modified

- `tests/test_drift_detection.py` - New file; TestScanDriftReport, TestConfigDrift, TestStateDrift, TestBaselineUpdate covering DRFT-01/02/03/05
- `tests/test_database.py` - Appended TestDriftBaselines with 5 CRUD tests for DRFT-04

## Decisions Made

- Module-level import in test_drift_detection.py causes ImportError at collection time — this is valid RED state for Wave-0 scaffolding and matches the plan's done criteria
- TestDriftBaselines uses real in-memory SQLite with `init_schema()` to test actual database behavior once the schema migration ships in Plan 02
- `test_ssh_probe_unreachable` patches `homelab_mcp.drift_detection.asyncssh.connect` and `get_proxmox_vm_status` to isolate the SSH probe failure path per plan spec

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Ruff auto-reformatted both test files on first commit attempt (line-length and import ordering). Re-staged and committed on second attempt — all hooks passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 15 test stubs are in RED state and ready for Plan 02 to make them GREEN
- Plan 02 must implement: `src/homelab_mcp/drift_detection.py` (scan_drift, _diff_vm_config, update_baseline_after_mutation) and SQLiteAdapter drift baseline CRUD methods
- TestDriftBaselines verify command: `uv run pytest tests/test_database.py::TestDriftBaselines -x`
- test_drift_detection.py verify command: `uv run pytest tests/test_drift_detection.py -x`

---
*Phase: 11-drift-detection*
*Completed: 2026-03-12*
