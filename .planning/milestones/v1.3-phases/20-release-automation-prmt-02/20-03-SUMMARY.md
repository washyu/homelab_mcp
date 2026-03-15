---
phase: 20-release-automation-prmt-02
plan: "03"
subsystem: prompts
tags: [mcp-prompts, prmt-02, cli-02, decommission, device-id, prompt-registry]

# Dependency graph
requires:
  - phase: 20-release-automation-prmt-02-01
    provides: Wave 0 RED tests for CLI-02 (get_network_sitemap + device_id assertions)
provides:
  - Fixed _build_decommission_result() using 5-step device_id resolution workflow
  - CLI-02 requirement satisfied: decommission_device_workflow prompt calls get_network_sitemap
affects: [future prompt changes, decommission_device_workflow users]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prompt text instructs AI to resolve hostname->device_id via get_network_sitemap before calling decommission_device"

key-files:
  created: []
  modified:
    - src/homelab_mcp/prompt_registry.py

key-decisions:
  - "5-step decommission workflow: get_network_sitemap (step 1) -> decommission_device_preview (step 2) -> confirm (step 3) -> decommission_device (step 4) -> report (step 5)"
  - "decommission_device and decommission_device_preview now receive device_id (integer), not hostname (string)"

patterns-established:
  - "Prompt text uses device_id parameter to match tool schema requirements — never pass hostname to tools that require integer IDs"

requirements-completed: [CLI-02]

# Metrics
duration: 2min
completed: 2026-03-15
---

# Phase 20 Plan 03: PRMT-02 Fix Summary

**decommission_device_workflow prompt rewritten to resolve hostname to device_id via get_network_sitemap, satisfying CLI-02 schema contract**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-15T04:03:29Z
- **Completed:** 2026-03-15T04:05:09Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced broken 4-step hostname-based decommission workflow with correct 5-step device_id resolution workflow
- Step 1 now calls get_network_sitemap to find device_id from hostname match
- Steps 2 and 4 use device_id (integer) instead of hostname (string) — matching the tool schema
- All 6 tests in test_mcp_prompts.py pass including all 4 CLI-02 assertions
- Full unit suite (634 tests) remains green; ruff + mypy clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix _build_decommission_result() to use device_id resolution via get_network_sitemap (GREEN)** - `5f025e1` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/homelab_mcp/prompt_registry.py` - Replaced `_build_decommission_result()` body with 5-step device_id workflow

## Decisions Made

- 5-step workflow: get_network_sitemap -> decommission_device_preview (device_id) -> confirm -> decommission_device (device_id) -> report
- Confirmation gate moved to "Do not proceed to step 4" (was step 3 in old broken version)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The RED test from Plan 01 failed exactly as expected, and the fix was a clean single-function rewrite.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CLI-02 is satisfied
- PRMT-02 parameter mismatch (v1.2 carry-over) is resolved
- Phase 20 is complete — all 3 plans done (RED tests, CI/CD pipeline, GREEN fix)
- PyPI OIDC trusted publisher setup remains as the one manual step before pushing a v* tag

## Self-Check: PASSED

- `src/homelab_mcp/prompt_registry.py` — FOUND
- Commit `5f025e1` — FOUND

---
*Phase: 20-release-automation-prmt-02*
*Completed: 2026-03-15*
