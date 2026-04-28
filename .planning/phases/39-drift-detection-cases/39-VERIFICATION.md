---
phase: 39-drift-detection-cases
verified: 2026-04-27T12:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 39: Drift Detection Cases Verification Report

**Phase Goal:** A user running `scan_infrastructure_drift` after a real-world change — a manually-created VM, an offline NAS, a kernel update that regressed Vulkan support — sees that change reported as drift, classified into the right bucket.
**Verified:** 2026-04-27T12:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Manually-created VM appears in **unknown** bucket with host node, VMID, and `discover_and_map` adoption pointer (DRFT-17) | VERIFIED | `_enumerate_proxmox_vms` + `_enumerate_unknown_vms` wired post-loop in `scan_drift` (drift_detection.py:705-706); per-VM record carries `hypervisor_hostname`, `node`, `vmid`, `vm_type`, `vm_name`, `vm_status`, `scan_timestamp`, `message` containing `discover_and_map` (drift_detection.py:252-265). Test `TestPhase39Unknown::test_unmatched_vm_in_unknown_bucket` GREEN. |
| 2 | Sitemap-known host that stops responding lands in **missing** sub-status of `unreachable[]` with `last_seen` and `decommission_device`/`purge_failed_discoveries` pointers (DRFT-18) | VERIFIED | `_classify_unreachable` returns `("missing", message)` when `last_seen > threshold_days`; called from BOTH unreachable branches (drift_detection.py:570-585, 676-691); message references both `decommission_device` and `purge_failed_discoveries` (lines 189-193). Test `TestPhase39Missing::test_old_last_seen_promotes_to_missing` GREEN. |
| 3 | Host whose kernel/package fingerprint differs from stored row lands in **changed[]** with per-field diff (DRFT-19) | VERIFIED | `_diff_fingerprints` walks `s.keys() & c.keys()` recursively emitting dotted-path → `{stored, current}` pairs (drift_detection.py:198-223); consumed in success branch (lines 631-660); diff non-empty → `changed.append(...)` with `changed_fields` key. Test `TestPhase39Changed::test_kernel_change_in_changed_bucket` asserts `changed_fields["kernel_version"] == {"stored": "6.5.13-1-pve", "current": "6.8.4-2-pve"}` GREEN. |
| 4 | Unknown via Proxmox API; missing/changed via SSH probes wrapped in `_run_with_timeout(10s)`; bulk scan does not hang past timeout | VERIFIED | `_enumerate_proxmox_vms` calls `client.get("/cluster/resources")` (drift_detection.py:312); `_bulk_universal_core_probes` uses `Semaphore(10)` + `asyncio.gather` + per-host `asyncio.wait_for(45.0)` (drift_detection.py:348, 368-371); outer `asyncio.wait_for(_bulk_universal_core_probes, timeout=120.0)` in `scan_drift` (drift_detection.py:518-526); `_probe_universal_core` wraps each of 4 probes (`uname -s`, `uname -r`, `cat /etc/os-release`, dpkg fingerprint) in `_run_with_timeout` (ssh_tools.py:451, 461, 473, 505). |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/homelab_mcp/ssh_tools.py::_probe_universal_core` | Phase 38 D-04 universal-core probe extracted as reusable async helper | VERIFIED | Defined at line 435; 4 `_run_with_timeout` calls inside body; called from `ssh_discover_system` at line 703. |
| `src/homelab_mcp/drift_detection.py::_diff_fingerprints` | Recursive walk emitting dotted-path leaf diffs | VERIFIED | Defined at line 198; only diffs `s.keys() & c.keys()` per D-09a. |
| `src/homelab_mcp/drift_detection.py::_classify_unreachable` | Routes probe failures to `unreachable` vs `missing` sub-status | VERIFIED | Defined at line 170; returns `("missing", msg)` or `("unreachable", sanitize_error(exc))`. Message references `decommission_device` and `purge_failed_discoveries`. |
| `src/homelab_mcp/drift_detection.py::_enumerate_unknown_vms` | Builds per-VM unknown[] rows with case-insensitive sitemap match | VERIFIED | Defined at line 226; case-insensitive match via `name.lower() in sitemap_hostnames`. |
| `src/homelab_mcp/drift_detection.py::_enumerate_proxmox_vms` | `/cluster/resources` enumeration with cluster_name de-dupe | VERIFIED | Defined at line 273; uses `_HOST_CLUSTER_CACHE`; loop-free de-dupe via `{(c or h): (h, c) for h, c in pairs}`. |
| `src/homelab_mcp/drift_detection.py::_bulk_universal_core_probes` | SSH pre-pass with Semaphore(10) + gather + per-host 45s | VERIFIED | Defined at line 327; Semaphore(10) at line 348; `asyncio.wait_for(..., timeout=45.0)` at line 368. |
| `src/homelab_mcp/drift_detection.py::_missing_threshold_days` | Env-var threshold clamp | VERIFIED | Defined at line 141; default 7; falls back to default on garbage. |
| `src/homelab_mcp/drift_detection.py::_parse_last_seen` | Naive-isoformat → UTC-aware datetime | VERIFIED | Defined at line 154. |
| `tests/conftest.py` | 9 shared Phase 39 fixtures | VERIFIED | 9 `@pytest.fixture` decorators present (verified via grep). |
| `tests/test_drift_detection.py::TestPhase39Helpers` | ≥15 helper unit tests | VERIFIED | 15 tests, all PASS. |
| `tests/test_drift_detection.py::TestPhase39Unknown` | DRFT-17 functional tests | VERIFIED | 5 tests, all PASS. |
| `tests/test_drift_detection.py::TestPhase39Missing` | DRFT-18 functional tests | VERIFIED | 4 tests, all PASS. |
| `tests/test_drift_detection.py::TestPhase39Changed` | DRFT-19 functional tests | VERIFIED | 5 tests, all PASS. |
| `tests/test_drift_detection.py::TestPhase39Bucket` | D-10 invariant tests | VERIFIED | 3 tests, all PASS. |
| `tests/test_ast_regression.py::TestPhase39DriftCases` | AST guard for new helpers' loop-free invariant | VERIFIED | 2 tests, all PASS. `PHASE_39_NEW_HELPERS = ("_diff_fingerprints", "_enumerate_unknown_vms", "_classify_unreachable")`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `ssh_discover_system` | `_probe_universal_core` | function call replacing inline probe block | WIRED | ssh_tools.py:703 — `await _probe_universal_core(conn, timed_out_commands)`. |
| `scan_drift` | `_bulk_universal_core_probes` | async pre-pass before main row loop | WIRED | drift_detection.py:518-526 — wrapped in `asyncio.wait_for(timeout=120.0)`. |
| `scan_drift` row loop | `_diff_fingerprints` | called inside row loop on probe success | WIRED | drift_detection.py:638-642 — diff routes to `changed[]` vs `probed_ok[]`. |
| `scan_drift` row loop | `_classify_unreachable` | called on probe failure | WIRED | Both branches: drift_detection.py:570 (resolver-during-walk failure) and 676 (cluster/status failure). |
| `scan_drift` | `_enumerate_proxmox_vms` | post-loop call consuming `probed_ok + changed` | WIRED | drift_detection.py:705 — feeds `_enumerate_unknown_vms`. |
| `_enumerate_proxmox_vms` | `_HOST_CLUSTER_CACHE` | imported + read for de-dupe | WIRED | drift_detection.py:39 (import), 301 (read). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `scan_drift` `unknown[]` | `unknown` | `_enumerate_unknown_vms(cluster_vm_map, sitemap_hostnames, scan_timestamp)` after `_enumerate_proxmox_vms(probed_ok + changed, session)` actually fetches `/cluster/resources` | Yes — full mock-then-real path verified by `TestPhase39Unknown::test_unmatched_vm_in_unknown_bucket` (counts.unknown == 2; vmid in (110, 200); message contains "discover_and_map"). | FLOWING |
| `scan_drift` `unreachable[]` (missing sub-status) | `record_inner` (and `record` outer branch) | `_classify_unreachable(row, exc, _missing_threshold_days(), datetime.now(UTC))` reads real `row["last_seen"]` and exception | Yes — verified by `TestPhase39Missing::test_old_last_seen_promotes_to_missing` (`status == "missing"`, `last_seen` field present, `decommission_device` in message). | FLOWING |
| `scan_drift` `changed[]` | `changed.append(...)` | `_diff_fingerprints(stored_fp, current_fp)` consumes `ssh_probe_results.get(hostname)` populated by `_bulk_universal_core_probes` | Yes — verified by `TestPhase39Changed::test_kernel_change_in_changed_bucket` (`changed_fields["kernel_version"] == {"stored": "6.5.13-1-pve", "current": "6.8.4-2-pve"}`). | FLOWING |
| Capability-only-stored does NOT diff | `diff` empty when current lacks key | `_diff_fingerprints` walks only `s.keys() & c.keys()` | Yes — verified by `TestPhase39Changed::test_capability_only_in_stored_does_not_diff` (counts.changed == 0). | FLOWING |
| Drift never writes to DB | `db_adapter.update_device_fingerprint.call_count == 0` | No call site in `scan_drift` (verified by code-read) | Yes — verified by `TestPhase39Changed::test_drift_does_not_update_fingerprint`. | FLOWING (read-only by construction) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All Phase 39 functional + AST tests pass | `uv run pytest tests/test_drift_detection.py::TestPhase39Helpers tests/test_drift_detection.py::TestPhase39Unknown tests/test_drift_detection.py::TestPhase39Missing tests/test_drift_detection.py::TestPhase39Changed tests/test_drift_detection.py::TestPhase39Bucket tests/test_ast_regression.py::TestPhase39DriftCases tests/test_ast_regression.py::TestPhase381CredBinding --no-cov` | 36 passed | PASS |
| Full unit suite | `uv run pytest -m "not integration" --no-cov` | 841 passed, 15 skipped, 25 deselected, 1 warning in 8.41s | PASS |
| Phase 38.1 D-15 AST guard preserved (no `continue` in `scan_drift` row loop) | `uv run pytest tests/test_ast_regression.py::TestPhase381CredBinding::test_scan_drift_no_continue_in_row_loop_phase38_1` | PASSED | PASS |
| Phase 39 D-11(b) AST guard (no `continue` in 3 named helpers) | `uv run pytest tests/test_ast_regression.py::TestPhase39DriftCases::test_phase39_helpers_no_continue` | PASSED | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DRFT-17 | 39-01, 39-02, 39-03 | Detect unknown infrastructure (manually-created VM) | SATISFIED | `unknown[]` populated post-loop via `/cluster/resources`; `TestPhase39Unknown` (5 tests GREEN). |
| DRFT-18 | 39-01, 39-03 | Detect missing infrastructure (offline host) | SATISFIED | `missing` sub-status of `unreachable[]` via `_classify_unreachable`; `TestPhase39Missing` (4 tests GREEN). |
| DRFT-19 | 39-01, 39-03 | Detect changed infrastructure (kernel/package change) | SATISFIED | `changed[]` populated via `_diff_fingerprints`; `TestPhase39Changed` (5 tests GREEN). |

No orphaned requirements — REQUIREMENTS.md lists DRFT-17/18/19 as "Phase 39 / pending" and all three are claimed by Plans 39-01/02/03.

### Anti-Patterns Found

(Sourced from `.planning/phases/39-drift-detection-cases/39-REVIEW.md` — these are advisory and do NOT block goal achievement; they feed `/gsd-code-review-fix`.)

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| drift_detection.py | 391-395 | Duplicate-hostname rows collapse SSH probe results in `dict(pairs)` | BLOCKER (review) | Phantom changed entries when sitemap has duplicate hostnames; advisory. |
| drift_detection.py | 255 | `int(vm.get("vmid", 0))` can raise on malformed Proxmox payload | BLOCKER (review) | Single garbage VM record could abort whole scan; advisory. |
| drift_detection.py | 296-307 | Cold `_HOST_CLUSTER_CACHE` defeats cluster de-dupe (5 calls instead of 1) | BLOCKER (review) | Server-restart scan duplicates unknown VM emissions; advisory. |
| drift_detection.py | 317-319 | Enumeration failures swallowed at `logger.debug`; invisible in production | BLOCKER (review) | Operators can't see broken enumeration; advisory. |
| drift_detection.py | 583, 689 | `record["last_seen"]` may pass non-string types unchanged | WARNING (review) | Postgres datetime objects break JSON serialization; advisory. |
| drift_detection.py | 476-485 | Per-row `unreachable` shape doc says 7 keys; missing-records have 9 | WARNING (review) | Docstring drift; advisory. |
| drift_detection.py | 154-167 | `_parse_last_seen` treats naive timestamps as UTC; sitemap writes local time | WARNING (review) | Threshold ± machine TZ offset; advisory. |
| drift_detection.py | 387-389 | Dead "defensive fallthrough" return in `_probe_one` | WARNING (review) | Dead code; advisory. |
| drift_detection.py | 213-223 | `_diff_fingerprints` skips current-only keys | WARNING (review) | Newly-appearing fields produce no first-scan signal; advisory. |
| drift_detection.py | 586-691 | `scope`/`cluster_name` reused across iterations on shared try/else | WARNING (review) | Fragile but not a correctness bug today; advisory. |
| drift_detection.py | 187 | `.days >` floors threshold semantics off-by-23h59m | WARNING (review) | Operators with `THRESHOLD=1` see ~47h promotion; advisory. |
| drift_detection.py | 517-526 | SSH pre-pass runs before degenerate-row routing | WARNING (review) | Degenerate row with stale credential triggers SSH connect attempt; advisory. |

These review findings will be addressed by `/gsd-code-review-fix`. They do NOT block the phase goal — every ROADMAP success criterion is met by the current implementation as verified by 36 GREEN tests.

### Human Verification Required

None. All 4 ROADMAP success criteria have programmatic test evidence:
- DRFT-17 unknown bucket → 5 functional tests covering case-insensitive match, cluster de-dupe, enumeration-failure isolation, parallel surface independence.
- DRFT-18 missing sub-status → 4 functional tests covering threshold default/override/invalid + recent-not-promoted.
- DRFT-19 changed bucket → 5 functional tests covering kernel diff, identical-no-diff, capability-one-sided, dotted-path, drift-never-writes.
- Bucket invariants + timeout pattern → 3 invariant tests + 2 AST guards + per-probe `_run_with_timeout(10s)` verified by code-read.

### Gaps Summary

No gaps. The phase goal is achieved end-to-end:

1. **DRFT-17 unknown** — `/cluster/resources` enumeration with cluster-name de-dupe surfaces unmatched VMs in `unknown[]` carrying `discover_and_map` adoption pointer.
2. **DRFT-18 missing** — `last_seen + threshold` classification routes stale unreachable hosts to `status="missing"` with `decommission_device`/`purge_failed_discoveries` recovery.
3. **DRFT-19 changed** — Per-leaf dotted-path fingerprint diff routes hosts with regressed/changed kernel/OS/package to `changed[]` with `changed_fields` dict-of-dicts.
4. **Bulk-scan timeout pattern** — Every SSH probe wrapped in `_run_with_timeout(10s)` (Phase 35 D-05), per-host `wait_for(45s)`, bulk pre-pass `wait_for(120s)` ceiling.

Drift remains read-only against the device fingerprint (D-04b) and the Phase 38.1 D-15 row-loop "no continue" AST guard remains GREEN.

A separate code review (`39-REVIEW.md`) found 4 BLOCKER + 8 WARNING quality/robustness issues in the implementation that should be addressed before shipping (duplicate-hostname collisions, malformed payload coercion, cold-cache de-dupe, log-level for enumeration failures, etc.). These are advisory at the goal-achievement gate — the phase ROADMAP goal is achieved; those issues feed `/gsd-code-review-fix` next.

---

_Verified: 2026-04-27T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
