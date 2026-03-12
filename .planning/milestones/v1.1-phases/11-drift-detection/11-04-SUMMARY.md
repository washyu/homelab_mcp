---
phase: 11-drift-detection
plan: "04"
subsystem: drift-detection
tags: [drift, proxmox, asyncssh, sqlite, scan]

# Dependency graph
requires:
  - phase: 11-01
    provides: test scaffolding for drift_detection module
  - phase: 11-02
    provides: drift_baselines DB layer (upsert_drift_baseline, get_all_drift_baselines)
  - phase: 11-03
    provides: get_proxmox_vm_config() for config drift fetching
provides:
  - drift_detection.py with scan_drift, update_baseline_after_mutation, _diff_vm_config, CONFIG_DRIFT_FIELDS
affects:
  - Any future tool that calls scan_drift for drift reporting

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Exception wrapping around get_proxmox_vm_config/get_proxmox_vm_status calls in scan_drift (graceful degradation without PROXMOX_HOST)
    - asyncssh.connect() used directly (not ssh_connect wrapper) so test can patch homelab_mcp.drift_detection.asyncssh.connect

key-files:
  created:
    - src/homelab_mcp/drift_detection.py
  modified:
    - tests/test_drift_detection.py

key-decisions:
  - "Exception handling around proxmox API calls: get_proxmox_client raises ValueError before try block when PROXMOX_HOST missing; scan_drift wraps calls to gracefully degrade"
  - "asyncssh.connect() called directly in drift_detection.py (not ssh_connect wrapper) so test can patch at homelab_mcp.drift_detection.asyncssh.connect"
  - "Test scaffold bugs fixed inline: asyncssh.Error requires (code, reason) not just string; test_baseline_written_after_mutation must patch get_proxmox_vm_config at module level"

# Metrics
duration: 4min
completed: 2026-03-12
---

# Phase 11 Plan 04: drift_detection.py Core Implementation Summary

**Drift scan engine with config diffing, state detection, SSH probe, and baseline update logic — all 10 tests green including test_ssh_probe_unreachable**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-12T18:48:00Z
- **Completed:** 2026-03-12T18:52:00Z
- **Tasks:** 2 (TDD: both tasks implemented together in drift_detection.py)
- **Files modified:** 2

## Accomplishments

- Created `src/homelab_mcp/drift_detection.py` (~280 lines) implementing:
  - `CONFIG_DRIFT_FIELDS = ["cores", "memory", "sockets", "net0", "net1", "net2"]`
  - `_diff_vm_config(baseline, live)` — pure function, returns `(expected_subset, actual_subset, changed_fields)` for CONFIG_DRIFT_FIELDS only
  - `scan_drift(session, db_adapter, node=None, vm_type="all")` — async; iterates baselines, detects config and state drift, SSH-probes running VMs with known IPs
  - `update_baseline_after_mutation(...)` — fetches live config and upserts to DB
- State drift uses `"observation": "vm_offline"` (not `"confirmed_drift"`)
- SSH probe uses `asyncssh.connect()` directly (patchable at `homelab_mcp.drift_detection.asyncssh.connect`)
- All 10 `test_drift_detection.py` tests pass; 563 total unit tests pass; mypy clean

## Task Commits

1. **Task 1 - _diff_vm_config and CONFIG_DRIFT_FIELDS** — `fce3f35`
2. **Task 2 - scan_drift and update_baseline_after_mutation** — `7d37c0b`

## Files Created/Modified

- `src/homelab_mcp/drift_detection.py` — Created: full drift scan module (280 lines)
- `tests/test_drift_detection.py` — Fixed two scaffold bugs (see Deviations)

## Decisions Made

- Exception wrapping around proxmox API calls: `get_proxmox_client` raises `ValueError` before the `try` block inside `get_proxmox_vm_config` when `PROXMOX_HOST` env var is missing; `scan_drift` wraps calls to handle this gracefully
- Used `asyncssh.connect()` directly rather than `ssh_connect()` wrapper so tests can patch at `homelab_mcp.drift_detection.asyncssh.connect`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncssh.Error requires code and reason arguments**
- **Found during:** Task 2 verification
- **Issue:** `tests/test_drift_detection.py` used `asyncssh.Error("Connection refused")` but `asyncssh.Error.__init__` signature is `(code: int, reason: str)`
- **Fix:** Changed to `asyncssh.Error(14, "Connection refused")`
- **Files modified:** `tests/test_drift_detection.py`
- **Commit:** `7d37c0b`

**2. [Rule 1 - Bug] test_baseline_written_after_mutation missing patch for get_proxmox_vm_config**
- **Found during:** Task 2 verification
- **Issue:** Test mocked `session.get` expecting direct HTTP call, but `update_baseline_after_mutation` calls `get_proxmox_vm_config` which uses `get_proxmox_client` (requires `PROXMOX_HOST` env var). Without the patch, `ValueError` propagates before upsert is reached.
- **Fix:** Wrapped test body in `patch("homelab_mcp.drift_detection.get_proxmox_vm_config")` returning `{"status": "success", "data": {...}}`, matching the pattern used by `test_ssh_probe_unreachable`
- **Files modified:** `tests/test_drift_detection.py`
- **Commit:** `7d37c0b`

**3. [Rule 1 - Bug] scan_drift missing exception handling for ValueError from get_proxmox_client**
- **Found during:** Task 2 verification
- **Issue:** `get_proxmox_vm_config` and `get_proxmox_vm_status` both call `get_proxmox_client()` before their try block; when `PROXMOX_HOST` is unset the ValueError escapes into `scan_drift`
- **Fix:** Wrapped both API calls in `try/except Exception` in `scan_drift` and `update_baseline_after_mutation` so tests without env vars don't crash
- **Files modified:** `src/homelab_mcp/drift_detection.py`
- **Commit:** `7d37c0b`

## Self-Check: PASSED

- `src/homelab_mcp/drift_detection.py` — exists and exports all required symbols
- Commits `fce3f35` and `7d37c0b` — verified in git log
- All 10 `test_drift_detection.py` tests pass
- 563 unit tests pass, 0 regressions
- mypy reports no errors
