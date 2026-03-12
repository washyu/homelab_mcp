---
phase: 08-dry-run-mode
plan: "04"
subsystem: infra
tags: [dry-run, proxmox, terraform, mcp, type-checking, pre-commit]

# Dependency graph
requires:
  - phase: 08-01
    provides: build_dry_run_response() DRY-07 contract builder

provides:
  - dry_run interception in handle_delete_proxmox_vm (calls get_proxmox_vm_status for preview)
  - dry_run interception in handle_destroy_terraform_service (calls plan_terraform_service for preview)
  - dry_run optional boolean in delete_proxmox_vm schema
  - dry_run optional boolean in destroy_terraform_service schema

affects: [09-advanced-proxmox, 11-drift-detection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - dry_run interception before destructive operation using arguments.get("dry_run", False)
    - filter dry_run from args before passing to installer/api via dict comprehension
    - return raw build_dry_run_response() dict (not content-wrapped) from dry-run path
    - patch get_proxmox_vm_status directly in proxmox_handlers module for dry-run tests
    - patch plan_terraform_service as AsyncMock alongside destroy mock in service handler tests

key-files:
  created: []
  modified:
    - src/homelab_mcp/tool_handlers/proxmox_handlers.py
    - src/homelab_mcp/tool_handlers/service_handlers.py
    - src/homelab_mcp/tool_schemas/proxmox_tools_schema.py
    - src/homelab_mcp/tool_schemas/service_tools_schema.py
    - tests/test_dry_run.py
    - .pre-commit-config.yaml
    - src/homelab_mcp/http_app.py

key-decisions:
  - "dry-run path in handle_delete_proxmox_vm calls get_proxmox_vm_status (read-only) not delete_proxmox_vm"
  - "dry-run path in handle_destroy_terraform_service calls plan_terraform_service and returns would_affect=[] if plan errors"
  - "pre-commit mirrors-mypy updated from v1.13.0 to v1.18.1 with asyncssh/aiohttp stubs to resolve mypy version conflict; v1.13-v1.16 incorrectly flagged valid type:ignore[return] as unused"
  - "http_app.py fallback import type:ignore removed as redundant with mypy 1.18.1 + proper stubs"

patterns-established:
  - "Wave 2 dry-run pattern: intercept at handler level, call read-only API for preview, strip dry_run from args before real execution"
  - "Test setup for dry-run with async dependencies: set plan_terraform_service as AsyncMock alongside destroy mock"

requirements-completed: [DRY-04, DRY-05]

# Metrics
duration: 25min
completed: 2026-03-12
---

# Phase 08 Plan 04: Dry-Run for delete_proxmox_vm and destroy_terraform_service Summary

**Dry-run interception for delete_proxmox_vm (using get_proxmox_vm_status preview) and destroy_terraform_service (using plan_terraform_service preview), with pre-commit mypy upgraded to v1.18.1 to resolve version conflict blocking commits**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-12T01:25:00Z
- **Completed:** 2026-03-12T01:50:13Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- `delete_proxmox_vm` schema and handler now support optional `dry_run` boolean
- `destroy_terraform_service` schema and handler now support optional `dry_run` boolean
- All 6 new tests (TestDeleteProxmoxVmDryRun x3, TestDestroyTerraformServiceDryRun x3) pass GREEN
- 18/22 tests in test_dry_run.py pass (remaining 4 are intentional RED stubs for future plans DRY-01 and DRY-06)
- Pre-commit mypy version conflict resolved: upgraded from v1.13.0 to v1.18.1 with asyncssh/aiohttp stubs

## Task Commits

1. **Task 1: Schema extensions** - `37853e8` (feat)
2. **Task 2: Handler dry-run interception** - `3626809` (feat)

## Files Created/Modified
- `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` - Added dry_run optional boolean to delete_proxmox_vm schema
- `src/homelab_mcp/tool_schemas/service_tools_schema.py` - Added dry_run optional boolean to destroy_terraform_service schema
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py` - Added dry_run interception: calls get_proxmox_vm_status for preview, skips delete_proxmox_vm
- `src/homelab_mcp/tool_handlers/service_handlers.py` - Added dry_run interception: calls plan_terraform_service for preview, skips destroy_terraform_service
- `tests/test_dry_run.py` - Updated TestDeleteProxmoxVmDryRun to mock get_proxmox_vm_status and get_resource_manager; updated TestDestroyTerraformServiceDryRun to set plan_terraform_service as AsyncMock
- `.pre-commit-config.yaml` - Upgraded mirrors-mypy from v1.13.0 to v1.18.1, added asyncssh/aiohttp to additional_dependencies
- `src/homelab_mcp/http_app.py` - Removed now-unnecessary type:ignore comment on fallback import (redundant with proper stubs)

## Decisions Made
- dry-run path in `handle_delete_proxmox_vm` calls `get_proxmox_vm_status` (read-only Proxmox GET) for preview data; real `delete_proxmox_vm` (which stops then deletes) is never called
- dry-run path in `handle_destroy_terraform_service` calls `plan_terraform_service` for terraform plan preview; `would_affect=[]` when plan errors or has no plan_output (Terraform dir absent)
- pre-commit mirrors-mypy v1.13-v1.16 incorrectly flagged `# type: ignore[return]` as "unused" for async-with patterns where asyncssh stubs weren't installed; upgrading to v1.18.1 with stubs resolves this without touching any source files
- Test stubs from 08-01 needed updates: proxmox dry-run tests required `get_proxmox_vm_status` mock; terraform dry-run tests required `plan_terraform_service` as `AsyncMock`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-commit mypy version conflict blocking all commits**
- **Found during:** Task 1 (schema extensions commit)
- **Issue:** pre-commit used mirrors-mypy v1.13.0 which flagged valid `# type: ignore[return]` and `# type: ignore[no-redef, attr-defined]` as "unused" in 5 source files; these were pre-existing annotations that v1.18.x handles correctly with asyncssh stubs
- **Fix:** Updated .pre-commit-config.yaml to use mirrors-mypy v1.18.1 and added asyncssh>=2.14.0 and aiohttp>=3.9.0 to additional_dependencies; removed now-redundant type:ignore from http_app.py
- **Files modified:** .pre-commit-config.yaml, src/homelab_mcp/http_app.py
- **Verification:** pre-commit hook passes: mypy type check passed
- **Committed in:** 37853e8 (Task 1 commit)

**2. [Rule 1 - Bug] Test stubs lacked proper async mocks for dependencies**
- **Found during:** Task 2 (handler implementation)
- **Issue:** TestDeleteProxmoxVmDryRun dry-run tests didn't mock get_proxmox_vm_status or get_resource_manager, causing RuntimeError; TestDestroyTerraformServiceDryRun tests didn't set plan_terraform_service as AsyncMock, causing TypeError on await
- **Fix:** Added @patch for get_proxmox_vm_status and get_resource_manager in proxmox dry-run tests; added AsyncMock for plan_terraform_service in terraform dry-run tests
- **Files modified:** tests/test_dry_run.py
- **Verification:** All 6 target tests pass GREEN
- **Committed in:** 3626809 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking pre-commit issue, 1 test stub bug)
**Impact on plan:** Both fixes necessary to unblock commits and make tests runnable. No scope creep.

## Issues Encountered
- mypy version conflict: mirrors-mypy v1.13-v1.16 has stricter `warn_unused_ignores` behavior that flags comments valid in v1.18+ with proper asyncssh stubs. Root cause: without asyncssh in pre-commit env, asyncssh types are `Any`, causing different mypy flow analysis. Solution: upgrade mypy version AND install stubs.

## Next Phase Readiness
- DRY-04 and DRY-05 requirements complete; delete_proxmox_vm and destroy_terraform_service have dry-run support
- Remaining in Phase 08: DRY-01 (decommission_device) and DRY-06 (rollback_infrastructure) still RED stubs
- Phase 08 nearly complete; remaining tools need dry-run in next plan

---
*Phase: 08-dry-run-mode*
*Completed: 2026-03-12*
