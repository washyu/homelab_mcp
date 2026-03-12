---
phase: 11-drift-detection
plan: "03"
subsystem: api
tags: [proxmox, aiohttp, drift-detection, vm-config]

# Dependency graph
requires:
  - phase: 11-01
    provides: drift_detection module scaffold and baseline storage layer
provides:
  - get_proxmox_vm_config() function in proxmox_api.py — fetches persistent VM config from /config endpoint
affects:
  - 11-04-PLAN.md (drift scan logic will call get_proxmox_vm_config for config drift detection)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Mirror get_proxmox_vm_status pattern for all Proxmox per-VM API calls (same params, catch same exceptions, same return shape)

key-files:
  created: []
  modified:
    - src/homelab_mcp/proxmox_api.py
    - tests/test_proxmox_api.py

key-decisions:
  - "get_proxmox_vm_config follows get_proxmox_vm_status pattern exactly — same signature, same error handling, only endpoint differs (/config vs /status/current)"

patterns-established:
  - "VM API functions: get_proxmox_client(host, session) -> client.get(endpoint) -> {status, node, vmid, type, data} or {status: error, message}"

requirements-completed: [DRFT-03]

# Metrics
duration: 8min
completed: 2026-03-12
---

# Phase 11 Plan 03: get_proxmox_vm_config — Persistent VM Config Endpoint

**Async get_proxmox_vm_config() added to proxmox_api.py calling GET /nodes/{node}/{vm_type}/{vmid}/config for drift-detectable config fields (cores, memory, sockets, net0)**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-12T18:40:00Z
- **Completed:** 2026-03-12T18:48:00Z
- **Tasks:** 1 (TDD: test + implementation commits)
- **Files modified:** 2

## Accomplishments
- Added `get_proxmox_vm_config()` to `src/homelab_mcp/proxmox_api.py` following the exact `get_proxmox_vm_status` pattern
- Calls `/nodes/{node}/{vm_type}/{vmid}/config` endpoint (distinct from `/status/current` runtime data)
- Returns `{status, node, vmid, type, data}` on success; `{status: error, message}` on `aiohttp.ClientError` or `ValueError`
- 5 new tests covering success (qemu/lxc), error paths (ClientError/ValueError), and default vm_type=qemu
- All 75 proxmox API tests pass; mypy clean

## Task Commits

TDD task with two commits:

1. **RED - Failing tests** - `2cd2cfe` (test)
2. **GREEN - Implementation** - `3d065a0` (feat)

## Files Created/Modified
- `src/homelab_mcp/proxmox_api.py` - Added `get_proxmox_vm_config()` function (44 lines) after `get_proxmox_vm_status`
- `tests/test_proxmox_api.py` - Added `TestGetProxmoxVMConfig` class with 5 test cases; added import of `get_proxmox_vm_config`

## Decisions Made
- Followed plan pattern verbatim: no architectural decisions required
- Function placed immediately after `get_proxmox_vm_status` in file for co-location of related functions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. The `uv run python -c` invocation exhibited exit code 120 in this environment, but the function imported correctly via `python3 -c` and all tests passed via `uv run pytest`. This is a shell quoting environment issue, not a code issue.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `get_proxmox_vm_config` is ready for use by the drift scan logic (DRFT-03)
- Phase 11-04 (drift scan engine) can now call this function to compare live Proxmox config against stored baselines

---
*Phase: 11-drift-detection*
*Completed: 2026-03-12*
