---
phase: 13-drift-resource
plan: 01
subsystem: testing
tags: [pytest, tdd, mcp, pydantic, drift-detection]

# Dependency graph
requires: []
provides:
  - "Wave 0 test scaffold: 5 tests defining the contract for DRFT-07, DRFT-08, DRFT-09, DRFT-10"
  - "test_drift_resource_registered: asserts homelab://drift/latest in HOMELAB_RESOURCES"
  - "test_drift_resource_empty_state: asserts read_drift_resource() returns {drift_detected: None} before scan"
  - "test_drift_resource_after_scan: asserts read_drift_resource() returns report after set_latest_drift_report"
  - "test_drift_resource_notification: asserts DRIFT_SCAN_TOOLS contains scan_infrastructure_drift"
  - "test_drift_resource_uri_roundtrip: GREEN — confirms pydantic AnyUrl roundtrip for homelab:// URIs"
affects: [13-02, 13-03, 13-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 RED tests at commit time — correctness verified by --collect-only, not by passing tests"
    - "Local imports inside test functions for symbols that don't exist yet — avoids collection-level ImportError"

key-files:
  created:
    - tests/test_drift_resource.py
  modified: []

key-decisions:
  - "Local imports inside test function bodies for symbols not yet implemented — avoids module-level ImportError that would prevent pytest collection"
  - "test_drift_resource_notification uses DRIFT_SCAN_TOOLS membership check (simpler than MCP session mocking) — full notification integration verified by manual test per 13-VALIDATION.md"

patterns-established:
  - "Wave 0 tests are intentionally RED at commit time — 4 RED / 1 GREEN is the correct Wave 0 state"

requirements-completed: [DRFT-07, DRFT-08, DRFT-09, DRFT-10]

# Metrics
duration: 5min
completed: 2026-03-13
---

# Phase 13 Plan 01: Drift Resource Wave 0 Test Scaffold Summary

**Five failing RED tests plus one GREEN URI roundtrip test defining the full contract for homelab://drift/latest resource (DRFT-07 through DRFT-10)**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-13T20:13:29Z
- **Completed:** 2026-03-13T20:18:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `tests/test_drift_resource.py` with five test functions, all collected by pytest without SyntaxError or ImportError
- `test_drift_resource_uri_roundtrip` passes GREEN — confirms `AnyUrl("homelab://drift/latest")` does not get normalised by pydantic
- Four tests are RED as expected — they define the implementation contract for Plan 02
- Pre-commit hooks (ruff lint, ruff format, mypy) all passed on commit

## Task Commits

1. **Task 1: Create tests/test_drift_resource.py (Wave 0 scaffold)** - `01626b7` (test)

**Plan metadata:** (pending final docs commit)

## Files Created/Modified

- `tests/test_drift_resource.py` - Wave 0 test scaffold with five functions covering resource registration, empty/post-scan state, notification wiring, and URI roundtrip

## Decisions Made

- Used local imports inside test function bodies for symbols that don't exist yet (`read_drift_resource`, `set_latest_drift_report`, `DRIFT_SCAN_TOOLS`) — this prevents module-level ImportError that would block pytest collection
- `test_drift_resource_notification` checks `DRIFT_SCAN_TOOLS` membership rather than mocking MCP session — avoids complex async session setup while still verifying DRFT-10 wiring constant exists
- Used `asyncio.run()` within sync test functions (consistent with project's STRICT asyncio mode — avoids `@pytest.mark.asyncio` which requires `asyncio_mode = auto` or fixture setup)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 scaffold complete; Plan 02 can now implement:
  - `homelab://drift/latest` entry in `HOMELAB_RESOURCES` (server.py)
  - `_latest_drift_report` module-level state + `get_latest_drift_report` / `set_latest_drift_report` (server.py)
  - `read_drift_resource()` in `resource_readers.py`
  - `DRIFT_SCAN_TOOLS` frozenset in `server.py`
  - Notification dispatch in `execute_tool()` for drift scan results
- All four RED tests will turn GREEN when Plan 02 is complete

---
*Phase: 13-drift-resource*
*Completed: 2026-03-13*

## Self-Check: PASSED

- `tests/test_drift_resource.py`: FOUND
- `13-01-SUMMARY.md`: FOUND
- Commit `01626b7`: FOUND — test(13-01): add Wave 0 test scaffold for drift resource (DRFT-07..10)
