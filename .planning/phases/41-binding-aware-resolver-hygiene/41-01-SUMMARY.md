---
phase: 41
plan: "01"
subsystem: tests
tags: [tdd, red-tests, regression-guard, ast-guard, xfail-strict]
dependency_graph:
  requires: []
  provides:
    - Phase 41 Wave 0 RED test scaffold (9 xfail-strict tests)
    - tests/test_phase41_binding_aware.py (6 functional tests)
    - tests/test_ast_regression.py::TestPhase41BindingAwareResolver (3 AST guards)
  affects:
    - tests/test_phase41_binding_aware.py
    - tests/test_ast_regression.py
tech_stack:
  added: []
  patterns:
    - xfail(strict=True) Wave 0 RED test pattern (established Phase 38.1)
    - MagicMock db_adapter + patch context-manager (mirror test_drift_detection.py)
    - in-memory SQLite fixture via NetworkSiteMap(db_path=:memory:)
    - AST guard class appended to test_ast_regression.py (mirror TestPhase41_1KeyringHygiene)
key_files:
  created: [tests/test_phase41_binding_aware.py]
  modified: [tests/test_ast_regression.py]
decisions:
  - Wave 0 TDD: RED tests exist before implementation; xfail-strict auto-converts RED->GREEN when Plans 02-04 land
  - Error payload WITHOUT hostname field exercises real zombie-row bug (ssh_connection_wrapper shape)
  - Added import pytest to test_ast_regression.py - required for new xfail decorators
metrics:
  duration: ~8 minutes
  completed: 2026-04-30T21:23:00Z
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 41 Plan 01: Wave 0 RED Test Scaffold Summary

Wave 0 RED test scaffold: 6 xfail-strict functional regression tests for Bugs AA/BB/V plus 3 xfail-strict AST guard methods in TestPhase41BindingAwareResolver, all confirming real behavior gaps before implementation lands.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create tests/test_phase41_binding_aware.py with 6 RED functional tests | 6a2553c | tests/test_phase41_binding_aware.py |
| 2 | Add TestPhase41BindingAwareResolver scaffold to tests/test_ast_regression.py | 471f0c6 | tests/test_ast_regression.py |

## What Was Built

### tests/test_phase41_binding_aware.py (6 functional RED tests)

Six async test functions, all xfail(strict=True), covering every Phase 41 bug:

| Test | Bug | What it asserts |
|------|-----|-----------------|
| test_discover_and_map_uses_row_binding_when_row_exists | AA | resolve_ssh_credentials called with credential_id kwarg when row has binding |
| test_failed_discover_writes_to_requested_identifier_row | BB | Error envelope without hostname field creates zombie; test asserts no zombie |
| test_failed_discover_does_not_collapse_to_empty_hostname | BB | JSONDecodeError row uses requested hostname, not empty or unknown |
| test_dial_target_uses_row_connection_ip | V (discover) | ssh_connect called with connection_ip not logical hostname |
| test_drift_dials_connection_ip_not_hostname | V (drift) | get_proxmox_client called with connection_ip not logical hostname |
| test_error_envelope_carries_hostname | BB (envelope) | ssh_connection_wrapper error envelope has hostname field |

### tests/test_ast_regression.py::TestPhase41BindingAwareResolver (3 AST guards)

New class appended after TestPhase41_1KeyringHygiene with 3 xfail-strict methods:

| Method | Guards |
|--------|--------|
| test_resolve_ssh_for_sitemap_row_helper_exists | resolve_ssh_for_sitemap_row FunctionDef exists in ssh_tools.py (RED until Plan 02) |
| test_shared_helper_used_by_both_call_sites | Both sitemap.py + drift_detection.py call helper under canonical name (RED until Plans 03+04) |
| test_no_unguarded_resolve_ssh_credentials_in_call_chain | Zero direct resolve_ssh_credentials calls in sitemap.py/drift_detection.py or all on allowlist (RED until Plans 03+04) |

## Verification

9 xfailed, 0 XPASS, 0 FAILED. Full test_ast_regression.py suite: 21 passed, 3 xfailed.

## Deviations from Plan

**1. [Rule 1 - Bug] test_failed_discover_writes_to_requested_identifier_row initial XPASS**
- Found during: Task 1 verification
- Issue: First draft included hostname field in error envelope -- test passed unexpectedly (XPASS with strict=True becomes FAILED). Real ssh_connection_wrapper envelopes omit hostname.
- Fix: Removed hostname from error payload to match actual wrapper output shape.
- Files: tests/test_phase41_binding_aware.py / Commit: 6a2553c

**2. [Rule 3 - Blocking] pytest not imported in test_ast_regression.py**
- Found during: Task 2 verification
- Issue: NameError at class definition time -- no import pytest existed in the file.
- Fix: Added import pytest to module imports.
- Files: tests/test_ast_regression.py / Commit: 471f0c6

## Known Stubs

None.

## Threat Flags

None -- test-only changes; no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- tests/test_phase41_binding_aware.py exists: CONFIRMED
- TestPhase41BindingAwareResolver class added to test_ast_regression.py: CONFIRMED
- Commits 6a2553c and 471f0c6 exist: CONFIRMED
- 9 XFAIL outcomes, 0 XPASS, 0 FAILED: CONFIRMED
- ruff check clean on both files: CONFIRMED
- 21 existing AST regression tests still PASSED: CONFIRMED
