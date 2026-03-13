---
phase: 14-mcp-prompts
plan: "01"
subsystem: mcp-prompts
tags: [tdd, wave-0, prompts, test-scaffold]
dependency_graph:
  requires: []
  provides: [wave-0-test-scaffold-prompts]
  affects: [tests/test_mcp_prompts.py]
tech_stack:
  added: []
  patterns: [local-import-pattern-for-wave-0-tests]
key_files:
  created:
    - tests/test_mcp_prompts.py
  modified: []
decisions:
  - "Wave 0 tests use local imports inside test function bodies — avoids collection-level ImportError for prompt_registry.py not yet implemented"
  - "Plain def (non-async) test functions used throughout — get_prompt_result is synchronous, @pytest.mark.asyncio not needed"
  - "test_prompts_capability_advertised fails with assert None is not None until server.py registers prompt handlers in Plan 02"
metrics:
  duration: "1 min"
  completed_date: "2026-03-13"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
---

# Phase 14 Plan 01: MCP Prompts Wave 0 Test Scaffold Summary

Wave 0 RED test scaffold for Phase 14 MCP Prompts — six failing tests covering PRMT-01 through PRMT-04 using local-import pattern to survive missing prompt_registry.py.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write Wave 0 test scaffold for MCP prompts | 8af0273 | tests/test_mcp_prompts.py |

## What Was Built

Created `tests/test_mcp_prompts.py` with six stub tests defining the contract for Plan 02 implementation:

1. `test_prompts_capability_advertised` — PRMT-01: verifies server advertises prompts capability
2. `test_list_prompts_returns_prompts` — PRMT-01: verifies HOMELAB_PROMPTS has 3 required prompt names
3. `test_decommission_workflow_prompt` — PRMT-02: verifies decommission workflow prompt structure
4. `test_deploy_service_workflow_prompt` — PRMT-03: verifies deploy service prompt has pre-flight guidance
5. `test_health_check_prompt_resources` — PRMT-04: verifies health check prompt references all 3 MCP resources
6. `test_get_unknown_prompt_raises_mcp_error` — PRMT-01: verifies McpError(-32002) for unknown prompts

## Verification

```
uv run pytest tests/test_mcp_prompts.py --collect-only -q
# => 6 tests collected, 0 collection errors

uv run pytest tests/test_mcp_prompts.py -v
# => 6 FAILED (expected Wave 0 behavior)
```

All failures are test-body ImportErrors or assertion failures — no collection-level errors.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] tests/test_mcp_prompts.py exists and contains 6 test functions
- [x] pytest --collect-only collects 6 tests, 0 errors
- [x] All 6 tests FAIL when run (Wave 0 RED confirmed)
- [x] Commit 8af0273 exists
