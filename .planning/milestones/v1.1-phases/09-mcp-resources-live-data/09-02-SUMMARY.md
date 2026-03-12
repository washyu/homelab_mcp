---
phase: 09-mcp-resources-live-data
plan: "02"
subsystem: server_resource_dispatch
tags:
  - mcp-resources
  - live-dispatch
  - circular-import-fix
  - tdd
dependency_graph:
  requires:
    - Phase 09 Plan 01: resource_readers module (read_vms_resource, read_devices_resource, read_service_resource)
    - Phase 07: server.py MCP resource scaffolding (HOMELAB_RESOURCES, handle_read_resource stub)
  provides:
    - server.handle_read_resource live dispatch to resource_readers functions
    - homelab://services/{name} template URI dispatch via read_service_resource
    - homelab://services/ (empty name) raises McpError -32002
    - Four new tests covering live dispatch, template URI, and error cases
  affects:
    - tests/test_resource_readers.py: patch paths updated from resource_readers to server namespace
tech_stack:
  added: []
  patterns:
    - Deferred/local import of get_resource_manager in resource_readers.py to break circular import
    - URI prefix matching (startswith) before HOMELAB_RESOURCES membership check
    - McpError re-raise pattern (except McpError: raise) for clean error propagation
    - Exception catch-all returns error payload with scanned_at (no uncaught exceptions from handler)
key_files:
  created: []
  modified:
    - src/homelab_mcp/server.py
    - src/homelab_mcp/resource_readers.py
    - tests/test_mcp_resources.py
    - tests/test_resource_readers.py
decisions:
  - "Deferred/local import of get_resource_manager inside each reader function in resource_readers.py to break circular import: server.py now imports resource_readers at module level, which would create a cycle with the existing module-level import of get_resource_manager from server. Local imports execute at call time when both modules are fully loaded."
  - "test_resource_readers.py patch paths updated from homelab_mcp.resource_readers.get_resource_manager to homelab_mcp.server.get_resource_manager since get_resource_manager is now imported locally (no module-level name in resource_readers namespace to patch)."
  - "HOMELAB_RESOURCES stub keys removed: stubs are no longer needed since all reads go through live reader functions. Metadata (name, description) retained for handle_list_resources."
  - "datetime.UTC alias used per ruff UP017 rule (Python 3.11+ standard, consistent with resource_readers.py)"
metrics:
  duration_seconds: 333
  completed_date: "2026-03-12"
  tasks_completed: 2
  files_created: 0
  files_modified: 4
---

# Phase 09 Plan 02: Live Resource Dispatch Summary

**One-liner:** Wired handle_read_resource to live reader functions with URI-based dispatch, breaking circular import via deferred get_resource_manager imports and adding four new dispatch tests.

## What Was Built

**`src/homelab_mcp/server.py`** — `handle_read_resource` replaced:
- Old: looked up URI in HOMELAB_RESOURCES, returned `meta["stub"]` as JSON
- New: dispatches based on URI string:
  - `homelab://vms` → `await read_vms_resource()`
  - `homelab://devices` → `await read_devices_resource()`
  - `homelab://services/{name}` → `await read_service_resource(name)`
  - `homelab://services/` (empty name) → McpError -32002 "Service name required"
  - `homelab://services` (bare, in HOMELAB_RESOURCES) → helpful note payload
  - unknown URI → McpError -32002 "Resource not found"
  - Non-McpError exceptions → caught, returned as `{"error": ..., "scanned_at": ...}`
- HOMELAB_RESOURCES entries: `stub` key removed from all three entries
- New imports: `read_vms_resource`, `read_devices_resource`, `read_service_resource`, `sanitize_error`, `UTC`, `datetime`

**`src/homelab_mcp/resource_readers.py`** — circular import fix:
- Removed module-level `from .server import get_resource_manager`
- Added deferred `from .server import get_resource_manager` inside each of the three reader functions
- No behavior change — only import timing changes

**`tests/test_mcp_resources.py`** — four new tests:
- `test_read_vms_resource_has_scanned_at`: patches `homelab_mcp.server.read_vms_resource`, verifies `scanned_at` in parsed response
- `test_read_devices_resource_has_scanned_at`: same pattern for devices
- `test_read_services_template_uri`: patches `homelab_mcp.server.read_service_resource`, verifies service field for `homelab://services/nginx`
- `test_read_services_empty_name_error`: verifies McpError with code -32002 for `homelab://services/`

**`tests/test_resource_readers.py`** — patch path update:
- All 9 tests updated: `homelab_mcp.resource_readers.get_resource_manager` → `homelab_mcp.server.get_resource_manager`

## TDD Execution

**Task 1 (server.py):**
- RED: New tests failed with `AttributeError: module 'homelab_mcp.server' does not have the attribute 'read_vms_resource'`
- GREEN: Implemented dispatch; discovered circular import (server imports resource_readers, resource_readers imports server). Fixed by making get_resource_manager a local deferred import in resource_readers.py. Updated test_resource_readers.py patch paths.
- REFACTOR: Fixed UP017 ruff violation (timezone.utc → UTC alias)

**Task 2 (tests):**
- Tests written first (RED), then implementation made them pass (GREEN)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Circular import between server.py and resource_readers.py**
- **Found during:** GREEN phase of Task 1 — `ImportError: cannot import name 'get_resource_manager' from partially initialized module 'src.homelab_mcp.server'`
- **Issue:** Plan 01 assumed server.py would never import resource_readers (correct at Plan 01 time). Plan 02 adds that import, creating a circular dependency.
- **Fix:** Changed `from .server import get_resource_manager` in resource_readers.py from module-level to a local deferred import inside each reader function. Updated test_resource_readers.py to patch at `homelab_mcp.server.get_resource_manager` (where the function actually lives) instead of `homelab_mcp.resource_readers.get_resource_manager` (which no longer holds the name).
- **Files modified:** `src/homelab_mcp/resource_readers.py`, `tests/test_resource_readers.py`
- **Commits:** 895acd5, fffffb9

**2. [Rule 1 - Bug] ruff UP017 - datetime.UTC alias**
- **Found during:** Pre-commit hook
- **Issue:** `timezone.utc` used in server.py dispatch code; ruff UP017 requires `UTC` alias (Python 3.11+)
- **Fix:** Changed import from `from datetime import datetime, timezone` to `from datetime import UTC, datetime`; replaced `timezone.utc` with `UTC` in two places
- **Files modified:** `src/homelab_mcp/server.py`
- **Commit:** 895acd5

## Verification

```
25/25 tests pass in test_mcp_resources.py + test_resource_readers.py
537 passed, 7 skipped in full unit suite (no regressions)
mypy: Success: no issues found in 2 source files
ruff: All checks passed!
```

## Self-Check: PASSED
- `src/homelab_mcp/server.py`: FOUND
- `src/homelab_mcp/resource_readers.py`: FOUND
- `tests/test_mcp_resources.py`: FOUND
- `tests/test_resource_readers.py`: FOUND
- Task 1 commit `895acd5`: FOUND
- Task 2 commit `fffffb9`: FOUND
