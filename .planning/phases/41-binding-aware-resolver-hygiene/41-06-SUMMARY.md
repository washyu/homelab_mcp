---
phase: 41
plan: 06
status: complete
type: execute
wave: 5
gap_closure: true
duration_min: 35
executed_by: orchestrator-inline
closes: ["41-REVIEW.md::CR-01", "41-REVIEW.md::WR-01", "41-REVIEW.md::WR-04"]
---

# Plan 41-06: Split resolver/cache key (host=) from TCP-dial target (dial_host=) on drift Proxmox path

## What was broken

Plan 41-04 set `host=row.connection_ip` on `get_proxmox_client` for the drift Proxmox path. The resolver inside `get_proxmox_client` then keyed `_RESOLUTION_TELEMETRY_CACHE[(connection_ip, binding)]`, but the very next block in `scan_drift` read `get_resolution_telemetry(hostname, binding)` — a guaranteed miss whenever `hostname != connection_ip`, defeating WR-04's double-resolve guard. Same bug ran in `_enumerate_proxmox_vms._enum_one` (only the implicit `host=h` form, but `_HOST_CLUSTER_CACHE.get(hostname)` dedupe collapsed wherever hostname differed from the dial target).

## What was fixed

**Source surgery:**

| File | Edit |
|------|------|
| `src/homelab_mcp/proxmox_api.py` | Added `dial_host: str \| None = None` keyword-only parameter to `get_proxmox_client`. Resolver call inside the body unchanged (uses `host`). `ProxmoxAPIClient(host=(dial_host or host), ...)` is the only line that switches — the TCP target uses the dial override; back-compat preserved when `dial_host=None`. Docstring updated. |
| `src/homelab_mcp/drift_detection.py::scan_drift` | Proxmox row loop now passes `host=hostname` + `dial_host=row.connection_ip or hostname` + `credential_id=binding`. Reverts Plan 41-04's `host=connection_ip` and adds the new dial split. |
| `src/homelab_mcp/drift_detection.py::_enumerate_proxmox_vms` | `pairs` now carries `(hostname, connection_ip, cluster_name)` triples; `targets` dedupe key is `(cluster_name OR hostname)` — NOT connection_ip — so the cluster-cache invariant holds. `_enum_one(h, dial_host, _c)` passes `host=h` + `dial_host=dial_host` to `get_proxmox_client`. |
| `src/homelab_mcp/drift_detection.py::_probe_one` | WR-04: removed the unreachable `raise AssertionError(...)` and shrunk the 17-line belt-and-braces comment to a 6-line note. Added a sentinel `return (hostname, {"_error": "probe_one_unreachable_fallthrough"})` to satisfy mypy's exhaustiveness check (runtime is unreachable per the comment). |

**Tests added:**

| File | Addition |
|------|----------|
| `tests/test_drift_detection.py` | New `test_resolver_runs_once_when_hostname_differs_from_connection_ip` inside `TestScanDrift4Bucket`. Asserts `get_proxmox_client` receives `host="pve"` and `dial_host="192.168.10.20"`, and the resolver is called keyed on hostname. |
| `tests/test_ast_regression.py` | New `TestPhase41HostDialHostHygiene` class with 4 methods: pairs-host-with-hostname-not-dial-target, with-dial-host-pairs-with-host, threads-credential-id (belt-and-braces), guard-call-site-floor. |

**Test-fake updates (Rule 1 deviation):**

- 36 `fake_get_client` signatures in `tests/test_drift_detection.py` updated to accept `dial_host=None` kwarg passthrough. Plan 41-06 introduced the new kwarg; without the bulk update, every test that mocks `get_proxmox_client` would fail with `TypeError: got an unexpected keyword argument 'dial_host'`.
- `test_node_filter_none_means_no_filter` and `test_node_filter_exact_hostname_match` assertions reverted to capture hostnames (not connection_ips) — `host=` is now the canonical resolver key.
- `test_drift_dials_connection_ip_not_hostname` (Phase 41-01 functional test) updated to assert the new pairing: `dial_host="192.168.10.20"` AND `host="pve"`.

## Verification

```
✓ ruff check src/homelab_mcp/proxmox_api.py src/homelab_mcp/drift_detection.py    — clean
✓ mypy src/homelab_mcp/proxmox_api.py src/homelab_mcp/drift_detection.py          — clean
✓ tests/test_drift_detection.py                                                   — 63 passed (62 + 1 new)
✓ tests/test_ast_regression.py::TestPhase41HostDialHostHygiene                    — 4/4 passed
✓ tests/test_ast_regression.py::TestPhase39_1NoSkipInDriftEnum                    — 2/2 passed (preserved)
✓ tests/test_ast_regression.py::TestPhase41BindingAwareResolver                   — 3/3 passed (preserved)
✓ Full unit suite                                                                  — 902 passed, 0 failed
```

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| `dial_host: str \| None = None` parameter added to `get_proxmox_client` | ✓ |
| `host=(dial_host or host)` in `ProxmoxAPIClient` constructor | ✓ |
| `scan_drift` Proxmox loop passes `host=hostname` + `dial_host=...` + `credential_id=binding` | ✓ |
| `_enum_one` passes `host=h` + `dial_host=dial_host` + `credential_id=binding` | ✓ |
| `grep -c "raise AssertionError" src/homelab_mcp/drift_detection.py` returns 0 | ✓ |
| `grep -c "credential_id=binding" src/homelab_mcp/drift_detection.py` returns ≥ 2 | ✓ (2: scan_drift + _enum_one) |
| `grep -c "get_resolution_telemetry(hostname" src/homelab_mcp/drift_detection.py` returns ≥ 1 | ✓ |
| `grep -c "_HOST_CLUSTER_CACHE.get(hostname)" src/homelab_mcp/drift_detection.py` returns ≥ 1 | ✓ |
| TestPhase39_1NoSkipInDriftEnum + TestPhase41BindingAwareResolver still GREEN | ✓ |
| New TestPhase41HostDialHostHygiene 4 methods all PASS | ✓ |
| Full unit suite GREEN | ✓ (902 passed) |

## Notable deviations

1. **Plan 41-04 didn't actually wire `_enum_one` for connection_ip dialing.** Plan 41-06's "current state" assumed Plan 41-04 had set `host=dial_host` in `_enum_one`, but Plan 41-04 only modified `_probe_one` and `scan_drift` (per its own files_modified). Plan 41-06 had to introduce the connection_ip carry through `pairs`/`targets` and the `dial_host` parameter in `_enum_one` from scratch.

2. **Sentinel return required for mypy exhaustiveness in `_probe_one`.** The plan claimed the bare `except Exception` would satisfy mypy without the unreachable raise; mypy 1.x disagreed. Added a sentinel `return (hostname, {"_error": "probe_one_unreachable_fallthrough"})` after the raise removal — runtime is still unreachable per the surrounding comment, but mypy now passes.

3. **36 test fakes updated.** The plan's `files_modified` listed `tests/test_drift_detection.py` and `tests/test_ast_regression.py` but did not call out the magnitude of the fake-signature update. Without the bulk update, every existing test mocking `get_proxmox_client` would raise `TypeError` on the new `dial_host=` kwarg.

4. **Inline orchestrator execution.** Smart App Control kept blocking subagents; this plan was executed inline by the orchestrator session.

## CR-01 + WR-01 + WR-04 status

**All three closed.**

- **CR-01:** `host=hostname` is the canonical resolver/cache key. `_RESOLUTION_TELEMETRY_CACHE[(hostname, binding)]` writes are read by the same key in `get_resolution_telemetry(hostname, binding)`. Single resolution per host.
- **WR-01:** `_HOST_CLUSTER_CACHE.get(hostname)` dedupe restored — cluster members enumerate once via `/cluster/resources`, not N times for N-node clusters.
- **WR-04:** Unreachable `raise AssertionError` removed; sentinel return preserves mypy's exhaustiveness check; comment shrunk from 17 lines to 6.

Future regression that drops back to `host=connection_ip` will fail `TestPhase41HostDialHostHygiene::test_drift_get_proxmox_client_pairs_host_with_hostname_not_dial_target`. Future regression that drops `dial_host=` will fail the resolver-runs-once functional test on hostname≠connection_ip rows.
