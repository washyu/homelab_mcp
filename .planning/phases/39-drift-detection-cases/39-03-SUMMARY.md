---
phase: 39-drift-detection-cases
plan: 03
subsystem: drift-detection
tags: [drift, missing, changed, ssh-prepass, ast-guard, drft-18, drft-19, wave-3]
dependency_graph:
  requires:
    - "Phase 39 Plan 01 helpers (_diff_fingerprints, _classify_unreachable, _missing_threshold_days, _probe_universal_core)"
    - "Phase 39 Plan 02 unknown-bucket pre-pass (_enumerate_proxmox_vms)"
    - "Phase 38.1 D-15 AST guard (no continue in scan_drift row loop)"
    - "Phase 38.1 D-08 locked envelope key order"
    - "Phase 35 D-02 Semaphore(10)+gather pattern"
    - "Phase 35 D-05 _run_with_timeout per-probe wrapping (inside _probe_universal_core)"
  provides:
    - "_bulk_universal_core_probes (drift_detection.py async helper) — DRFT-19 SSH pre-pass"
    - "scan_drift row-loop wiring for DRFT-18 (missing sub-status) + DRFT-19 (changed bucket)"
    - "120s outer timeout on SSH pre-pass (CONTEXT D-04a-narrowed)"
    - "TestPhase39Missing class (4 functional tests)"
    - "TestPhase39Changed class (5 functional tests)"
    - "TestPhase39Bucket class (3 D-10 invariant tests)"
    - "TestPhase39DriftCases AST guard (2 tests — D-11(b) + D-12 sibling)"
  affects:
    - "scan_drift response: probed_ok / unreachable / changed bucket placement"
    - "scan_drift: success path consults ssh_probe_results to decide changed vs probed_ok"
    - "scan_drift: failure paths now classify unreachable vs missing via last_seen + threshold"
    - "_enumerate_proxmox_vms now consumes probed_ok + changed (both = host responded to /cluster/status)"
tech_stack:
  added:
    - "asyncssh (added to drift_detection.py imports for SSH pre-pass error catch)"
  patterns:
    - "Per-scan Semaphore(10) + asyncio.gather for bulk SSH probe (Phase 35 D-02 reused)"
    - "Per-host asyncio.wait_for(45s) bounding probe (Pitfall 3 outer-bound)"
    - "Outer asyncio.wait_for(120s) on bulk pre-pass (CONTEXT D-04a-narrowed)"
    - "if/elif/else + try/except chain (no continue) — Phase 38.1 D-15 invariant preserved"
    - "asyncssh.Error/OSError/TimeoutError/ValueError + Exception (CredentialNotFoundError) catch with sanitize_error"
key_files:
  created:
    - ".planning/phases/39-drift-detection-cases/39-03-SUMMARY.md"
  modified:
    - "src/homelab_mcp/drift_detection.py"
    - "tests/test_drift_detection.py"
    - "tests/test_ast_regression.py"
decisions:
  - "Outer 120s timeout wraps SSH pre-pass only (not full scan_drift body) — preserves Phase 38.1 D-15 AST guard's `n.name == 'scan_drift'` target without renaming. Per-host wait_for(45s) + per-probe _run_with_timeout(10s) bound the rest. Aligns with CONTEXT D-04a-narrowed (Phase 35 has no full-scan ceiling either)."
  - "Both unreachable branches (resolver-during-walk + /cluster/status failure) call _classify_unreachable for uniform missing-promotion behavior. The plan only required the inner branch; broadening to both is Rule 2 critical correctness — a stale-credential row whose probe also fails gets the same actionable missing message."
  - "_enumerate_proxmox_vms now consumes probed_ok + changed lists (not just probed_ok). A 'changed' host has successfully responded to /cluster/status, so its VMs are still enumerable; D-10 keeps unknown[] independent of host bucket. Caught by TestPhase39Bucket::test_changed_host_with_unknown_vms."
  - "_bulk_universal_core_probes catches bare Exception (after the typed asyncssh/OSError/TimeoutError/ValueError tuple) to handle CredentialNotFoundError without leaking the row's binding state. Matches Plan 02's defensive Exception catch on _enum_one. Documented inline; out of D-11(b) AST guard scope (helper has zero ast.Continue nodes)."
  - "Defensive fallthrough return added at end of inner _probe_one to satisfy mypy strict — async with semaphore + nested async with await ssh_connect couldn't be proven exhaustive otherwise. Returns ('_error', 'unreachable_fallthrough') which is unreachable in practice."
metrics:
  duration: "~30 minutes"
  completed_date: "2026-04-27"
  tasks_completed: 3
  files_created: 1
  files_modified: 3
  test_count: 12
  test_class: "TestPhase39Missing + TestPhase39Changed + TestPhase39Bucket + TestPhase39DriftCases"
requirements:
  - DRFT-18
  - DRFT-19
---

# Phase 39 Plan 03: DRFT-18 (Missing) + DRFT-19 (Changed) Summary

Wired the missing-sub-status and changed-bucket cases into `scan_drift`. Added a new SSH pre-pass helper `_bulk_universal_core_probes` (Semaphore(10) + gather, per-host wait_for(45s)) wrapped in an outer `asyncio.wait_for(120s)` per CONTEXT D-04a-narrowed. The success branch now consults the pre-pass result and calls `_diff_fingerprints` to decide changed vs probed_ok; both unreachable branches now call `_classify_unreachable` to decide unreachable vs missing sub-status. Added 12 functional tests (TestPhase39Missing, TestPhase39Changed, TestPhase39Bucket) plus a 2-test AST guard class (TestPhase39DriftCases). All Phase 39 functional tests GREEN; full unit suite 841 passed.

## Helper Added

### `src/homelab_mcp/drift_detection.py`

| Symbol | Lines | Signature | Returns |
|--------|-------|-----------|---------|
| `_bulk_universal_core_probes` | 327–395 | `async def _bulk_universal_core_probes(rows: list[dict[str, Any]])` | `dict[str, dict[str, Any]]` (`{hostname: {fingerprint, partial, timed_out_commands}}` on success or `{hostname: {_error: str}}` on failure) |

**Imports added (drift_detection.py:34, 44–45):**
- `import asyncssh`
- `from .ssh_connection import ssh_connect`
- `from .ssh_tools import _probe_universal_core, resolve_ssh_credentials`

**Outer 120s timeout placement (drift_detection.py:511–520):**

```python
try:
    ssh_probe_results: dict[str, dict[str, Any]] = await asyncio.wait_for(
        _bulk_universal_core_probes(rows),
        timeout=120.0,
    )
except TimeoutError:
    logger.warning(
        "scan_drift: SSH pre-pass exceeded 120s; proceeding with empty probe results"
    )
    ssh_probe_results = {}
```

The 120s ceiling wraps **the SSH pre-pass only**. Per-host probe is bounded internally by `asyncio.wait_for(45.0)`; per-probe by `_run_with_timeout(10.0)` from Plan 01's `_probe_universal_core`. Proxmox API calls in the row loop have aiohttp default timeouts. CONTEXT D-04a-narrowed locked this scope: "Phase 35 itself does not impose a `wait_for` ceiling on the row loop, so this narrowing matches Phase 35 precedent rather than adding a new ceiling. The row loop is short (per-row dict lookups + branch) and does not perform I/O, so it does not need a wrap."

**Why not wrap full body:** Phase 38.1 D-15 AST guard targets `n.name == "scan_drift"` and walks for the row-loop. Renaming to `_scan_drift_body` would have required updating the guard. The chosen scope (SSH pre-pass only) keeps both invariants clean.

## scan_drift Row-Loop Edits (NO `continue` introduced)

| Line range | Change | Decision |
|------------|--------|----------|
| 511–520 | NEW: outer 120s `asyncio.wait_for` wrapping `_bulk_universal_core_probes` call before the `for row in rows:` loop | Phase 39 D-04a-narrowed |
| 580–597 | MODIFIED: resolver-during-walk failure branch now calls `_classify_unreachable(row, exc, threshold, now)`; appends `record` dict with `status=substatus` and (when missing) `last_seen` + recovery `message` | Phase 39 D-01/D-02 |
| 633–699 | MODIFIED: success branch consults `ssh_probe_results.get(hostname)`; computes `_diff_fingerprints(stored, current)`; non-empty diff → `changed.append(...)` with D-08 record shape (`status="changed"`, `changed_fields`, message); empty diff → `probed_ok.append(...)` (existing shape preserved) | Phase 39 D-08/D-09a |
| 700–718 | MODIFIED: `/cluster/status` failure branch now calls `_classify_unreachable(...)`; appends record with `status=substatus` and missing-only fields | Phase 39 D-01/D-02 |
| 723 | MODIFIED: `_enumerate_proxmox_vms(probed_ok + changed, session)` (was `probed_ok` only) | D-10 — unknown[] independent of host bucket; changed host's VMs still enumerable |

**No `continue` introduced anywhere.** Both Phase 38.1 D-15 (`test_scan_drift_no_continue_in_row_loop_phase38_1`) and the new Phase 39 D-12 sibling guard (`test_phase381_d15_still_green`) confirm zero `ast.Continue` nodes inside `scan_drift`'s `for row in rows:` body.

## D-04b Assertion Approach

**Test:** `TestPhase39Changed::test_drift_does_not_update_fingerprint`

**Method:** `db_adapter` is a `MagicMock`; the test runs the full drift cycle (drifted fingerprint via mocked `_bulk_universal_core_probes`, host lands in `changed[]`) then asserts `db_adapter.update_device_fingerprint.call_count == 0`.

**Why this works:** `MagicMock` records every attribute access and call automatically. If any code path in `scan_drift` (or any helper it calls during this scan) reached `db_adapter.update_device_fingerprint(...)`, the mock would record it. Zero calls means drift is structurally read-only against `devices.fingerprint` — locking Phase 39 CONTEXT D-04b ("Drift NEVER updates devices.fingerprint").

**Verified by code-read too:** `grep -A 200 "async def scan_drift" src/homelab_mcp/drift_detection.py | grep update_device_fingerprint` returns 0 matches in the function body.

## Test Counts

| Class | Test Count | Status |
|-------|------------|--------|
| `TestPhase39Missing` | 4 | All GREEN |
| `TestPhase39Changed` | 5 | All GREEN |
| `TestPhase39Bucket` | 3 | All GREEN |
| `TestPhase39DriftCases` (AST) | 2 | All GREEN |

12 functional tests + 2 AST guards = **14 new tests**. Combined with Plan 01's `TestPhase39Helpers` (15 tests) and Plan 02's `TestPhase39Unknown` (5 tests), total Phase 39 test count is **34** new tests.

### TestPhase39Missing (4 tests)
1. `test_old_last_seen_promotes_to_missing` — 12d-old last_seen + probe failure → status='missing' with last_seen + decommission_device pointer.
2. `test_recent_unreachable_not_promoted` — 1d-old last_seen + probe failure → status='unreachable' (not missing).
3. `test_threshold_env_var_override` — `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS=3` + 5d-old → missing.
4. `test_threshold_env_var_invalid_uses_default` — Invalid env (`abc`) + 5d-old → unreachable (default 7d applies).

### TestPhase39Changed (5 tests)
1. `test_kernel_change_in_changed_bucket` — Stored 6.5.13 vs probed 6.8.4 → changed[]; changed_fields["kernel_version"] = {stored, current}.
2. `test_no_diff_stays_probed_ok` — Probe returns identical fingerprint → probed_ok[]; counts.changed == 0.
3. `test_capability_only_in_stored_does_not_diff` — Stored has capabilities.vulkan; probe has universal-core only → counts.changed == 0 (D-09a leaf-level present-in-both).
4. `test_drift_does_not_update_fingerprint` — D-04b assertion via call_count.
5. `test_changed_field_dotted_path_for_capabilities` — Both sides have `capabilities.vulkan.available` → diff key uses dotted-path; stored=True, current=False.

### TestPhase39Bucket (3 tests)
1. `test_scanned_equals_counts_sum` — 4-row sitemap covering 4 host buckets + 1 unknown VM → invariant holds.
2. `test_changed_host_with_unknown_vms` — Drifted host yields counts.changed=1 AND counts.unknown=1 (parallel surfaces).
3. `test_bucket_priority_unreachable_over_changed` — Probe failure dominates fingerprint diff (D-10 priority).

### TestPhase39DriftCases AST Guard (2 tests)
1. `test_phase39_helpers_no_continue` — Walks AST; `_diff_fingerprints`, `_enumerate_unknown_vms`, `_classify_unreachable` each have zero `ast.Continue`.
2. `test_phase381_d15_still_green` — Locally re-asserts the Phase 38.1 D-15 row-loop continue-free invariant; D-12 sibling guard.

## AST Guard Verification

| Guard | Source | Status |
|-------|--------|--------|
| Phase 35 D-15 — `test_ssh_discover_system_wraps_every_conn_run_phase35` | `tests/test_ast_regression.py:447` | GREEN (sibling helper extraction stayed wrapped via `_probe_universal_core`) |
| Phase 38.1 D-15 — `test_scan_drift_no_continue_in_row_loop_phase38_1` | `tests/test_ast_regression.py:763` | GREEN (no `continue` introduced into row loop) |
| Phase 38.1 D-17 — `test_drift_loop_routes_degenerate_to_not_eligible_phase38_1` | `tests/test_ast_regression.py:808` | GREEN (`not_eligible.append` calls preserved) |
| Phase 39 D-11(b) — `test_phase39_helpers_no_continue` | `tests/test_ast_regression.py:864` | GREEN (3 helpers loop-free) |
| Phase 39 D-12 — `test_phase381_d15_still_green` (sibling) | `tests/test_ast_regression.py:891` | GREEN (re-asserts row-loop invariant locally) |

The new helper `_bulk_universal_core_probes` is OUT of guard scope per D-12 (named-function allowlist). It contains zero `ast.Continue` anyway; structurally clean.

## Regression Status

| Suite | Result |
|-------|--------|
| `tests/test_drift_detection.py::TestPhase39Helpers` (Plan 01) | **15/15 PASS** |
| `tests/test_drift_detection.py::TestPhase39Unknown` (Plan 02) | **5/5 PASS** |
| `tests/test_drift_detection.py::TestPhase39Missing` (Plan 03) | **4/4 PASS** |
| `tests/test_drift_detection.py::TestPhase39Changed` (Plan 03) | **5/5 PASS** |
| `tests/test_drift_detection.py::TestPhase39Bucket` (Plan 03) | **3/3 PASS** |
| `tests/test_drift_detection.py::TestScanDrift4Bucket` (Phase 36/37 regression) | **PASS** |
| `tests/test_drift_detection.py::TestScanDriftNotEligible` (Phase 38.1 regression) | **PASS** |
| `tests/test_ast_regression.py::TestPhase381CredBinding` (Phase 38.1 D-15/D-17) | **PASS** |
| `tests/test_ast_regression.py::TestPhase39DriftCases` (Phase 39 D-11/D-12) | **2/2 PASS** |
| `tests/test_drift_wiring.py` + `tests/test_drift_resource.py` | **PASS** (88/88 across drift suites) |
| Full unit sweep (`-m "not integration"`) | **841 passed, 15 skipped, 25 deselected** |

## Quality Gates

- `uv run pytest -m "not integration" --no-cov` — **841 passed, 15 skipped, 25 deselected** (9.19s)
- `uv run mypy src/homelab_mcp/drift_detection.py` — **clean**
- `uv run ruff check src/homelab_mcp/drift_detection.py tests/test_drift_detection.py tests/test_ast_regression.py tests/conftest.py` — **clean**
- `uv run bandit -r src/homelab_mcp/drift_detection.py` — **0 high/medium/low issues**

**Out-of-scope ruff/mypy noise:** `uv run ruff check src/ tests/` reports 9 pre-existing F401/F541/UP037 issues in `tests/test_credentials_cli.py`, `tests/test_credential_store.py`, and `tests/test_ast_regression.py` (lines unrelated to Phase 39 additions). `uv run mypy src/` reports 1 pre-existing `import-untyped` for jsonschema in `openapi_app.py`. Neither set is touched by Plan 03 — flagged for backlog cleanup, NOT introduced by this plan.

## Phase ROADMAP Success Criteria

| Criterion | Test Evidence | Status |
|-----------|---------------|--------|
| 1. Detect unknown infrastructure (DRFT-17) | Plan 02 `TestPhase39Unknown` (5 tests, all GREEN) | ✓ PASS |
| 2. Detect missing infrastructure (DRFT-18) | Plan 03 `TestPhase39Missing::test_old_last_seen_promotes_to_missing` etc. (4 tests, all GREEN) | ✓ PASS |
| 3. Detect changed infrastructure (DRFT-19) | Plan 03 `TestPhase39Changed::test_kernel_change_in_changed_bucket` etc. (5 tests, all GREEN) | ✓ PASS |
| 4. Bucket priority + scanned invariant (D-10) | `TestPhase39Bucket` (3 tests, all GREEN) | ✓ PASS |

**Phase 39 goal satisfied — all three drift cases live end-to-end.**

## Deviations from Plan

### [Rule 1 — Bug] `_enumerate_proxmox_vms` only consumed `probed_ok`, not `changed`

- **Found during:** Task 3 GREEN — `TestPhase39Bucket::test_changed_host_with_unknown_vms` failed with `counts.unknown == 0` instead of 1.
- **Issue:** Plan 02 wired `cluster_vm_map = await _enumerate_proxmox_vms(probed_ok, session)`. Once Plan 03 starts routing hosts to `changed[]`, those hosts (which DID succeed `/cluster/status`) no longer feed VM enumeration — their VMs become invisible to `unknown[]`. This violates D-10 (unknown[] is a parallel per-VM surface independent of host bucket).
- **Fix:** Changed call site to `_enumerate_proxmox_vms(probed_ok + changed, session)`. Both bucket lists hold hosts that successfully responded to `/cluster/status`; both contribute to enumeration.
- **Why this is safe:** A `changed[]` host is by definition reachable AND has the same hostname/connection_ip shape as `probed_ok[]` (the dict shapes are compatible — `_enumerate_proxmox_vms` only reads `record["hostname"]`). De-dupe via `_HOST_CLUSTER_CACHE` still applies.
- **Files modified:** `src/homelab_mcp/drift_detection.py` (within commit `30cb0e7`)
- **Tracked as:** `[Rule 1 — Bug]` Auto-fix to satisfy D-10 invariant.

### [Rule 2 — Critical functionality] `_classify_unreachable` applied to BOTH unreachable branches, not just inner

- **Found during:** Task 3 implementation — code-reading the row loop.
- **Issue:** Plan's `<behavior>` only mandated `_classify_unreachable` on the inner `/cluster/status` failure branch. The outer "resolver-during-cluster-walk failure" branch (at the original lines 570–582) also routes to unreachable; if a sitemap-known host's resolver fails AND its last_seen is 12d old, the user should still see the missing promotion.
- **Fix:** Both unreachable branches now call `_classify_unreachable(row, exc, _missing_threshold_days(), datetime.now(UTC))`. Symmetric routing across both probe-failure paths.
- **Why this is safe:** Per Phase 39 D-01, `missing` is a sub-status of `unreachable` triggered by `last_seen + threshold`. The two branches catch the same exception types (`aiohttp.ClientError, TimeoutError, ValueError`), so calling the same classifier on both is correctness-preserving — there's no semantic distinction between "host can't be resolved any more" and "host was resolvable but probe just failed" for the missing question.
- **Files modified:** `src/homelab_mcp/drift_detection.py` (within commit `30cb0e7`)
- **Tracked as:** `[Rule 2 — Critical functionality]` Uniform missing-promotion across both probe-failure exits.

### [Rule 3 — Blocker fix] Defensive fallthrough return in `_probe_one`

- **Found during:** Task 2 GREEN — mypy strict reported `error: Missing return statement [return]` on the inner `_probe_one(row)` function.
- **Issue:** Mypy couldn't prove the `async with semaphore:` + nested `async with await ssh_connect(...) as conn:` block exhaustively returns. The try-block's success path returns; both except branches return; but mypy can't prove `__aexit__` won't swallow.
- **Fix:** Added a defensive `return (hostname, {"_error": "unreachable_fallthrough"})` after the `async with semaphore:` block. Documented inline as unreachable-in-practice.
- **Why this is safe:** Cannot execute at runtime — every code path inside the `with` block returns. The fallthrough is purely a typing dance; the `_error` key consistency means callers handle it identically to other failure modes.
- **Files modified:** `src/homelab_mcp/drift_detection.py` (within commit `00ab40e`)
- **Tracked as:** `[Rule 3 — Blocker]` mypy strict satisfaction.

No other deviations.

## Locked Envelope Key Order Preserved

`response` assembly in `scan_drift` continues to set keys in the locked Phase 38.1 D-08 order:
`status → scan_timestamp → scanned → counts → [guidance] → probed_ok → unreachable → not_eligible → unknown → changed`

Verified by inspection — assignment order around lines 781–795 unchanged from Phase 38.1.

## Commit Hashes

| # | Type | Commit | Description |
|---|------|--------|-------------|
| 1 | RED | `a93fab5` | `test(39-03): wave 0 RED tests for missing/changed buckets + AST guard` |
| 2 | Feature | `00ab40e` | `feat(39-03): add _bulk_universal_core_probes SSH pre-pass with 120s outer timeout` |
| 3 | Feature | `30cb0e7` | `feat(39-03): wire DRFT-18 missing + DRFT-19 changed into scan_drift row loop` |

## Files Modified

- `src/homelab_mcp/drift_detection.py` — added imports (asyncssh, ssh_connect, _probe_universal_core, resolve_ssh_credentials); added `_bulk_universal_core_probes` helper (lines 327–395); added 120s outer wait_for around SSH pre-pass call (lines 511–520); modified both unreachable branches in row loop to use `_classify_unreachable`; modified success branch to consult `ssh_probe_results` and route to `changed[]` vs `probed_ok[]` via `_diff_fingerprints`; widened `_enumerate_proxmox_vms` call to consume `probed_ok + changed`.
- `tests/test_drift_detection.py` — appended `TestPhase39Missing` (4 tests), `TestPhase39Changed` (5 tests), `TestPhase39Bucket` (3 tests).
- `tests/test_ast_regression.py` — appended `TestPhase39DriftCases` class (`PHASE_39_NEW_HELPERS` tuple + `test_phase39_helpers_no_continue` + `test_phase381_d15_still_green` sibling guard).

## Self-Check: PASSED

Verified files exist on disk:
- `.planning/phases/39-drift-detection-cases/39-03-SUMMARY.md` — FOUND (this file)
- `src/homelab_mcp/drift_detection.py::_bulk_universal_core_probes` — FOUND (line 327)
- `tests/test_drift_detection.py::TestPhase39Missing` — FOUND
- `tests/test_drift_detection.py::TestPhase39Changed` — FOUND
- `tests/test_drift_detection.py::TestPhase39Bucket` — FOUND
- `tests/test_ast_regression.py::TestPhase39DriftCases` — FOUND

Verified commits exist in git log:
- `a93fab5` — FOUND (RED tests commit)
- `00ab40e` — FOUND (SSH pre-pass commit)
- `30cb0e7` — FOUND (row-loop wiring commit)
