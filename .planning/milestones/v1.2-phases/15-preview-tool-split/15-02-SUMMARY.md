---
phase: 15-preview-tool-split
plan: "02"
subsystem: api
tags: [mcp, tool-registry, preview-tools, dry-run, annotations]

# Dependency graph
requires:
  - phase: 15-01
    provides: Wave 0 RED tests for all 6 preview tool variants (test_preview_tools.py)
provides:
  - 6 *_preview tool schemas (no dry_run param) in 5 schema files
  - 6 *_preview delegation handlers in 5 handler modules
  - All 6 preview handlers registered in TOOL_HANDLERS dict
  - All 6 preview names in _READ_ONLY_TOOLS annotation list
  - 56 total tools with full schema/annotation parity
affects:
  - server.py (tools/list now returns 56 tools including all 6 preview variants)
  - any MCP client consuming tools/list

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Preview handler delegation pattern — handle_*_preview({**arguments, "dry_run": True}) transparently injects dry_run without exposing it in the schema
    - Schema co-location — preview schema appended outside dict literal immediately after parent tool dict via dict assignment syntax

key-files:
  created: []
  modified:
    - src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py
    - src/homelab_mcp/tool_schemas/vm_tools_schema.py
    - src/homelab_mcp/tool_schemas/credential_tools_schema.py
    - src/homelab_mcp/tool_schemas/proxmox_tools_schema.py
    - src/homelab_mcp/tool_schemas/service_tools_schema.py
    - src/homelab_mcp/tool_handlers/infrastructure_handlers.py
    - src/homelab_mcp/tool_handlers/vm_handlers.py
    - src/homelab_mcp/tool_handlers/credential_handlers.py
    - src/homelab_mcp/tool_handlers/proxmox_handlers.py
    - src/homelab_mcp/tool_handlers/service_handlers.py
    - src/homelab_mcp/tool_handlers/__init__.py
    - src/homelab_mcp/tool_annotations.py

key-decisions:
  - "Preview handlers inject dry_run=True transparently — callers never set it and schemas never expose it"
  - "Delegation pattern keeps preview handler logic to 3 lines; all dry-run logic lives in the parent handler"
  - "Preview tools annotated as readOnlyHint=True, destructiveHint=False — distinct from parent destructive tools"

patterns-established:
  - "Preview handler delegation: async def handle_foo_preview(arguments) -> dict: return await handle_foo({**arguments, 'dry_run': True})"
  - "Schema extension outside dict literal: TOOL_DICT['foo_preview'] = {...} appended after closing brace"

requirements-completed: [PREV-01, PREV-02, PREV-03, PREV-04, PREV-05, PREV-06, PREV-07, PREV-08]

# Metrics
duration: 4min
completed: 2026-03-13
---

# Phase 15 Plan 02: Preview Tool Split — Implementation Summary

**6 *_preview tool variants added with readOnlyHint=True annotation, delegation to parent handler with dry_run=True injected, and no dry_run exposed in preview schemas — 56 tools total**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-13T21:40:36Z
- **Completed:** 2026-03-13T21:44:32Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Added 6 preview tool schemas across 5 schema files with no dry_run parameter exposed
- Added 6 delegation handler functions in 5 handler modules using {**arguments, "dry_run": True} pattern
- Registered all 6 preview handlers in TOOL_HANDLERS and added all 6 to _READ_ONLY_TOOLS annotations
- All 9 preview tests went GREEN, annotation parity test (56 == 56) GREEN, full 603-test unit suite GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 6 preview schemas to 5 schema files** - `ad0fdec` (feat)
2. **Task 2: Add 6 preview handlers + register in __init__.py + update annotations** - `d603af6` (feat)

## Files Created/Modified

- `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py` - Added decommission_device_preview and rollback_infrastructure_changes_preview schemas
- `src/homelab_mcp/tool_schemas/vm_tools_schema.py` - Added remove_vm_preview schema
- `src/homelab_mcp/tool_schemas/credential_tools_schema.py` - Added remove_server_preview schema
- `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` - Added delete_proxmox_vm_preview schema
- `src/homelab_mcp/tool_schemas/service_tools_schema.py` - Added destroy_terraform_service_preview schema
- `src/homelab_mcp/tool_handlers/infrastructure_handlers.py` - Added handle_decommission_device_preview and handle_rollback_infrastructure_changes_preview
- `src/homelab_mcp/tool_handlers/vm_handlers.py` - Added handle_remove_vm_preview
- `src/homelab_mcp/tool_handlers/credential_handlers.py` - Added handle_remove_server_preview
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py` - Added handle_delete_proxmox_vm_preview
- `src/homelab_mcp/tool_handlers/service_handlers.py` - Added handle_destroy_terraform_service_preview
- `src/homelab_mcp/tool_handlers/__init__.py` - Added 6 preview imports and 6 TOOL_HANDLERS entries
- `src/homelab_mcp/tool_annotations.py` - Added 6 preview names to _READ_ONLY_TOOLS, updated docstring to 56

## Decisions Made

- Delegation pattern keeps preview handler logic minimal — all real logic lives in parent handler's dry_run branch
- Schemas exclude dry_run so MCP clients cannot accidentally pass it; the handler always injects it as True

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 15 now complete: 56 tools with full schema/annotation/handler parity
- All 6 original destructive tools unchanged with their dry_run parameter intact
- Preview tools return structured dry-run reports without modifying infrastructure
- No blockers for subsequent phases

## Self-Check

- `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py` contains decommission_device_preview: FOUND
- `src/homelab_mcp/tool_handlers/__init__.py` contains handle_decommission_device_preview: FOUND
- Commits ad0fdec and d603af6 verified in git log

## Self-Check: PASSED

---
*Phase: 15-preview-tool-split*
*Completed: 2026-03-13*
