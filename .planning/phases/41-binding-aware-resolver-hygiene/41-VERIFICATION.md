---
phase: 41
phase_name: binding-aware-resolver-hygiene
status: passed
verified_by: orchestrator-inline
date: 2026-05-01
plans_executed: 9/9
must_haves_verified: 4/4
---

# Phase 41 Verification Report

## Phase goal (from ROADMAP)

> A user calling `discover_and_map hostname=pve` against a sitemap-known host succeeds via the same UUID-binding path that drift scan already uses; sitemap-known hosts dial `connection_ip` rather than `hostname`; failed discoveries write errors to a row tagged with the requested identifier and never collapse onto degenerate-hostname zombie rows.

## Must-haves (verified against the codebase)

| # | Must-have | Status | Evidence |
|---|-----------|--------|----------|
| 1 | **Bug AA closed** — `discover_and_map` resolves SSH credentials via the same row-binding-aware helper that drift scan uses; both call sites share one helper, locked by an AST guard. | ✓ | `resolve_ssh_for_sitemap_row` exists in `ssh_tools.py` (Plan 41-02). `sitemap.discover_and_store` calls it (Plan 41-03). `drift_detection._probe_one` calls it (Plan 41-04). `TestPhase41BindingAwareResolver::test_shared_helper_used_by_both_call_sites` PASSes — call-site count ≥ 2 verified by AST. |
| 2 | **Bug V closed** — Sitemap row exists → SSH dial target + Proxmox API client both use `row.connection_ip`. | ✓ | `discover_and_store` derives `dial_target = row.connection_ip OR hostname` and passes it (Plan 41-03 + 41-09). `drift_detection._probe_one` derives `dial_target` and passes to `ssh_connect` (Plan 41-04). `drift_detection.scan_drift` Proxmox loop and `_enum_one` pass `host=hostname, dial_host=connection_ip` to `get_proxmox_client` (Plan 41-06). `TestPhase41HostDialHostHygiene` AST guard locks the host/dial_host pairing (Plan 41-06). `test_dial_target_uses_row_connection_ip` and `test_drift_dials_connection_ip_not_hostname` functional tests PASS. |
| 3 | **Bug BB closed** — Failed `discover_and_map` writes the error to a row matching the requested identifier; degenerate-hostname zombies never collect errors. | ✓ | `parse_discovery_output(requested_identifier=...)` preserves the requested identifier on JSONDecodeError (Plan 41-03). `ssh_connection_wrapper` error envelopes carry both `hostname` (requested) and `connection_ip` (dial target) split (Plan 41-09 + WR-05). `test_failed_discover_writes_to_requested_identifier_row` and `test_failed_discover_does_not_collapse_to_empty_hostname` PASS, with `mock_discover.assert_called_once()` locking that the patched discovery layer is actually reached (Plan 41-08 + WR-03 + WARN-01/WARN-02). |
| 4 | **AST guard locks the shared-helper invariant** for both `discover_and_store` and `_drift_probe_one` (or successor symbols). | ✓ | `TestPhase41BindingAwareResolver` (Plan 41-05): `test_resolve_ssh_for_sitemap_row_helper_exists`, `test_shared_helper_used_by_both_call_sites`, `test_no_unguarded_resolve_ssh_credentials_in_call_chain` — all 3 PASS without xfail-strict markers. Empty `_RESOLVER_CALLS_ALLOWLIST` proves zero direct `resolve_ssh_credentials(...)` calls remain in `sitemap.py` or `drift_detection.py`. |

## Gap-closure findings (41-REVIEW.md)

| Finding | Plan | Status |
|---------|------|--------|
| **CR-01** — drift's host=connection_ip broke the resolver/cache key contract | 41-06 | ✓ Closed (host/dial_host split) |
| **WR-01** — `_HOST_CLUSTER_CACHE` dedupe collapsed on hostname≠connection_ip rows | 41-06 | ✓ Closed (`_enum_one` keyed on `h`) |
| **WR-02** — `_probe_one` did not thread `db_adapter` into resolver | 41-07 | ✓ Closed (kwarg threaded; AST guard `TestPhase41DBAdapterHygiene`) |
| **WR-03** — Bug-BB tests patched the wrong symbol | 41-08 | ✓ Closed (repointed at `ssh_discover_system`) |
| **WR-04** — unreachable `raise AssertionError` in `_probe_one` | 41-06 | ✓ Closed (removed; sentinel return for mypy) |
| **WR-05** — envelope conflated requested identifier and dial target | 41-09 | ✓ Closed (split via `dial_target=` kwarg + 2 regression tests) |

## Quality gates

| Gate | Result |
|------|--------|
| Full unit suite (`uv run pytest -m "not integration"`) | ✓ 907 passed, 0 failed, 15 skipped |
| ruff on Phase 41 source files | ✓ clean (`error_handling.py`, `ssh_tools.py`, `sitemap.py`, `drift_detection.py`, `proxmox_api.py`) |
| mypy on Phase 41 source files | ✓ clean (5 source files, 0 issues) |
| Phase 39.1 D-16 invariant (`get_proxmox_client(...)` carries `credential_id=`) | ✓ Preserved (`TestPhase39_1NoSkipInDriftEnum` PASSes; 5 occurrences confirmed) |
| Phase 41.1 keyring hygiene | ✓ Preserved (`TestPhase41_1KeyringHygiene` PASSes) |

## AST guards in place after Phase 41

- `TestPhase41BindingAwareResolver` (3 methods) — shared-helper invariant
- `TestPhase41HostDialHostHygiene` (4 methods) — host/dial_host pairing on `get_proxmox_client`
- `TestPhase41DBAdapterHygiene` (2 methods) — db_adapter threading on `resolve_ssh_for_sitemap_row`

## Verification methodology

This phase was verified inline by the orchestrator session (the standard `gsd-verifier` subagent path was unavailable due to Smart App Control intermittently blocking subagent tool permissions on the developer's Win11 machine — see saved memory `feedback_windows_smart_app_control.md`). The inline verification:

1. Confirmed all 9 plan SUMMARYs exist
2. Re-ran the full unit suite (`uv run pytest tests/ -m "not integration"`) → 907/907 passed
3. Ran ruff + mypy on every Phase 41-modified source file → all clean
4. Cross-referenced each must-have to its closing plan + functional/AST regression test
5. Confirmed the empty `_RESOLVER_CALLS_ALLOWLIST` proves zero direct `resolve_ssh_credentials(...)` calls remain in `sitemap.py` or `drift_detection.py` (Plan 41-05 audit)

No human verification items remain — all 6 functional regression tests in `tests/test_phase41_binding_aware.py` exercise the bugs end-to-end with real-shape mocks.

## Verdict

**PASSED.** All 4 must-haves verified. All 6 review findings closed. Full unit suite green. Code-quality gates clean. Phase ready to advance to Phase 41.1.
