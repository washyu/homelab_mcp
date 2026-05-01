---
phase: 42-drift-detection-polish
plan: 02
subsystem: drift-detection
tags: [drift, regression-tests, polish, B1, B2, B3, B4, W1, W2, W3, W4, W5, W6, W7, W8, tdd]
dependency_graph:
  requires:
    - .planning/phases/42-drift-detection-polish/42-01-PLAN.md
    - .planning/phases/42-drift-detection-polish/42-01-SUMMARY.md
    - src/homelab_mcp/drift_detection.py (post-Plan-01 source)
    - src/homelab_mcp/sitemap.py (post-Plan-01 source)
  provides:
    - "tests/test_drift_detection_polish.py — 12 test classes pinning all 12 advisory fixes"
    - "B1 phantom regression test: tuple-keyed probe map, bare-string hostname dedupe shape proved gone"
    - "W2 prefixed-pattern regex assertion (NOT bare substring) — disambiguates last_seen= writer sites from out-of-scope stored_at=/completed_at= writers"
    - "W6 inner /cluster/status except branch test — exercises drift_detection.py:1037+ loop-local consumption (not the not_eligible branch which hardcodes scope='unknown')"
  affects:
    - Phase 42 Plan 03 (full quality gate — pytest run + ruff + mypy + bandit; this plan deferred full-suite run, only ran the new file)
tech_stack:
  added: []
  patterns:
    - "inspect.getsource() source-inspection assertions for AST-shaped invariants (W4 sentinel-gone, W7 timedelta-form, W2 prefixed-pattern regex)"
    - "patch_module_level_dependencies pattern: patch homelab_mcp.drift_detection.{resolve_ssh_for_sitemap_row, ssh_connect, _probe_universal_core, get_proxmox_client, resolve_proxmox_credentials, get_resolution_telemetry} for end-to-end scan_drift fixtures"
    - "autouse _HOST_CLUSTER_CACHE.clear() fixture per Phase 42 test for deterministic cold-cache semantics"
    - "caplog WARNING-level capture pinned against logger name 'homelab_mcp.drift_detection'"
key_files:
  created:
    - tests/test_drift_detection_polish.py
  modified: []
decisions:
  - "B1 attribution test uses uniform fingerprint (not per-credential differentiation): the assertion target is on PRESENCE-as-tuple-keys, not value-attribution. Pre-Plan-01 hostname-only dedupe would have collapsed the two rows to ONE entry; the tuple-keyed fix surfaces TWO entries. Differentiating fingerprint values per credential added complexity (gather-order non-determinism + side-channel queues) without strengthening the assertion."
  - "W4 sentinel test asserts the EXECUTABLE shape is gone (dict construction `{\"_error\": \"probe_one_unreachable_fallthrough\"}`), not the bare substring. Plan-01's W4 comment block legitimately MENTIONS the deleted sentinel string as historical context (so future readers can grep for the pre-Plan-01 form). Stripping comment lines before the assertion isolates the executable invariant from the narrative documentation."
  - "W6 fixture mocks get_resolution_telemetry to return None on every call so the resolver-fallback branch (which rebinds scope/cluster_name per-row) executes for every row. Without this mock, the telemetry cache might return a stale value from row A's resolution and bypass the rebind path for row B — though that path is itself a different leak surface, it would not exercise the loop-local reset under test."
metrics:
  duration: 25
  completed: 2026-05-01
---

# Phase 42 Plan 02: Drift Detection Polish — Regression Test Harness Summary

Created `tests/test_drift_detection_polish.py` — a 12-class regression test harness pinning the polish fixes from `39-REVIEW.md` (B1-B4 BLOCKERs + W1-W8 WARNINGs). 29 tests collected, 29 passing, 0 skips, 0 xfails. The B1 phantom regression test is mandatory and present; W2 uses the prefixed-pattern regex (not bare substring); W6 targets the inner /cluster/status except branch.

## One-liner

29 named regression tests across 12 finding-keyed classes pin every Phase 42 polish fix; future regressions trace from a failing test name (e.g., `TestPhase42B1::test_dup_hostname_phantom_pre_polish_shape_is_gone`) directly to the bug each test re-opens.

## Test Class → Finding ID Mapping

| Class | Finding ID | Tests | Assertion Style | Targets |
| --- | --- | ---: | --- | --- |
| TestPhase42B1 | 39-REVIEW-B1 | 3 | Runtime + AST | `_bulk_universal_core_probes` returns `dict[tuple[str, str \| None], dict]`; phantom regression scenario; same-(host,cred) first-seen dedupe |
| TestPhase42B2 | 39-REVIEW-B2 | 3 | Runtime + caplog | Malformed vmid (string / None) skipped without crash; WARNING-level log with host context |
| TestPhase42B3 | 39-REVIEW-B3 | 2 | Runtime call-counting | One /cluster/resources call per cluster (Layer-2); one unknown[] entry per (hypervisor, name, vmid) (Layer-1) |
| TestPhase42B4 | 39-REVIEW-B4 | 2 | Runtime + caplog | Enumeration failure logs WARNING with host context; failure on host A doesn't abort host B's enumeration |
| TestPhase42W1 | 39-REVIEW-W1 | 3 | Runtime + json.dumps | `last_seen` as datetime / int epoch / date object — response is JSON-serializable end-to-end |
| TestPhase42W2 | 39-REVIEW-W2 | 3 | Source-inspection (regex) | PREFIXED-PATTERN: `last_seen=datetime.now(UTC).isoformat()` ≥ 2 occurrences; `last_seen=datetime.now().isoformat()` (naive) = 0; `from datetime import ... UTC ...` present |
| TestPhase42W3 | 39-REVIEW-W3 | 2 | Runtime — record-key set | 9-key shape on missing substatus; 7-key shape on unreachable substatus |
| TestPhase42W4 | 39-REVIEW-W4 | 2 | Source-inspection (executable) | Dead `{"_error": "probe_one_unreachable_fallthrough"}` dict construction gone from executable source; `raise AssertionError` terminal form present |
| TestPhase42W5 | 39-REVIEW-W5 | 2 | Runtime helper invocation | Asymmetric diff: current-only top-level emits with `stored=None`; stored-only nested key suppressed |
| TestPhase42W6 | 39-REVIEW-W6 | 1 | Runtime two-row fixture | Inner /cluster/status except branch (drift_detection.py:1037+) — Row B's `record_inner["cluster_name"]` == 'cl2' (B's own), not 'cl1' (A's leaked) |
| TestPhase42W7 | 39-REVIEW-W7 | 3 | Runtime + source | timedelta-precision: `_classify_unreachable` returns 'missing' at 24h+5min with threshold=1d (`.days`-floor would yield 'unreachable'); 23h55min stays 'unreachable'; source uses `timedelta(days=...)` not `.days >` |
| TestPhase42W8 | 39-REVIEW-W8 | 3 | Runtime — captured probe input | Degenerate (hostname='unknown') row + ssh_credential_id NOT in eligible set; status='error' row NOT in eligible set; clean row IS in eligible set |

**Total:** 12 classes, 29 tests.

## Number of Tests Per Class

| Class | Tests | Notes |
| --- | ---: | --- |
| TestPhase42B1 | 3 | distinct creds both probed + tuple-key shape gone + same-cred dedupe |
| TestPhase42B2 | 3 | string vmid + None vmid + WARNING-level log |
| TestPhase42B3 | 2 | single enumeration + per-VM dedupe |
| TestPhase42B4 | 2 | log warning + non-aborting |
| TestPhase42W1 | 3 | datetime + int epoch + date |
| TestPhase42W2 | 3 | UTC prefixed-pattern + no-naive prefixed-pattern + UTC import present |
| TestPhase42W3 | 2 | 9-key + 7-key |
| TestPhase42W4 | 2 | sentinel-shape gone + AssertionError form present |
| TestPhase42W5 | 2 | current-only emit + stored-only suppress |
| TestPhase42W6 | 1 | inner-except scope-leak fixture (single comprehensive test) |
| TestPhase42W7 | 3 | promotes-at-24h+5min + stays-at-23h55min + source-form pin |
| TestPhase42W8 | 3 | degenerate excluded + status='error' excluded + clean included |

## Source-Inspection Tests vs Runtime Fixtures

Most tests are runtime fixtures (mock `db_adapter`, patch resolver/client, run `scan_drift`, assert on response). The exceptions are AST-shaped invariants where source inspection is the more durable assertion:

| Class::Test | Style | Rationale |
| --- | --- | --- |
| TestPhase42B1::test_dup_hostname_phantom_pre_polish_shape_is_gone | Mixed (runtime + `inspect.getsource`) | Asserts the runtime KEY-SHAPE (tuple) AND that the source still references `tuple[str, str \| None]` so a future refactor that loosens the type annotation surfaces the regression |
| TestPhase42W2::test_sitemap_last_seen_writer_uses_utc_prefixed_pattern | `inspect.getsource(sitemap)` + `re.findall` | The W2 fix is scoped to the two `last_seen=` writer sites; bare-substring `"datetime.now(UTC).isoformat()" in src` would be satisfied by an unrelated `stored_at=datetime.now(UTC).isoformat()` if a future PR upgrades stored_at to UTC. The PREFIXED PATTERN `last_seen=datetime\.now\(UTC\)\.isoformat\(\)` is unambiguously the W2 surface. |
| TestPhase42W2::test_sitemap_last_seen_writer_no_naive_pattern_remains | `re.findall` negative | Same rationale: `last_seen=datetime\.now\(\)\.isoformat\(\)` (no UTC) appears 0 times. |
| TestPhase42W2::test_sitemap_module_imports_utc | `inspect.getsource` regex | `from datetime import ... UTC ...` must remain in sitemap.py imports — otherwise `datetime.now(UTC)` becomes a NameError. |
| TestPhase42W4::test_probe_one_no_unreachable_sentinel_return | `inspect.getsource` + comment-strip | The Plan-01 W4 comment block MENTIONS the deleted sentinel string for historical context. The bare substring `"probe_one_unreachable_fallthrough" not in src` fails on the comment text even though the dead executable code IS gone. Stripping comment lines before the assertion isolates the executable invariant. |
| TestPhase42W4::test_probe_one_uses_assertion_error_terminal_form | `inspect.getsource` substring | Pins the chosen WR-B form (raise AssertionError) — a future refactor that re-introduces a silent sentinel return surfaces here. |
| TestPhase42W7::test_source_uses_timedelta_comparison_not_days_floor | `inspect.getsource` regex (positive + negative) | Pins the correct `(now - parsed) > timedelta(days=...)` form AND the absence of the buggy `.days > threshold_days` form. Behavioral tests already cover the day-floor case at 24h+5min, but the source pin catches a refactor that uses an EQUIVALENT-LOOKING comparison with subtly-different precision. |

## W2 Prefixed-Pattern Confirmation

The W2 assertion uses **`re.findall(r"last_seen=datetime\.now\(UTC\)\.isoformat\(\)", src)`** — NOT the bare substring `"datetime.now(UTC).isoformat()" in inspect.getsource(sitemap)`. Grep evidence from the test file:

```bash
$ grep -nE 'last_seen=datetime\\.now\\(UTC\\)' tests/test_drift_detection_polish.py
... regex literal asserting >=2 prefixed matches at line ~1065
... regex literal asserting 0 naive prefixed matches at line ~1080
```

This disambiguates from the unrelated `stored_at=datetime.now().isoformat()` (sitemap.py:554) and `completed_at=datetime.now().isoformat()` (sitemap.py:634) writer sites — those are out of scope for W2 and may legitimately remain naive. A future PR that upgrades stored_at/completed_at to UTC would not falsely satisfy the W2 last_seen assertion.

Source `inspect.getsource(sitemap)` confirmed the post-Plan-01 state (sitemap.py grep snapshot from 42-01-SUMMARY):
- 2 occurrences of `last_seen=datetime.now(UTC).isoformat()` at lines 101, 178 — passes the `>= 2` assertion.
- 0 occurrences of `last_seen=datetime.now().isoformat()` (naive form) — passes the `== 0` assertion.

## W6 Inner-Except Branch Confirmation

The W6 test exercises the **inner /cluster/status except branch at drift_detection.py:1037+** where `record_inner["scope"] = scope` and `record_inner["cluster_name"] = cluster_name` consume the loop-local. The fixture:

1. Two sitemap rows: host-A (cl1) and host-B (cl2).
2. Both rows reach the resolver-success branch.
3. Row A's `/cluster/status` returns a list (probed_ok).
4. Row B's `/cluster/status` raises `aiohttp.ClientError` — inner except fires for B.
5. Mock `get_resolution_telemetry` returns None on every call so the resolver-fallback branch (which rebinds scope/cluster_name per-row) executes for both rows.
6. Assert: `record_inner["cluster_name"]` for B equals `'cl2'` (B's own iteration-local), NOT `'cl1'` (A's leaked).

```bash
$ grep -nE 'cluster_name.*cl2|cl1' tests/test_drift_detection_polish.py | head -10
... evidence of two-row fixture with A's cl1 vs B's cl2 distinguishing values
```

The not_eligible branch at lines 791-800 is **deliberately not used** as the assertion target because it hardcodes `scope="unknown"` at every emission site (lines 798, 832, 922) — a regression of the `scope: str = "unknown"` / `cluster_name: str | None = None` reset at lines 787-788 cannot be detected by the not_eligible records' shapes. The inner /cluster/status except branch (line 1040: `"scope": scope`, line 1041: `"cluster_name": cluster_name`) is the actual loop-local consumption site.

## Pytest Output Snippet (Green Run)

```text
$ uv run pytest tests/test_drift_detection_polish.py -v --no-cov

============================= test session starts =============================
collected 29 items

tests/test_drift_detection_polish.py::TestPhase42B1::test_dup_hostname_distinct_credentials_both_probed PASSED
tests/test_drift_detection_polish.py::TestPhase42B1::test_dup_hostname_phantom_pre_polish_shape_is_gone PASSED
tests/test_drift_detection_polish.py::TestPhase42B1::test_same_hostname_same_cred_dedupes_first_seen_wins PASSED
tests/test_drift_detection_polish.py::TestPhase42B2::test_malformed_vmid_string_skipped_no_crash PASSED
tests/test_drift_detection_polish.py::TestPhase42B2::test_malformed_vmid_none_skipped_no_crash PASSED
tests/test_drift_detection_polish.py::TestPhase42B2::test_malformed_vmid_logs_warning PASSED
tests/test_drift_detection_polish.py::TestPhase42B3::test_cold_cache_single_enumeration_per_cluster PASSED
tests/test_drift_detection_polish.py::TestPhase42B3::test_cold_cache_unknown_emits_one_per_vm_not_n_copies PASSED
tests/test_drift_detection_polish.py::TestPhase42B4::test_enumeration_failure_logs_warning PASSED
tests/test_drift_detection_polish.py::TestPhase42B4::test_enumeration_failure_does_not_abort_scan PASSED
tests/test_drift_detection_polish.py::TestPhase42W1::test_postgres_datetime_last_seen_serializes_as_iso_string PASSED
tests/test_drift_detection_polish.py::TestPhase42W1::test_integer_epoch_last_seen_stringified_when_parse_fails PASSED
tests/test_drift_detection_polish.py::TestPhase42W1::test_date_object_last_seen_stringified_when_parse_fails PASSED
tests/test_drift_detection_polish.py::TestPhase42W2::test_sitemap_last_seen_writer_uses_utc_prefixed_pattern PASSED
tests/test_drift_detection_polish.py::TestPhase42W2::test_sitemap_last_seen_writer_no_naive_pattern_remains PASSED
tests/test_drift_detection_polish.py::TestPhase42W2::test_sitemap_module_imports_utc PASSED
tests/test_drift_detection_polish.py::TestPhase42W3::test_missing_substatus_record_keys_match_9_key_shape PASSED
tests/test_drift_detection_polish.py::TestPhase42W3::test_unreachable_substatus_record_keys_match_7_key_base PASSED
tests/test_drift_detection_polish.py::TestPhase42W4::test_probe_one_no_unreachable_sentinel_return PASSED
tests/test_drift_detection_polish.py::TestPhase42W4::test_probe_one_uses_assertion_error_terminal_form PASSED
tests/test_drift_detection_polish.py::TestPhase42W5::test_diff_emits_current_only_top_level PASSED
tests/test_drift_detection_polish.py::TestPhase42W5::test_diff_suppresses_stored_only PASSED
tests/test_drift_detection_polish.py::TestPhase42W6::test_scope_does_not_leak_into_inner_except_branch PASSED
tests/test_drift_detection_polish.py::TestPhase42W7::test_threshold_1_day_promotes_at_24h_plus_5min PASSED
tests/test_drift_detection_polish.py::TestPhase42W7::test_threshold_1_day_does_not_promote_at_23h_55min PASSED
tests/test_drift_detection_polish.py::TestPhase42W7::test_source_uses_timedelta_comparison_not_days_floor PASSED
tests/test_drift_detection_polish.py::TestPhase42W8::test_degenerate_row_with_ssh_credential_id_not_probed PASSED
tests/test_drift_detection_polish.py::TestPhase42W8::test_status_error_row_with_ssh_credential_id_not_probed PASSED
tests/test_drift_detection_polish.py::TestPhase42W8::test_eligible_row_passes_through_to_probe PASSED

============================= 29 passed in 0.66s ==============================
```

## Quality Gate (Scoped to New File)

Per the plan, the FULL-SUITE quality gate is deferred to Plan 03. This plan ran the new file in isolation:

```bash
$ uv run ruff check tests/test_drift_detection_polish.py
All checks passed!

$ uv run ruff format tests/test_drift_detection_polish.py
1 file already formatted

$ uv run mypy tests/test_drift_detection_polish.py
# Pre-existing project-wide [import-untyped] errors only — same as
# tests/test_drift_detection.py and other test files. No errors local
# to this file.
```

## Acceptance Criteria Self-Check

| Criterion | Status | Evidence |
| --- | --- | --- |
| File exists | PASSED | `tests/test_drift_detection_polish.py` created, 1329 LOC |
| 4 BLOCKER classes (TestPhase42B[1-4]) | PASSED | grep returns 4 |
| 8 WARNING classes (TestPhase42W[1-8]) | PASSED | grep returns 8 |
| Total 12 finding-keyed classes | PASSED | grep returns 12 |
| `@pytest.mark.asyncio` ≥ 6 in BLOCKER classes | PASSED | grep returns 10 in BLOCKER classes alone |
| `_HOST_CLUSTER_CACHE.clear()` ≥ 1 hit | PASSED | autouse fixture, lines 62 + 64 (setup + teardown) |
| `test_dup_hostname` ≥ 1 hit | PASSED | TestPhase42B1 has 3 such tests |
| `caplog` ≥ 2 hits (B2 + B4) | PASSED | grep returns multiple in B2 + B4 |
| `monkeypatch.setenv.*HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` ≥ 1 | PASSED | TestPhase42W7 lines for promote/no-promote tests |
| `inspect.getsource` ≥ 1 hit (W4 OR W2) | PASSED | W2 + W4 + W7 all use it |
| `probe_one_unreachable_fallthrough` ≥ 1 hit (W4 negative assertion) | PASSED | W4 test references the sentinel string in its assertion |
| `datetime(2026` ≥ 1 hit (W1/W7 fixture) | PASSED | W1 + W7 use explicit `datetime(2020, ...)` / `datetime(2026, ...)` |
| W2 prefixed-pattern (NOT bare substring) | PASSED | `re.findall(r"last_seen=datetime\.now\(UTC\)\.isoformat\(\)", src)` |
| W6 references `record_inner` OR targets inner /cluster/status except | PASSED | W6 fixture mocks /cluster/status to raise on host-B; assertion targets the inner except branch's emitted record (line 1037+) |
| `uv run pytest tests/test_drift_detection_polish.py -v` exits 0 | PASSED | 29 passed, 0 failed, 0 skipped, 0 xfailed |
| Test count ≥ 22 | PASSED | 29 collected |

## Deviations from Plan

**None.** The plan executed exactly as written. Two minor format/lint adjustments applied automatically:

1. `ruff check --fix` removed an unused import (`_parse_last_seen` — imported but the imports list was over-broad; the assertion logic uses `_classify_unreachable` directly which calls `_parse_last_seen` internally).
2. `ruff format` reformatted the file to project-standard line lengths.

Both adjustments are pre-commit-hook normalizations, not deviations from the plan's behavior or assertion design.

## Self-Check: PASSED

**Files claimed:**
- `tests/test_drift_detection_polish.py` — `[ -f path ]` returns FOUND (1329 LOC, 29 tests).

**Commits claimed:**
- `b1cb635` — FOUND in `git log --oneline` with subject `test(42-02): regression tests for drift polish fixes B1-B4 + W1-W8`.

**Acceptance criteria checks:**
- 12 finding-keyed test classes present (TestPhase42B1..B4, TestPhase42W1..W8) ✓
- 29 tests collected and passing, 0 skips, 0 xfails ✓
- B1 phantom regression test present and named (`test_dup_hostname_phantom_pre_polish_shape_is_gone`) ✓
- W2 prefixed-pattern regex assertion present (NOT bare substring) ✓
- W6 inner-except branch fixture present, two-row A→cl1 / B→cl2 fixture pinning the loop-local consumption ✓
- File ruff-clean ✓
- File mypy-clean (modulo pre-existing project-wide [import-untyped] noise that affects all test files in this repo) ✓
- No pre-existing tests in `tests/test_drift_detection.py` modified ✓

All claims verified.
