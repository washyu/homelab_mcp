---
phase: 39-drift-detection-cases
plan: 02
subsystem: drift-detection
tags: [drift, unknown-vm, proxmox-api, cluster-resources, drft-17, wave-2]
dependency_graph:
  requires:
    - "Phase 39 Plan 01 helpers (_enumerate_unknown_vms, _HOST_CLUSTER_CACHE wiring already in place)"
    - "Phase 38.1 D-15 AST guard (no continue in scan_drift row loop)"
    - "Phase 38.1 D-08 locked envelope key order"
  provides:
    - "_enumerate_proxmox_vms (drift_detection.py async helper)"
    - "scan_drift unknown[] population — DRFT-17 closed end-to-end"
    - "TestPhase39Unknown class (5 functional tests)"
  affects:
    - "scan_drift docstring (Returns block + per-VM record shape doc)"
    - "TestScanDrift4Bucket node-filter assertions loosened to host-set checks"
tech_stack:
  added: []
  patterns:
    - "Loop-free dict-comprehension de-dupe by cluster_name"
    - "asyncio.gather across cluster targets — bounded by typical 1-3 clusters in homelab"
    - "Enumeration failure isolation — try/except returns (host, []) so probed_ok placement is preserved"
key_files:
  created:
    - ".planning/phases/39-drift-detection-cases/39-02-SUMMARY.md"
  modified:
    - "src/homelab_mcp/drift_detection.py"
    - "tests/test_drift_detection.py"
decisions:
  - "_HOST_CLUSTER_CACHE is dict[str, str] (hostname → cluster_name), not the dict[str, tuple[str, str|None]] shape sketched in the plan's <interfaces> block. Looked up directly via _HOST_CLUSTER_CACHE.get(hostname); standalone hosts get None back and key off themselves in the de-dupe dict."
  - "asyncio.gather across cluster targets without a Semaphore — homelabs typically have 1-3 clusters, so bounding fanout would be over-engineered. Phase 35 D-02's Semaphore(10) is for SSH probes (potentially dozens of hosts), not cluster enumeration."
  - "TestScanDrift4Bucket node-filter assertions loosened from called_hosts == [...] to set(called_hosts) == {...}. The Phase 37 invariant being protected is 'filtered-out rows are never probed'; the call count is now an implementation detail (probed_ok hosts get a second call from the post-loop /cluster/resources pre-pass)."
  - "CredentialNotFoundError added to the enumeration except clause alongside aiohttp.ClientError / TimeoutError / ValueError. The post-loop helper re-invokes get_proxmox_client; on a flaky keyring backend that succeeded the row-loop call but fails the second call, the host stays in probed_ok with empty unknown[] rather than crashing the scan."
metrics:
  duration: "~30 minutes"
  completed_date: "2026-04-27"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  test_count: 5
  test_class: "TestPhase39Unknown"
requirements:
  - DRFT-17
---

# Phase 39 Plan 02: Unknown VM Detection (DRFT-17) Summary

Wired `/cluster/resources`-based unknown-VM detection into `scan_drift` via a new async `_enumerate_proxmox_vms` helper that runs as a post-row-loop pre-pass, de-dupes per cluster_name through `_HOST_CLUSTER_CACHE`, and feeds matched results through Plan 01's `_enumerate_unknown_vms` to populate the previously-empty `unknown[]` bucket. A user creating a VM directly in the Proxmox UI now sees it surface in their next drift scan with a `discover_and_map` adoption pointer. All 5 `TestPhase39Unknown` tests GREEN, Phase 36/37/38.1 regression tests stay GREEN, AST guards untouched, mypy/ruff clean.

## Helper Added

### `src/homelab_mcp/drift_detection.py`

| Symbol | Lines | Signature | Returns |
|--------|-------|-----------|---------|
| `_enumerate_proxmox_vms` | 270–322 | `async def _enumerate_proxmox_vms(probed_ok_records: list[dict[str, Any]], session: aiohttp.ClientSession \| None)` | `dict[str, list[dict[str, Any]]]` (representative_hostname → vm_records) |

**Imports added:**
- `import asyncio` (top of module)
- `_HOST_CLUSTER_CACHE` joined the existing `from .proxmox_api import (...)` block

**De-dupe shape (D-05 / D-11(b) clean):**

```python
pairs = [(record["hostname"], _HOST_CLUSTER_CACHE.get(record["hostname"]))
         for record in probed_ok_records if record.get("hostname")]
targets = list({(c or h): (h, c) for h, c in pairs}.values())  # one per cluster_name OR hostname
```

A 5-node Proxmox cluster sharing `cluster_name="homelab-prod"` yields exactly ONE call to `/cluster/resources` (verified by `test_cluster_dedup_single_enumeration`'s call counter).

## scan_drift Edits (no row-loop changes)

| Line range | Change |
|------------|--------|
| 27–43 (imports) | Added `import asyncio`; added `_HOST_CLUSTER_CACHE` to the `proxmox_api` import block. |
| 411 (var decl comment) | Updated `unknown` declaration comment from "reserved for Phase 39 DRFT-17" to "Phase 39 DRFT-17: populated by post-loop enumeration". |
| 553–565 | NEW post-row-loop pre-pass (10 lines): build `sitemap_hostnames` set, call `_enumerate_proxmox_vms(probed_ok, session)`, call `_enumerate_unknown_vms(...)`. |
| Docstring (~390-410) | Updated `Returns` block: removed "always 0 in Phase 38.1" for `unknown`, added per-VM record shape doc per D-07. |

**No edits inside the `for row in rows:` row loop.** Phase 38.1 D-15 AST guard stays GREEN — the new code lives between the row-loop close and the counts-dict build.

## TestPhase39Unknown — 5 Tests, All GREEN

| # | Test | Coverage |
|---|------|----------|
| 1 | `test_unmatched_vm_in_unknown_bucket` | D-06 case-insensitive match + D-07 per-VM record shape (4-element `mock_cluster_resources_response` fixture: ubuntu-prod matches; ubuntu-test/pi-hole unmatched; node-type filtered) |
| 2 | `test_cluster_dedup_single_enumeration` | D-05 — 5-node cluster, all bound to same cluster_name → 1 `/cluster/resources` call (call-counter assertion) |
| 3 | `test_case_insensitive_match` | D-06 — VM `Plex-Server` matches sitemap `plex-server` |
| 4 | `test_enumeration_failure_keeps_host_in_probed_ok` | T-39-07 / D-10 — `aiohttp.ClientError` on `/cluster/resources` does NOT degrade host bucket |
| 5 | `test_unknown_independent_of_host_bucket` | D-10 — probed_ok host can simultaneously contribute unknown[] entries |

**RED stage:** 3/5 tests failed RED on the empty unknown[] bucket; 2/5 (case-insensitive match, enumeration-failure isolation) trivially passed pre-implementation because their assertions hold in both empty- and populated-bucket worlds. Both protect correctness invariants under the new code path. The 3-test RED was sufficient signal that the helper genuinely did not yet exist.

## Cluster De-dupe Verification

Test 2 instruments the mock `client.get` with a closure-scoped counter that increments only when `path == "/cluster/resources"`. With 5 sitemap rows pre-seeded into `_HOST_CLUSTER_CACHE` as `{"pve1": "homelab-prod", ..., "pve5": "homelab-prod"}` and the resolver fake returning `("cluster", "homelab-prod")` for every host, the assertion `resources_call_count == 1` passes — confirming D-05's "one call per cluster_name" invariant.

## Regression Status

| Suite | Result |
|-------|--------|
| `tests/test_drift_detection.py::TestPhase39Unknown` | **5/5 PASS** |
| `tests/test_drift_detection.py::TestScanDrift4Bucket` | **PASS** (after node-filter assertion loosening) |
| `tests/test_drift_detection.py::TestScanDriftNotEligible` | **PASS** |
| `tests/test_drift_detection.py::TestPhase39Helpers` | **PASS** (15/15) |
| `tests/test_ast_regression.py::TestPhase381CredBinding` | **PASS** (D-15 row-loop continue guard untouched) |
| Full unit sweep (`tests/ -m "not integration"`) | **827 passed, 15 skipped** |
| `mypy src/homelab_mcp/drift_detection.py` | **clean** |
| `ruff check src/homelab_mcp/drift_detection.py tests/test_drift_detection.py` | **clean** |

## Deviations from Plan

### [Rule 3 — Blocker fix] `_HOST_CLUSTER_CACHE` actual shape vs plan's interface block

- **Found during:** Task 2 implementation (read `src/homelab_mcp/proxmox_api.py:22`)
- **Issue:** Plan's `<interfaces>` block declared `_HOST_CLUSTER_CACHE: dict[str, tuple[str, str | None]]` (hostname → (scope, cluster_name)). Actual production code is `dict[str, str]` (hostname → cluster_name) at `proxmox_api.py:22`. The tuple-shaped cache is the SEPARATE `_RESOLUTION_TELEMETRY_CACHE` keyed on `(host, credential_id)`.
- **Fix:** Look up cluster_name directly via `_HOST_CLUSTER_CACHE.get(hostname)`; the result is `str | None`. The plan's recommended dict-comprehension de-dupe (`{(c or h): (h, c) for h, c in pairs}`) works unchanged with the simpler shape.
- **Files modified:** `src/homelab_mcp/drift_detection.py` (within commit `e05df24`)

### [Rule 1 — Bug] TestScanDrift4Bucket node-filter assertions over-strict for Phase 39

- **Found during:** Task 2 GREEN regression sweep
- **Issue:** `test_node_filter_exact_hostname_match` and `test_node_filter_none_means_no_filter` asserted `called_hosts == ["pve1"]` / `sorted(called_hosts) == ["pve1", "pve2"]`. Phase 39's post-row-loop pre-pass adds a second `get_proxmox_client` call per probed_ok host (for `/cluster/resources`), so a single-row scan now records `["pve1", "pve1"]` and a 2-row scan records 4 entries.
- **Fix:** Loosened both assertions from list-equality to set-equality — the Phase 37 invariant being protected is "filtered-out rows are never probed", which the set check preserves. Added an inline comment explaining the Phase 39 cause.
- **Why this is safe:** No filter-leak regression possible (filtered-out hosts would still appear in the set); the test's original intent is intact.
- **Files modified:** `tests/test_drift_detection.py` (within commit `e05df24`)

### [Rule 2 — Critical functionality] CredentialNotFoundError caught in enumeration

- **Found during:** Task 2 implementation (writing `_enum_one`)
- **Issue:** Plan's recommended except clause was `(aiohttp.ClientError, TimeoutError, ValueError)`. The post-loop helper re-invokes `get_proxmox_client`, which can raise `CredentialNotFoundError` on a flaky keyring backend (the row-loop's first call already succeeded, so the host is in probed_ok — but the second call could fail).
- **Fix:** Added `CredentialNotFoundError` to the except tuple so an unlikely flake degrades gracefully (returns empty VM list for that host) rather than crashing the scan.
- **Why this is safe:** Treating credential resolution failure as an enumeration failure on the second attempt is consistent with D-10 ("enumeration failure isolated; host stays in probed_ok"). The first-call success already guarantees the credentials work; the failure mode this catches is purely defensive.
- **Files modified:** `src/homelab_mcp/drift_detection.py` (within commit `e05df24`)

No other deviations.

## AST Guard Verification

| Guard | Source | Status |
|-------|--------|--------|
| Phase 38.1 D-15 — `test_scan_drift_no_continue_in_row_loop_phase38_1` | `tests/test_ast_regression.py:763` | **GREEN** (scan_drift row loop body unmodified) |
| Phase 38.1 D-17 — `test_drift_loop_routes_degenerate_to_not_eligible_phase38_1` | `tests/test_ast_regression.py:808` | **GREEN** (`not_eligible.append` calls unchanged) |
| Phase 39 D-12 — `_enumerate_proxmox_vms` outside guard scope | guard targets `n.name == "scan_drift"` only | **GREEN** by construction — sibling helpers are not walked |

The new helper contains a `for record in probed_ok_records:` loop with a `continue` for empty-hostname guard. This loop builds enumeration TARGETS (does not iterate sitemap rows feeding bucket appends), so it is OUTSIDE the AST guard's targeted scope per D-12. Plan 03 explicitly enumerates Phase 39 helpers under a new `TestPhase39DriftCases` AST guard if needed.

## Locked Envelope Key Order Preserved

`response` assembly in `scan_drift` continues to set keys in the locked Phase 38.1 D-08 order:
`status → scan_timestamp → scanned → counts → [guidance] → probed_ok → unreachable → not_eligible → unknown → changed`

Verified by inspection — the assignment order around lines 596–608 is unchanged from Phase 38.1.

## Commit Hashes

| # | Type | Commit | Description |
|---|------|--------|-------------|
| 1 | RED | `4253e4b` | `test(39-02): wave 0 RED tests for unknown VM detection (DRFT-17)` |
| 2 | Feature | `e05df24` | `feat(39-02): wire DRFT-17 unknown VM detection via /cluster/resources de-dupe` |

## Files Modified

- `src/homelab_mcp/drift_detection.py` — added `import asyncio` + `_HOST_CLUSTER_CACHE` import; added `_enumerate_proxmox_vms` helper (lines 270–322); added post-row-loop unknown enumeration block in `scan_drift` (lines 553–565); updated docstring `Returns` block + per-VM record shape.
- `tests/test_drift_detection.py` — appended `TestPhase39Unknown` class (5 tests) after `TestPhase39Helpers`; loosened two `TestScanDrift4Bucket` node-filter assertions from list-equality to set-equality.

## Self-Check: PASSED

Verified files exist on disk:
- `.planning/phases/39-drift-detection-cases/39-02-SUMMARY.md` — FOUND (this file)
- `src/homelab_mcp/drift_detection.py::_enumerate_proxmox_vms` — FOUND (line 270)
- `tests/test_drift_detection.py::TestPhase39Unknown` — FOUND

Verified commits exist in git log:
- `4253e4b` — FOUND (RED test commit)
- `e05df24` — FOUND (GREEN feature commit)
