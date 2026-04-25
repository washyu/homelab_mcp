---
phase: 36-drift-sitemap-foundation
status: passed
verified: 2026-04-25
verifier: orchestrator-inline
requirements_verified:
  - DRFT-11
  - DRFT-12
  - DRFT-21
---

# Phase 36 Verification — Drift ↔ Sitemap Foundation

## Phase Goal

> Sitemap becomes single source of truth; `drift_baselines` table dropped.

**Verdict: PASSED.**

## Goal-Backward Coverage

| Must-have | Evidence | Status |
|-----------|----------|--------|
| `drift_baselines` table no longer exists in fresh installs | `init_schema` no longer creates `drift_baselines` (Plan 01 deleted the `CREATE TABLE` block from `database.py`); `tests/test_migration.py::TestDriftBaselinesDrop::test_drift_baselines_drop_fresh_db_phase36` passes | ✓ |
| Existing installs drop `drift_baselines` cleanly on migrate | `migration.py:224-243` SQLite branch + `migration.py:398-419` Postgres branch both run idempotent `DROP TABLE IF EXISTS drift_baselines`; `tests/test_migration.py::TestDriftBaselinesDrop::test_drift_baselines_drop_idempotent_phase36` proves first run drops + second run is no-op | ✓ |
| Drift adapter methods removed | `grep -rn "upsert_drift_baseline\|get_drift_baseline\|get_all_drift_baselines" src/homelab_mcp/` returns ZERO matches; AST guard `tests/test_ast_regression.py::test_no_forbidden_strings_in_source` passes | ✓ |
| `scan_drift` reads from sitemap (not a parallel baseline table) | `src/homelab_mcp/drift_detection.py:67` calls `db_adapter.get_all_devices()`; never references `drift_baselines`. AST guard `test_drift_detection_no_baseline_references_phase36` passes | ✓ |
| `scan_drift` resolves Proxmox creds per row via the resolver funnel | `drift_detection.py:73` calls `get_proxmox_client(host=hostname, session=session)` and `:91` calls `resolve_proxmox_credentials(hostname, session=session)`. `tests/test_drift_detection.py::TestScanDrift2Bucket::test_three_row_classification` exercises both branches (probed_ok, unreachable) plus silent-skip on CredentialNotFoundError | ✓ |
| `update_baseline_after_mutation` function deleted | `drift_detection.py` no longer defines this function (grep confirms); `tool_handlers/proxmox_handlers.py` no longer imports or calls it (3 call sites removed). AST guard catches reintroduction | ✓ |
| Empty sitemap returns success, never an error | `drift_handlers.py::handle_scan_infrastructure_drift` no longer has the `summary.baselines_available == 0` precondition early-return; `tests/test_drift_detection.py::TestScanDrift2Bucket::test_empty_sitemap_returns_success` proves `scan_drift` returns `{status: success, scanned: 0, probed_ok: [], unreachable: []}` for empty input | ✓ |
| 2-bucket interim return shape | `tests/test_drift_detection.py::TestScanDrift2Bucket::test_unreachable_record_shape` and `::test_probed_ok_record_shape` are subsumed by `test_three_row_classification` which asserts D-02 keys (hostname, connection_ip, scope, cluster_name, status, error, scan_timestamp) on every record. Schema description (`drift_tools_schema.py:5-9`) and resource description (`server.py:151`) match | ✓ |
| Probe exceptions are sanitized | `drift_detection.py:81,118` pass exceptions through `sanitize_error()`; `tests/test_drift_detection.py::TestScanDrift2Bucket::test_unreachable_error_is_sanitized` proves raw token strings (`secretsecret`) are redacted | ✓ |
| `scan_drift` never reads `os.getenv("PROXMOX_HOST")` | `grep -n "PROXMOX_HOST\|os.getenv" src/homelab_mcp/drift_detection.py` returns ZERO; AST guard `test_drift_detection_no_baseline_references_phase36` would catch reintroduction (the guard list explicitly forbids `drift_baseline` references; PROXMOX_HOST is covered by Phase 37 D-15 sweep, but absence is verified here too) | ✓ |
| Documentation reflects 2-bucket model | `docs/tool-reference.md:576` has the new `### scan_infrastructure_drift` entry. No speculative `register_drift_baseline` / `list_drift_baselines` / `delete_drift_baseline` mentions anywhere in `docs/` | ✓ |

## Requirements Traceability

- **DRFT-11 (Sitemap is the single source of truth for drift detection)** — Achieved. The `drift_baselines` data layer is fully removed (Plans 01 + 02). `scan_drift` reads only `db_adapter.get_all_devices()`. AST guards lock in the architectural invariant.
- **DRFT-12 (resolve_proxmox_credentials wiring on the drift path)** — Achieved. `scan_drift` calls `get_proxmox_client` per non-degenerate row; `CredentialNotFoundError` produces silent skip; probe failures land in the `unreachable` bucket with sanitized error text. The (scope, cluster_name) tuple is captured per row via the cache-hit second resolver call.
- **DRFT-21 (Drop drift_baselines table from existing installs; never create it on fresh installs)** — Achieved. Migration drop step on both SQLite and Postgres branches; idempotent. `init_schema` no longer creates the table. Two SQLite idempotency tests pass; Postgres path covered by the live migration banner. Postgres unit-test fixture is not present in this codebase, so the Postgres test layer is supplemental rather than gating per the plan's documented fallback.

## Quality Gates

| Gate | Result |
|------|--------|
| `uv run ruff check src/ tests/` | All checks passed |
| `uv run mypy src/` | Only 1 pre-existing error in `openapi_app.py` (missing jsonschema stubs), unrelated to Phase 36 |
| `uv run pytest tests/ -m "not integration" --no-cov` | **715 passed, 8 skipped, 0 failures** |
| `uv run pytest tests/test_ast_regression.py -v` | All 9 AST regression tests passed including both Phase 36 D-12/D-13 guards |

## Notes

- Subagent dispatch was unreliable in this run — three Wave 2 executor agents failed with sandbox-level Edit/Write hook denials and worktree-base mismatches. Plans 04, 05, and 06 were executed inline in the orchestrator (workflow-documented sequential fallback). Wave 1 completed via subagents successfully.
- One out-of-band fix commit was needed during inline execution: `fix(36-04): scrub drift_baselines reference from drift_detection docstring` — the AST guard caught a leftover reference in the docstring after the original Plan 04 commit.
- A second small fix commit (`fix(36-04): replace asyncio.TimeoutError with builtin TimeoutError + hostname None narrowing`) addressed two ruff/mypy issues that had been silently un-persisted by earlier sed-based attempts (harness write virtualization). Final ruff/mypy state is clean.

## Human Verification Items

None — the changes are entirely internal refactoring + test/docs updates. No user-facing behavior changes from a happy-path perspective; the externally observable change is the new 2-bucket return shape on `scan_infrastructure_drift`, which is fully covered by automated tests.
