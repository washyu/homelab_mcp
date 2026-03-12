---
phase: 11-drift-detection
plan: "05"
subsystem: drift-detection
tags: [drift, mcp-wiring, tool-registry, proxmox-handlers, tdd]
dependency_graph:
  requires: [11-04]
  provides: [scan_infrastructure_drift-tool, baseline-mutation-hooks]
  affects: [tool_schemas, tool_handlers, tool_annotations, proxmox_handlers]
tech_stack:
  added: []
  patterns: [local-inline-import, try-except-swallow-baseline-error]
key_files:
  created:
    - src/homelab_mcp/tool_schemas/drift_tools_schema.py
    - src/homelab_mcp/tool_handlers/drift_handlers.py
    - tests/test_drift_wiring.py
    - tests/test_proxmox_baseline_hooks.py
  modified:
    - src/homelab_mcp/tool_schemas/__init__.py
    - src/homelab_mcp/tool_handlers/__init__.py
    - src/homelab_mcp/tool_annotations.py
    - src/homelab_mcp/tool_handlers/proxmox_handlers.py
    - tests/test_tools.py
decisions:
  - "Local inline import of update_baseline_after_mutation inside each handler to avoid circular import risk"
  - "Try/except wraps baseline update calls so handler always returns result even if baseline fails"
  - "scan_infrastructure_drift added to _READ_ONLY_TOOLS (readOnlyHint=True, destructiveHint=False)"
  - "test_tools.py tool count bumped from 49 to 50 after adding scan_infrastructure_drift"
metrics:
  duration: "~9 minutes"
  completed: "2026-03-12"
  tasks_completed: 2
  files_modified: 9
---

# Phase 11 Plan 05: MCP Server Wiring for Drift Detection Summary

**One-liner:** Wired scan_infrastructure_drift tool into MCP registries and hooked update_baseline_after_mutation into proxmox VM create/clone handlers with error-swallowing guards.

## What Was Built

### Task 1: Schema, Handler, and Annotation Registration

Created `drift_tools_schema.py` with the `DRIFT_TOOLS` dict containing the `scan_infrastructure_drift` schema (node + vm_type parameters). Merged it into `get_all_tool_schemas()` via `**DRIFT_TOOLS`. Created `drift_handlers.py` with `handle_scan_infrastructure_drift` that calls `scan_drift()` via lazy-loaded `get_resource_manager()`. Registered handler in `TOOL_HANDLERS`. Added `scan_infrastructure_drift` to `_READ_ONLY_TOOLS` in `tool_annotations.py`.

### Task 2: Baseline Mutation Hooks in Proxmox Handlers

Added `update_baseline_after_mutation` call after success check in `handle_create_proxmox_vm` (vm_type=qemu), `handle_create_proxmox_lxc` (vm_type=lxc), and `handle_clone_proxmox_vm` (vmid=new_vmid, vm_type from args). Each hook is wrapped in try/except so baseline failures are logged at DEBUG level and swallowed — the original result is always returned to the caller.

## Verification

- `scan_infrastructure_drift` in `get_all_tool_schemas()` result
- `scan_infrastructure_drift` in `TOOL_HANDLERS`
- `TOOL_ANNOTATIONS['scan_infrastructure_drift'].readOnlyHint == True`
- All three proxmox handlers call `update_baseline_after_mutation` on `status == "success"`
- `uv run pytest tests/ -m "not integration"` — 578 passed, 7 skipped, 29 deselected
- mypy clean on modified files
- ruff clean on all modified files

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_tools.py hardcoded tool count 49 now stale**
- **Found during:** Task 1 (full suite run)
- **Issue:** `test_get_available_tools` asserts `len(tools) == 49`; adding `scan_infrastructure_drift` made it 50
- **Fix:** Updated assertion to `len(tools) == 50` with updated comment
- **Files modified:** `tests/test_tools.py`
- **Commit:** 429299e

**2. [Rule 3 - Blocking] logger placement caused ruff E402**
- **Found during:** Task 2 (pre-commit hook)
- **Issue:** `logger = logging.getLogger(__name__)` placed between stdlib imports and relative imports, triggering E402 (module level import not at top of file)
- **Fix:** Moved logger assignment after all import statements
- **Files modified:** `src/homelab_mcp/tool_handlers/proxmox_handlers.py`
- **Commit:** 429299e

**3. [Rule 2 - Safety] Baseline call needs explicit error guard**
- **Found during:** Task 2 (test writing)
- **Issue:** Plan says "update_baseline_after_mutation handles errors internally" but test simulates an unexpected exception escaping — handler must still return result
- **Fix:** Wrapped each baseline call in try/except with DEBUG log; test `test_result_returned_even_if_baseline_fails` verifies this
- **Files modified:** `src/homelab_mcp/tool_handlers/proxmox_handlers.py`

## Self-Check

Checking created files exist:
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/tool_schemas/drift_tools_schema.py` — FOUND
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/tool_handlers/drift_handlers.py` — FOUND
- `/home/shaun/projects/mcp_python_server/tests/test_drift_wiring.py` — FOUND
- `/home/shaun/projects/mcp_python_server/tests/test_proxmox_baseline_hooks.py` — FOUND

Checking commits exist:
- `75e97ff` feat(11-05): wire scan_infrastructure_drift into MCP tool registries — FOUND
- `429299e` feat(11-05): hook update_baseline_after_mutation into proxmox create/clone handlers — FOUND

## Self-Check: PASSED
