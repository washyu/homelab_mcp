---
phase: 37-drift-output-shape-error-hygiene
plan: "04"
subsystem: drift-detection
tags:
  - testing
  - regression
  - drift
  - phase-37
dependency_graph:
  requires:
    - 37-01-PLAN.md  # scan_drift 4-bucket envelope (implementation this plan tests)
  provides:
    - TestScanDrift4Bucket (21 tests) covering Phase 37 envelope contract
  affects:
    - tests/test_drift_detection.py
tech_stack:
  added: []
  patterns:
    - AsyncMock + MagicMock + patch idiom for async drift scan testing
    - Per-scenario inline mock closures (fake_get_client / fake_resolve)
key_files:
  modified:
    - tests/test_drift_detection.py
decisions:
  - "Merged TestScanDrift2Bucket into TestScanDrift4Bucket (single class) rather than keeping two separate classes — Plan 01 had created a parallel TestScanDrift4Bucket; Plan 04 consolidates into one class with all 6 Phase 36 + 15 Phase 37 tests"
  - "Pre-existing mypy src/ error (jsonschema missing stubs in openapi_app.py) is out of scope — not caused by this plan's changes; pre-commit hooks passed"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-26T02:46:08Z"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
  tests_added: 15
  tests_total: 21
---

# Phase 37 Plan 04: Drift Detection Regression Tests Summary

**One-liner:** Merged TestScanDrift2Bucket into TestScanDrift4Bucket, adding 15 Phase 37 envelope/filter/guidance regression tests alongside 6 preserved Phase 36 sanity tests (21 total).

## What Was Built

`tests/test_drift_detection.py` now contains a single `TestScanDrift4Bucket` class combining:

- **6 Phase 36 sanity tests** (preserved verbatim from the former `TestScanDrift2Bucket`):
  - `test_three_row_classification` — 3-row probed_ok/unreachable/skipped classification
  - `test_empty_sitemap_returns_success` — zero-row success path
  - `test_degenerate_rows_excluded` — status=error / empty hostname skip
  - `test_silent_skip_on_credential_not_found` — CredentialNotFoundError exclusion
  - `test_unreachable_error_is_sanitized` — sanitize_error() redaction
  - `test_inert_filter_passthrough` — node/vm_type kwargs accepted without error

- **15 Phase 37 regression tests** (new, exact names per must_haves):
  - `test_envelope_has_all_four_bucket_keys` — D-04/D-05: all four keys always present
  - `test_counts_subdict_mirrors_bucket_sizes` — D-07: counts sub-dict shape and values
  - `test_counts_sum_equals_top_level_scanned` — D-07 invariant: scanned == sum(counts.values())
  - `test_guidance_present_when_scanned_zero` — D-09: guidance present and non-empty
  - `test_guidance_absent_when_scanned_nonzero` — D-09: guidance absent when scanned > 0
  - `test_guidance_text_references_sitemap_crud_tools` — DRFT-15: discover_and_map + get_network_sitemap
  - `test_guidance_text_does_not_mention_proxmox_host` — DRFT-15 lock: PROXMOX_HOST absent
  - `test_node_filter_exact_hostname_match` — D-01: exact match narrows to single host
  - `test_node_filter_no_match_returns_success_empty` — D-01/D-03/D-09: no-match = success + guidance
  - `test_node_filter_none_means_no_filter` — D-01: node=None iterates all rows
  - `test_vm_type_inert_across_qemu_lxc_all` — D-02: identical structure across all three vm_type values
  - `test_envelope_key_order_is_locked` — locked key insertion order for scanned==0 and scanned>0
  - `test_per_row_record_shape_preserved_for_probed_ok` — D-10: 7-key per-row contract
  - `test_per_row_record_shape_preserved_for_unreachable` — D-10: 7-key per-row contract
  - `test_unknown_and_changed_buckets_always_empty_in_phase_37` — D-05/D-06: always [] in Phase 37

## Deviations from Plan

### Auto-resolved Situation

**Situation: Plan 01 had already created a separate TestScanDrift4Bucket class**

- **Found during:** Analysis before writing
- **Situation:** Plan 37-04 was written assuming `TestScanDrift2Bucket` still existed as the only class. Plan 01 (per CONTEXT bullet 8) chose to ADD a new `TestScanDrift4Bucket` while keeping `TestScanDrift2Bucket` intact — so both classes coexisted in HEAD.
- **Resolution:** Merged both classes into a single `TestScanDrift4Bucket`. The 6 Phase 36 methods from `TestScanDrift2Bucket` were preserved verbatim; the existing 11 Phase 37 methods from Plan 01's `TestScanDrift4Bucket` were replaced with the 15 exact method names required by Plan 04's must_haves (Plan 01's tests had partial coverage but different names). Final result: one class with 21 tests, all acceptance criteria satisfied.
- **Files modified:** `tests/test_drift_detection.py`
- **Commit:** `aa5fa8b`

### Pre-existing Out-of-Scope Issue

**`uv run mypy src/` fails on `openapi_app.py` — jsonschema missing stubs**

- This error existed in HEAD (commit `43c22a7`) before Plan 04 ran. It is not caused by changes in this plan (Plan 04 only modifies `tests/test_drift_detection.py`). The pre-commit hook runs `mypy src --ignore-missing-imports` and passed. Logged here for traceability; not a Plan 04 regression.

## Quality Gates

| Gate | Result |
|------|--------|
| `ruff check tests/test_drift_detection.py` | PASSED |
| `ruff format tests/test_drift_detection.py` | Auto-formatted by pre-commit hook; committed clean |
| `mypy src/` | Pre-existing failure in openapi_app.py (out of scope); pre-commit mypy src --ignore-missing-imports PASSED |
| `pytest tests/test_drift_detection.py::TestScanDrift4Bucket -v --no-cov` | PASSED (21/21) |
| `pytest tests/ -m "not integration" -x --tb=short` | PASSED (732 passed, 8 skipped) |

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `class TestScanDrift4Bucket` — exactly 1 match | PASSED |
| `class TestScanDrift2Bucket` — exactly 0 matches | PASSED |
| All 15 required Phase 37 method names present | PASSED |
| All 6 Phase 36 method names present | PASSED |
| No `_EMPTY_SCAN_GUIDANCE` import in test file | PASSED |
| 21+ tests collected in TestScanDrift4Bucket | PASSED (21) |
| Full unit suite green | PASSED (732 tests) |

## Self-Check: PASSED

### File exists:
- `tests/test_drift_detection.py` — FOUND (modified, 21 tests)
- `.planning/phases/37-drift-output-shape-error-hygiene/37-04-SUMMARY.md` — this file

### Commit exists:
- `aa5fa8b` — FOUND (test(37-04): rename TestScanDrift2Bucket to TestScanDrift4Bucket, add 15 Phase 37 envelope regression tests)
