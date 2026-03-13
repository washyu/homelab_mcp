---
phase: 14-mcp-prompts
plan: 02
subsystem: api
tags: [mcp, prompts, mcp-sdk, python, homelab]

# Dependency graph
requires:
  - phase: 14-mcp-prompts-01
    provides: Wave 0 RED test scaffold (tests/test_mcp_prompts.py) for PRMT-01..04

provides:
  - prompt_registry.py with HOMELAB_PROMPTS dict and get_prompt_result() dispatcher
  - server.py list_prompts and get_prompt handler registrations
  - MCP PromptsCapability advertised in server.get_capabilities()

affects:
  - 15-mcp-completions (if planned — prompts are prerequisite)
  - any future phase extending prompt templates

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "prompt_registry.py imports only mcp.types and mcp.shared.exceptions — no homelab_mcp imports (circular import prevention)"
    - "HOMELAB_PROMPTS dict keyed by name; handle_list_prompts returns list(HOMELAB_PROMPTS.values())"
    - "get_prompt_result() dispatcher pattern with named _build_*_result() helpers"
    - "@server.list_prompts() registration is sufficient to auto-advertise PromptsCapability in SDK"

key-files:
  created:
    - src/homelab_mcp/prompt_registry.py
  modified:
    - src/homelab_mcp/server.py
    - tests/test_mcp_prompts.py

key-decisions:
  - "prompt_registry.py has zero homelab_mcp imports — only mcp.types and mcp.shared.exceptions — preventing circular import"
  - "HOMELAB_PROMPTS is dict[str, types.Prompt] keyed by name; handle_list_prompts uses list(HOMELAB_PROMPTS.values())"
  - "get_prompt_result raises McpError with code -32002 (RESOURCE_NOT_FOUND) for unknown prompt names"
  - "test_list_prompts_returns_prompts bug fixed: must iterate HOMELAB_PROMPTS.values() not HOMELAB_PROMPTS keys"

patterns-established:
  - "Prompt registry pattern: thin static module with PROMPTS dict + dispatcher, no business logic"
  - "server.py prompt handlers delegate entirely to prompt_registry — server stays as registration hub only"

requirements-completed: [PRMT-01, PRMT-02, PRMT-03, PRMT-04]

# Metrics
duration: 4min
completed: 2026-03-13
---

# Phase 14 Plan 02: MCP Prompts Implementation Summary

**Three static MCP prompt templates wired into homelab server via prompt_registry.py module and server.py handler registrations, turning all 6 Wave 0 RED tests GREEN**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-13T20:52:07Z
- **Completed:** 2026-03-13T20:55:16Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `prompt_registry.py` with `HOMELAB_PROMPTS` dict (3 entries) and `get_prompt_result()` dispatcher
- Wired `@server.list_prompts()` and `@server.get_prompt()` handlers into `server.py`
- All 6 Wave 0 tests GREEN; 594 unit tests pass with zero regressions
- `caps.prompts` is not None confirming PromptsCapability advertisement

## Task Commits

Each task was committed atomically:

1. **Task 1: Create prompt_registry.py with three static prompts** - `cca1b9a` (feat)
2. **Task 2: Wire list_prompts and get_prompt handlers into server.py** - `7e46016` (feat)

## Files Created/Modified

- `src/homelab_mcp/prompt_registry.py` - Static prompt registry: HOMELAB_PROMPTS dict + get_prompt_result() dispatcher
- `src/homelab_mcp/server.py` - Added import + handle_list_prompts and handle_get_prompt handler decorators
- `tests/test_mcp_prompts.py` - Bug fix: iterate `.values()` not dict keys in test_list_prompts_returns_prompts

## Decisions Made

- `prompt_registry.py` imports only `mcp.types` and `mcp.shared.exceptions` — no homelab_mcp imports (per RESEARCH.md pitfall 1 and STATE.md architectural pattern)
- `HOMELAB_PROMPTS` is `dict[str, types.Prompt]` keyed by name; `handle_list_prompts` returns `list(HOMELAB_PROMPTS.values())`
- `get_prompt_result()` raises `McpError` with code `-32002` for unknown names — handler needs no additional try/except
- Registering `@server.list_prompts()` is sufficient for SDK to auto-include `PromptsCapability` in `get_capabilities()`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_list_prompts_returns_prompts iterating over dict keys instead of values**
- **Found during:** Task 1 (GREEN phase test run)
- **Issue:** Wave 0 scaffold test did `[p.name for p in HOMELAB_PROMPTS]` which iterates dict keys (strings), not Prompt objects; `AttributeError: 'str' object has no attribute 'name'`
- **Fix:** Changed to `[p.name for p in HOMELAB_PROMPTS.values()]` in `tests/test_mcp_prompts.py`
- **Files modified:** `tests/test_mcp_prompts.py`
- **Verification:** `test_list_prompts_returns_prompts` passes GREEN after fix
- **Committed in:** `cca1b9a` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in Wave 0 test scaffold)
**Impact on plan:** Fix necessary for test correctness; no scope creep.

## Issues Encountered

None - implementation followed plan exactly after test bug fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MCP Prompts capability (PRMT-01..04) fully implemented and verified
- Phase 14 complete — all Wave 0 tests GREEN, capability advertised, three prompt templates operational
- Ready for Phase 15 if planned

---
*Phase: 14-mcp-prompts*
*Completed: 2026-03-13*
