---
phase: 04-mcp-protocol-compliance
plan: 02
subsystem: security
tags: [origin-validation, dns-rebinding, starlette-middleware, http-security]

requires:
  - phase: 01-architecture-foundation
    provides: Starlette HTTP app with middleware stack (http_app.py)
provides:
  - OriginValidationMiddleware for DNS rebinding protection
  - Default localhost-only binding for HTTP transport
  - MCP_ALLOWED_ORIGINS env var for custom origin configuration
affects: [deployment, http-transport]

tech-stack:
  added: []
  patterns: [pure-ASGI middleware without BaseHTTPMiddleware for performance]

key-files:
  created: [tests/test_http_app.py]
  modified: [src/homelab_mcp/http_app.py, run_server.py]

key-decisions:
  - "Pure ASGI middleware instead of BaseHTTPMiddleware for lower overhead"
  - "Port variants accepted implicitly via startswith check (localhost:3000 matches localhost)"

patterns-established:
  - "Origin validation as pure ASGI middleware pattern (no BaseHTTPMiddleware dependency)"

requirements-completed: [MCP-04]

duration: 3min
completed: 2026-03-11
---

# Phase 04 Plan 02: Origin Validation and Localhost Binding Summary

**OriginValidationMiddleware with DNS rebinding protection, configurable via MCP_ALLOWED_ORIGINS, default bind 127.0.0.1**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T17:09:22Z
- **Completed:** 2026-03-11T17:12:10Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- OriginValidationMiddleware rejects disallowed origins with 403 JSON response
- No-Origin requests (non-browser/CLI clients) pass through without restriction
- Localhost variants (http/https, 127.0.0.1) allowed by default with port variant support
- MCP_ALLOWED_ORIGINS env var enables custom origins (comma-separated)
- Default HTTP bind address changed from 0.0.0.0 to 127.0.0.1 per MCP spec recommendation

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing Origin validation tests** - `7901217` (test)
2. **Task 1 (GREEN): OriginValidationMiddleware + localhost bind** - `2f07276` (feat)

_Note: TDD task with RED + GREEN commits_

## Files Created/Modified
- `src/homelab_mcp/http_app.py` - Added OriginValidationMiddleware class and wired into middleware stack before CORSMiddleware
- `run_server.py` - Changed default host from 0.0.0.0 to 127.0.0.1 in CLI args, env var default, and run_http function
- `tests/test_http_app.py` - 8 tests covering all origin validation scenarios

## Decisions Made
- Used pure ASGI middleware pattern (__call__ with scope/receive/send) instead of BaseHTTPMiddleware for lower overhead and simpler implementation
- Port variants accepted via startswith check: if "http://localhost" is allowed, "http://localhost:3000" matches automatically

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Origin validation and localhost binding complete
- Ready for remaining Phase 04 plans (if any) or Phase 05

---
*Phase: 04-mcp-protocol-compliance*
*Completed: 2026-03-11*
