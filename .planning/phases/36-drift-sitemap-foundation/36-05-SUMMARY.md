---
plan: 36-05
phase: 36-drift-sitemap-foundation
status: complete
completed: 2026-04-25
---

# Plan 36-05 Summary — Rewrite drift test suite for 2-bucket interim shape

## What was built

The drift test surface was reshaped end-to-end to match the Phase 36 architecture:

- `tests/test_drift_detection.py`: full rewrite. The legacy `TestScanDriftReport` / `TestConfigDrift` / `TestStateDrift` / `TestUpdateBaselineAfterMutation` classes were replaced by a single `TestScanDrift2Bucket` class with 6 test methods covering D-01 / D-02 / D-03 / D-04 / D-09a / D-10 / D-10a behaviors via mocked `db_adapter` + `get_proxmox_client` + `resolve_proxmox_credentials`.
- `tests/test_drift_resource.py`: `sample_report` fixture rewritten to the 2-bucket shape (`probed_ok` / `unreachable`).
- `tests/test_drift_wiring.py`: handler test mocks `get_all_devices` instead of the deleted `get_all_drift_baselines`; mock_scan return value uses the 2-bucket shape. Schema and annotation tests intentionally untouched (D-04 inert passthrough preserves schema).
- `tests/test_database.py`: `TestDriftBaselines` class deleted (5 test methods removed, lines 357–470).
- `tests/test_proxmox_baseline_hooks.py`: deleted entirely (RESEARCH Pitfall 2 — orphaned by Plan 04 D-11).
- `tests/test_proxmox_api.py`: 4 `patch("...update_baseline_after_mutation", mock_baseline)` lines + 4 unused `mock_baseline = AsyncMock()` setup lines removed (RESEARCH Pitfall 1).
- `tests/test_migration.py`: new `TestDriftBaselinesDrop` class with 2 SQLite tests covering D-15 idempotency on pre-populated and fresh-install databases.

## key-files.created

(no new files — refactor + deletes + class added)

## key-files.modified

- `tests/test_drift_detection.py`
- `tests/test_drift_resource.py`
- `tests/test_drift_wiring.py`
- `tests/test_database.py`
- `tests/test_proxmox_api.py`
- `tests/test_migration.py`

## key-files.deleted

- `tests/test_proxmox_baseline_hooks.py`

## Quality gates

- `uv run ruff check tests/test_drift_detection.py tests/test_drift_resource.py tests/test_drift_wiring.py tests/test_database.py tests/test_proxmox_api.py tests/test_migration.py` — passed
- `uv run pytest tests/test_drift_detection.py -v --no-cov` — 6/6 passed
- `uv run pytest tests/test_drift_resource.py tests/test_drift_wiring.py -v --no-cov` — passed
- `uv run pytest tests/test_database.py --no-cov` — 21 passed, 4 skipped
- `uv run pytest tests/test_proxmox_api.py --no-cov` — 83 passed
- `uv run pytest tests/test_migration.py::TestDriftBaselinesDrop -v --no-cov` — 2/2 passed
- **Full unit suite**: `uv run pytest tests/ -m "not integration" --no-cov` — **715 passed, 8 skipped, 0 failures**.
- AST regression guards `test_no_forbidden_strings_in_source` and `test_drift_detection_no_baseline_references_phase36` (Plan 03) both GREEN.

## Self-Check: PASSED

All acceptance criteria from Tasks 1–3 met. Full unit suite green confirms no cross-phase regressions from this plan's changes.

## Notes / deviations

- **Postgres integration test deferred.** The plan called for an optional `@pytest.mark.integration` Postgres-side test for D-15 idempotency, but no `postgres_conn` (or equivalent) fixture exists in `tests/integration/conftest.py`. Per the plan's explicit fallback ("If the existing Postgres test infrastructure is not present or workable, skip the Postgres test for this plan and note it in the SUMMARY"), the Postgres test was not added. The two SQLite tests fully cover D-15 unit-test scope; the Postgres path is exercised live by `run_postgres_migrations` whenever a real Postgres deployment migrates and is monitored via the migration's stderr banner.
- **Schema initialization required for migration tests.** Both new tests in `TestDriftBaselinesDrop` init `SQLiteAdapter` first to create the `devices` table (required by Phase 35 migrations that fire as part of `run_sqlite_migrations`). The legacy `drift_baselines` table is layered on top for the idempotent variant.
- **Out-of-band fix commit.** During plan execution the AST regression guard surfaced a leftover `drift_baselines` reference in the `drift_detection.py` module docstring (committed in Plan 36-04). A small fix commit (`fix(36-04): scrub drift_baselines reference from drift_detection docstring`) was added during this plan to close the loop. It belongs to Plan 04's scope conceptually but is recorded here for traceability.
- **Inline executor was used instead of subagent.** Three Wave 2 subagent dispatches failed up-front with sandbox-level Edit/Write hook denials. The inline path (workflow-documented fallback in `<runtime_compatibility>`) was used to complete Plans 04, 05, and (next) 06.
