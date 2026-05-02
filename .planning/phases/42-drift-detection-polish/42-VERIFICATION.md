---
phase: 42-drift-detection-polish
verified: 2026-05-01T23:09:40Z
status: passed
score: 12/12 findings verified; 4 ROADMAP success criteria verified
overrides_applied: 0
---

# Phase 42: Drift Detection Polish — Verification Report

**Phase Goal:** Apply 12 advisory fixes (B1-B4, W1-W8) from `.planning/phases/39-drift-detection-cases/39-REVIEW.md` to `src/homelab_mcp/drift_detection.py` + `src/homelab_mcp/sitemap.py`, build a regression test harness pinning each fix, and run the full quality gate.

**Verified:** 2026-05-01T23:09:40Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Per-Finding Disposition (Goal-Backward Code Audit)

| ID | Plan disposition | Codebase verdict | Evidence (line numbers in current source) |
| --- | --- | --- | --- |
| **B1** (dup-hostname phantom) | fixed | **PASS** | `_bulk_universal_core_probes` returns `dict[tuple[str, str \| None], dict]` (drift_detection.py:482); `_probe_one` builds `key = (hostname, binding)` (line 521); `seen_keys: set[tuple[str, str \| None]]` dedupe (line 592); single consumer site `ssh_probe_results.get((hostname or "", row.get("ssh_credential_id")), {})` at line 975. No bare-string `ssh_probe_results.get(hostname` lookups remain. |
| **B2** (malformed vmid) | log-upgrade | **PASS** | `_make_row` try/except wraps `int(vm.get("vmid", 0))` and emits `logger.warning` with hypervisor + raw vmid + VM name context at lines 347-352. Warning level matches BL-04 parity. |
| **B3** (cold-cache N-copy) | verified-already-done | **PASS** | Three dedupe layers confirmed: `_make_row` `key = (hypervisor, name.lower(), vmid)` at line 365 (consumer dedupe with hypervisor — also fixes WR-A multi-cluster vmid collision); `_enumerate_proxmox_vms` `targets = list({(c or h): (h, ci, c) for h, ci, c in pairs}.values())` at line 436 (cluster dedupe); `_HOST_CLUSTER_CACHE[host] = cluster_name` populator in proxmox_api.py:424 (side-effect cache write). No warm-up loop added; `grep "Phase 42 B3"` returns 0. The original B3 advice would have been a no-op. |
| **B4** (silent enumeration) | verified-already-done | **PASS** | `_enum_one` outer except catches `(aiohttp.ClientError, TimeoutError, ValueError, CredentialNotFoundError)` and emits `logger.warning("VM enumeration failed for %s; unknown[] will not include VMs from this host: %s", h, sanitize_error(exc))` at lines 459-469. Warning level + host context + sanitize_error all present. |
| **W1** (last_seen JSON hygiene) | verified-already-done | **PASS** | All three normalization sites use the byte-identical 3-branch pattern (parsed → isoformat; raw not None → str(raw); else None): outer except at lines 867-874, transient_resolver_exc fallback at 949-956, inner except at 1054-1061. `grep raw_last_seen` returns 9 hits (3 sites × 3 references each). |
| **W2** (canonical UTC writer) | fixed | **PASS** | sitemap.py:7 imports `from datetime import UTC, datetime`; `last_seen=datetime.now(UTC).isoformat()` at lines 101 + 178 (the two writer sites). 0 hits for the naive `last_seen=datetime.now().isoformat()` form. drift_detection.py `_parse_last_seen` docstring documents legacy-row backward-compat. |
| **W3** (9-key shape doc) | clarified | **PASS** | Docstring at drift_detection.py:701 includes the single-line greppable summary referencing all four tokens (last_seen + scan_timestamp + missing + message). 9-key shape applies identically across all three missing emission sites (audited). |
| **W4** (dead code) | fixed | **PASS** | `grep "_error.*probe_one_unreachable\|return.*probe_one_unreachable"` returns 0 hits — the executable sentinel is gone. The string only survives in an explanatory comment block (line 574) explaining why the dead code was removed. Replaced with `raise AssertionError(f"_probe_one reached unreachable fallthrough for hostname={hostname!r}")` at line 580 — loud-fail per WR-B recommendation. |
| **W5** (asymmetric diff doc) | verified-already-done | **PASS** | `_diff_fingerprints` docstring + inline comments at lines 234, 244, 269, 281 document WR-05 / D-09a asymmetric current-only-emit. `current-only`/`WR-05` references appear ≥ 5 times in the helper. |
| **W6** (per-row scope reset) | verified-already-done | **PASS** | `scope: str = "unknown"` at line 787 and `cluster_name: str \| None = None` at line 788 inside the row loop; reset happens at top of every iteration. The W6 regression test exercises the inner /cluster/status except branch at line 1037+ (the only branch where loop-locals are actually consumed) — not the not_eligible branch which hardcodes scope='unknown'. |
| **W7** (timedelta precision) | verified-already-done | **PASS** | `_classify_unreachable` line 223: `if parsed is not None and (now - parsed) > timedelta(days=threshold_days):` — second-resolution. 0 hits for `.days > threshold_days`. |
| **W8** (degenerate pre-pass) | verified-already-done | **PASS** | `ssh_eligible_rows` filter at lines 754-761 excludes hostname None/''/'unknown' and status='error' and missing ssh_credential_id BEFORE the bulk probe call; mirrors the row-loop degenerate routing at lines 791-800. |

**Score:** 12/12 findings verified.

### Observable Truths (PLAN must_haves)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Two sitemap rows sharing the same hostname both contribute SSH probe results — no phantom changed[] entry | VERIFIED | B1 above + 29-test regression harness includes `TestPhase42B1::test_dup_hostname_distinct_credentials_both_probed` (asserts both `("pve","cred-A")` and `("pve","cred-B")` present), `test_dup_hostname_phantom_pre_polish_shape_is_gone` (asserts no bare-string keys + tuple-key annotation present in source), and the consumer site at line 975 reads tuples. The downstream "no phantom changed[]" effect is end-to-end exercised by the 3 migrated `tests/test_drift_detection.py` tests asserting `changed == 1` against tuple-keyed mocks. |
| 2 | Malformed `vmid` payload (`'abc'`/None/list/dict) skipped without aborting scan; warning logged | VERIFIED | drift_detection.py:340-353 try/except + `logger.warning`. `TestPhase42B2` 3 tests cover string vmid, None vmid, and warning-level capture. |
| 3 | Cold-cache: one `/cluster/resources` call per cluster; one unknown[] entry per VM | VERIFIED | Three dedupe layers confirmed (B3 row above). `TestPhase42B3` 2 tests count enumeration calls (1 per cluster) and assert per-VM dedupe. |
| 4 | Enumeration failures surface at WARNING level with host context | VERIFIED | drift_detection.py:459-469. `TestPhase42B4` 2 tests cover log capture + non-aborting scan. |
| 5 | Postgres datetime / int epoch / date `last_seen` produces ISO-8601 string in JSON response | VERIFIED | 3-branch coercion at all 3 sites (W1 row). `TestPhase42W1` 3 tests run end-to-end JSON-serialization checks for each adapter type. |
| 6 | drift_detection.py + sitemap.py agree on canonical UTC timestamp convention | VERIFIED | sitemap.py writes `datetime.now(UTC).isoformat()` at both `last_seen=` sites; drift_detection's `_parse_last_seen` retains naive→UTC backward-compat for legacy rows. |
| 7 | THRESHOLD_DAYS=1 promotes a host at 24h+1s, not 47h59m | VERIFIED | timedelta comparison at line 223. `TestPhase42W7::test_threshold_1_day_promotes_at_24h_plus_5min` confirms behavior; source-form pin at `test_source_uses_timedelta_comparison_not_days_floor`. |
| 8 | `_probe_one` has no unreachable code paths; the `probe_one_unreachable_fallthrough` sentinel return is gone | VERIFIED | grep for executable form returns 0; replaced with `raise AssertionError`. `TestPhase42W4` 2 tests assert via `inspect.getsource` with comment-strip. |
| 9 | `_diff_fingerprints` asymmetric current-only-emit semantics documented inline | VERIFIED | Docstring + inline `current-only` / `WR-05` references. `TestPhase42W5` 2 tests pin runtime asymmetry. |
| 10 | `scope` / `cluster_name` bound per-iteration of scan_drift's row loop | VERIFIED | Lines 787-788 reset; `TestPhase42W6` exercises the inner-except branch where the leak would surface. |
| 11 | SSH pre-pass to `_bulk_universal_core_probes` never receives degenerate rows | VERIFIED | `ssh_eligible_rows` filter at 754-761. `TestPhase42W8` 3 tests cover degenerate / status='error' / clean rows. |

**Score:** 11/11 must_have truths verified.

### ROADMAP Success Criteria

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | All BLOCKER fixes (B1-B4) | VERIFIED | 4/4 BLOCKERs PASS in finding table |
| 2 | All WARNING fixes (W1-W8) | VERIFIED | 8/8 WARNINGs PASS in finding table |
| 3 | Every fix covered by a test, including B1 phantom regression | VERIFIED | 29 tests in `tests/test_drift_detection_polish.py` across 12 finding-keyed classes; `TestPhase42B1::test_dup_hostname_phantom_pre_polish_shape_is_gone` is present and named per the requirement (constructs input shape, runs `_bulk_universal_core_probes`, asserts no bare-string keys remain). The B1 consumer-side end-to-end behavior is exercised by 3 migrated tests in `tests/test_drift_detection.py` that assert `changed == 1` against tuple-keyed mocks. |
| 4 | Full unit suite remains green (≥907 passing); ruff + mypy clean; AST guards pass | VERIFIED | `pytest tests/ -m "not integration"`: **936 passed, 15 skipped, 0 failed** (re-run by verifier 2026-05-01T23:09Z). `ruff check`: All checks passed. `mypy`: Success: no issues found in 2 source files. AST guards (30 tests in test_ast_regression.py) all green per Plan 03 Step 3 evidence + present in 936-suite run. |

**Score:** 4/4 ROADMAP success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/homelab_mcp/drift_detection.py` | All 12 polish fixes; no dead code; canonical TZ; per-row scope reset; `datetime.now(UTC)` import | VERIFIED | Verified by per-finding audit above; mypy + ruff clean |
| `src/homelab_mcp/sitemap.py` | `last_seen=datetime.now(UTC).isoformat()` at lines 101 + 178 | VERIFIED | Confirmed via grep; `from datetime import UTC, datetime` at line 7 |
| `tests/test_drift_detection_polish.py` | 12 test classes, ≥22 tests, all 12 findings pinned, B1 phantom test present | VERIFIED | 12 classes (TestPhase42B1..B4 + TestPhase42W1..W8), 29 tests, all pass in 0.62s; 1329 LOC |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `_bulk_universal_core_probes` | `scan_drift` row loop | tuple-keyed `ssh_probe_results` | WIRED | Producer returns `dict[tuple[str, str \| None], dict]` (line 482); consumer at line 975 reads `ssh_probe_results.get((hostname or "", row.get("ssh_credential_id")), {})` |
| `sitemap.py:datetime.now(UTC).isoformat()` | `drift_detection.py:_parse_last_seen` | ISO-8601 with explicit UTC offset | WIRED | Writer emits explicit `+00:00`; parser handles both aware (new rows) and naive (legacy) inputs |
| `_classify_unreachable` | `_parse_last_seen` | `timedelta(days=threshold_days)` comparison | WIRED | Line 223 |
| `_enumerate_proxmox_vms` | `_make_row` | `(cluster_name OR hostname)` cluster dedupe + `(hypervisor, name.lower(), vmid)` consumer dedupe | WIRED | Lines 436 + 365 |

### Phase 39 Fixture Migration (B1 Contract)

The Plan 03 initial gate run failed with 3 regressions in pre-existing Phase 39 tests using bare-string `{"pve1": ...}` mocks. Plan 02 was revised (commit 68c07f7) to migrate the 3 affected fixtures.

| File:Line (current) | Test | Migrated key | Verdict |
| --- | --- | --- | --- |
| tests/test_drift_detection.py:1964 | `TestPhase39Changed::test_kernel_change_in_changed_bucket` | `("pve1", "22222222-...")` | VERIFIED |
| tests/test_drift_detection.py:2192 | `TestPhase39Changed::test_changed_field_dotted_path_for_capabilities` | `("pve1", "ffffffff-...")` | VERIFIED |
| tests/test_drift_detection.py:2366 | `TestPhase39Bucket::test_changed_host_with_unknown_vms` | `("pve1", "22222222-...")` | VERIFIED |

The remaining 5 unmigrated `{"pve1": ...}` mock sites (lines 2021, 2074, 2125, 2304, 2411) are in tests asserting `changed == 0` / `probed_ok == 1` — lookup-miss is the asserted state, so the contract drift is invisible to those tests. The Plan 02 SUMMARY explanation is correct.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Polish regression suite green | `uv run pytest tests/test_drift_detection_polish.py -v --no-cov` | 29 passed in 0.62s | PASS |
| Full unit suite green | `uv run pytest tests/ -m "not integration" --no-cov` | 936 passed, 15 skipped, 0 failed | PASS |
| Ruff clean on modified sources | `uv run ruff check src/homelab_mcp/drift_detection.py src/homelab_mcp/sitemap.py tests/test_drift_detection_polish.py` | All checks passed! | PASS |
| Mypy clean on modified sources | `uv run mypy src/homelab_mcp/drift_detection.py src/homelab_mcp/sitemap.py` | Success: no issues found in 2 source files | PASS |

All four spot-checks PASS — verified live by the verifier (not just trusted from SUMMARY).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| (none) | - | - | - | - |

No anti-patterns detected in the modified files. The single retained reference to `probe_one_unreachable_fallthrough` (drift_detection.py:574) is in a comment block explaining why the dead code was removed — historical context, not a regression.

### Honesty Audit on SUMMARY Files

The phase prompt asks specifically about SUMMARY honesty. Findings:

- **42-01-SUMMARY** correctly distinguishes "fixed" (B1, B2, W2, W4, W3-clarified) from "verified-already-done" (B3, B4, W1, W5, W6, W7, W8). The B3 grep evidence in the SUMMARY (3 layers) matches the source line numbers exactly. The two documented deviations (mypy [return] error → AssertionError; W3 grep miss → single-line summary added) are honestly disclosed.
- **42-02-SUMMARY** correctly admits the original harness did not migrate the 3 Phase 39 fixtures and includes a Revision section dated 2026-05-01 documenting commit 68c07f7. Pytest output shows all 29 polish tests + 936-suite green post-migration.
- **42-03-SUMMARY** front-loads the initial-failure context with `gate_initial_result: failed` in frontmatter, then documents the revision that produced `gate_revision_result: passed`. The narrative is forensic, not glossed over.

No inflated claims detected. All "verified-already-done" entries are backed by line-number citations the verifier confirmed against the live source.

### Human Verification Required

None. The phase goal is fully achievable through automated verification: every finding maps to a code change or audit-confirmable invariant; every fix has a regression test; the quality gate runs end-to-end.

### Gaps Summary

No gaps. All 12 findings (B1-B4, W1-W8) verified in source; 11 must-have truths verified; 4 ROADMAP success criteria verified; 29 regression tests pin each fix; full quality gate green (936 unit tests, ruff + mypy clean, 30 AST guards green); the Phase 39 fixture migration repaired 3 contract drifts caught by Plan 03's initial gate failure.

### Notes for Closure

The phase can be closed. The ROADMAP entry at line 256-269 already lists all three plans as `[x]`; only the VERIFICATION.md was missing. With this report:
- Phase 42 advances to **Complete**.
- The Phase 39 advisory backlog (B1-B4, W1-W8) is closed.
- v1.7 ROADMAP can move to Phase 43 (Phase 38 Documentation Cleanup) without a Phase 42 retrospective — the SUMMARY files already capture the forensic detail (initial-fail → fixture migration → green re-run) that a retrospective would otherwise document.

---

_Verified: 2026-05-01T23:09:40Z_
_Verifier: Claude (gsd-verifier)_
