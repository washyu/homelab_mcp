---
phase: 27-update-tests-to-make-sure-we-are-testing-all-parameters-of-the-tools
plan: "01"
subsystem: testing

tags: [pytest, proxmox, handler-wiring, parameter-coverage]

# Dependency graph
requires:
  - phase: 26-sync-tool-schema-file-to-match-current-tool-parameters
    provides: "Phase 26-03 Proxmox VM/LXC parameters (sockets, cdrom, net0, ostype, swap, ssh_public_keys, unprivileged) wired into proxmox_handlers.py"
provides:
  - "Handler wiring tests for create_proxmox_vm Phase 26-03 parameters (sockets, cdrom, net0, ostype)"
  - "Handler wiring tests for create_proxmox_lxc Phase 26-03 parameters (swap, ssh_public_keys, unprivileged)"
  - "Explicit-value path and default-value path tests for each parameter set"
affects:
  - "Future edits to proxmox_handlers.py handle_create_proxmox_vm and handle_create_proxmox_lxc"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Patch API function via patch.object(_ph_mod, 'fn_name') and update_baseline_after_mutation via patch('src.homelab_mcp.drift_detection.update_baseline_after_mutation') since it is a local import inside the handler"

key-files:
  created: []
  modified:
    - tests/test_proxmox_api.py

key-decisions:
  - "Patch update_baseline_after_mutation at src.homelab_mcp.drift_detection.update_baseline_after_mutation, not via patch.object(_ph_mod, ...) — it is imported locally inside the handler function, not at module level, so the module attribute does not exist"

patterns-established:
  - "Handler wiring test pattern: import _ph_mod module + handler function, mock mock_rm with proxmox_session and db_adapter, patch get_resource_manager + API function via _ph_mod + drift_detection baseline, call handler, assert call_args.kwargs"

requirements-completed:
  - TEST-PXV-01
  - TEST-PXV-02
  - TEST-PXL-01
  - TEST-PXL-02

# Metrics
duration: 7min
completed: "2026-03-19"
---

# Phase 27 Plan 01: Proxmox Handler Wiring Tests Summary

**Four handler-wiring tests proving create_proxmox_vm and create_proxmox_lxc Phase 26-03 parameters are correctly extracted and forwarded with both explicit values and correct defaults**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-19T20:13:39Z
- **Completed:** 2026-03-19T20:20:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added `test_handle_create_proxmox_vm_passes_explicit_params` — asserts sockets=2, cdrom, net0, ostype forwarded when provided
- Added `test_handle_create_proxmox_vm_uses_defaults` — asserts sockets=1, cdrom=None, net0="virtio,bridge=vmbr0", ostype="l26" when omitted
- Added `test_handle_create_proxmox_lxc_passes_explicit_params` — asserts swap=1024, ssh_public_keys, unprivileged=False forwarded when provided
- Added `test_handle_create_proxmox_lxc_uses_defaults` — asserts swap=512, ssh_public_keys=None, unprivileged=True when omitted

## Task Commits

Each task was committed atomically:

1. **Task 1: Add handle_create_proxmox_vm wiring tests** - `baae9b8` (test)
2. **Task 2: Add handle_create_proxmox_lxc wiring tests** - `8a1b49d` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `tests/test_proxmox_api.py` - Added 4 new test methods to TestHandlerSessionThreading class

## Decisions Made
- Patching `update_baseline_after_mutation` at `src.homelab_mcp.drift_detection.update_baseline_after_mutation` rather than via `patch.object(_ph_mod, ...)` because the function is imported locally inside the handler body (`from ..drift_detection import update_baseline_after_mutation`), so the module-level attribute does not exist and `patch.object` raises `AttributeError`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed patch target for update_baseline_after_mutation**
- **Found during:** Task 1 (test_handle_create_proxmox_vm_passes_explicit_params)
- **Issue:** Plan instructed `patch.object(_ph_mod, "update_baseline_after_mutation", ...)` but the function is a local import inside the handler, not a module-level attribute — raised `AttributeError`
- **Fix:** Changed to `patch("src.homelab_mcp.drift_detection.update_baseline_after_mutation", mock_baseline)` targeting the actual module where the function lives
- **Files modified:** tests/test_proxmox_api.py
- **Verification:** Tests pass after fix
- **Committed in:** baae9b8 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug: incorrect patch target)
**Impact on plan:** Minimal — single patch path correction, no scope change.

## Issues Encountered
None beyond the patch target deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 4 Phase 26-03 parameter-wiring tests are green
- TestHandlerSessionThreading class now covers: list_resources, node_status, manage_vm, delete_vm session threading, and create_proxmox_vm/lxc parameter wiring
- Phase 27 plan 01 complete

---
*Phase: 27-update-tests-to-make-sure-we-are-testing-all-parameters-of-the-tools*
*Completed: 2026-03-19*
