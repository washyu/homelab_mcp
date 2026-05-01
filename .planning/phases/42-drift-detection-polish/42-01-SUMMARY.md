---
phase: 42-drift-detection-polish
plan: 01
subsystem: drift-detection
tags: [drift, sitemap, polish, audit, B1, B2, B3, B4, W1, W2, W3, W4, W5, W6, W7, W8]
dependency_graph:
  requires:
    - .planning/phases/39-drift-detection-cases/39-REVIEW.md (B1-B4, W1-W8 findings)
    - .planning/phases/39-drift-detection-cases/39-REVIEW-FIX.md (re-review notes)
    - Phase 41-04/06 host=hostname / dial_host=connection_ip split
  provides:
    - "_bulk_universal_core_probes returns dict[tuple[str, str | None], dict] keyed on (hostname, ssh_credential_id)"
    - "scan_drift consumer site reads probe via (hostname, ssh_credential_id) tuple lookup (no phantom changed[])"
    - "sitemap.py last_seen writers emit datetime.now(UTC).isoformat() at both sites"
    - "_probe_one mypy-clean without dead sentinel return; defensive AssertionError raises loudly"
    - "_make_row malformed-vmid log upgraded to logger.warning with VM name context"
  affects:
    - Phase 42 Plan 02 (regression tests will exercise the (hostname, ssh_credential_id) tuple key + B3 dedupe layers + W2 UTC writer + W6 inner-except scope reset)
    - Phase 42 Plan 03 (full quality gate — full pytest run; this plan deferred test execution)
tech_stack:
  added: []
  patterns:
    - "tuple-keyed result map for credential-aware multi-result attribution"
    - "raise AssertionError sentinel for mypy exhaustiveness on async-with control flow"
    - "logger.warning over logger.debug for per-record skip events that affect drift coverage"
key_files:
  created: []
  modified:
    - src/homelab_mcp/drift_detection.py
    - src/homelab_mcp/sitemap.py
decisions:
  - "B1 chose tuple key (hostname, ssh_credential_id) over hostname-only dedupe-and-drop, preserving probe attribution for legitimately-duplicate hostnames with distinct credentials"
  - "B3 verified-already-done (no source change) — three existing dedupe layers deliver the truth without a warm-up loop"
  - "W4 chose raise AssertionError over silent sentinel return per 39-REVIEW WR-B (loud-fail beats poison probe map)"
  - "W2 scoped UTC writer change to last_seen= sites only (lines 95+101, 168+178); stored_at/completed_at at lines 544/624 left untouched per plan scope"
metrics:
  duration: 357
  completed: 2026-05-01
---

# Phase 42 Plan 01: Drift Detection Polish — Source Changes Summary

Applied all 12 advisory fixes from `.planning/phases/39-drift-detection-cases/39-REVIEW.md` (B1-B4, W1-W8) to `drift_detection.py` and `sitemap.py`. Four are real source edits (B1 multi-result attribution, B2 log-level upgrade, W2 canonical UTC writer, W4 dead-code removal); the remaining eight are verified-already-done audits with grep evidence.

## One-liner

Phase 42 Plan 01 lands the still-outstanding polish fixes — B1 tuple-keyed probe map, B2 warning-level malformed-vmid log, W2 canonical UTC writer in sitemap.py, W4 dead sentinel return removal — and audits the partially-already-done findings (B3, B4, W1, W3, W5, W6, W7, W8) so the source matches the 39-REVIEW intent.

## Findings Disposition Table

| ID | Disposition | Site | Evidence |
| --- | --- | --- | --- |
| B1 | **fixed** | drift_detection.py:514-602, 939, 768 | `_bulk_universal_core_probes` re-keyed to `dict[tuple[str, str \| None], dict]`; consumer site `ssh_probe_results.get((hostname or "", row.get("ssh_credential_id")), {})` at line 994; `seen_hostnames` set replaced by `seen_keys: set[tuple[str, str \| None]]`; type annotation at scan_drift line 768 widened to match new return type. |
| B2 | **log-upgrade** | drift_detection.py:347-352 | `logger.debug` → `logger.warning` with VM name context for malformed-vmid skip in `_make_row`. |
| B3 | **verified-already-done** (no source change) | drift_detection.py:365, 435; proxmox_api.py:424 | Three dedupe layers deliver the truth without a warm-up loop — see grep snippets below. |
| B4 | **verified-already-done** | drift_detection.py:464-468 | `_enum_one` already uses `logger.warning` with sanitize_error and host context. |
| W1 | **verified-already-done** | drift_detection.py:862-869, 944-951, 1049-1056 | Three sites use byte-identical 3-branch coercion (modulo `_r` / `_inner` suffixes). `grep -c raw_last_seen` returns 9 (3 sites × 3 references). |
| W2 | **fixed** | sitemap.py:7, 101, 178 | Import upgraded to `from datetime import UTC, datetime`; both `last_seen=` writers now emit `datetime.now(UTC).isoformat()`. drift_detection.py `_parse_last_seen` docstring updated to mark WR-03 imprecision RESOLVED at the writer side, with legacy-row backward-compat note retained. |
| W3 | **clarified** | drift_detection.py:701, 715-718 | Docstring already documented 7-key + 9-key shapes; added a one-line summary listing all four tokens (last_seen + scan_timestamp + missing + message) so the cross-site invariant is greppable. Cross-site invariant notes that all three missing emission sites emit the same shape. |
| W4 | **fixed** | drift_detection.py:566-579 | `probe_one_unreachable_fallthrough` sentinel return DELETED. Replaced with `raise AssertionError` outside the `async with semaphore` block (per 39-REVIEW WR-B — loud-fail beats silent sentinel). Mypy `[return]` exhaustiveness check satisfied without poisoning the probe map. |
| W5 | **verified-already-done** | drift_detection.py:234, 244, 269, 281 | `_diff_fingerprints` docstring + inline comments document the WR-05 asymmetric current-only-emit semantic (D-09a — stored-only suppress, current-only emit). |
| W6 | **verified-already-done** | drift_detection.py:782-783 | `scope: str = "unknown"` and `cluster_name: str \| None = None` reset at the top of every row loop iteration. The W6 regression test (Plan 02) must exercise the inner /cluster/status except branch at line 1037+ where `record_inner["scope"] = scope` reads the loop-local; the `not_eligible` branch at 791-800 hardcodes `scope="unknown"` and cannot detect leakage. |
| W7 | **verified-already-done** | drift_detection.py:223 | `_classify_unreachable` already uses `(now - parsed) > timedelta(days=threshold_days)` (second-resolution). `grep .days >\s*threshold_days` returns 0 hits. |
| W8 | **verified-already-done** | drift_detection.py:754-761 | `ssh_eligible_rows` filter excludes hostname None/`''`/`'unknown'` and `status='error'` and missing `ssh_credential_id` BEFORE the bulk probe call. Parity with row-loop degenerate routing at lines 791-800 confirmed. |

## B3 Verified-Already-Done — Grep Evidence

Three layers deliver the "exactly one /cluster/resources call per cluster, exactly one unknown[] entry per VM" truth without a warm-up loop. The original B3 advice would have iterated `probed_ok + changed` calling `_HOST_CLUSTER_CACHE.setdefault(...)` — a no-op because every row in those buckets has already touched `get_proxmox_client(host=hostname, ...)` which writes the cache as a side-effect.

```bash
# Layer 1 — _make_row consumer dedupe by (hypervisor, name.lower(), vmid)
$ grep -nE "key = \(hypervisor, name\.lower\(\), vmid\)" src/homelab_mcp/drift_detection.py
365:        key = (hypervisor, name.lower(), vmid)

# Layer 2 — _enumerate_proxmox_vms cluster-level dedupe by (cluster_name OR hostname)
$ grep -nE "\(c or h\): \(h, ci, c\)" src/homelab_mcp/drift_detection.py
435:    targets = list({(c or h): (h, ci, c) for h, ci, c in pairs}.values())

# Layer 3 — _HOST_CLUSTER_CACHE side-effect populator inside get_proxmox_client
$ grep -nE "_HOST_CLUSTER_CACHE\[" src/homelab_mcp/proxmox_api.py
424:            _HOST_CLUSTER_CACHE[host] = cluster_name
```

No `Phase 42 B3` warm-up comment block was added (`grep -nc "Phase 42 B3" src/homelab_mcp/drift_detection.py` returns 0).

## Cross-Phase Invariant Preservation Evidence

| Invariant | Evidence |
| --- | --- |
| Phase 36 D-12/D-13 (sitemap is single source-of-truth) | `grep -n "db_adapter.get_all_devices" src/homelab_mcp/drift_detection.py` returns 1 hit at line 736; no parallel-table reads added. |
| Phase 38.1 D-15 (no `continue` inside scan_drift's row loop body) | `grep -nE "^\s+continue" src/homelab_mcp/drift_detection.py` returns 1 hit at line 425 — INSIDE `_enumerate_proxmox_vms` (sibling helper), NOT inside scan_drift's row loop. The scan_drift row loop body (lines 775-1058) contains 0 `continue` statements. |
| Phase 39.1 D-16 (credential_id= threading through _enumerate_proxmox_vms._enum_one) | `grep -n "credential_id=binding" src/homelab_mcp/drift_detection.py` returns 2 hits (line 451 inside `_enum_one`, line 822 in scan_drift's row loop) — both unchanged by Phase 42. |
| Phase 41-04/06 host=hostname / dial_host=connection_ip split | scan_drift row loop at line 819-823 still uses `host=hostname, dial_host=dial_host`; `_enum_one` at line 449-453 still uses `host=h, dial_host=dial_host`. No regression. |
| Phase 39 D-11(b) (helpers loop-free w.r.t. bucket appends) | `_bulk_universal_core_probes` re-key did not add bucket-feeding loops; `_make_row` warning-upgrade did not change loop structure. |

## Detailed Source Changes

### B1 — `_bulk_universal_core_probes` tuple-keyed return map

`drift_detection.py` ~70 LOC restructured at lines 472-602:
- Return type widened from `dict[str, dict[str, Any]]` to `dict[tuple[str, str | None], dict[str, Any]]`.
- `_probe_one` builds a per-row `key = (hostname, binding)` and returns `(key, probe_result)` on every code path.
- Pre-gather dedupe replaced: `seen_hostnames: set[str]` → `seen_keys: set[tuple[str, str | None]]`. Two rows sharing a hostname but with distinct `ssh_credential_id` values both contribute probes; two rows with identical `(hostname, ssh_credential_id)` are still deduped (first-seen wins).
- W4 dead sentinel `return (hostname, {"_error": "probe_one_unreachable_fallthrough"})` deleted; replaced with `raise AssertionError(...)` outside the `async with semaphore:` block (mypy-clean, runtime-loud).

scan_drift consumer site at line 994:
```python
# Before:
probe = ssh_probe_results.get(hostname or "", {})
# After:
probe = ssh_probe_results.get((hostname or "", row.get("ssh_credential_id")), {})
```

scan_drift type annotation at line 768:
```python
# Before:
ssh_probe_results: dict[str, dict[str, Any]] = await asyncio.wait_for(...)
# After:
ssh_probe_results: dict[tuple[str, str | None], dict[str, Any]] = await asyncio.wait_for(...)
```

### B2 — `_make_row` malformed-vmid log upgrade

`drift_detection.py:347-352` — `logger.debug` → `logger.warning`, format string extended with VM name (`(VM name=%r)`). Operators now see the skip event in default log streams instead of needing to enable debug-level capture.

### W2 — `sitemap.py` canonical UTC writer

`sitemap.py:7` — import upgraded:
```python
# Before:
from datetime import datetime
# After:
from datetime import UTC, datetime
```

`sitemap.py:95-101` (success branch) and `sitemap.py:168-178` (JSONDecodeError fallback) — both `last_seen=datetime.now().isoformat()` writes upgraded to `last_seen=datetime.now(UTC).isoformat()` with explanatory comment block.

`drift_detection.py:155-194` — `_parse_last_seen` docstring updated:
- WR-03 paragraph marked "RESOLVED at the writer side in Phase 42 W2".
- Added note that legacy pre-Phase-42 rows still parse correctly via the unconditional `replace(tzinfo=UTC)` shim.
- Code unchanged (already handles aware and naive datetimes correctly).

### W3 — Docstring 9-key shape clarification

`drift_detection.py:699-718` — added a one-line summary listing all four tokens (last_seen + scan_timestamp + missing + message) so future grep-based audits land on a single line. Cross-site note added: the 9-key shape applies identically across all three missing emission sites (outer except, transient_resolver_exc fallback, inner except).

### W4 — `_probe_one` dead-code removal

Done as part of B1's restructuring. The `return (hostname, {"_error": "probe_one_unreachable_fallthrough"})` sentinel return at the old line 561 deleted; replaced with `raise AssertionError` at the bottom of `_probe_one` outside the `async with semaphore:` block. Mypy's `[return]` exhaustiveness check satisfied; runtime is structurally unreachable; future refactors that narrow the except clauses will crash loudly inside `asyncio.gather(return_exceptions=False)` rather than silently poisoning the probe map.

## Plan-End Quality Gate

```bash
$ uv run ruff check src/homelab_mcp/drift_detection.py src/homelab_mcp/sitemap.py
All checks passed!

$ uv run mypy src/homelab_mcp/drift_detection.py src/homelab_mcp/sitemap.py
Success: no issues found in 2 source files

$ git diff --stat HEAD~3 HEAD -- src/homelab_mcp/drift_detection.py src/homelab_mcp/sitemap.py
 src/homelab_mcp/drift_detection.py | 146 +++++++++++++++++++++++--------------
 src/homelab_mcp/sitemap.py         |  16 +++-
 2 files changed, 104 insertions(+), 58 deletions(-)
```

Diff confined to the two scoped files, as required by the verification block in the plan.

## Commits

| Task | Commit | Subject |
| --- | --- | --- |
| 1 | `a8a07b0` | fix(42-01): enumeration robustness — B1 multi-result attribution + B2 log upgrade + W4 dead-code removal |
| 2 | `75ceeb9` | fix(42-01): canonical UTC writer + threshold/JSON hygiene — W1 verified, W2 fixed, W7 verified |
| 3 | `632a148` | docs(42-01): docstring sweep — W3 9-key shape clarified, W4/W5/W6 verified |

## Deviations from Plan

**Auto-fixed Issues**

**1. [Rule 1 — Bug] mypy `[return]` error after W4 sentinel deletion**
- **Found during:** Task 1, after deleting `probe_one_unreachable_fallthrough` sentinel return.
- **Issue:** `mypy --strict` flagged `_probe_one` with `Missing return statement [return]`. Ruff was clean but mypy's control-flow analysis on `async with semaphore:` blocks does not deduce that the bare `except Exception` catches every path.
- **Fix:** Used the defensive AssertionError form documented in the plan's W4 action ("If mypy DOES complain (unlikely but possible due to async-with control flow analysis), use this defensive form instead"). Loud-fail beats silent-sentinel — exactly the rationale 39-REVIEW WR-B cited.
- **Files modified:** drift_detection.py:566-579
- **Commit:** `a8a07b0`

**2. [Rule 2 — Missing critical functionality] W3 docstring acceptance grep not satisfied by existing docstring**
- **Found during:** Task 3, running the W3 acceptance criterion `grep -n "last_seen.*scan_timestamp.*missing.*message" src/homelab_mcp/drift_detection.py`.
- **Issue:** The existing docstring at lines 699-708 documents the 9-key shape across multiple lines with intermediate punctuation, so the single-line regex returns no match without `--multiline`. The plan said "currently looks correct — leave untouched", but the acceptance criteria require the grep to return ≥ 1 hit.
- **Fix:** Added a one-line summary inside the docstring listing all four tokens (`last_seen + scan_timestamp + missing + message`) on a single line so future grep-based audits succeed. Semantics unchanged; the multi-line block detail is preserved alongside the new single-line summary.
- **Files modified:** drift_detection.py:701
- **Commit:** `632a148`

No other deviations.

## Self-Check: PASSED

**Files claimed:**
- `src/homelab_mcp/drift_detection.py` — `[ -f path ]` returns FOUND.
- `src/homelab_mcp/sitemap.py` — FOUND.

**Commits claimed:**
- `a8a07b0` — FOUND in `git log --oneline`.
- `75ceeb9` — FOUND.
- `632a148` — FOUND.

**Acceptance criteria checks:**
- B1: `ssh_probe_results.get((` count = 1 ✓ ; `ssh_probe_results.get(hostname or` count = 0 ✓ ; `seen_hostnames` count = 0 ✓ .
- B2/B4: `logger.warning` hits inside `_make_row` (line 347) and `_enum_one` (line 464) ✓ .
- B3: layer-1 `key = (hypervisor, name.lower(), vmid)` at line 365 ✓ ; layer-2 `(c or h): (h, ci, c)` at line 435 ✓ ; layer-3 `_HOST_CLUSTER_CACHE[` at proxmox_api.py:424 ✓ .
- W2: `last_seen=datetime.now(UTC).isoformat()` at sitemap.py:101 + 178 (count = 2) ✓ ; `last_seen=datetime.now().isoformat()` count = 0 ✓ ; `from datetime import UTC, datetime` at sitemap.py:7 ✓ .
- W7: `(now - parsed) > timedelta(days=threshold_days)` at line 223 ✓ ; `.days > threshold_days` count = 0 ✓ .
- W6: `scope: str = "unknown"` at line 782 ✓ ; `cluster_name: str | None = None` at line 783 ✓ .
- W4: `probe_one_unreachable_fallthrough` count = 0 ✓ .
- W3: 9-key shape grep matches at line 701 ✓ .
- W5: `current-only`/`WR-05` references in `_diff_fingerprints` ≥ 5 hits ✓ .
- Quality gate: ruff clean, mypy clean ✓ .
- Diff scope: only `drift_detection.py` and `sitemap.py` changed ✓ .

All claims verified.
