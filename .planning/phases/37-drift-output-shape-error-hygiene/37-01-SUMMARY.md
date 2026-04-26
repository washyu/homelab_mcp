---
phase: 37-drift-output-shape-error-hygiene
plan: "01"
subsystem: drift-detection
tags:
  - drift
  - scan_drift
  - 4-bucket
  - hostname-filter
  - counts
  - guidance
  - tdd
dependency_graph:
  requires:
    - 36-drift-sitemap-foundation (scan_drift foundation, per-row record shape D-02, degenerate-row skip D-10a)
    - Phase 35 db_adapter.get_all_devices() (sitemap read funnel)
    - Phase 34 resolve_proxmox_credentials / get_proxmox_client (credential resolver)
    - Phase 36 log_filter.sanitize_error (per-row error redaction D-09a)
  provides:
    - scan_drift Phase 37 stable 4-bucket envelope
    - hostname exact-match node filter (D-01)
    - counts sub-dict (D-07)
    - conditional guidance field (D-09)
    - _EMPTY_SCAN_GUIDANCE module constant
  affects:
    - tests/test_drift_detection.py (TestScanDrift4Bucket class added)
    - Future: Phase 39 DRFT-17/18/19 will populate unknown/changed buckets
    - Future: Plan 37-04 will add assertions for new envelope keys to existing TestScanDrift2Bucket tests
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle (failing tests committed before implementation)
    - Module-level constant for shared guidance text (_EMPTY_SCAN_GUIDANCE)
    - Conditional dict key insertion (guidance present iff scanned == 0)
    - Defensive sum(counts.values()) for scanned invariant
key_files:
  created: []
  modified:
    - src/homelab_mcp/drift_detection.py
    - tests/test_drift_detection.py
decisions:
  - "guidance constant _EMPTY_SCAN_GUIDANCE placed at module level as single source of truth — identical text for empty-sitemap and filter-narrowed-to-zero cases (D-09, Claude's Discretion 6)"
  - "counts dict key order matches bucket declaration order: probed_ok, unreachable, unknown, changed"
  - "comment referencing PROXMOX_HOST removed from module to satisfy zero-match acceptance criterion; intent preserved in adjacent comment"
metrics:
  duration_minutes: 12
  completed_date: "2026-04-26"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
requirements_completed:
  - DRFT-13
  - DRFT-14
  - DRFT-15
---

# Phase 37 Plan 01: Drift 4-Bucket Envelope + Hostname Filter Summary

**One-liner:** Phase 37 stable scan_drift rewrite — 4-bucket envelope (probed_ok/unreachable/unknown/changed always present), hostname exact-match node filter (D-01), counts sub-dict (D-07), and conditional guidance field (D-09) pointing to sitemap CRUD tools.

## What Was Built

Rewrote `scan_drift` in `src/homelab_mcp/drift_detection.py` to deliver Phase 37's locked response envelope. The Phase 36 function returned a 2-bucket dict (`probed_ok`, `unreachable`); the Phase 37 function returns a 9-key dict with stable shape regardless of filter scope.

### Key changes

1. **Module docstring** — replaced "Phase 36 ships a 2-bucket interim shape... Phase 37 will expand" with a Phase-37-stable description of all four buckets, including that `unknown` and `changed` are reserved-empty until Phase 39.

2. **D-01 hostname filter** — after `db_adapter.get_all_devices()` and before the degenerate-row skip, a list-comprehension filters rows to `row.get("hostname") == node` when `node is not None`. No-match returns `status="success"` with all four buckets empty (never an error).

3. **D-04/D-05 four buckets** — `unknown` and `changed` initialised as empty lists. Never appended to in Phase 37; reserved for Phase 39 (DRFT-17/19). Clients iterate without `dict.get(..., [])` defensive checks.

4. **D-07 counts sub-dict** — `counts = {"probed_ok": N, "unreachable": N, "unknown": 0, "changed": 0}` inserted before `probed_ok` in return dict. `scanned = sum(counts.values())` (defensive vs. Phase 39 bucket expansion).

5. **D-09 guidance field** — `_EMPTY_SCAN_GUIDANCE` module constant. Inserted into response iff `scanned == 0`; absent otherwise. Text mentions `discover_and_map`, `get_network_sitemap`, `purge_failed_discoveries`, `decommission_device`. No `PROXMOX_HOST` reference anywhere in the file.

6. **Locked envelope key order** — `status, scan_timestamp, scanned, counts, [guidance,] probed_ok, unreachable, unknown, changed`. Built via sequential dict insertion (Python insertion-order preserved).

7. **Tests** — `TestScanDrift4Bucket` class with 11 tests added to `tests/test_drift_detection.py`. TDD RED/GREEN protocol followed: failing tests committed (db1d9b3), implementation committed after all pass (e88906f).

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED — failing tests | db1d9b3 | 9 of 11 new tests failed against Phase 36 code |
| GREEN — implementation | e88906f | 17/17 tests pass (6 Phase 36 + 11 Phase 37) |
| REFACTOR | not needed | Code was clean; ruff and mypy both clean |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| db1d9b3 | test | RED gate — TestScanDrift4Bucket failing tests |
| e88906f | feat | GREEN gate — Phase 37 scan_drift implementation |

## Verification Results

### Automated checks (all pass)

| Check | Result |
|-------|--------|
| `ruff check src/homelab_mcp/drift_detection.py` | PASS |
| `mypy src/homelab_mcp/drift_detection.py` | PASS — no issues |
| `pytest tests/test_drift_detection.py -v --no-cov` | PASS — 17/17 |
| `pytest tests/test_ast_regression.py -v --no-cov` | PASS — 9/9 |
| `pytest tests/test_drift_detection.py::TestScanDrift2Bucket` | PASS — 6/6 (Phase 36 preserved) |
| `pytest tests/test_ast_regression.py::test_drift_detection_no_baseline_references_phase36` | PASS |

### Acceptance criteria grep checks (all pass)

| Criterion | Result |
|-----------|--------|
| `grep -c "PROXMOX_HOST" drift_detection.py` | 0 |
| `grep -c "os.getenv" drift_detection.py` | 0 |
| `grep -c "drift_baseline" drift_detection.py` | 0 |
| `grep -c "2-bucket interim" drift_detection.py` | 0 |
| `grep -n "_EMPTY_SCAN_GUIDANCE"` | 2 matches (definition + reference) |
| `grep -n "discover_and_map\|get_network_sitemap"` | 2 matches |
| `grep -n "purge_failed_discoveries\|decommission_device"` | 2 matches |
| `grep -n '"counts"'` | 2 matches |
| `grep -n '"guidance"'` | 4 matches (docstring + conditional insertion) |
| `grep -n "if node is not None"` | 1 match |
| `grep -n 'row.get("hostname") == node'` | 1 match |

### Inline Python verification (all pass)

- Empty-sitemap D-04/D-05/D-07/D-09 simultaneous: `envelope ok`
- node-filter no-match D-01/D-09: `node-filter no-match ok`
- Key order locked: `key order ok`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PROXMOX_HOST substring in comment**
- **Found during:** Task 1 acceptance-criteria check
- **Issue:** The plan's verbatim file content included a comment `# mentions PROXMOX_HOST (closes Bug B...)` which caused `grep -c "PROXMOX_HOST"` to return 1 instead of 0 — violating the acceptance criterion.
- **Fix:** Rewrote the comment to say "References only tool names, no env-var credentials" preserving the intent without the forbidden substring.
- **Files modified:** `src/homelab_mcp/drift_detection.py`
- **Impact:** Zero — purely a comment-text change. The acceptance criterion `grep -c "PROXMOX_HOST" ... returns ZERO` now passes.

## Known Stubs

None — `unknown` and `changed` are intentionally reserved-empty `[]` per Phase 37 design (D-06). They are not stubs; they are placeholder buckets whose record shape is deferred to Phase 39 (DRFT-17/19) by explicit decision. The plan's goal (stable 4-bucket envelope) is fully achieved.

## Threat Flags

No new threat surface introduced. The `node` parameter is consumed only via Python list-comprehension equality (`row.get("hostname") == node`) — no SQL interpolation, no subprocess, no eval. The `_EMPTY_SCAN_GUIDANCE` constant is static text with no user-data substitution. All STRIDE threats T-37-01-01 through T-37-01-10 addressed as documented in the plan's threat register.

## Self-Check: PASSED

### Files exist

- `src/homelab_mcp/drift_detection.py` — present, contains Phase 37 implementation
- `tests/test_drift_detection.py` — present, contains `TestScanDrift4Bucket` class

### Commits exist

- `db1d9b3` — present (test RED gate)
- `e88906f` — present (feat GREEN gate)
