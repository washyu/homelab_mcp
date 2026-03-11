---
phase: 03-functional-completeness
plan: 03
subsystem: api
tags: [mcp, annotations, tool-metadata, error-handling, isError]

# Dependency graph
requires:
  - phase: 01-architecture-foundation
    provides: lowlevel.Server with handle_list_tools and handle_call_tool
provides:
  - TOOL_ANNOTATIONS dict mapping all 49 tools to ToolAnnotations
  - get_tool_annotations() function for annotation lookup
  - ToolError exception class for error result signaling
  - _is_error_result() and _extract_error_text() helpers
affects: [04-protocol-transport]

# Tech tracking
tech-stack:
  added: []
  patterns: [error-dict-to-exception conversion via ToolError, tool annotation registry]

key-files:
  created: [src/homelab_mcp/tool_annotations.py]
  modified: [src/homelab_mcp/server.py, tests/test_server.py]

key-decisions:
  - "Shared ToolAnnotations instances for read-only and destructive categories reduce memory and ensure consistency"
  - "ToolError exception pattern leverages SDK call_tool decorator auto-isError behavior rather than modifying return types"
  - "Nested JSON error detection handles both direct error dicts and content-wrapped error responses"

patterns-established:
  - "Tool annotation registry: centralized TOOL_ANNOTATIONS dict with get_tool_annotations() lookup"
  - "Error result conversion: _is_error_result() detects error patterns, ToolError propagates to SDK for isError=True"

requirements-completed: [MCP-01, MCP-02]

# Metrics
duration: 4min
completed: 2026-03-09
---

# Phase 3 Plan 03: MCP Tool Annotations and isError Summary

**ToolAnnotations on all 49 tools with readOnlyHint/destructiveHint/idempotentHint, plus ToolError-based isError detection for error results**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-09T18:02:15Z
- **Completed:** 2026-03-09T18:06:35Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- All 49 tools now have MCP ToolAnnotations with readOnlyHint, destructiveHint, and idempotentHint set -- MCP clients can distinguish safe from dangerous operations
- handle_call_tool detects error results (direct and nested JSON patterns) and raises ToolError, causing the SDK to set isError=True in CallToolResult
- 8 new tests covering annotation completeness, consistency invariants, and isError behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tool_annotations.py and wire annotations** - `4a3ae8c` (test) + `2445eff` (feat)
2. **Task 2: Add isError detection to handle_call_tool** - `e68fc63` (test) + `a7577a3` (feat)

_Note: TDD tasks have two commits each (RED: failing test, GREEN: implementation)_

## Files Created/Modified
- `src/homelab_mcp/tool_annotations.py` - TOOL_ANNOTATIONS dict mapping 49 tools to ToolAnnotations (21 read-only, 22 mutating, 6 destructive)
- `src/homelab_mcp/server.py` - Added ToolError, _is_error_result(), _extract_error_text(), wired annotations into handle_list_tools
- `tests/test_server.py` - 8 new tests for annotations (4) and isError detection (4)

## Decisions Made
- Shared ToolAnnotations instances for read-only and destructive categories -- reduces object count from 49 to ~25 unique instances
- ToolError exception approach leverages SDK decorator's built-in isError=True on exception, avoiding custom CallToolResult construction
- Nested JSON error detection catches both {"status": "error"} and {"content": [{"text": '{"status": "error"}'}]} patterns

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing test failure in test_service_installer.py::TestInstallScriptServiceDirect::test_install_script_success -- confirmed pre-existing (fails on clean stash), not related to this plan's changes. Out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- MCP-01 (tool annotations) and MCP-02 (isError signaling) now complete
- Ready for Phase 4 protocol/transport work

---
*Phase: 03-functional-completeness*
*Completed: 2026-03-09*
