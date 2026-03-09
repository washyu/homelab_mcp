---
phase: 01-architecture-foundation
plan: 02
subsystem: infra
tags: [mcp-sdk, lowlevel-server, stdio, streamable-http, starlette]

# Dependency graph
requires:
  - phase: 01-01
    provides: ResourceManager class with initialize/shutdown lifecycle
provides:
  - MCP SDK lowlevel.Server with list_tools and call_tool handlers
  - StreamableHTTPSessionManager-based HTTP transport on /mcp
  - Stdio transport via mcp.server.stdio.stdio_server()
  - Result conversion adapter from legacy dict format to SDK types
  - Module-level get_resource_manager() accessor
affects: [01-03, 02-security, 03-functional]

# Tech tracking
tech-stack:
  added: [mcp.server.lowlevel.Server, mcp.server.streamable_http_manager.StreamableHTTPSessionManager]
  patterns: [sdk-decorator-handlers, lifespan-context-manager, result-adapter-pattern]

key-files:
  created:
    - src/homelab_mcp/http_app.py
  modified:
    - src/homelab_mcp/server.py
    - run_server.py
    - tests/test_server.py
    - tests/test_http_transport.py
    - src/homelab_mcp/http_transport.py

key-decisions:
  - "Used lowlevel.Server (not FastMCP) per CONTEXT.md decision for maximum control"
  - "Module-level _resource_manager with get_resource_manager() accessor avoids threading request_context through every handler"
  - "Result adapter pattern converts legacy handler dicts to SDK content types without touching handler code"

patterns-established:
  - "SDK handler pattern: @server.list_tools() and @server.call_tool() decorators on module functions"
  - "Result adapter: _convert_result() normalizes legacy {content: [{type, text}]} to types.TextContent/ImageContent"
  - "Starlette + MCP composition: Mount('/mcp') for SDK, regular Routes for /health, /shell"

requirements-completed: [ARCH-01]

# Metrics
duration: 4min
completed: 2026-03-09
---

# Phase 1 Plan 2: MCP SDK Server Migration Summary

**Replaced hand-rolled JSON-RPC HomelabMCPServer with MCP SDK lowlevel.Server using list_tools/call_tool decorators, stdio and StreamableHTTP transports**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-09T05:35:43Z
- **Completed:** 2026-03-09T05:39:53Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Server.py fully rewritten: 312 lines of hand-rolled JSON-RPC replaced with 127 lines of SDK-based code
- Both transports working: stdio via stdio_server(), HTTP via StreamableHTTPSessionManager
- 16 new server tests all passing, 356 total unit tests pass with zero regressions
- ResourceManager wired through SDK lifespan with module-level accessor

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite server.py with MCP SDK lowlevel.Server** - `111c8ea` (feat)
2. **Task 2: Create http_app.py and update run_server.py** - `fb8c51a` (feat)
3. **Task 3: Rewrite test_server.py for SDK-based server** - `3c7b560` (feat)

## Files Created/Modified
- `src/homelab_mcp/server.py` - MCP SDK lowlevel.Server with lifespan, list_tools, call_tool handlers
- `src/homelab_mcp/http_app.py` - Starlette app composing MCP SDK HTTP transport with custom routes
- `run_server.py` - Entry point selecting stdio or HTTP mode using SDK transports
- `tests/test_server.py` - 16 tests for SDK-based server (tool listing, calling, conversion, lifespan)
- `tests/test_http_transport.py` - Updated to use new http_app module instead of old HomelabMCPServer
- `src/homelab_mcp/http_transport.py` - Marked as deprecated (retained for reference)

## Decisions Made
- Used lowlevel.Server per existing CONTEXT.md decision -- @server.list_tools() and @server.call_tool() decorators satisfy the "decorator-based" intent
- Module-level _resource_manager reference set during lifespan avoids every handler needing to thread through request_context
- Result adapter pattern in _convert_result() means existing tool handlers need zero changes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated test_http_transport.py to remove HomelabMCPServer import**
- **Found during:** Task 3 (running full test suite)
- **Issue:** test_http_transport.py imported HomelabMCPServer which no longer exists, causing ImportError
- **Fix:** Rewrote test fixtures to use create_http_app() from new http_app module, removed old MCPHTTPTransport tests
- **Files modified:** tests/test_http_transport.py
- **Verification:** Full test suite passes (356 passed)
- **Committed in:** 3c7b560 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix -- existing test file referenced removed class. No scope creep.

## Issues Encountered
- `uv run python` returns exit code 120 silently in this environment; used `.venv/bin/python` directly as workaround

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SDK server ready for Plan 03 (handler wiring to use ResourceManager)
- All 49 tool handlers still use legacy dispatch; Plan 03 will wire them through ResourceManager
- HTTP transport is functional but auth middleware (APIKeyAuth) not yet integrated with new app

---
*Phase: 01-architecture-foundation*
*Completed: 2026-03-09*
