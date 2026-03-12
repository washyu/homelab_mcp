---
phase: 09-mcp-resources-live-data
plan: "01"
subsystem: resource_readers
tags:
  - mcp-resources
  - proxmox
  - database
  - service-installer
  - tdd
dependency_graph:
  requires:
    - Phase 07: ResourceManager and server.py lifespan plumbing
    - Phase 06: proxmox_session wiring in ResourceManager
  provides:
    - resource_readers.read_vms_resource (live Proxmox data)
    - resource_readers.read_devices_resource (enriched DB device list)
    - resource_readers.read_service_resource (SSH service status)
  affects:
    - Plan 09-02: server.py resource dispatch wiring will import from this module
tech_stack:
  added: []
  patterns:
    - Graceful error payload pattern (no exceptions propagate from reader functions)
    - last_discovery_data enrichment by joining device rows with change history
    - Module-level import of get_resource_manager avoids circular imports while remaining patchable in tests
key_files:
  created:
    - src/homelab_mcp/resource_readers.py
    - tests/test_resource_readers.py
  modified: []
decisions:
  - "Module-level import of get_resource_manager (not local/deferred) is safe because server.py does not import resource_readers — no circular import cycle exists. Tests patch at homelab_mcp.resource_readers.get_resource_manager."
  - "datetime.now(UTC) used instead of datetime.now(timezone.utc) per ruff UP017 rule for Python 3.11+ compatibility"
metrics:
  duration_seconds: 228
  completed_date: "2026-03-12"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
---

# Phase 09 Plan 01: resource_readers Module Summary

**One-liner:** Isolated async readers for Proxmox VMs, DB devices with discovery history, and SSH service status — all returning graceful error payloads.

## What Was Built

`src/homelab_mcp/resource_readers.py` — a new module with three async functions that fetch live data for MCP Resource URIs:

- **`read_vms_resource()`** — calls `list_proxmox_resources(session=rm.proxmox_session)`, returns `{"vms": [...], "total": N, "scanned_at": "...", "providers": ["proxmox"]}`. Returns `config_error` key when PROXMOX_HOST is not set (ValueError), and `error` key when ResourceManager is unavailable (RuntimeError).

- **`read_devices_resource()`** — fetches all DB device rows and enriches each with `last_discovery_data` from `get_device_changes(device_id, limit=1)`. Returns `None` for the field if no history exists.

- **`read_service_resource(service_name)`** — resolves hostname from `MCP_DEFAULT_SERVICE_HOST` env var or first DB device with `connection_ip`/`hostname`, then calls `ServiceInstaller().get_service_status()`. Injects `scanned_at` into the returned status dict. Returns `unconfigured` status when no hostname can be resolved.

`tests/test_resource_readers.py` — 9 test functions covering all success, error, and edge cases.

## TDD Execution

**RED commit:** `fc592b7` — 9 failing tests (module did not exist)
**GREEN commit:** `70824bc` — implementation passes all 9 tests
**REFACTOR:** No refactoring required

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level import instead of local function-body import**
- **Found during:** GREEN phase — tests patch `homelab_mcp.resource_readers.get_resource_manager` at module level, which requires the name to be bound in the module's namespace
- **Issue:** Plan specified local import inside function body to avoid circular imports. This makes the name unpatchable at `homelab_mcp.resource_readers.get_resource_manager`
- **Fix:** Moved `from .server import get_resource_manager` to module level. Verified no circular import exists: server.py imports from resource_manager, config, log_filter, progress, tool_handlers, tool_schemas — not from resource_readers
- **Files modified:** src/homelab_mcp/resource_readers.py

**2. [Rule 1 - Bug] ruff UP017 — datetime.UTC alias**
- **Found during:** Pre-commit ruff lint check
- **Issue:** `timezone.utc` should be `UTC` (Python 3.11+ alias, ruff UP017)
- **Fix:** Auto-fixed by `ruff check --fix`; changed import from `from datetime import datetime, timezone` to `from datetime import UTC, datetime`
- **Files modified:** src/homelab_mcp/resource_readers.py

## Verification

```
9/9 tests pass in tests/test_resource_readers.py
533 passed, 7 skipped in full unit test suite (no regressions)
ruff check: 0 errors
mypy: Success: no issues found
```

## Self-Check: PASSED
- `src/homelab_mcp/resource_readers.py`: FOUND
- `tests/test_resource_readers.py`: FOUND
- RED commit `fc592b7`: FOUND
- GREEN commit `70824bc`: FOUND
