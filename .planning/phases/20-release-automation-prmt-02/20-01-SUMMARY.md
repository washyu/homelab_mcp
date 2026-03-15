---
phase: 20-release-automation-prmt-02
plan: 01
subsystem: testing
tags: [tdd, mcp-prompts, prompt_registry, cli-02, wave-0]

# Dependency graph
requires:
  - phase: 14-mcp-prompts
    provides: prompt_registry.py with _build_decommission_result and test_mcp_prompts.py baseline
provides:
  - Wave 0 RED test contract for CLI-02 device_id resolution in decommission_device_workflow prompt
affects:
  - 20-02 (prompt_registry.py GREEN implementation — must make these assertions pass)
  - 20-03 (end-to-end prompt fix verification)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 tests are intentionally RED at commit time — correctness verified by pytest --collect-only (consistent with Phase 12/13/14/15/19 pattern)"

key-files:
  created: []
  modified:
    - tests/test_mcp_prompts.py

key-decisions:
  - "Wave 0 RED assertions committed without GREEN implementation — plan 20-03 will implement the fix"
  - "Two assertions added: 'get_network_sitemap' in combined_text and 'device_id' in combined_text"

patterns-established:
  - "Wave 0 TDD RED: new assertions added to existing test function, existing assertions retained as regression guards"

requirements-completed: [CLI-02]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 20 Plan 01: PRMT-02 Wave 0 RED Test Contract Summary

**Wave 0 TDD RED assertions added to test_decommission_workflow_prompt requiring 'get_network_sitemap' call and 'device_id' parameter in decommission prompt text**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-14T03:30:00Z
- **Completed:** 2026-03-14T03:35:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Extended `test_decommission_workflow_prompt` with two new RED assertions for CLI-02
- Confirmed test fails on `get_network_sitemap` assertion (current prompt still uses `hostname=` not `device_id`)
- All 5 other tests in `test_mcp_prompts.py` remain GREEN
- `pytest --collect-only` passes with no collection errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing device_id assertions to test_decommission_workflow_prompt (RED)** - `d76a972` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/test_mcp_prompts.py` - Added two assertions after existing guards: `get_network_sitemap` in combined_text and `device_id` in combined_text

## Decisions Made

- Wave 0 pattern followed: RED assertions committed before GREEN implementation (consistent with Phase 12/14/15/19 precedent)
- Existing assertions (`decommission_device_preview`, `confirm`) retained to guard against regression during fix

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 contract established: `test_decommission_workflow_prompt` has two RED assertions for CLI-02
- Plan 20-03 must update `_build_decommission_result` in `prompt_registry.py` to instruct AI to call `get_network_sitemap` first and use `device_id` (integer) instead of `hostname` (string)
- Current prompt text path: `src/homelab_mcp/prompt_registry.py::_build_decommission_result`

---
*Phase: 20-release-automation-prmt-02*
*Completed: 2026-03-14*
