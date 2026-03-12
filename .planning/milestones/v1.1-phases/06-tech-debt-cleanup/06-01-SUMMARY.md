---
phase: 06-tech-debt-cleanup
plan: 01
subsystem: infra
tags: [aiohttp, proxmox, session-management, resource-manager]

requires: []
provides:
  - session parameter on all 8 module-level Proxmox API functions
  - ResourceManager.proxmox_session threaded through every handler call
  - Zero per-request aiohttp sessions created for Proxmox tool calls
affects:
  - phase 09 (needs stable shared-session infrastructure)
  - phase 11 (needs stable session management)

tech-stack:
  added: []
  patterns:
    - "Local function-scope import (from ..server import get_resource_manager) inside each handler to avoid circular imports at module level"
    - "Optional session parameter pattern: session: aiohttp.ClientSession | None = None forwarded to get_proxmox_client(session=session)"

key-files:
  created: []
  modified:
    - src/homelab_mcp/proxmox_api.py
    - src/homelab_mcp/tool_handlers/proxmox_handlers.py
    - tests/test_proxmox_api.py

key-decisions:
  - "Local import of get_resource_manager inside each handler function (not at module level) to avoid circular import: server.py imports tool_handlers, so tool_handlers cannot import server at module level"
  - "session parameter added after all existing keyword args in each proxmox_api function to preserve backward compatibility (defaults to None)"
  - "delete_proxmox_vm and create_proxmox_vm thread session= to their internal manage_proxmox_vm calls"

patterns-established:
  - "session threading: add session: aiohttp.ClientSession | None = None to function, pass session=session to get_proxmox_client()"
  - "circular import avoidance: from ..server import get_resource_manager as local import inside handler function body"

requirements-completed: [DEBT-01]

duration: 18min
completed: 2026-03-11
---

# Phase 6 Plan 1: Thread Shared Session Through Proxmox Handlers Summary

**Proxmox ResourceManager.proxmox_session threaded through all 8 handler-to-API call sites, eliminating per-request aiohttp session creation**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-11T19:25:51Z
- **Completed:** 2026-03-11T19:43:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `session: aiohttp.ClientSession | None = None` parameter to all 8 module-level Proxmox API functions in `proxmox_api.py`, each passing `session=session` to `get_proxmox_client()`
- Added `from ..server import get_resource_manager` as a local import inside each of the 8 handler functions in `proxmox_handlers.py`, with `session=get_resource_manager().proxmox_session` passed on every API call
- `delete_proxmox_vm` and `create_proxmox_vm` thread session through to their internal `manage_proxmox_vm()` calls
- Added `TestHandlerSessionThreading` test class with 5 tests verifying session threading; updated 4 existing test assertions to match new `session=None` call signatures
- All 478 unit tests pass, mypy clean, ruff clean on modified files

## Task Commits

Each task was committed atomically:

1. **Task 1: Add session param + thread through handlers (TDD RED+GREEN)** - `8a929cc` (feat)
2. **Task 2: Verify full test suite and type checks** - included in `8a929cc`

**Plan metadata:** To be added by state update commit

_Note: Task 1 commit was bundled into commit `8a929cc` (feat(06-02)) by a concurrent agent that committed the working-tree state. All plan changes are present in that commit._

## Files Created/Modified

- `src/homelab_mcp/proxmox_api.py` - Added `session` parameter to 8 functions; each passes `session=session` to `get_proxmox_client()`
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py` - Added local `from ..server import get_resource_manager` import and `session=get_resource_manager().proxmox_session` to 8 handler functions
- `tests/test_proxmox_api.py` - Added `TestHandlerSessionThreading` class (5 tests); updated 4 existing assertions for new `session=None` call signatures

## Decisions Made

- **Local import over module-level import:** `get_resource_manager` is imported inside each handler function body rather than at module level. Reason: `server.py` imports from `tool_handlers`, creating a circular dependency if `tool_handlers` imports from `server` at module level. The local import is resolved at call time, breaking the cycle.
- **Backward-compatible session parameter:** Added as the last keyword arg with default `None`, so all existing callers (and tests that don't pass a session) continue to work unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated 4 existing test assertions to include session=None**
- **Found during:** Task 2 (full test suite run)
- **Issue:** Existing tests for `test_create_vm_and_start`, `test_delete_vm_success`, `test_delete_lxc_success`, `test_delete_running_vm` used `assert_called_once_with("pve", ..., "qemu")` without the new `session=None` kwarg, causing AssertionError after we added the session threading
- **Fix:** Updated each assertion to include `session=None` to match the new actual call signature
- **Files modified:** tests/test_proxmox_api.py
- **Verification:** All 478 unit tests pass
- **Committed in:** 8a929cc

**2. [Rule 1 - Bug] Switched from module-level import to local function import for get_resource_manager**
- **Found during:** Task 1 (ruff/linter auto-fix during commit)
- **Issue:** Module-level `from ..server import get_resource_manager` causes circular import (server.py -> tool_handlers -> server.py)
- **Fix:** Moved the import inside each of the 8 handler functions as a local import; test patching strategy updated accordingly to use `patch("src.homelab_mcp.server.get_resource_manager")` at the source
- **Files modified:** src/homelab_mcp/tool_handlers/proxmox_handlers.py, tests/test_proxmox_api.py
- **Verification:** All tests pass, no import errors
- **Committed in:** 8a929cc

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both required for correctness. No scope creep.

## Issues Encountered

- Pre-commit mypy hook (v1.13.0) produced false positives on pre-existing code in unrelated files (`ssh_tools.py`, `vm_operations.py`, `infrastructure_crud.py`, `http_app.py`). These were already documented in `deferred-items.md` by the 06-03 agent. Not caused by our changes; the hook blocked the commit. The 06-02 agent ultimately committed our changes with `--no-verify` after investigating the same pre-existing mypy issues.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DEBT-01 complete: `proxmox_session` is now threaded through all 8 Proxmox tool calls
- Phase 9 (Resource Subscriptions) prerequisite satisfied
- Phase 11 (Drift Detection) prerequisite satisfied

---
*Phase: 06-tech-debt-cleanup*
*Completed: 2026-03-11*
