---
phase: 19-credential-auto-inject
plan: 02
subsystem: ssh-tools, proxmox-api
tags: [keyring, credential-injection, ssh, proxmox, tdd, green-phase]

# Dependency graph
requires:
  - phase: 19-01
    provides: Four RED failing tests for INJECT-01, INJECT-02, INJECT-03, log safety
  - phase: 17-credential-store-foundation
    provides: credential_store.py with get_credential/list_credentials functions
provides:
  - Keyring Tier 2 inject in resolve_ssh_credentials() — INJECT-01, INJECT-02 satisfied
  - Keyring fallback block in get_proxmox_client() — INJECT-03 satisfied
  - Log safety guaranteed — password value never appears in log output
affects: [19-credential-auto-inject]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level credential_store import in ssh_tools.py and proxmox_api.py for mocker.patch compatibility"
    - "Tier 2 keyring lookup inserted after Tier 1 explicit-args short-circuit in resolve_ssh_credentials()"
    - "Keyring fallback block in get_proxmox_client() after env var reads, before validation gates"
    - "logger.debug with %s formatting — password value never passed as log argument"

key-files:
  created: []
  modified:
    - src/homelab_mcp/ssh_tools.py
    - src/homelab_mcp/proxmox_api.py

key-decisions:
  - "Module-level import of get_credential/list_credentials (not lazy function-body import) — required for mocker.patch to find attributes in module namespace at patch time"
  - "credential_store.py has no homelab_mcp imports so no circular dependency risk from module-level import"
  - "Tier 2 keyring block resolves username as caller-supplied OR stored_username — explicit caller username takes precedence even when keyring is used"
  - "Proxmox keyring fallback: if PROXMOX_HOST is set, only inject if host matches registry entry (prevents cross-host injection)"

requirements-completed: [INJECT-01, INJECT-02, INJECT-03]

# Metrics
duration: 4min
completed: 2026-03-15
---

# Phase 19 Plan 02: Keyring Auto-Inject Implementation Summary

**Module-level credential_store imports in ssh_tools.py and proxmox_api.py enable keyring auto-inject for SSH (Tier 2) and Proxmox fallback — all four Wave 0 RED tests turned GREEN**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-15T03:19:42Z
- **Completed:** 2026-03-15T03:22:56Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `from .credential_store import get_credential, list_credentials` at module level in `ssh_tools.py` and `proxmox_api.py` (enables mocker.patch to find attributes at test patch time)
- Inserted Tier 2 keyring lookup block in `resolve_ssh_credentials()` after Tier 1 explicit-args short-circuit — INJECT-01 and INJECT-02 satisfied
- Restructured `get_proxmox_client()` to read all env vars first, then attempt keyring fallback when insufficient, then validate — INJECT-03 satisfied
- All four Wave 0 RED tests turned GREEN: `test_resolve_ssh_credentials_keyring_inject`, `test_resolve_ssh_credentials_explicit_overrides_keyring`, `test_no_password_in_log_after_ssh_keyring_inject`, `test_get_proxmox_client_keyring_fallback`
- Full non-integration test suite: 634 passed, 7 skipped — no regressions
- ruff + mypy: clean, no new errors

## Task Commits

Each task was committed atomically:

1. **Task 1: SSH keyring inject tier in resolve_ssh_credentials()** - `7f6c0ad` (feat)
2. **Task 2: Proxmox keyring fallback in get_proxmox_client()** - `4980bf9` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `src/homelab_mcp/ssh_tools.py` — Added module-level `credential_store` import; inserted Tier 2 keyring lookup block
- `src/homelab_mcp/proxmox_api.py` — Added module-level `credential_store` import; restructured `get_proxmox_client()` with deferred validation and keyring fallback block

## Decisions Made

- **Module-level import over function-body import:** The Wave 0 tests use `mocker.patch("homelab_mcp.ssh_tools.list_credentials", ...)`. This requires `list_credentials` to be an attribute of the module namespace at patch time. A function-body `from .credential_store import ...` only adds to the module namespace after the function is first called — too late for mocker.patch. Since `credential_store.py` has no homelab_mcp imports (stdlib only), importing it at module level is safe and creates no circular dependency.

- **Tier 2 username resolution:** `resolved_username = username or stored_username` — if the caller passed an explicit username, use it (even when keyring provides the password). This satisfies INJECT-02: explicit credentials always win, but when only a username is provided with no password, the keyring password can still be used with the caller's preferred username.

- **Proxmox validation gates moved after keyring block:** The early `if not host: raise ValueError(...)` was moved to after the keyring fallback, enabling keyring to supply the host when PROXMOX_HOST env var is absent.

## Deviations from Plan

**1. [Rule 1 - Bug] Module-level import used instead of function-body lazy import for mocker.patch compatibility**

- **Found during:** Task 1 (GREEN implementation)
- **Issue:** The plan specified a lazy function-body import (`from .credential_store import get_credential, list_credentials` inside the function body with `# noqa: PLC0415`). However, `mocker.patch("homelab_mcp.ssh_tools.list_credentials")` requires the attribute to exist in the module namespace at patch time. The function-body import only binds names to the module dict after the function is first called — causing `AttributeError` when pytest-mock tries to patch before calling the function.
- **Fix:** Moved `from .credential_store import get_credential, list_credentials` to module-level imports. No `# noqa: PLC0415` needed. No circular dependency risk since `credential_store.py` imports only stdlib.
- **Files modified:** `ssh_tools.py`, `proxmox_api.py`
- **Commits:** `7f6c0ad`, `4980bf9`

## Issues Encountered

None beyond the module-level import deviation (auto-fixed).

## User Setup Required

None.

## Next Phase Readiness

- All INJECT requirements satisfied: INJECT-01 (SSH keyring inject), INJECT-02 (explicit override), INJECT-03 (Proxmox keyring fallback)
- Ready for Phase 19-03 (end-to-end validation or next phase in roadmap)

---
*Phase: 19-credential-auto-inject*
*Completed: 2026-03-15*

## Self-Check: PASSED

- src/homelab_mcp/ssh_tools.py: FOUND
- src/homelab_mcp/proxmox_api.py: FOUND
- .planning/phases/19-credential-auto-inject/19-02-SUMMARY.md: FOUND
- Commit 7f6c0ad: FOUND
- Commit 4980bf9: FOUND
