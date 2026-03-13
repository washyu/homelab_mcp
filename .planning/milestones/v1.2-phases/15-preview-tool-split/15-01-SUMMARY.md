---
phase: 15-preview-tool-split
plan: "01"
subsystem: testing
tags: [tdd, wave-0, preview-tools, test-scaffold]
dependency_graph:
  requires: []
  provides: [wave-0-test-stubs-for-preview-tools]
  affects: [tests/test_preview_tools.py, tests/test_tools.py]
tech_stack:
  added: []
  patterns: [local-imports-in-test-functions, red-green-tdd-wave-pattern]
key_files:
  created:
    - tests/test_preview_tools.py
  modified:
    - tests/test_tools.py
decisions:
  - Wave 0 tests use local imports inside test function bodies — avoids collection-level ImportError for symbols not yet implemented (consistent with Phase 13 and 14 pattern)
  - test_preview_tool_schema_has_no_dry_run_param uses pytest.skip() rather than ERROR when schema not yet present — keeps test RED rather than ERROR for pre-implementation state
  - test_original_destructive_tools_still_present is intentionally GREEN at Wave 0 — validates originals are unchanged before preview variants are added
metrics:
  duration_minutes: 2
  completed_date: "2026-03-13"
  tasks_completed: 2
  files_changed: 2
---

# Phase 15 Plan 01: Wave 0 Test Scaffold for Preview Tools Summary

Wave 0 TDD test scaffold for 6 *_preview tool variants — 9 RED stubs in tests/test_preview_tools.py and tool count assertion updated from 50 to 56 in tests/test_tools.py.

## What Was Built

Created `tests/test_preview_tools.py` with 9 test functions using local imports to avoid collection-level ImportError. Updated `tests/test_tools.py` line 16 tool count from 50 to 56.

### tests/test_preview_tools.py (new file)

Nine test functions covering PREV-01 through PREV-08:

- 6 schema registry tests (one per preview tool name): assert each `*_preview` name is in `get_all_tool_schemas()`
- 1 annotations test: assert each preview tool has `readOnlyHint=True` and `destructiveHint=False`
- 1 destructive tools preservation test (GREEN immediately): assert original destructive tools still present with `dry_run` param
- 1 no-dry-run test: assert preview tool schemas do not include a `dry_run` parameter

### tests/test_tools.py (updated)

Line 16 updated: `len(tools) == 50` → `len(tools) == 56` (RED until Plan 02 adds 6 preview schemas)

## Test Results at Commit

| State | Count | Tests |
|-------|-------|-------|
| FAILED (RED) | 7 | All schema/annotation tests for preview tools |
| PASSED (GREEN) | 1 | test_original_destructive_tools_still_present |
| SKIPPED | 1 | test_preview_tool_schema_has_no_dry_run_param |

This is the expected Wave 0 state. Tests will go GREEN after Plan 02 adds the preview tool schemas and annotations.

## Verification

- `pytest --collect-only -q tests/test_preview_tools.py`: 9 tests collected, no ImportError
- `pytest tests/ -m "not integration" --collect-only`: 610 tests collected, no errors
- `pytest tests/test_tools.py -k test_get_available_tools`: FAILED with `assert 50 == 56` (expected RED)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | a7f70b0 | test(15-01): add RED stub tests for preview tool variants |
| Task 2 | 34bb7dc | test(15-01): update tool count assertion from 50 to 56 |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- tests/test_preview_tools.py: FOUND
- tests/test_tools.py: FOUND (len == 56)
- Commit a7f70b0: FOUND
- Commit 34bb7dc: FOUND
