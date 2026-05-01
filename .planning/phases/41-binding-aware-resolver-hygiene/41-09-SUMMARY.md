---
phase: 41
plan: 09
status: complete
type: execute
wave: 6
gap_closure: true
duration_min: 25
executed_by: orchestrator-inline
closes: ["41-REVIEW.md::WR-05"]
---

# Plan 41-09: Split request identifier from dial target on ssh_connection_wrapper envelopes (WR-05)

## What was broken

`ssh_connection_wrapper` extracted `hostname = kwargs.get("hostname", args[0] if args else "unknown")` and emitted both `"hostname": hostname` and `"connection_ip": hostname` in every error envelope. After Plan 41-03, `discover_and_store` passed the dial target (`row.connection_ip`) as the positional `hostname` argument to `ssh_discover_system` — so the envelope's `hostname` field actually carried the dial target, and the original requested identifier was lost.

`discover_and_store`'s post-parse `find_devices_by_hostname_or_ip` merge salvaged the row identity for the discover path, but any direct caller of `ssh_discover_system` / `ssh_execute_command` (e.g., MCP tool dispatchers) saw an envelope where the requested identifier was unrecoverable.

## What was fixed

**Source surgery — option (a) per WR-05 §"Fix":**

| File | Edit |
|------|------|
| `src/homelab_mcp/error_handling.py::ssh_connection_wrapper` | All 5 error envelope branches now do two-value extraction: `requested = kwargs.get("hostname", args[0] if args else "unknown")` + `dial_target = kwargs.get("dial_target", requested)`. Each `json.dumps({...})` block emits `"hostname": requested, "connection_ip": dial_target`. Back-compat: when no `dial_target=` kwarg supplied, `dial_target == requested` and both fields carry the same value (identical to pre-Phase-41-09 behavior). |
| `src/homelab_mcp/ssh_tools.py::ssh_discover_system` | Added keyword-only `dial_target: str \| None = None`. Body derives `effective_dial = dial_target or hostname`; `ssh_connect(hostname=effective_dial, ...)`. Success-path payload's `connection_ip` field flips from `hostname` (Plan 41-03's dial-target literal) to `effective_dial` — faithful passthrough at `parse_discovery_output` (which reads `connection_ip` with no transformation). |
| `src/homelab_mcp/ssh_tools.py::ssh_execute_command` | Added keyword-only `dial_target: str \| None = None`. Same `effective_dial` derivation; `ssh_connect(hostname=effective_dial, ...)`. No success-path `connection_ip` field to flip. |
| `src/homelab_mcp/sitemap.py::discover_and_store` | `ssh_discover_system(dial_target, creds.username, ...)` (positional dial-target) → `ssh_discover_system(hostname, creds.username, ..., dial_target=dial_target)` (positional requested-identifier + dedicated kwarg). The `dial_target` local var derivation (`(row.get("connection_ip") if row else None) or hostname`) stays unchanged. |

**Tests added:**

| File | Addition |
|------|----------|
| `tests/test_phase41_binding_aware.py` | `test_envelope_split_request_identifier_from_dial_target` — asserts envelope has `hostname='pve'` AND `connection_ip='192.168.10.20'` when both kwargs supplied (and the two fields differ). |
| `tests/test_phase41_binding_aware.py` | `test_envelope_back_compat_when_dial_target_omitted` — asserts envelope has `hostname == connection_ip == 'pve'` when only `hostname` supplied (legacy behavior preserved). |

**Test-fake updates:**

| File | Change |
|------|--------|
| `tests/test_sitemap.py` | `mock_ssh_discover.assert_called_once_with(...)` updated to expect `dial_target='test-host'` kwarg. Two `fake_ssh_discover` signatures gain `*, dial_target=None` passthrough. |

## Verification

```
✓ ruff check src/homelab_mcp/error_handling.py + ssh_tools.py + sitemap.py    — clean
✓ mypy src/homelab_mcp/error_handling.py + ssh_tools.py + sitemap.py          — clean
✓ tests/test_phase41_binding_aware.py                                         — 8 passed (6 functional + 2 new envelope tests)
✓ tests/test_sitemap.py                                                       — 33 passed (no regression)
✓ tests/test_ssh_tools.py                                                     — passed (no regression)
✓ Full unit suite                                                             — 907 passed, 0 failed
```

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| `grep -c "dial_target = kwargs.get" error_handling.py` returns 5 | ✓ |
| `grep -c '"hostname": requested,' error_handling.py` returns 5 | ✓ |
| `grep -c '"connection_ip": dial_target,' error_handling.py` returns 5 | ✓ |
| `grep -c '"hostname": hostname,' error_handling.py` returns 0 | ✓ |
| `grep -c "dial_target: str \| None = None" ssh_tools.py` returns 2 | ✓ |
| `grep -c "effective_dial = dial_target or hostname" ssh_tools.py` returns 2 | ✓ |
| `grep -c "dial_target=dial_target" sitemap.py` returns ≥ 1 | ✓ |
| Existing `test_error_envelope_carries_hostname` still PASSes | ✓ (back-compat) |
| Two new envelope tests PASS | ✓ |
| Full unit suite GREEN | ✓ (907 passed) |

## parse_discovery_output coherence (plan WARN-03 mandate)

Confirmed empirically via the read step: `parse_discovery_output` reads `data.get("connection_ip", "")` with NO transformation. Flipping the success-path JSON's `connection_ip` field from `hostname` (Plan 41-03's dial-target literal) to `effective_dial = dial_target or hostname` is a faithful passthrough:
- **Back-compat callers (no `dial_target` supplied):** `effective_dial == hostname` → JSON `connection_ip` is byte-identical to pre-41-09.
- **Phase 41 callers (`discover_and_store` passing `dial_target=row.connection_ip`):** JSON `connection_ip` flips to the actual TCP target — exactly what Plan 41-03 wanted (the row's `connection_ip` column reflects the actual dial target on success).

`test_discover_and_map_uses_row_binding_when_row_exists` and the rest of `test_phase41_binding_aware.py` PASS — empirical confirmation that row routing on the success path is preserved.

## External caller audit

Per the plan's Step 6 audit: `ssh_discover_system` and `ssh_execute_command` are called from:
- `src/homelab_mcp/sitemap.py::discover_and_store` — UPDATED to use the new `dial_target=` kwarg.
- `src/homelab_mcp/service_installer.py`, `vm_operations.py`, `infrastructure_crud.py`, MCP tool dispatchers — all pass the user-facing hostname positionally; `dial_target` defaults to `None` → `effective_dial == hostname` → identical pre-41-09 behavior. **No changes needed.**
- `tests/` — only `test_sitemap.py` directly asserts on `ssh_discover_system`'s call signature (now expects `dial_target=` kwarg). Other test fakes use `**kwargs` or have been updated.

## Notable deviations

1. **Inline orchestrator execution.** Smart App Control kept blocking subagents; this plan was executed inline.
2. **Bulk Python rewrite** for the 5 `ssh_connection_wrapper` envelope branches (instead of 5 separate `Edit` calls) because the pattern was uniform and the `Edit` tool's exact-string matching would have required 5 distinct context windows.

## WR-05 status

**Closed.** Future regression that drops the kwarg split (e.g., emits `"connection_ip": requested`) will fail `test_envelope_split_request_identifier_from_dial_target`. Future regression that breaks back-compat (e.g., requires `dial_target=` to be supplied) will fail `test_envelope_back_compat_when_dial_target_omitted`.

The split is by-documentation rather than by-AST-guard — the contract is type-checked via `dial_target: str | None = None` in the function signatures and locked at runtime via the two regression tests. AST guards beyond what already exists are not warranted (the contract isn't grep-detectable on call sites without semantic analysis).
