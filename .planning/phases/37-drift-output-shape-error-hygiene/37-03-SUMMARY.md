---
phase: 37-drift-output-shape-error-hygiene
plan: "03"
subsystem: test-regression-guards
tags: [ast-regression, drift, proxmox-host, baseline-tools, footgun-removal]
dependency_graph:
  requires: []
  provides:
    - "TestPhase37DriftHygiene.test_no_proxmox_host_in_drift_files (D-11 AST guard)"
    - "TestPhase37DriftHygiene.test_no_baseline_lifecycle_tool_names_in_source (D-12 AST guard)"
  affects:
    - "tests/test_ast_regression.py"
tech_stack:
  added: []
  patterns:
    - "pathlib.Path rglob + read_text + substring scan (extends Phase 32/33/35/36 pattern)"
    - "INFRA_REQUIREMENTS dict-value import for narrow per-entry scan (avoids line-number coupling)"
key_files:
  created: []
  modified:
    - "tests/test_ast_regression.py"
decisions:
  - "D-11 guard uses dict-value import (not whole-file scan) for openapi_app.py to avoid false positives on the legitimate Proxmox entry (Phase 40 POL-03 territory)"
  - "D-12 guard has zero allowed exceptions — baseline-lifecycle tools were never built and must never be built"
  - "Both guards in TestPhase37DriftHygiene class (D-14 / CONTEXT bullet 7 — one file, one place)"
  - "D-11 is RED until Plan 02 ships its drift surface text scrub (Wave-0-TDD pattern from Phase 36)"
metrics:
  duration: "2m 23s"
  completed_date: "2026-04-26"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
requirements_closed:
  - DRFT-15
  - DRFT-16
---

# Phase 37 Plan 03: AST Regression Guards (D-11 / D-12) Summary

**One-liner:** Two AST regression guards in `TestPhase37DriftHygiene` lock in DRFT-15 (PROXMOX_HOST forbidden in drift surface) and DRFT-16 (no baseline-lifecycle MCP tool names anywhere in src/).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add TestPhase37DriftHygiene class with D-11 PROXMOX_HOST guard + D-12 tool-name guard | adf5ea6 | tests/test_ast_regression.py (+148 lines) |

## What Was Built

Extended `tests/test_ast_regression.py` with a new `TestPhase37DriftHygiene` class containing two test methods:

**`test_no_proxmox_host_in_drift_files` (D-11 / DRFT-15 closure):**
- File scan: `drift_detection.py`, `tool_handlers/drift_handlers.py`, `tool_schemas/drift_tools_schema.py` — each must have zero `PROXMOX_HOST` substring matches.
- Dict-value scan: imports `INFRA_REQUIREMENTS` from `openapi_app` and checks only `INFRA_REQUIREMENTS["Drift Detection"]` — the `"Proxmox"` entry is intentionally NOT checked (Phase 40 POL-03 territory per CONTEXT D-08).
- Failure message names the exact file or dict key so a future reverter knows immediately what to fix.

**`test_no_baseline_lifecycle_tool_names_in_source` (D-12 / DRFT-16 closure):**
- Walks every `*.py` under `src/homelab_mcp/` via `rglob` and scans each file for `register_drift_baseline`, `list_drift_baselines`, `delete_drift_baseline`.
- Zero matches required across all files — no allowed exceptions.
- Failure message reports repo-root-relative file path and the offending tool name.

## Test Outcomes

| Test | Status | Notes |
|------|--------|-------|
| `test_no_baseline_lifecycle_tool_names_in_source` (D-12) | GREEN | Bug C tools never existed in codebase; passes immediately |
| `test_no_proxmox_host_in_drift_files` (D-11) | RED | Expected — `openapi_app.py INFRA_REQUIREMENTS["Drift Detection"]` still contains `PROXMOX_HOST`; Plan 02 scrubs this in Wave 1 (Wave-0-TDD pattern) |
| All pre-existing Phase 33/35/36 guards | GREEN | Unchanged; all 9 pre-existing tests pass |

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed two f-strings without placeholders**
- **Found during:** Task 1 ruff check
- **Issue:** Two string literals in the `violations.append(...)` call for the openapi_app.py dict-value violation were incorrectly prefixed with `f` despite having no `{}` placeholders (ruff F541).
- **Fix:** Removed `f` prefix from both string literals; concatenated as plain strings.
- **Files modified:** `tests/test_ast_regression.py`
- **Commit:** adf5ea6 (included in the same task commit after fix)

## Known Stubs

None. This plan is test-only; no production code stubs introduced.

## Threat Flags

None. The test file additions introduce no new network endpoints, auth paths, file writes, or trust boundary changes.

## Self-Check: PASSED

Verified:

```
[ -f "tests/test_ast_regression.py" ] → FOUND
git log --oneline | grep adf5ea6 → FOUND: adf5ea6 test(37-03): add TestPhase37DriftHygiene AST guards (D-11 / D-12)
grep "class TestPhase37DriftHygiene" tests/test_ast_regression.py → 1 match (line 599)
grep "def test_no_proxmox_host_in_drift_files" tests/test_ast_regression.py → 1 match (line 636)
grep "def test_no_baseline_lifecycle_tool_names_in_source" tests/test_ast_regression.py → 1 match (line 701)
uv run ruff check tests/test_ast_regression.py → All checks passed
uv run pytest TestPhase37DriftHygiene::test_no_baseline_lifecycle_tool_names_in_source → PASSED
```
