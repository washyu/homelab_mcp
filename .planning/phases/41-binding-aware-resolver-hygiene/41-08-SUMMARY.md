---
phase: 41
plan: 08
status: complete
type: execute
wave: 5
gap_closure: true
duration_min: 12
executed_by: orchestrator-inline
closes: ["41-REVIEW.md::WR-03"]
---

# Plan 41-08: Repoint Bug-BB regression tests at canonical patch target (WR-03)

## What was broken

Per `41-REVIEW.md` WR-03, the two Bug-BB regression tests in
`tests/test_phase41_binding_aware.py` were structurally broken in two ways:

1. **Wrong patch target.** Both tests patched
   `homelab_mcp.ssh_tools.ssh_discover_system_with_binding`. After Plan 41-03,
   `sitemap.discover_and_store` no longer calls that wrapper — it calls
   `ssh_discover_system` directly via a function-body deferred import. The
   patched mock was never invoked.

2. **Unparseable-UUID seed silently short-circuited the test.** The seed row
   carried `ssh_credential_id="uuid-abc"`. `resolve_ssh_for_sitemap_row`
   passed this to `resolve_ssh_credentials`, which raised
   `CredentialNotFoundError("binding stale: malformed credential_id")` BEFORE
   any discovery call fired. `discover_and_store` then synthesized its own
   well-formed JSON error envelope — which happened to make the test's
   downstream assertions pass for the wrong reason.

Both Bug-BB scenarios (real timeout from a discovery RPC, real malformed JSON
return) were uncovered.

## What was fixed

**Both rewritten tests now use option (b) per WR-03 §Fix — the keyring-stub
path** (mandated by WARN-01: option (a) UUID-not-in-registry would still
short-circuit before the patched mock runs).

**Pattern 2** (`monkeypatch.setattr` on `resolve_ssh_credentials`) chosen over
Pattern 1 (`register_credential`) because it has zero dependencies on conftest
details and `register_credential`'s signature does not accept a `password`
kwarg — passwords are stored separately in the keyring.

Both tests:

1. `monkeypatch.setattr("homelab_mcp.ssh_tools.resolve_ssh_credentials", ...)`
   to return a stub `SSHCredentials` with valid `username/password/port`.
2. `patch("homelab_mcp.ssh_tools.ssh_discover_system", new=AsyncMock(return_value=...))`
   so the canonical discovery layer is intercepted.
3. Capture the patched mock and assert `mock_discover.assert_called_once()`
   inside the `with patch(...)` block AFTER `await discover_and_store(...)`.
   This is the WARN-02 invariant — without it, a future short-circuit
   regression would silently pass the patch-target presence grep while
   leaving the mock unreached.

## Files modified

| File | Change |
|------|--------|
| `tests/test_phase41_binding_aware.py` | Rewrote `test_failed_discover_writes_to_requested_identifier_row` and `test_failed_discover_does_not_collapse_to_empty_hostname` per WARN-01 + WARN-02 mandates. Added `monkeypatch` fixture. Updated docstrings to cite Phase 41-08 WR-03 + WARN-01/WARN-02 in-place. |

## Verification

```
✓ tests/test_phase41_binding_aware.py::test_failed_discover_writes_to_requested_identifier_row → PASSED
✓ tests/test_phase41_binding_aware.py::test_failed_discover_does_not_collapse_to_empty_hostname → PASSED
✓ tests/test_phase41_binding_aware.py (full)                              → 6/6 PASSED
✓ Full unit suite (-m "not integration")                                  → 897 passed, 15 skipped
✓ ruff check tests/test_phase41_binding_aware.py                          → clean
✓ mypy tests/test_phase41_binding_aware.py                                → 5 pre-existing import-untyped warnings (homelab_mcp module — pre-Phase-41), no new issues
```

The other 4 Phase 41 tests in `test_phase41_binding_aware.py` (`test_discover_and_map_uses_row_binding_when_row_exists`, `test_dial_target_uses_row_connection_ip`, `test_drift_dials_connection_ip_not_hostname`, `test_error_envelope_carries_hostname`) were correct already — they remain GREEN.

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| Two Bug-BB tests patch `homelab_mcp.ssh_tools.ssh_discover_system` (not the old wrapper) | ✓ |
| Neither test seeds `ssh_credential_id="uuid-abc"` (the unparseable-UUID short-circuit is gone from these two tests) | ✓ |
| Both tests assert `mock_discover.assert_called_once()` (WARN-02) | ✓ |
| Both tests cite Phase 41-08 WR-03 + WARN-01 + WARN-02 in docstrings | ✓ |
| Both tests PASS for the right reason (patched mock IS invoked end-to-end) | ✓ |
| 4 already-correct Phase 41 tests stay GREEN | ✓ |
| Full unit suite GREEN | ✓ (897 passed) |
| ruff + mypy clean on modified file | ✓ (no new issues) |

## Notable deviations

1. **Plan acceptance criterion `grep -c "ssh_discover_system_with_binding" == 0` not literally satisfied** — that string still appears 2× in the docstrings of the two rewritten tests as intentional historical context (describing what was broken before Plan 41-08). The acceptance was over-broad: the *patch target* references are gone (which is the point); the *prose references* in docstrings clarify the regression for future maintainers.

2. **Plan acceptance criterion `grep -c "uuid-abc" == 0` not literally satisfied** — `uuid-abc` is also used legitimately in OTHER Phase 41 tests (`test_discover_and_map_uses_row_binding_when_row_exists`, `test_dial_target_uses_row_connection_ip`) where the binding marker drives Tier-0 short-circuit assertions. Plan 41-08's intent was scoped to the two broken Bug-BB tests; the other tests are correct.

3. **Used Pattern 2 (`monkeypatch.setattr`) over Pattern 1 (`register_credential`)** — `register_credential`'s signature has no `password` kwarg (passwords are separate keyring writes), so Pattern 1 would have required additional setup. Pattern 2 has fewer dependencies. Both patterns are equivalent per the plan.

4. **Inline orchestrator execution** — Smart App Control kept blocking subagents on Win11; this plan was executed inline by the orchestrator session.

## WR-03 Status

**Closed.** Both Bug-BB tests now exercise the real Bug-BB scenarios:
- Test 1: a timeout-style error envelope from `ssh_connection_wrapper` reaches `parse_discovery_output` → `find_devices_by_hostname_or_ip` merge salvages row identity.
- Test 2: malformed JSON from a discovery RPC reaches `parse_discovery_output`'s `JSONDecodeError` branch with `requested_identifier='fakehost.local'`, preserving the requested hostname (Plan 41-03's fix).

A future regression that drops `requested_identifier` from `parse_discovery_output` or removes the `_seed_row(...)` upsert path will fail these tests, locking the invariant structurally.
