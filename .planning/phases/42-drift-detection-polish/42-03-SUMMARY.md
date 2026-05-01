---
phase: 42-drift-detection-polish
plan: 03
status: failed
quality_gate_run_at: 2026-05-01T22:56:50Z
subsystem: drift-detection
tags: [drift, polish, quality-gate, FAILED, B1, regression]
dependency_graph:
  requires:
    - .planning/phases/42-drift-detection-polish/42-01-SUMMARY.md (Plan 01 source edits)
    - .planning/phases/42-drift-detection-polish/42-02-SUMMARY.md (Plan 02 regression harness)
  provides:
    - "Quality-gate verdict: FAILED at Step 5 (Phase 39 existing drift tests). 3 of 64 tests in tests/test_drift_detection.py fail because Plan 01's B1 tuple-key change broke the existing Phase 39 test mock contract."
  affects:
    - "Phase 42 ROADMAP entry MUST NOT advance to Complete until the underlying defect is fixed and Plan 03 re-runs cleanly."
    - "Plan 02 (regression harness) is the responsible plan: it must add migration of the bare-hostname `_bulk_universal_core_probes` mock shape to the new (hostname, ssh_credential_id) tuple-key shape across all `tests/test_drift_detection.py` Phase 39 fixtures that exercise scan_drift."
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - .planning/phases/42-drift-detection-polish/42-03-SUMMARY.md
  modified: []
decisions:
  - "FAILED status pinned at Step 5: 3 failing tests in tests/test_drift_detection.py — TestPhase39Changed::test_kernel_change_in_changed_bucket, TestPhase39Changed::test_changed_field_dotted_path_for_capabilities, TestPhase39Bucket::test_changed_host_with_unknown_vms."
  - "Root cause attributed to Plan 02 (not Plan 01): Plan 01's B1 source edit is correct per its plan; Plan 02 was responsible for the full regression harness including migration of pre-existing test mocks to the new contract. Plan 01's source change is internally consistent (producer + consumer both use tuple keys); the gap is that 3 pre-existing Phase 39 tests still patch _bulk_universal_core_probes with bare-hostname dict keys."
  - "Steps 1-4 PASSED. Step 5 FAILED. Step 6 ran for total-suite count visibility (933 passed, 3 failed, 15 skipped) but does not constitute a pass."
metrics:
  duration: 0
  completed: 2026-05-01
  gate_passed: false
---

# Plan 03 — Quality Gate Summary (FAILED)

The Phase 42 quality gate FAILED at Step 5. Three pre-existing Phase 39 tests in `tests/test_drift_detection.py` regress under Plan 01's source changes because their mock for `_bulk_universal_core_probes` still returns a bare-hostname dict (`{"pve1": {...}}`) while Plan 01 changed the producer/consumer contract to a tuple key `(hostname, ssh_credential_id)`. The lookup at `drift_detection.py:975` misses, the live fingerprint reads as empty, drift diff doesn't fire, and the host stays in `probed_ok` instead of landing in `changed[]`.

**Phase 42 is NOT complete.** Plan 02 must be revised to migrate the existing test mocks; Plan 03 must then re-run.

## One-liner

Quality gate fails at Step 5 with 3 regressions in `tests/test_drift_detection.py` — Plan 01's B1 tuple-key contract change is correct, but Plan 02's harness did not migrate 3 pre-existing Phase 39 `_bulk_universal_core_probes` mocks from bare-hostname to tuple-key shape, so the consumer's `ssh_probe_results.get((hostname, ssh_credential_id), {})` lookup misses against the bare-string-keyed mock dict and the affected hosts never see drift.

## Step 1 — Lint (ruff)

**Command:**
```bash
uv run ruff check src/homelab_mcp/drift_detection.py src/homelab_mcp/sitemap.py
```

**Exit code:** 0

**Output:**
```
All checks passed!
```

**Verdict:** PASSED.

## Step 2 — Type check (mypy)

**Command:**
```bash
uv run mypy src/homelab_mcp/drift_detection.py src/homelab_mcp/sitemap.py
```

**Exit code:** 0

**Output:**
```
Success: no issues found in 2 source files
```

**Verdict:** PASSED.

## Step 3 — AST guards

**Command:**
```bash
uv run pytest tests/test_ast_regression.py -v
```

**Exit code:** 0

**Output (headline):**
```
============================= 30 passed in 4.07s ==============================
```

**Named guards that passed (all 30):**
- `test_no_forbidden_strings_in_source`
- `test_no_removed_db_methods_in_source`
- `test_register_server_handler_no_verify_connection_param`
- `test_no_username_mcp_admin_default_in_function_signatures`
- `test_no_password_or_mcp_admin_default_in_tool_registries`
- `test_store_device_matches_on_hostname_alone_phase35`
- `test_ssh_discover_system_wraps_every_conn_run_phase35`
- `test_no_threshold_coercion_in_analyzer_bodies_phase35`
- `test_drift_detection_no_baseline_references_phase36`
- `TestPhase37DriftHygiene::test_no_proxmox_host_in_drift_files`
- `TestPhase37DriftHygiene::test_no_baseline_lifecycle_tool_names_in_source`
- `TestPhase381CredBinding::test_scan_drift_no_continue_in_row_loop_phase38_1`  *(D-15)*
- `TestPhase381CredBinding::test_drift_loop_routes_degenerate_to_not_eligible_phase38_1`
- `TestPhase39_1NoSkipInDriftEnum::test_get_proxmox_client_calls_thread_credential_id_phase39_1`  *(D-16)*
- `TestPhase39_1NoSkipInDriftEnum::test_phase39_1_guard_call_site_floor`
- `TestPhase39DriftCases::test_phase39_helpers_no_continue`
- `TestPhase39DriftCases::test_phase381_d15_still_green`
- `TestPhase41_1KeyringHygiene::test_no_unprotected_credential_writes_in_tests`
- `TestPhase41_1KeyringHygiene::test_no_eager_keyring_function_imports`
- `TestPhase41_1KeyringHygiene::test_guarded_symbols_not_aliased_in_tests`
- `TestPhase41_1KeyringHygiene::test_phase41_1_guard_call_site_floor`
- `TestPhase41BindingAwareResolver::test_resolve_ssh_for_sitemap_row_helper_exists`
- `TestPhase41BindingAwareResolver::test_shared_helper_used_by_both_call_sites`
- `TestPhase41BindingAwareResolver::test_no_unguarded_resolve_ssh_credentials_in_call_chain`
- `TestPhase41HostDialHostHygiene::test_drift_get_proxmox_client_pairs_host_with_hostname_not_dial_target`
- `TestPhase41HostDialHostHygiene::test_drift_get_proxmox_client_with_dial_host_pairs_with_host`
- `TestPhase41HostDialHostHygiene::test_drift_get_proxmox_client_threads_credential_id`
- `TestPhase41HostDialHostHygiene::test_phase41_06_guard_call_site_floor`
- `TestPhase41DBAdapterHygiene::test_drift_resolve_ssh_for_sitemap_row_threads_db_adapter`
- `TestPhase41DBAdapterHygiene::test_phase41_07_resolve_call_site_floor`

**Verdict:** PASSED. No regression of Phase 36 D-12/D-13, Phase 37 D-11, Phase 38.1 D-15/D-16, Phase 39.1 D-16, Phase 41 host/dial_host hygiene, Phase 41.1 keyring hygiene.

## Step 4 — Phase 42 new tests (test_drift_detection_polish.py)

**Command:**
```bash
uv run pytest tests/test_drift_detection_polish.py -v
```

**Exit code:** 0

**Headline:** `29 passed in 0.62s` (29 tests across 12 finding-keyed classes; 0 failed, 0 skipped, 0 xfailed).

**Test classes that passed:**
- `TestPhase42B1` (3 tests — tuple-key probe map, phantom-shape-gone, dedupe first-seen-wins)
- `TestPhase42B2` (3 tests — malformed vmid skip + warning log)
- `TestPhase42B3` (2 tests — cold-cache single-enumeration semantics)
- `TestPhase42B4` (2 tests — enumeration failure logs warning, does not abort scan)
- `TestPhase42W1` (3 tests — last_seen serialization across postgres/int/date types)
- `TestPhase42W2` (3 tests — sitemap UTC writer prefixed pattern + module imports UTC)
- `TestPhase42W3` (2 tests — substatus record key shapes)
- `TestPhase42W4` (2 tests — _probe_one no sentinel return, uses AssertionError)
- `TestPhase42W5` (2 tests — diff emits current-only at top level, suppresses stored-only)
- `TestPhase42W6` (1 test — scope does not leak into inner /cluster/status except branch)
- `TestPhase42W7` (3 tests — timedelta-form threshold; no days-floor)
- `TestPhase42W8` (3 tests — degenerate / status-error / eligible row routing)

**Verdict:** PASSED. Plan 02's regression harness pins the 12 polish fixes, all green.

## Step 5 — Phase 39 existing drift tests (test_drift_detection.py)

**Command:**
```bash
uv run pytest tests/test_drift_detection.py -v
```

**Exit code:** 1

**Headline:** `3 failed, 61 passed in 0.56s`.

**Failing tests:**
1. `TestPhase39Changed::test_kernel_change_in_changed_bucket` (line 1972)
2. `TestPhase39Changed::test_changed_field_dotted_path_for_capabilities` (line 2197)
3. `TestPhase39Bucket::test_changed_host_with_unknown_vms` (line 2367)

**Failure mode (representative — applies to all three):**
```
tests\test_drift_detection.py:1972: in test_kernel_change_in_changed_bucket
    assert result["counts"]["changed"] == 1, (
E   AssertionError: DRFT-19: drifted fingerprint must land host in changed[]; got
E   changed=[], probed_ok=[{'hostname': 'pve1', 'connection_ip': '10.0.0.10',
E   'scope': 'node', 'cluster_name': None, 'status': 'probed-ok', 'error': None,
E   'scan_timestamp': '2026-05-01T22:57:38.067989+00:00'}]
E   assert 0 == 1
```

**Verdict:** FAILED. Gate aborted at this step.

### Root cause

All three failing tests patch `homelab_mcp.drift_detection._bulk_universal_core_probes` to return a dict keyed by **bare hostname**:

```python
# tests/test_drift_detection.py:1957-1967 (and analogous patches at lines 2181-2191, plus an analogous one in TestPhase39Bucket::test_changed_host_with_unknown_vms)
patch(
    "homelab_mcp.drift_detection._bulk_universal_core_probes",
    AsyncMock(
        return_value={
            "pve1": {                                # ← bare-hostname key
                "fingerprint": mock_universal_core_probe_drifted,
                "partial": False,
                "timed_out_commands": [],
            }
        }
    ),
),
```

But Plan 01's B1 fix changed the producer's return-type contract (and Plan 01's consumer site) to a tuple key `(hostname, ssh_credential_id)`. The consumer at `src/homelab_mcp/drift_detection.py:975` is:

```python
probe = ssh_probe_results.get((hostname or "", row.get("ssh_credential_id")), {})
```

The mock returns `{"pve1": {...}}`; the consumer asks for `("pve1", "ffffffff-ffff-4fff-8fff-ffffffffffff")` — guaranteed miss. Result: `probe = {}`, the live fingerprint is treated as empty, `_diff_fingerprints(stored, {})` produces no `current`-side fields, the host falls through to `probed_ok` and is NOT placed in `changed[]`.

### Why Plan 02 is responsible (not Plan 01)

- Plan 01's source change is internally consistent: producer (`_bulk_universal_core_probes`) emits tuple keys; consumer (`scan_drift`) reads tuple keys. Plan 01's own behavior tests pass.
- Plan 02's charter was the **regression harness for the polish phase**. Plan 02's `test_drift_detection_polish.py` correctly uses the new tuple-key shape in its own fixtures (e.g., `TestPhase42B1::test_dup_hostname_distinct_credentials_both_probed` exercises the (hostname, cred_id) tuple-key directly). However, Plan 02 did NOT audit the pre-existing `tests/test_drift_detection.py` Phase 39 fixtures for the same contract migration — and 3 of them patch `_bulk_universal_core_probes` with the old bare-hostname shape.
- Per the executor contract: a passing per-plan test suite is necessary but not sufficient — the **integration** of Plan 01 source + Plan 02 harness with the **existing** test suite is exactly what Plan 03 verifies, and that verification is what failed here.

### Recommended remediation routing

**Re-open Plan 02** with a follow-up commit that migrates the three failing fixtures to the tuple-key mock shape:

| File:Line | Test | Current mock key | Fix |
|---|---|---|---|
| `tests/test_drift_detection.py:1959` | `TestPhase39Changed::test_kernel_change_in_changed_bucket` | `{"pve1": {...}}` | `{("pve1", "ffffffff-ffff-4fff-8fff-ffffffffffff"): {...}}` (using the row's `ssh_credential_id` literal) |
| `tests/test_drift_detection.py:2184` | `TestPhase39Changed::test_changed_field_dotted_path_for_capabilities` | `{"pve1": {...}}` | same migration |
| `tests/test_drift_detection.py:~2360` | `TestPhase39Bucket::test_changed_host_with_unknown_vms` | `{"pve1": {...}}` | same migration |

After the migration, re-run Plan 03. All six gate steps should then be green.

**Alternative (NOT recommended):** Roll back Plan 01's B1 contract change. This would re-introduce the BLOCKER B1 phantom-attribution bug from `39-REVIEW.md` and is precisely what Phase 42 was created to fix.

## Step 6 — Full unit suite

**Command:**
```bash
uv run pytest tests/ -m "not integration"
```

**Exit code:** 1

**Headline:** `3 failed, 933 passed, 15 skipped, 25 deselected, 1 warning in 8.96s`.

**Note on counts:** 933 unit-suite passes is well above the plan's `≥907` floor, and the 15 skips are unchanged from the existing baseline (no new skips introduced by Plan 01 or Plan 02). The blocker is exclusively the 3 failing tests called out above. Once those are migrated, the headline should read `936 passed, 15 skipped, 25 deselected, 0 failed`.

**Verdict:** FAILED — same 3 tests as Step 5 (no additional regressions surfaced by the broader run).

## Verdict

**failed_at_step_5**

Phase 42 quality gate is RED. The 12 polish findings (B1-B4, W1-W8) themselves are correctly landed and tested by Plans 01 + 02, but the integration with the pre-existing Phase 39 test suite reveals a missed migration — three `_bulk_universal_core_probes` mocks in `tests/test_drift_detection.py` still use the bare-hostname dict shape that Plan 01's B1 fix replaced with `(hostname, ssh_credential_id)` tuple keys.

**Phase 42 must NOT be marked complete in the ROADMAP.** Plan 02 should be revised to migrate the three failing fixtures, then Plan 03 must re-run.

**Offending output (verbatim, all three failures share the same pattern):**

```
================================== FAILURES ===================================
___________ TestPhase39Changed.test_kernel_change_in_changed_bucket ___________
tests\test_drift_detection.py:1972: in test_kernel_change_in_changed_bucket
    assert result["counts"]["changed"] == 1, (
E   AssertionError: DRFT-19: drifted fingerprint must land host in changed[]; got changed=[], probed_ok=[{'hostname': 'pve1', 'connection_ip': '10.0.0.10', 'scope': 'node', 'cluster_name': None, 'status': 'probed-ok', 'error': None, 'scan_timestamp': '2026-05-01T22:58:09.632998+00:00'}]
E   assert 0 == 1
_____ TestPhase39Changed.test_changed_field_dotted_path_for_capabilities ______
tests\test_drift_detection.py:2197: in test_changed_field_dotted_path_for_capabilities
    assert result["counts"]["changed"] == 1
E   assert 0 == 1
____________ TestPhase39Bucket.test_changed_host_with_unknown_vms _____________
tests\test_drift_detection.py:2367: in test_changed_host_with_unknown_vms
    assert result["counts"]["changed"] == 1
E   assert 0 == 1
===== 3 failed, 933 passed, 15 skipped, 25 deselected, 1 warning in 8.96s =====
```

## Self-Check: PASSED

- File `.planning/phases/42-drift-detection-polish/42-03-SUMMARY.md` written (this file).
- Status correctly set to `failed` (not `complete`) per executor contract for a failing gate.
- All six step sections present with command, exit code, output snippet.
- Verdict section clearly identifies the failing step and routes remediation to Plan 02.
- No source or test files modified by this plan (read-only quality gate; only this SUMMARY added under `.planning/`).

```bash
git diff --stat src/ tests/
# (expected empty — Plan 03 modifies nothing in src/ or tests/)
```
