---
phase: 23-workflow-completeness
plan: "01"
subsystem: mcp-prompts
tags: [mcp, prompts, onboarding, tofu, tdd]

# Dependency graph
requires:
  - phase: 22-agent-guidance
    provides: prompt_registry.py with HOMELAB_PROMPTS and get_prompt_result dispatcher
provides:
  - connect_to_device MCP prompt with 6-step device onboarding sequence
  - HOMELAB_PROMPTS expanded to 4 entries
affects: [agent-guidance, workflow-completeness]

# Tech tracking
tech-stack:
  added: []
  patterns: [TDD RED-then-GREEN for prompt additions, elif dispatcher chain in get_prompt_result]

key-files:
  created: []
  modified:
    - src/homelab_mcp/prompt_registry.py
    - tests/test_mcp_prompts.py

key-decisions:
  - "connect_to_device prompt lists all 6 onboarding tools/commands in order: setup_mcp_admin, credentials add, register_server, ssh_discover, discover_and_map, verify_mcp_admin"
  - "Hostname interpolated into each step via f-string so prompt is actionable without further substitution"

patterns-established:
  - "New prompts follow three-change pattern: dict entry in HOMELAB_PROMPTS, builder function _build_*_result, elif case in get_prompt_result"

requirements-completed: [TOFU-03]

# Metrics
duration: 8min
completed: 2026-03-15
---

# Phase 23 Plan 01: connect_to_device Onboarding Prompt Summary

**connect_to_device MCP prompt added to prompt_registry.py guiding agents through 6-step device onboarding (setup_mcp_admin through verify_mcp_admin)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-15T18:42:00Z
- **Completed:** 2026-03-15T18:50:09Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Added `test_connect_to_device_prompt` test asserting all 6 onboarding steps and hostname interpolation (RED first)
- Updated `test_list_prompts_returns_prompts` to require >= 4 prompts and assert `connect_to_device` is present
- Implemented `connect_to_device` entry in `HOMELAB_PROMPTS` dict (4 total prompts now)
- Added `_build_connect_to_device_result` builder producing the 6-step onboarding sequence
- Added `elif name == "connect_to_device":` dispatcher case in `get_prompt_result`
- All 7 prompt tests pass, full 656-test suite green

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED test for connect_to_device prompt** - `2c46378` (test)
2. **Task 2: Implement connect_to_device prompt and go GREEN** - `30e47c6` (feat)

_Note: TDD tasks have two commits (test RED → feat GREEN)_

## Files Created/Modified
- `tests/test_mcp_prompts.py` - Added test_connect_to_device_prompt and updated test_list_prompts_returns_prompts count/assertion
- `src/homelab_mcp/prompt_registry.py` - Added connect_to_device prompt entry, builder function, and dispatcher case

## Decisions Made
- Hostname interpolated into every step of the onboarding text so the returned prompt is immediately actionable
- Steps use exact tool names (setup_mcp_admin, register_server, ssh_discover, discover_and_map, verify_mcp_admin) and exact CLI syntax (credentials add) matching TOFU-03 requirements

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- TOFU-03 requirement fulfilled: agents can invoke connect_to_device and receive a deterministic 6-step onboarding sequence
- Ready for remaining Phase 23 plans

---
*Phase: 23-workflow-completeness*
*Completed: 2026-03-15*

## Self-Check: PASSED
- src/homelab_mcp/prompt_registry.py: FOUND
- tests/test_mcp_prompts.py: FOUND
- Commit 2c46378 (RED test): FOUND
- Commit 30e47c6 (GREEN implementation): FOUND
