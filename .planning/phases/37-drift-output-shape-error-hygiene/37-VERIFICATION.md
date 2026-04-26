---
phase: 37-drift-output-shape-error-hygiene
verified: 2026-04-25T00:00:00Z
status: passed
score: 4/4 success criteria verified
overrides_applied: 0
---

# Phase 37: Drift Output Shape & Error Hygiene Verification Report

**Phase Goal:** A user calling `scan_infrastructure_drift` gets the same response shape regardless of filter scope, can see at a glance which hosts were probed and which weren't, and never sees an error message pointing to a deprecated env var or a non-existent baseline tool.
**Verified:** 2026-04-25T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `scan_infrastructure_drift` returns identical envelope shape regardless of filter scope (empty, node=existing, node=missing, vm_type=qemu/lxc/all) — empty match returns empty result, never a scope error (closes Bugs A and E) | VERIFIED | `scan_drift` applies D-01 hostname exact-match filter at row-iteration step (drift_detection.py:133-134); `vm_type` is inert at host-scan level (no branching). `test_node_filter_no_match_returns_success_empty` and `test_vm_type_inert_across_qemu_lxc_all` both pass (21/21 TestScanDrift4Bucket tests green). |
| 2 | Drift report distinguishes four buckets — probed_ok, unreachable, unknown, changed — all always present in response so a user can tell which hosts were covered and which weren't (closes Bug D) | VERIFIED | `drift_detection.py:123-126` initializes all four bucket lists; return dict unconditionally includes all four keys (lines 223-226). `counts` sub-dict mirrors sizes. `test_envelope_has_all_four_bucket_keys`, `test_counts_subdict_mirrors_bucket_sizes`, `test_unknown_and_changed_buckets_always_empty_in_phase_37` all pass. |
| 3 | Every drift-family error message / recovery text that suggests a recovery action points to existing sitemap CRUD tools (discover_and_map, get_network_sitemap, purge_failed_discoveries, decommission_device) — no message mentions PROXMOX_HOST (closes Bug B) | VERIFIED | `_EMPTY_SCAN_GUIDANCE` constant (drift_detection.py:45-51) references all four sitemap CRUD tools and contains no PROXMOX_HOST. Drift surface files (drift_detection.py, drift_handlers.py, drift_tools_schema.py, server.py) all return 0 PROXMOX_HOST matches. openapi_app.py Drift Detection entry scrubbed (exactly 1 PROXMOX_HOST remains in file — the intentionally-preserved Proxmox entry on line 59). AST guard `TestPhase37DriftHygiene::test_no_proxmox_host_in_drift_files` passes. `test_guidance_text_does_not_mention_proxmox_host` passes at runtime level. |
| 4 | MCP tool list contains no `register_drift_baseline`, `list_drift_baselines`, or `delete_drift_baseline` tool — drift docs and baseline-lifecycle error messages reference existing sitemap CRUD tools (closes Bug C architecturally) | VERIFIED | `TestPhase37DriftHygiene::test_no_baseline_lifecycle_tool_names_in_source` passes — zero matches for all three forbidden tool names across all `*.py` under `src/homelab_mcp/`. docs/tool-reference.md: 0 matches for forbidden tool names, 0 "stored baselines" references. docs entry fully rewritten for 4-bucket envelope with sitemap CRUD recovery pointers. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/homelab_mcp/drift_detection.py` | scan_drift with 4-bucket envelope, hostname filter, counts sub-dict, conditional guidance | VERIFIED | File present; contains `probed_ok`, `unreachable`, `unknown`, `changed` bucket initializations; `_EMPTY_SCAN_GUIDANCE` constant defined and referenced; `if node is not None` filter at line 133; `counts` sub-dict at line 201; conditional guidance insertion at line 220-221; module docstring updated for Phase 37 stable shape. No `PROXMOX_HOST`, no `os.getenv`, no `drift_baseline` references. |
| `src/homelab_mcp/tool_schemas/drift_tools_schema.py` | Phase 37 stable description with 4-bucket names, hostname-filter semantics, Phase 39 vm_type reservation | VERIFIED | Description mentions all four bucket names (probed_ok, unreachable, unknown, changed), counts sub-dict, conditional guidance, discover_and_map recovery pointer. node description states "Exact-match only — no wildcards, no case folding." vm_type description includes "Reserved for Phase 39 per-VM detection." enum ["qemu","lxc","all"] and default "all" preserved. Zero PROXMOX_HOST. |
| `src/homelab_mcp/server.py` | homelab://drift/latest resource description reflecting Phase 37 stable 4-bucket shape | VERIFIED | HOMELAB_RESOURCES["homelab://drift/latest"]["description"] (lines 150-157) describes "Four-bucket coverage report (probed_ok, unreachable, unknown, changed) with per-bucket counts and a conditional guidance field"; references discover_and_map. No "2-bucket interim" or "stabilizes in Phase 37". |
| `src/homelab_mcp/openapi_app.py` | Drift Detection INFRA_REQUIREMENTS entry cleaned; Proxmox entry untouched | VERIFIED | Line 60 Drift Detection entry: "a Proxmox VE host registered in the sitemap. Populate via 'discover_and_map' and configure credentials with 'homelab-mcp credentials add --type proxmox'". Line 59 Proxmox entry: unchanged, still contains "Set PROXMOX_HOST and credentials via environment". grep -c PROXMOX_HOST returns exactly 1. |
| `src/homelab_mcp/tool_handlers/drift_handlers.py` | handle_scan_infrastructure_drift docstring updated to 4-bucket framing; body unchanged | VERIFIED | Docstring mentions "Phase 37 four-bucket envelope", "DRFT-13", and lists all four sitemap CRUD tools. Body (scan_drift call, set_latest_drift_report cache, return) is identical to Phase 36. |
| `docs/tool-reference.md` | scan_infrastructure_drift entry rewritten for 4-bucket shape, hostname filter, counts, conditional guidance | VERIFIED | Entry at line 576 fully rewritten. Prose describes four-bucket coverage, exact-match node filter, conditional guidance, counts sub-dict. Arguments table: node with exact-match semantics, vm_type with Phase 39 reservation note. Two Returns examples shown (populated and empty-scan). Recovery section references `homelab-mcp credentials add --type proxmox`. Annotations badge `[Read-Only]` `[Idempotent]` preserved. Zero PROXMOX_HOST or "stored baselines" in entry. |
| `tests/test_drift_detection.py` | TestScanDrift4Bucket class with 6 Phase 36 sanity tests + 15 Phase 37 regression tests = 21 total | VERIFIED | Single `TestScanDrift4Bucket` class (TestScanDrift2Bucket: 0 matches). All 21 tests pass (confirmed by `pytest tests/test_drift_detection.py::TestScanDrift4Bucket -v --no-cov`). All 15 Phase 37 method names present. All 6 Phase 36 methods preserved. No `_EMPTY_SCAN_GUIDANCE` import in test file. |
| `tests/test_ast_regression.py` | TestPhase37DriftHygiene class with test_no_proxmox_host_in_drift_files (D-11) and test_no_baseline_lifecycle_tool_names_in_source (D-12) | VERIFIED | Class at line 599. Both test methods discoverable and passing. `_DRIFT_SURFACE_FILES` and `_FORBIDDEN_BASELINE_TOOL_NAMES` class-level tuples defined. D-11 check uses dict-value import for openapi_app.py (not whole-file scan, preserving Proxmox entry). Phase 36 D-13 guard unchanged. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| scan_drift (drift_detection.py) | db_adapter.get_all_devices() | Direct call at line 128 | VERIFIED | Sitemap is sole data source |
| scan_drift D-01 filter | row.get("hostname") == node | List comprehension at line 134 | VERIFIED | Exact-match applied before degenerate-row skip |
| scan_drift return dict | Top-level envelope keys in locked order | Sequential dict insertion | VERIFIED | `test_envelope_key_order_is_locked` passes for both scanned==0 (9-key with guidance) and scanned>0 (8-key without guidance) |
| scan_drift response | counts sub-dict sum == scanned | `scanned = sum(counts.values())` at line 208 | VERIFIED | `test_counts_sum_equals_top_level_scanned` passes; uses defensive sum() not hardcoded two-bucket addition |
| scan_drift guidance field | _EMPTY_SCAN_GUIDANCE constant | Conditional insertion when scanned==0 | VERIFIED | `test_guidance_present_when_scanned_zero`, `test_guidance_absent_when_scanned_nonzero` both pass |
| handle_scan_infrastructure_drift | scan_drift | Import + call at drift_handlers.py:6,24 | VERIFIED | Passes node and vm_type arguments; caches result for homelab://drift/latest resource |
| TestPhase37DriftHygiene D-11 | INFRA_REQUIREMENTS["Drift Detection"] | Dict-value import from openapi_app | VERIFIED | Guard passes; intentionally does NOT check INFRA_REQUIREMENTS["Proxmox"] (Phase 40 POL-03 territory) |

### Data-Flow Trace (Level 4)

Phase 37 is a shape-correctness and text-hygiene phase. The core scan_drift function renders dynamic data (real-time Proxmox probe results from sitemap rows via get_proxmox_client). The data source is correctly wired: sitemap rows come from `db_adapter.get_all_devices()`, and probe results come from live `client.get("/cluster/status")` calls. All mock tests patch `get_proxmox_client` and `resolve_proxmox_credentials` appropriately. No hollow-prop or disconnected data path detected.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| drift_detection.py scan_drift | probed_ok / unreachable | db_adapter.get_all_devices() + get_proxmox_client().get("/cluster/status") | Yes — live DB reads + live Proxmox probe | FLOWING |
| _EMPTY_SCAN_GUIDANCE | guidance | Module-level constant | N/A — static text by design | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 21 TestScanDrift4Bucket tests all pass | `uv run pytest tests/test_drift_detection.py::TestScanDrift4Bucket -v --no-cov` | 21 passed in 0.33s | PASS |
| Phase 37 AST guards both pass | `uv run pytest tests/test_ast_regression.py::TestPhase37DriftHygiene -v --no-cov` | 2 passed in 0.63s | PASS |
| Full unit suite green (no regressions) | `uv run pytest tests/ -m "not integration" -x --tb=short --no-cov -q` | 732 passed, 8 skipped, 19 deselected, 1 warning | PASS |
| PROXMOX_HOST absent from drift surface files | `grep -c PROXMOX_HOST drift_detection.py drift_handlers.py drift_tools_schema.py server.py` | 0/0/0/0 | PASS |
| PROXMOX_HOST exactly 1 in openapi_app.py (Proxmox entry preserved) | `grep -c PROXMOX_HOST src/homelab_mcp/openapi_app.py` | 1 | PASS |
| No forbidden baseline tool names in docs | `grep -c "register_drift_baseline\|list_drift_baselines\|delete_drift_baseline" docs/tool-reference.md` | 0 | PASS |
| No "stored baselines" anywhere in docs | `grep -c "stored baselines" docs/tool-reference.md` | 0 | PASS |
| TestScanDrift2Bucket fully renamed | `grep -c "class TestScanDrift2Bucket" tests/test_drift_detection.py` | 0 | PASS |
| TestScanDrift4Bucket is sole class | `grep -c "class TestScanDrift4Bucket" tests/test_drift_detection.py` | 1 | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| DRFT-13 | 37-01, 37-04 | Consistent shape across all filter scopes; empty result on no-match, never scope error | SATISFIED | D-01 hostname filter (drift_detection.py:133-134) returns success with empty buckets on no-match. vm_type inert. All envelope-shape and filter tests pass. |
| DRFT-14 | 37-01, 37-04 | Four buckets (probed-OK, unreachable, unknown, changed) always present for coverage transparency | SATISFIED | All four bucket keys always in response dict; counts sub-dict mirrors sizes; unknown/changed reserved-empty for Phase 39. |
| DRFT-15 | 37-01, 37-02, 37-03, 37-04 | Drift family error messages point to sitemap CRUD tools, never PROXMOX_HOST | SATISFIED | _EMPTY_SCAN_GUIDANCE references all four sitemap tools; PROXMOX_HOST removed from all drift surface files; D-11 AST guard locks this in; runtime test `test_guidance_text_does_not_mention_proxmox_host` passes. |
| DRFT-16 | 37-03 | No register_drift_baseline / list_drift_baselines / delete_drift_baseline MCP tools; architectural dissolution via sitemap unification | SATISFIED | D-12 AST guard passes (zero matches for all three forbidden tool names across all src/homelab_mcp/*.py). Docs entry references sitemap CRUD tools for baseline lifecycle. |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `src/homelab_mcp/drift_detection.py:170-172` | Defensive `continue` after second `resolve_proxmox_credentials` call (WR-01 from REVIEW.md) — if cache invariant breaks, row silently dropped from all buckets, making scanned inconsistent | Warning | Unreachable in practice because get_proxmox_client already succeeded with same credentials; represents a correctness gap if cache invariant is broken in future. Does NOT affect Phase 37 success criteria — the four-bucket guarantee holds for all current code paths. Not a blocker. |
| `tests/test_drift_detection.py:165` | `test_inert_filter_passthrough` docstring says "inert in Phase 36" — stale claim since node filter is active in Phase 37 (WR-02 from REVIEW.md) | Warning | Cosmetic/misleading for future readers; test itself exercises empty-sitemap path where filter result is identical either way. Existing Phase 37 filter tests (`test_node_filter_*`) fully cover the active filter semantics. Not a blocker. |

**Note on WR-01 and success criterion 2:** The review flagged the defensive `continue` as potentially breaking the four-bucket `scanned` invariant. However, this code path (CredentialNotFoundError on the second resolver call after the first succeeded) is logically unreachable in the current implementation because `get_proxmox_client` and `resolve_proxmox_credentials` share the same credential cache (`_HOST_CLUSTER_CACHE`). If `get_proxmox_client` succeeded, the cache is warm and the second call cannot fail with CredentialNotFoundError. The four-bucket guarantee (SC-2) is not broken by this code path in any reachable scenario. The warning stands as a latent correctness gap for future code changes, but does not block SC-2 verification.

### Human Verification Required

None — all success criteria are verifiable programmatically. Phase 37 is shape correctness and text hygiene work; no UI, real-time behavior, or external service integration was added.

### Gaps Summary

No gaps. All four success criteria verified against actual codebase implementation. The two REVIEW.md warnings (WR-01 defensive continue, WR-02 stale docstring) are cosmetic/latent issues that do not block any success criterion and are not flagged in the review's critical or blocking categories. Both are recorded in Anti-Patterns above for traceability.

---

_Verified: 2026-04-25T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
