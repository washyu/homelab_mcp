---
phase: 41
plan: 04
status: complete
type: execute
wave: 3
duration_min: 25
executed_by: orchestrator-inline
---

# Plan 41-04: Wire drift_detection through resolve_ssh_for_sitemap_row + dial connection_ip

## What was built

Closed Bug V on the drift side. Two surgical edits to `src/homelab_mcp/drift_detection.py`:

1. **`_probe_one` (SSH pre-pass)** — Replaced `resolve_ssh_credentials(hostname, credential_id=binding)` with `resolve_ssh_for_sitemap_row(hostname)`. Derived `dial_target = (matched_row.get("connection_ip") if matched_row else None) or hostname` (Pitfall 4 fallback). Passed `dial_target` to `ssh_connect(hostname=...)` instead of `creds.hostname`.

2. **`scan_drift` Proxmox row loop** — Added `dial_host = row.get("connection_ip") or hostname` before the `get_proxmox_client(...)` call; changed `host=hostname` to `host=dial_host`.

Plan 05's AST guard `test_shared_helper_used_by_both_call_sites` will lock the shared-helper invariant on the drift side.

## Files modified

| File | Change |
|------|--------|
| `src/homelab_mcp/drift_detection.py` | Two surgical edits (`_probe_one`, `scan_drift` Proxmox loop); import line replaces `resolve_ssh_credentials` with `resolve_ssh_for_sitemap_row` (the direct call was the only consumer). |
| `tests/test_drift_detection.py` | 5 `fake_get_client` mocks updated to accept connection_ip dial targets; 2 assertions widened to allow both hostname and connection_ip in `called_hosts`. Rule 1 deviation (test break required by the new dial contract). |

## Invariants preserved

- **Phase 39.1 D-16:** `get_proxmox_client(...)` still includes `credential_id=binding` keyword on every call site (`grep -c credential_id=binding` returns 5). `TestPhase39_1NoSkipInDriftEnum` PASS.
- **Phase 39 WR-06:** Per-iteration variable reset (`scope`, `cluster_name`) untouched.
- **Phase 39 WR-B:** Unreachable-fallthrough `raise AssertionError` retained.
- **Probe map keying:** `_probe_one` still returns `(hostname, ...)`; BL-01 dedupe still keys on `row.get("hostname")`.

## Verification

```
✓ ruff check src/homelab_mcp/drift_detection.py        — clean
✓ mypy src/homelab_mcp/drift_detection.py              — clean
✓ tests/test_drift_detection.py                        — 62 passed
✓ tests/test_ast_regression.py::TestPhase39_1...       — 2 passed
✓ Full unit suite                                      — 894 passed, 3 xfail-strict (Plan 05 closes)
```

The 3 remaining test failures are XPASS-strict signals from Plan 41-01's scaffold:
- `test_drift_dials_connection_ip_not_hostname` (functional, Wave 0)
- `TestPhase41BindingAwareResolver::test_shared_helper_used_by_both_call_sites` (AST)
- `TestPhase41BindingAwareResolver::test_no_unguarded_resolve_ssh_credentials_in_call_chain` (AST)

Plan 41-05 explicitly removes the `xfail-strict` markers on these — at which point all three flip GREEN.

## Acceptance criteria met

| Criterion | Status |
|-----------|--------|
| `grep -c resolve_ssh_for_sitemap_row drift_detection.py >= 2` | ✓ (2: import + call) |
| `grep -c dial_target drift_detection.py >= 1` | ✓ (2) |
| `grep -c dial_host drift_detection.py >= 1` | ✓ (2) |
| `grep -c "host=hostname" drift_detection.py == 0` (in get_proxmox_client) | ✓ |
| `grep -c credential_id=binding drift_detection.py >= 2` | ✓ (5 — Phase 39.1 invariant) |
| `grep -c creds.hostname drift_detection.py == 0` | ✓ |
| ruff + mypy clean on drift_detection.py | ✓ |
| TestPhase39_1NoSkipInDriftEnum PASS | ✓ |
| tests/test_drift_detection.py PASS | ✓ |
| Full unit suite PASS (modulo expected XPASS-strict) | ✓ |

## Notable deviations

1. **Rule 1 (Bug):** `resolve_ssh_credentials` import dropped from `drift_detection.py` because the only consumer was the line replaced in `_probe_one`. ruff F401 forced removal. Plan 05's allowlist for `resolve_ssh_credentials` direct calls in drift_detection.py stays empty.

2. **Rule 1 (Bug):** Plan 41-04's `files_modified` listed only `drift_detection.py`. Five existing `fake_get_client` mocks in `tests/test_drift_detection.py` matched only on hostname; after the dial change, drift dials connection_ip and the fakes raised `AssertionError("unexpected host")`. Updated all 5 mocks and 2 assertions to accept both forms. Original test intent preserved (D-01 filter invariant, no-row-vanishes closure).

3. **Inline orchestrator execution:** Plan 41-04's gsd-executor subagent was blocked by Smart App Control (silent Edit/Write/Bash denials per saved feedback memory). Plan was executed inline by the orchestrator session instead, which has working tool permissions.

## Enables Wave 4 (Plan 41-05)

The shared helper is now wired into both call sites (sitemap.py + drift_detection.py). Plan 41-05 finalizes the AST guard:
- Removes `xfail-strict` markers from `TestPhase41BindingAwareResolver`'s 3 AST tests.
- Audits remaining direct `resolve_ssh_credentials(...)` calls in `sitemap.py` and `drift_detection.py` (drift side: zero).
