---
phase: 36-drift-sitemap-foundation
plan: 03
subsystem: tests/regression-guards
tags: [ast-meta-test, regression-guard, footgun-removal, phase-36-d12, phase-36-d13, drft-21]
requirements-completed: [DRFT-21]
dependency-graph:
  requires:
    - tests/test_ast_regression.py (existing FORBIDDEN_SOURCE_STRINGS list, ALLOWED_EXCEPTIONS dict, test_no_forbidden_strings_in_source AST walk)
  provides:
    - "Codified SC-4 — AST meta-test fails CI if any future code path on the drift-scan call chain reads from a parallel baseline table"
    - "Belt-and-braces D-13 guard pinning drift_detection.py specifically against any drift_baseline reference"
  affects:
    - "Wave 2 plans 01, 02, 04, 05 — RED tests now block until those plans land"
tech-stack:
  added: []
  patterns:
    - "Phase 33/35 AST meta-test extension (FORBIDDEN_SOURCE_STRINGS list addition + ALLOWED_EXCEPTIONS narrow allowance for migration.py)"
    - "Phase 35 D-15 single-file substring-scan guard idiom (analog: test_ssh_discover_system_wraps_every_conn_run_phase35)"
key-files:
  created: []
  modified:
    - tests/test_ast_regression.py
decisions:
  - "Consolidated D-12/D-13 guards into existing tests/test_ast_regression.py (per RESEARCH §Open Questions Q1) rather than creating a new tests/test_drift_baselines_removed.py file — matches Phase 33/35 convention for single-discovery-point AST guards"
  - "Updated cosmetic assertion message from 'Phase 33 regression' to 'Phase 33+36 regression' to reflect expanded scope (purely cosmetic, no behavior change)"
  - "Did NOT add upsert_drift_baseline / get_drift_baseline / get_all_drift_baselines to ALLOWED_EXCEPTIONS — those method names should never appear anywhere in source post-Plan 01 (D-07 deletes the methods entirely)"
metrics:
  duration: "~5 minutes"
  completed: 2026-04-25
  tasks-completed: 2
  files-modified: 1
  lines-added: 39
  lines-removed: 1
---

# Phase 36 Plan 03: AST Regression Guards for D-12 / D-13 Summary

Extended `tests/test_ast_regression.py` with Phase 36 footgun-removal guards: four new entries
in `FORBIDDEN_SOURCE_STRINGS` (`drift_baselines`, `upsert_drift_baseline`,
`get_drift_baseline`, `get_all_drift_baselines`), one new `ALLOWED_EXCEPTIONS` entry allowing
`drift_baselines` only in `migration.py` (where the `DROP TABLE` statement legitimately
references the literal table name), and a new `test_drift_detection_no_baseline_references_phase36`
function that pins `drift_detection.py` specifically against any `drift_baseline` reference
(belt-and-braces guard on top of the broader AST walk).

## Outcome

This plan ships **RED** tests intentionally. Per the Wave 0 TDD pattern, the
`test_no_forbidden_strings_in_source` test (which now consumes the four new entries) will
fail until Plans 01 (`database.py` cleanup), 02 (`migration.py` cleanup, where `migration.py`
ends up the sole holder of the `drift_baselines` literal), 04 (`drift_detection.py` rewrite),
and 05 (test rewrites) land. The new `test_drift_detection_no_baseline_references_phase36`
test was confirmed RED with the expected failure mode — substring violations found
(`['drift_baseline', 'drift_baselines']`) — not a collection error, SyntaxError, or
ImportError, proving the test itself is well-formed.

Once Wave 2 plans land, both tests will go GREEN. Future commits that reintroduce any of
the forbidden strings outside `migration.py` will fail CI with a clear violation message
naming the offending file and forbidden string.

## Tasks Completed

| Task | Description | Commit | Files Modified |
|------|-------------|--------|----------------|
| 1 | Extend FORBIDDEN_SOURCE_STRINGS + ALLOWED_EXCEPTIONS for Phase 36 D-12 | `f0a3e04` | tests/test_ast_regression.py |
| 2 | Add test_drift_detection_no_baseline_references_phase36 function (D-13 belt-and-braces guard) | `a4a37b6` | tests/test_ast_regression.py |

## Verification Run

```bash
uv run ruff check tests/test_ast_regression.py
# All checks passed!

uv run python -c "import importlib.util, sys; spec = importlib.util.spec_from_file_location('test_ast_regression', 'tests/test_ast_regression.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); assert 'drift_baselines' in m.FORBIDDEN_SOURCE_STRINGS; assert 'upsert_drift_baseline' in m.FORBIDDEN_SOURCE_STRINGS; assert 'get_drift_baseline' in m.FORBIDDEN_SOURCE_STRINGS; assert 'get_all_drift_baselines' in m.FORBIDDEN_SOURCE_STRINGS; assert m.ALLOWED_EXCEPTIONS.get('drift_baselines') == {'migration.py'}; print('ok')"
# ok

uv run pytest tests/test_ast_regression.py --collect-only -q | grep test_drift_detection_no_baseline_references_phase36
# <Function test_drift_detection_no_baseline_references_phase36>

uv run pytest tests/test_ast_regression.py::test_drift_detection_no_baseline_references_phase36 -v --tb=short
# FAILED — AssertionError: Phase 36 D-13 regression — drift_detection.py contains forbidden
# baseline references: ['drift_baseline', 'drift_baselines'] (expected RED until Plan 04 lands)
```

## Acceptance Criteria

All acceptance criteria from the plan satisfied:

- `grep -n '"drift_baselines"' tests/test_ast_regression.py` returns matches in
  FORBIDDEN_SOURCE_STRINGS context (also in ALLOWED_EXCEPTIONS context).
- `grep -n '"upsert_drift_baseline"' tests/test_ast_regression.py` returns a match.
- `grep -n '"get_drift_baseline"' tests/test_ast_regression.py` returns a match.
- `grep -n '"get_all_drift_baselines"' tests/test_ast_regression.py` returns a match.
- `grep -n '"drift_baselines": {"migration.py"}' tests/test_ast_regression.py` returns a
  match in ALLOWED_EXCEPTIONS.
- `uv run ruff check tests/test_ast_regression.py` exits 0.
- The Python introspection assertion in `<verify>` exits 0.
- The test FILE imports cleanly (verified via `importlib.util.spec_from_file_location`).
- Phase 33 / 33.1 entries (`ssh_credentials`, `add_credential`, `verify_mcp_admin_access`,
  etc.) remain in `FORBIDDEN_SOURCE_STRINGS` unchanged.
- `grep -n "def test_drift_detection_no_baseline_references_phase36"` returns exactly one
  match (line 570).
- `pytest --collect-only` lists the new test function.
- Function body uses substring `in` check
  (`violations = [s for s in forbidden if s in source]`) — verified via grep at line 587.
- Assertion message contains "Phase 36 D-13 regression" — verified at line 589.
- Phase 35 D-15 analog test (`test_ssh_discover_system_wraps_every_conn_run_phase35`) is
  untouched at line 447.

## Deviations from Plan

None — plan executed exactly as written. The optional cosmetic update to the assert message
("Phase 33 regression" → "Phase 33+36 regression") was applied per the planner's suggestion.

## Decisions Made

1. **Consolidate into `tests/test_ast_regression.py` rather than create a new file.** Per
   RESEARCH §Open Questions Q1, the established convention is single-file consolidation —
   already extended through Phase 33 / 33.1 / 35. CONTEXT.md D-12 listed this as Claude's
   discretion (recommended new file `tests/test_drift_baselines_removed.py`); chose
   consolidation for one discovery point for "all AST guards in this project".

2. **Method names NOT added to `ALLOWED_EXCEPTIONS`.** The three adapter method names
   (`upsert_drift_baseline`, `get_drift_baseline`, `get_all_drift_baselines`) are
   intentionally not allowlisted anywhere — they should never appear in any source file
   post-Plan 01 (D-07 deletes the methods entirely). Only the literal table name
   `drift_baselines` is allowed in `migration.py` for the DROP TABLE statement.

3. **Cosmetic assertion message update.** Updated `"Phase 33 regression"` → `"Phase 33+36
   regression"` in the assert message of `test_no_forbidden_strings_in_source` to reflect
   the expanded scope. Pure cosmetic change; behavior unchanged.

## Wave 2 Handoff

These RED tests serve as the contract for Wave 2 plans:

| Plan | Action that turns this test GREEN |
|------|-----------------------------------|
| 36-01 | Removes `drift_baselines` references from `database.py` (DELETE adapter methods + CREATE TABLE block) |
| 36-02 | Cleans `migration.py` (DROP TABLE step is the sole remaining `drift_baselines` reference, satisfying ALLOWED_EXCEPTIONS) |
| 36-04 | Rewrites `drift_detection.py` to remove `_diff_vm_config` + `update_baseline_after_mutation` + the existing `scan_drift` body (turns D-13 GREEN) |
| 36-05 | Removes test files + patches that still reference baseline methods |

After all four plans land, `test_no_forbidden_strings_in_source` and
`test_drift_detection_no_baseline_references_phase36` both pass GREEN. Subsequent
commits that reintroduce any forbidden string outside `migration.py` will fail CI with
the message "Phase 33+36 regression" / "Phase 36 D-13 regression" plus the violating
file/string.

## Self-Check: PASSED

- File modified `tests/test_ast_regression.py` exists at expected path.
- Commit `f0a3e04` (Task 1) found in git log.
- Commit `a4a37b6` (Task 2) found in git log.
- New test function `test_drift_detection_no_baseline_references_phase36` discoverable by
  pytest at line 570.
- All acceptance criteria checks pass.
