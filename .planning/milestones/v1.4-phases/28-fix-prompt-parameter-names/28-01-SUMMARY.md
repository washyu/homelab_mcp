---
phase: 28-fix-prompt-parameter-names
plan: 01
subsystem: testing
tags: [mcp, prompts, parameter-names, regression-tests, tdd]

# Dependency graph
requires:
  - phase: 23-workflow-completeness
    provides: connect_to_device and deploy_service_workflow prompt implementations in prompt_registry.py
provides:
  - Corrected prompt text with hostname= parameter names in all tool call instructions
  - Regression tests preventing future host=/hostname= parameter name drift
affects: [future prompt changes, MCP agent E2E onboarding flows]

# Tech tracking
tech-stack:
  added: []
  patterns: [TDD RED/GREEN cycle for prompt parameter name regression guard]

key-files:
  created: []
  modified:
    - tests/test_mcp_prompts.py
    - src/homelab_mcp/prompt_registry.py

key-decisions:
  - "Assert 'host=' not in combined text rather than checking each tool individually — catches any future host= regression anywhere in the prompt"
  - "Keep register_server hostname= (line 134 in prompt_registry) unchanged — it was already correct in Phase 23"

patterns-established:
  - "Parameter name regression pattern: assert 'wrong_param=' not in combined, assert 'correct_param=' in combined"

requirements-completed: [TOFU-03]

# Metrics
duration: 2min
completed: 2026-03-19
---

# Phase 28 Plan 01: Fix Prompt Parameter Names Summary

**Fixed host= bug in connect_to_device and deploy_service_workflow prompts, with TDD regression tests preventing parameter name drift**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-19T20:34:38Z
- **Completed:** 2026-03-19T20:36:26Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added two regression tests that assert `host=` never appears in prompt text and `hostname=` is always used
- Fixed `_build_deploy_service_result`: three tool call steps updated from `host=` to `hostname=`
- Fixed `_build_connect_to_device_result`: four tool call steps updated from `host=` to `hostname=`
- All 9 prompt tests pass; 682 unit tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add parameter name regression tests (RED)** - `eb77d4c` (test)
2. **Task 2: Fix host= to hostname= in both prompts (GREEN)** - `7eaecfc` (fix)

**Plan metadata:** (docs commit to follow)

_Note: TDD task 1 committed in RED state; task 2 is the GREEN implementation commit_

## Files Created/Modified

- `tests/test_mcp_prompts.py` - Added `test_connect_to_device_prompt_parameter_names` and `test_deploy_service_workflow_prompt_parameter_names`
- `src/homelab_mcp/prompt_registry.py` - Fixed 7 occurrences of `host=` replaced with `hostname=` in prompt text

## Decisions Made

- Assert `"host=" not in combined` (negative check on full combined text) rather than per-tool positive checks — broader coverage, catches any future drift anywhere in the prompt body
- The `register_server with hostname=` line in `_build_connect_to_device_result` was already correct from Phase 23 — left unchanged; final count is 8 `hostname=` occurrences (not 7 as estimated in plan, because register_server was already correct)

## Deviations from Plan

None - plan executed exactly as written. The `hostname=` count was 8 (not 7 as estimated in the plan acceptance criteria) because `register_server with hostname=` on line 134 was already correct before this fix. The key requirement `host="` = 0 was fully satisfied.

## Issues Encountered

- ruff-format reformatted the test file after the first commit attempt (multi-line f-strings collapsed to single line); re-staged and committed after formatting passed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TOFU-03 fully satisfied: both prompts now use correct `hostname=` parameter names matching MCP tool schemas
- Regression tests prevent future parameter name drift in both prompts
- No blockers for subsequent phases
