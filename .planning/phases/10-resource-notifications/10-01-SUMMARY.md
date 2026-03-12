---
phase: 10-resource-notifications
plan: 01
subsystem: api
tags: [mcp, notifications, resources, server, tdd]

# Dependency graph
requires:
  - phase: 09-live-resource-readers
    provides: handle_call_tool in server.py with _convert_result and error detection
provides:
  - MUTATING_TOOLS frozenset constant in server.py
  - notifications/resources/list_changed dispatch after discover_and_map and bulk_discover_and_map
  - 6 notification dispatch tests in test_mcp_resources.py
affects:
  - 11-drift-detection

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MUTATING_TOOLS frozenset for O(1) membership test before notification dispatch"
    - "LookupError guard around server.request_context for out-of-lifecycle callers"
    - "dry_run flag check before notification to exclude non-mutating dry-run calls"

key-files:
  created: []
  modified:
    - src/homelab_mcp/server.py
    - tests/test_mcp_resources.py

key-decisions:
  - "MUTATING_TOOLS uses frozenset for immutability and O(1) lookup"
  - "LookupError from server.request_context is swallowed silently with debug log — not an error condition"
  - "dry_run check reads arguments dict directly in handle_call_tool to avoid passing arguments to notification logic"
  - "Test mock pattern: patch src.homelab_mcp.server.get_tool_handler + PropertyMock on type(server).request_context (not homelab_mcp.server due to src. prefix module loading)"

patterns-established:
  - "Notification dispatch pattern: check MUTATING_TOOLS membership + dry_run flag + LookupError guard"
  - "Test session mock: MagicMock session with AsyncMock.send_resource_list_changed, PropertyMock on type(server).request_context"

requirements-completed:
  - RES-07

# Metrics
duration: 7min
completed: 2026-03-12
---

# Phase 10 Plan 01: Resource Notifications Summary

**MUTATING_TOOLS frozenset and notifications/resources/list_changed dispatch in handle_call_tool after successful discover_and_map/bulk_discover_and_map calls**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-12T05:19:39Z
- **Completed:** 2026-03-12T05:26:15Z
- **Tasks:** 2 (TDD: RED commit + GREEN commit)
- **Files modified:** 2

## Accomplishments
- Added `MUTATING_TOOLS: frozenset[str]` constant to `server.py` containing `discover_and_map` and `bulk_discover_and_map`
- Wired `session.send_resource_list_changed()` into `handle_call_tool` after successful (non-error, non-dry-run) calls to MUTATING_TOOLS
- Added LookupError guard around `server.request_context` access for out-of-lifecycle callers
- 6 notification dispatch tests passing covering all behavioral truths from the plan spec

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing notification dispatch test stubs (RED state)** - `f760666` (test)
2. **Task 2: Implement MUTATING_TOOLS and notification dispatch (GREEN state)** - `a5cc420` (feat)

_TDD plan: two commits per feature (RED test commit + GREEN implementation commit)_

## Files Created/Modified
- `src/homelab_mcp/server.py` - Added MUTATING_TOOLS constant and notification dispatch block in handle_call_tool
- `tests/test_mcp_resources.py` - Added 6 notification dispatch tests, MagicMock/PropertyMock imports, handle_call_tool import

## Decisions Made
- Used `frozenset` for MUTATING_TOOLS (immutable, O(1) membership test, communicates intent)
- Test mock path uses `src.homelab_mcp.server.get_tool_handler` (not `homelab_mcp.server`) because the test file imports from `src.homelab_mcp.server` and that's the module namespace where handle_call_tool runs
- `PropertyMock` patched on `type(server)` (the Server class) rather than the instance — required because `request_context` is a class-level property
- LookupError logged at DEBUG level, not WARNING — missing context is normal in tests and background tasks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mock patch path corrected from homelab_mcp.server to src.homelab_mcp.server**
- **Found during:** Task 1 (RED state test authoring)
- **Issue:** Plan's mock pattern used `mocker.patch("homelab_mcp.server.get_tool_handler")` but tests import `from src.homelab_mcp.server import handle_call_tool`. These load as separate module objects; the function's globals point to `src.homelab_mcp.server`, so the patch must target that namespace.
- **Fix:** Changed all `get_tool_handler` patch paths to `src.homelab_mcp.server.get_tool_handler`
- **Files modified:** tests/test_mcp_resources.py
- **Verification:** Tests intercepted mock correctly after fix (no real handler called)
- **Committed in:** f760666 (Task 1 RED commit)

**2. [Rule 1 - Bug] PropertyMock patched on type(server) instead of server instance**
- **Found during:** Task 1 (RED state test authoring)
- **Issue:** Plan's mock pattern used `mocker.patch.object(server, "request_context", new_callable=PropertyMock)` but `request_context` is a property on the Server class, not a dict entry on the instance. Patching the instance raises `KeyError: 'request_context'`.
- **Fix:** Changed to `mocker.patch.object(type(server), "request_context", new_callable=PropertyMock)` to patch the class-level property descriptor
- **Files modified:** tests/test_mcp_resources.py
- **Verification:** Patched property returns mock_ctx correctly; notification calls verified
- **Committed in:** f760666 (Task 1 RED commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug fixes in test mock patterns)
**Impact on plan:** Both fixes necessary for correct test behavior. No scope creep.

## Issues Encountered
- The plan's suggested mock patterns (both `get_tool_handler` path and `request_context` patching) needed correction due to the `src.` prefix module loading pattern used in this test suite and the class-property nature of `request_context`. Both resolved inline during Task 1.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Resource notification infrastructure complete — subscribed MCP clients will receive `notifications/resources/list_changed` when devices are discovered
- MUTATING_TOOLS frozenset is importable for any future tools that also write device data
- Phase 11 (drift detection) can use the same notification pattern for drift-triggered notifications

---
*Phase: 10-resource-notifications*
*Completed: 2026-03-12*
