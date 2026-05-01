---
phase: 41
plan: 07
status: complete
type: execute
wave: 6
gap_closure: true
duration_min: 12
executed_by: orchestrator-inline
closes: ["41-REVIEW.md::WR-02"]
---

# Plan 41-07: Thread db_adapter through SSH pre-pass (WR-02)

## What was broken

`scan_drift(db_adapter=...)` reads sitemap rows through the supplied adapter at line 706, but the SSH pre-pass `_bulk_universal_core_probes(rows)` did not accept or forward `db_adapter`. The nested `_probe_one(row)` then called `resolve_ssh_for_sitemap_row(hostname)` with no `db_adapter=`, falling through to `get_database_adapter()` — which consults `os.getenv("DATABASE_TYPE")` and constructs a fresh `SQLiteAdapter` / `PostgreSQLAdapter`. Potentially against a different db_path / different schema than the one `scan_drift` was handed.

Test code that passes a `MagicMock` `db_adapter` into `scan_drift` saw `_probe_one`'s row lookup land on the production database instead — invisible because most drift tests mock `_bulk_universal_core_probes` as a whole.

## What was fixed

Three surgical edits to `src/homelab_mcp/drift_detection.py`:

| Edit | Change |
|------|--------|
| `_bulk_universal_core_probes` signature | Added `*, db_adapter: DatabaseAdapter` (required, no default — `scan_drift` is the sole caller and always has one). |
| `_probe_one` resolve call | `resolve_ssh_for_sitemap_row(hostname)` → `resolve_ssh_for_sitemap_row(hostname, db_adapter=db_adapter)`. `_probe_one` is a closure inside `_bulk_universal_core_probes`, so `db_adapter` is in lexical scope — no `_probe_one` signature change. |
| `scan_drift` call site | `_bulk_universal_core_probes(ssh_eligible_rows)` → `_bulk_universal_core_probes(ssh_eligible_rows, db_adapter=db_adapter)`. The wrapping `asyncio.wait_for(..., 120.0)` and surrounding try/except untouched. |

## Tests added

| File | Addition |
|------|----------|
| `tests/test_drift_detection.py` | `test_probe_one_forwards_db_adapter` inside `TestScanDrift4Bucket`. Patches `homelab_mcp.drift_detection.resolve_ssh_for_sitemap_row` to capture every call's kwargs and short-circuit via `CredentialNotFoundError`. Asserts every call's `db_adapter` kwarg `is` the SAME instance (identity, not equality) the test passed into `scan_drift`. |
| `tests/test_ast_regression.py` | `TestPhase41DBAdapterHygiene` class with 2 methods: (1) AST walk asserts every `resolve_ssh_for_sitemap_row(...)` Call in `drift_detection.py` carries `db_adapter=` kwarg; (2) call-site floor (≥ 1) prevents silent guard erosion. |

## Verification

```
✓ ruff check src/homelab_mcp/drift_detection.py                            — clean
✓ mypy src/homelab_mcp/drift_detection.py                                  — clean
✓ tests/test_drift_detection.py                                            — 64 passed (63 + 1 new)
✓ tests/test_ast_regression.py::TestPhase41DBAdapterHygiene                — 2/2 passed
✓ tests/test_ast_regression.py (full)                                      — 28 passed (no regression on prior phases)
✓ Full unit suite                                                          — 905 passed, 0 failed
```

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| `_bulk_universal_core_probes` signature has `*, db_adapter: DatabaseAdapter` | ✓ |
| `grep -c "db_adapter=db_adapter" drift_detection.py` returns ≥ 2 | ✓ |
| `grep -c "resolve_ssh_for_sitemap_row(hostname, db_adapter=db_adapter)" drift_detection.py` returns 1 | ✓ |
| `grep -c "_bulk_universal_core_probes(ssh_eligible_rows, db_adapter=db_adapter)" drift_detection.py` returns 1 | ✓ |
| TestPhase39_1NoSkipInDriftEnum + TestPhase41BindingAwareResolver + TestPhase41HostDialHostHygiene + TestPhase41DBAdapterHygiene all GREEN | ✓ |
| Full unit suite GREEN | ✓ (905 passed) |

## Test-suite impact

All 9 existing references to `_bulk_universal_core_probes` in `tests/` are `patch(...)` mocks (mocking the helper as an attribute), so they automatically accept the new kwarg. No test-file edits required beyond the new regression test.

## Notable deviations

1. **Inline orchestrator execution** — Smart App Control kept blocking subagents; this plan was executed inline.

## WR-02 status

**Closed.** scan_drift's single-source-of-truth contract now holds end-to-end through the SSH pre-pass.

Future regression that drops the `db_adapter=` kwarg from any `resolve_ssh_for_sitemap_row(...)` call inside `drift_detection.py` will fail `TestPhase41DBAdapterHygiene::test_drift_resolve_ssh_for_sitemap_row_threads_db_adapter` (structural lock). A regression that silently constructs a fresh adapter through `get_database_adapter()` will fail `test_probe_one_forwards_db_adapter`'s identity check (functional lock).
