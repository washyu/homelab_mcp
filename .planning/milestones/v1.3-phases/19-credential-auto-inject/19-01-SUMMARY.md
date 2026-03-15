---
phase: 19-credential-auto-inject
plan: 01
subsystem: testing
tags: [pytest, tdd, red-tests, credential-injection, keyring, ssh, proxmox]

# Dependency graph
requires:
  - phase: 17-credential-store-foundation
    provides: credential_store.py with list_credentials/get_credential functions
  - phase: 18-credentials-cli-version
    provides: credential_store module-level imports in server.py for monkeypatching
provides:
  - Four RED failing tests establishing contracts for INJECT-01, INJECT-02, INJECT-03, and log safety
affects: [19-credential-auto-inject]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 RED tests use local imports inside function bodies — consistent with Phases 12-18 pattern"
    - "Patch targets are dotted paths where imports will live in production code (homelab_mcp.ssh_tools.list_credentials, etc.)"

key-files:
  created: []
  modified:
    - tests/test_ssh_tools.py
    - tests/test_proxmox_api.py

key-decisions:
  - "Patch targets homelab_mcp.ssh_tools.list_credentials and homelab_mcp.ssh_tools.get_credential (function-body import pattern, not module-level)"
  - "Patch targets homelab_mcp.proxmox_api.list_credentials and homelab_mcp.proxmox_api.get_credential for Proxmox keyring fallback"
  - "Tests fail with AttributeError from pytest-mock (attribute not found in module) which shows as FAILED not ERROR — acceptable RED state since production imports not yet present"

patterns-established:
  - "Wave 0 tests: all 4 fail with FAILED (not ERROR) — collection clean, 90 existing tests stay GREEN"

requirements-completed: [INJECT-01, INJECT-02, INJECT-03]

# Metrics
duration: 1min
completed: 2026-03-15
---

# Phase 19 Plan 01: Wave 0 RED Tests Summary

**Four failing test contracts for SSH keyring auto-inject, explicit override precedence, log safety, and Proxmox keyring fallback — all FAILED (not ERROR), 90 existing tests remain GREEN**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-15T03:16:15Z
- **Completed:** 2026-03-15T03:17:30Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Appended 3 RED tests to `tests/test_ssh_tools.py` covering INJECT-01, INJECT-02, and log safety (INJECT-04)
- Appended 1 RED test to `tests/test_proxmox_api.py` covering INJECT-03 (Proxmox keyring fallback)
- Verified collection passes: 94 tests collected (4 new), no ImportErrors
- Verified all 4 new tests are FAILED, all 90 existing tests are PASSED

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED tests for INJECT-01, INJECT-02, INJECT-03, log safety** - `be7e2e8` (test)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `tests/test_ssh_tools.py` - Added `test_resolve_ssh_credentials_keyring_inject`, `test_resolve_ssh_credentials_explicit_overrides_keyring`, `test_no_password_in_log_after_ssh_keyring_inject`
- `tests/test_proxmox_api.py` - Added `test_get_proxmox_client_keyring_fallback`

## Decisions Made

- Patch targets use `homelab_mcp.*` module path (not `src.homelab_mcp.*`) — consistent with function-body import pattern established in Phases 12-18
- Tests fail at pytest-mock patch time (AttributeError: module has no attribute) which registers as FAILED not ERROR — acceptable Wave 0 RED state

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 RED tests complete; ready for Phase 19-02 (GREEN — implement keyring injection in `resolve_ssh_credentials` and `get_proxmox_client`)
- Patch targets confirmed: `homelab_mcp.ssh_tools.list_credentials`, `homelab_mcp.ssh_tools.get_credential`, `homelab_mcp.proxmox_api.list_credentials`, `homelab_mcp.proxmox_api.get_credential`

---
*Phase: 19-credential-auto-inject*
*Completed: 2026-03-15*

## Self-Check: PASSED

- tests/test_ssh_tools.py: FOUND
- tests/test_proxmox_api.py: FOUND
- 19-01-SUMMARY.md: FOUND
- Commit be7e2e8: FOUND
