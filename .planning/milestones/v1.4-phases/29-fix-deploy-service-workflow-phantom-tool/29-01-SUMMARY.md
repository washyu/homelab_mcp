---
phase: 29-fix-deploy-service-workflow-phantom-tool
plan: 01
subsystem: testing
tags: [mcp, prompts, phantom-tool, regression-guard]

# Dependency graph
requires:
  - phase: 28-fix-prompt-parameter-names
    provides: deploy_service_workflow prompt with correct hostname= parameter names
provides:
  - deploy_service_workflow prompt step 2 uses get_service_status (registered tool) instead of list_installed_services (phantom)
  - Regression test test_deploy_service_workflow_no_phantom_tool blocks phantom tool re-introduction
affects: [any phase modifying prompt_registry.py or test_mcp_prompts.py]

# Tech tracking
tech-stack:
  added: []
  patterns: [Negative assertion regression guard blocks phantom tool re-introduction]

key-files:
  created: []
  modified:
    - src/homelab_mcp/prompt_registry.py
    - tests/test_mcp_prompts.py

key-decisions:
  - "Replace list_installed_services with get_service_status in deploy_service_workflow step 2 — get_service_status is the registered tool with service_name and hostname params; list_installed_services never existed in the tool registry"
  - "Add negative assertion regression test (test_deploy_service_workflow_no_phantom_tool) to permanently block phantom tool re-introduction via CI"

patterns-established:
  - "Phantom tool guard pattern: add negative assertion test that asserts phantom_tool_name not in prompt text to catch future re-introduction at test time"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 29 Plan 01: Fix deploy_service_workflow Phantom Tool Summary

**Fixed deploy_service_workflow prompt step 2 to call registered get_service_status with service_name= and hostname= params; removed phantom list_installed_services reference that caused ValueError on every deploy workflow execution**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T02:16:49Z
- **Completed:** 2026-03-20T02:18:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Replaced phantom `list_installed_services` call in `_build_deploy_service_result()` with registered `get_service_status` including both required params (`service_name=` and `hostname=`)
- Updated `test_deploy_service_workflow_prompt` to positively assert `get_service_status` is present and removed `list_installed_services` from accepted keywords
- Added `test_deploy_service_workflow_no_phantom_tool` regression guard that permanently blocks phantom tool re-introduction via CI

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace phantom list_installed_services with get_service_status** - `5d0d563` (fix)
2. **Task 2: Update existing test and add phantom tool regression guard** - `999142b` (test)

## Files Created/Modified
- `src/homelab_mcp/prompt_registry.py` - Line 114 changed: phantom list_installed_services replaced with get_service_status with service_name= and hostname= parameters
- `tests/test_mcp_prompts.py` - Updated PRMT-03 assertion; added test_deploy_service_workflow_no_phantom_tool regression test

## Decisions Made
- Replace `list_installed_services` with `get_service_status` — the registered service tool that accepts `service_name` (string) and `hostname` (string), matching the pattern of other prompt steps. The phantom tool name never appeared in any tool schema or registry.
- Add a dedicated negative assertion regression test rather than relying solely on the existing PRMT-03 assertion — guarantees the specific phantom tool name can never silently re-enter the prompt.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Ruff reformatted the test file on first commit attempt (pre-commit hook). Staged the reformatted file and committed successfully on second attempt.

## Next Phase Readiness
- deploy_service_workflow prompt is fully functional; agents will no longer hit `ValueError: Unknown tool: list_installed_services`
- Regression test in CI prevents future phantom tool re-introduction
- Phase 29 complete

---
*Phase: 29-fix-deploy-service-workflow-phantom-tool*
*Completed: 2026-03-20*
