---
phase: 41
plan: 05
status: complete
type: execute
wave: 4
duration_min: 10
executed_by: orchestrator-inline
---

# Plan 41-05: Finalize Phase 41 AST guard

## What was built

Converted `TestPhase41BindingAwareResolver` from a Wave-0 RED scaffold into the final regression lock. After this plan, any future commit that:
- Removes the `resolve_ssh_for_sitemap_row` helper, OR
- Drops one of the call sites in `sitemap.py` / `drift_detection.py`, OR
- Aliases the import (`from .ssh_tools import resolve_ssh_for_sitemap_row as foo`), OR
- Re-introduces an unguarded `resolve_ssh_credentials(...)` call in either file outside the documented allowlist
…will fail this guard.

## Audit results — direct callers of `resolve_ssh_credentials`

```
grep -n "resolve_ssh_credentials(" src/homelab_mcp/sitemap.py        → 0 matches
grep -n "resolve_ssh_credentials(" src/homelab_mcp/drift_detection.py → 0 matches
```

**Allowlist contents:** `frozenset()` (empty). Strongest invariant — any future direct call fails the guard.

## Files modified

| File | Change |
|------|--------|
| `tests/test_ast_regression.py` | (1) Removed `@pytest.mark.xfail(strict=True, ...)` from `test_shared_helper_used_by_both_call_sites` and `test_no_unguarded_resolve_ssh_credentials_in_call_chain`. (2) Refined `_RESOLVER_CALLS_ALLOWLIST` definition to `frozenset()` with audit comment. (3) Added `line_to_func` enclosing-function tracking to `test_no_unguarded...` so violations name the function (not just line numbers) — more readable + stable across small refactors. (4) Removed unused `import pytest` (no decorators left). |
| `tests/test_phase41_binding_aware.py` | Removed `@pytest.mark.xfail(strict=True, ...)` from `test_drift_dials_connection_ip_not_hostname`. Plan 41-04 wired drift through the helper; this test now passes plainly (was the last remaining xfail-strict marker that needed manual removal). |

## Verification

```
✓ tests/test_ast_regression.py::TestPhase41BindingAwareResolver  — 3/3 PASS
✓ tests/test_ast_regression.py (full AST suite)                  — 24/24 PASS
✓ tests/test_phase41_binding_aware.py                            — 6/6 PASS
✓ Full unit suite                                                — 897 passed, 0 failed, 0 xfail, 0 xpass
✓ ruff on Phase 41 files                                         — clean
✓ mypy src/homelab_mcp/                                          — clean (1 pre-existing jsonschema stubs warning in openapi_app.py, unrelated)
✓ bandit                                                         — same 13 medium / 31 high counts as pre-Phase-41 (none introduced by this work)
```

Pre-existing ruff issues in `tests/test_credential_store.py` (UP037 type-annotation quotes) and one mypy import-untyped warning in `src/homelab_mcp/openapi_app.py` are not from Phase 41 work — confirmed via `git stash` + re-run.

## Prior-phase AST guards verified GREEN

- `TestPhase41_1KeyringHygiene` — keyring hygiene allowlist unchanged
- `TestPhase39_1NoSkipInDriftEnum` — `get_proxmox_client(...)` still includes `credential_id=` kwarg on every call site (5 occurrences)
- `TestPhase38_1*` — all PASS
- `TestPhase35*`, `TestPhase33_1*`, `TestPhase32*` — all PASS
- 24/24 in the full AST suite

## ROADMAP success criteria closed

- **SC #4** ("AST guard locks the shared-helper invariant for both `discover_and_map` and `_drift_probe_one`") → **closed**.

## Notable deviations

1. **Rule 1 (Bug):** Plan 41-05's `files_modified` listed only `tests/test_ast_regression.py`. Found a leftover `xfail-strict` marker on `test_drift_dials_connection_ip_not_hostname` in `tests/test_phase41_binding_aware.py` (Plan 41-01 added 6 markers; Plan 41-03 removed 5 of them; Plan 41-04 should have removed the 6th when wiring drift but did not because Plan 04's `files_modified` was scoped to `drift_detection.py` only). Plan 41-05 removed it as part of finalization.

2. **Rule 1 (Bug):** Pre-existing `import pytest` in `test_ast_regression.py` was added by Plan 41-01 only to enable the xfail decorators. Removing the decorators left it unused — ruff F401 forced removal.

3. **Inline orchestrator execution:** Plan 41-05 was executed inline (no subagent) following the same fallback path as Plan 41-04. Smart App Control kept blocking subagent Edit/Write/Bash.

## Phase 41 status after Plan 05

All 9 Phase 41 tests (6 functional + 3 AST) PASS without xfail markers. Bugs AA, BB, V are closed on both the discover path and the drift path. The shared `resolve_ssh_for_sitemap_row` helper is the only credential-resolution route from `sitemap.py` and `drift_detection.py`. AST guard locks the invariant.

Wave 4 (Plan 05) closes the original Phase 41 plan (5 plans). Waves 5–6 (Plans 06–09) are gap-closure plans for `41-REVIEW.md` findings (CR-01 + WR-01 through WR-05).
