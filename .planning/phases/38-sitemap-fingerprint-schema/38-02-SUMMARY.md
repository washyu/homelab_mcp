---
phase: 38-sitemap-fingerprint-schema
plan: 02
subsystem: database
tags: [sqlite, migration, schema, sitemap, fingerprint, drift-detection, alter-table]

# Dependency graph
requires:
  - phase: 35-sitemap-discovery-reliability
    provides: NetworkDevice JSON-string-in-dataclass convention (D-09b), ALTER TABLE ADD COLUMN migration pattern (D-09c), schema-rebuild branch with target_cols list, hostname-as-natural-key upsert (D-01)
  - phase: 36-drift-sitemap-foundation
    provides: sitemap as single source of truth for drift detection (D-01)
provides:
  - "NetworkDevice.fingerprint: str | None field (JSON-serialized dict)"
  - "parse_discovery_output branch that JSON-serializes data['fingerprint'] into device.fingerprint"
  - "SQLite devices table includes fingerprint TEXT column between block_devices and uptime"
  - "run_sqlite_migrations idempotent ALTER TABLE devices ADD COLUMN fingerprint TEXT step (mirrors Phase 35 D-09c)"
  - "Schema-rebuild branch carries fingerprint column on pre-Phase-35 → Phase 38 upgrade path (CREATE TABLE devices_new + target_cols list both updated)"
affects: [38-03, 38-04, 38-05, 38-06, 39, drift-detection, sitemap-changed-bucket]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-column JSON-string convention for freeform per-host capability data (Phase 35 D-09b mirror)"
    - "Idempotent PRAGMA-then-ALTER migration step (Phase 35 D-09c mirror)"
    - "Schema-rebuild branch dual-update (CREATE TABLE devices_new column block + dynamic target_cols list)"

key-files:
  created: []
  modified:
    - "src/homelab_mcp/sitemap.py (NetworkDevice field at line 58, parse branch at lines 130-132)"
    - "src/homelab_mcp/database.py (CREATE TABLE devices column at line 143)"
    - "src/homelab_mcp/migration.py (ALTER TABLE step at lines 81-91, schema-rebuild CREATE TABLE devices_new column at line 183, target_cols list entry at line 219)"
    - "tests/test_sitemap.py (sample_ssh_discovery_success fixture extension at lines 55-61, test_parse_discovery_output_fingerprint_phase38 at lines 133-142)"
    - "tests/test_database.py (test_run_sqlite_migrations_adds_fingerprint_column_idempotently_phase38 at lines 681-731)"

key-decisions:
  - "Field placement: fingerprint declared after block_devices in NetworkDevice dataclass (sitemap.py line 58), keeping JSON-string fields grouped together — mirrors Phase 35 D-09b layout."
  - "Migration step uses literal column name in ALTER TABLE (not f-string interpolation against a variable) — single-column case doesn't need the loop pattern that Phase 35 D-09c used for three columns."
  - "Schema-rebuild branch update placed between block_devices and uptime in BOTH CREATE TABLE devices_new AND target_cols list — consistent ordering with init_schema's CREATE TABLE."

patterns-established:
  - "Phase 38 fingerprint column: idempotent ADD COLUMN + schema-rebuild parity. Future phases adding sitemap columns must update both the SQLiteAdapter.init_schema CREATE TABLE block AND the migration.py schema-rebuild CREATE TABLE devices_new + target_cols list (D-08b)."

requirements-completed: [DRFT-20]

# Metrics
duration: 18min
completed: 2026-04-26
---

# Phase 38 Plan 02: Sitemap Fingerprint Schema Substrate Summary

**SQLite devices table extended with idempotent fingerprint TEXT column + NetworkDevice dataclass field + parse_discovery_output JSON-string branch — plus schema-rebuild branch parity for pre-Phase-35 DB upgrade paths.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-26T06:41Z (worktree base reset)
- **Completed:** 2026-04-26T06:59Z
- **Tasks:** 2 (TDD: RED gate + GREEN gate)
- **Files modified:** 5 (3 source, 2 test)

## Accomplishments

- **NetworkDevice.fingerprint field** added to dataclass with JSON-string type signature, mirroring Phase 35 D-09b convention for usb/pci/block columns.
- **parse_discovery_output branch** wires `data["fingerprint"]` from the discovery payload into `device.fingerprint = json.dumps(...)`, keeping serialization at parse time rather than write time.
- **SQLite CREATE TABLE devices** includes new `fingerprint TEXT` column between `block_devices TEXT` and `uptime TEXT` in `SQLiteAdapter.init_schema()` so fresh installs land the column without needing migrations to fire.
- **Idempotent migration step** (`add_column_fingerprint`) added to `run_sqlite_migrations` mirroring the Phase 35 D-09c PRAGMA-then-ALTER pattern; legacy DBs receive the column with NULL on existing rows.
- **Schema-rebuild branch parity** (D-08b): the rebuild path that fires when stale `UNIQUE(hostname, connection_ip)` is detected now carries `fingerprint TEXT` in BOTH the `CREATE TABLE devices_new` block AND the dynamic `target_cols` list — without this, pre-Phase-35 DBs upgrading through Phase 38 would lose the column on rebuild.
- **TDD discipline observed**: RED gate (Task 1) verified before GREEN (Task 2). Both new tests fail with the expected error messages before implementation lands and pass after.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave-0 RED tests for parse + migration** — `e837481` (test)
2. **Task 2: Land schema field + parse branch + migration** — `6100dc1` (feat)

_Note: Task 2 is a single GREEN commit per the plan's TDD instructions; no separate refactor commit was needed (the implementations stand on their own, mirroring established Phase 35 patterns)._

## Files Created/Modified

- `src/homelab_mcp/sitemap.py` — added `fingerprint: str | None = None` field to `NetworkDevice` (line 58); added parse branch in `parse_discovery_output` that JSON-serializes `data["fingerprint"]` (lines 130-132).
- `src/homelab_mcp/database.py` — added `fingerprint TEXT` column to `SQLiteAdapter.init_schema()` `CREATE TABLE devices` block between `block_devices TEXT` and `uptime TEXT` (line 143).
- `src/homelab_mcp/migration.py` — added Phase 38 D-08 PRAGMA-then-ALTER block immediately after the Phase 35 D-09c block (lines 81-91, appends `add_column_fingerprint`); added `fingerprint TEXT` to the schema-rebuild `CREATE TABLE devices_new` block (line 183); added `"fingerprint",` to the `target_cols` list literal (line 219).
- `tests/test_sitemap.py` — extended `sample_ssh_discovery_success` fixture with a `fingerprint` sub-dict containing kernel/os/package keys (lines 55-61); added `test_parse_discovery_output_fingerprint_phase38` (lines 133-142).
- `tests/test_database.py` — added `test_run_sqlite_migrations_adds_fingerprint_column_idempotently_phase38` (lines 681-731): builds a pre-Phase-38 schema with usb/pci/block but no fingerprint, inserts a legacy row, runs the migration, asserts `add_column_fingerprint` in `applied1` AND that the legacy row survived with NULL fingerprint, then re-runs and asserts `add_column_fingerprint` is NOT in `applied2`.

## Decisions Made

- **Single-column ALTER pattern.** Phase 35 D-09c used a loop over `("usb_devices", "pci_devices", "block_devices")` because it added three columns at once. Phase 38 only adds one column, so the literal `ALTER TABLE devices ADD COLUMN fingerprint TEXT` is cleaner than a one-element loop. The PRAGMA + idempotency guard is identical.
- **Schema-rebuild grouping.** Placed `fingerprint TEXT` and `"fingerprint",` between `block_devices` and `uptime` in BOTH the migration's schema-rebuild CREATE TABLE block AND the target_cols list — consistent with the position chosen in `SQLiteAdapter.init_schema`'s CREATE TABLE. Future phases that add sitemap columns can pattern-match this ordering.
- **No store_device wiring in this plan.** The plan explicitly defers store_device's UPDATE/INSERT branch updates to Plan 03. Confirmed during Task 2 validation that the round-trip test `test_store_and_retrieve_device` passes despite the new column — `device_data.get("fingerprint")` returns None which SQLite stores as NULL via the absent-from-INSERT path. No round-trip tests needed Plan 03 attention.

## Deviations from Plan

None — plan executed exactly as written. Both Task 1 RED tests landed verbatim (with the fixture extension and assertion structure described in the plan); both Task 2 source edits mirror the Phase 35 D-09b/D-09c patterns the plan referenced.

The only out-of-band activity was a worktree-routing recovery: the initial Edit calls to the test files used the unprefixed `C:\Users\washy\projects\mcp_python_server\tests\...` path (which resolves to the main repo) instead of the worktree-prefixed path. The misplaced edits in the main repo were reverted via `git checkout --` (operating on the main repo, NOT the worktree) and then re-applied to the worktree's `.claude\worktrees\agent-a7d9194b0d07601d2\tests\...` path. Final commits in this worktree contain exactly the intended changes; no rules-driven deviations were triggered.

## Issues Encountered

- **Worktree path routing.** The Edit tool defaulted to the main repo path for test files when the path didn't include the worktree prefix. Caught the issue when `git status` in the worktree was empty despite expected edits. Recovery: reverted the misplaced main-repo edits, re-applied with explicit `C:\Users\washy\projects\mcp_python_server\.claude\worktrees\agent-a7d9194b0d07601d2\tests\...` paths, and verified via `git status --short` in the worktree before each commit. Final-state verification: `grep -c fingerprint tests/test_sitemap.py tests/test_database.py` returned the expected counts (7 and 10) in the worktree files.
- **ruff-format reformatting out-of-scope files.** `scripts/quality-check.sh` invoked `ruff format` which restyled multi-line dict literals in `src/homelab_mcp/drift_detection.py`, `tests/test_ast_regression.py`, and `tests/test_migration.py`. These reformats are pre-existing formatting drift unrelated to Phase 38 D-08. Per the executor scope boundary, those files were restored via `git checkout -- <files>` before committing Task 2 — only the three intended source files (`sitemap.py`, `database.py`, `migration.py`) were committed. Ruff/mypy on the three targeted files pass clean.

## Notes for Plan 03

- **`store_device` is untouched.** Plan 03 owns the SQLite UPDATE/INSERT branch additions for `fingerprint`, the SQLite `get_all_devices` JSON-decode loop addition (`{}` default for fingerprint vs `[]` for usb/pci/block since fingerprint is a dict), the Postgres `_maybe_json_load` wiring inside `system_info`, and the Postgres `get_all_devices` flatten dict.
- **Existing round-trip tests still pass.** No `test_database.py` round-trip tests broke from the CREATE TABLE addition alone — `device_data.get("fingerprint")` returns None on dataclasses that don't set it and SQLite stores NULL silently. No flagged test debt for Plan 03.
- **AST guard at `tests/test_ast_regression.py:392`** (hostname-natural-key for SELECT FROM devices) was not triggered: this plan adds CREATE TABLE / ALTER TABLE / INSERT INTO devices_new logic but no new SELECT-by-hostname query against `devices`. Plan 04 will add `update_device_fingerprint` adapter method, which will need to use the Phase 35 D-01 pattern for its hostname lookup.

## User Setup Required

None — no external service configuration required. Migration is automatic on next `NetworkSiteMap` instantiation.

## Next Phase Readiness

- **Plan 03 (SQLite + Postgres adapter wiring) unblocked.** The schema substrate exists; Plan 03 can wire `store_device` round-trip without needing column-creation work.
- **Plan 04 (`update_device_fingerprint` adapter method + MCP tool) unblocked on the column-existence side.** Plan 04 still needs Plan 03's round-trip wiring before its merge logic can read existing values, but the column it reads/writes against is now present.
- **Phase 39's `changed` bucket detection (DRFT-19) reads what Plan 02-04 store.** Plan 02 ships the storage substrate; Phase 39 will diff what gets persisted.

## Self-Check

- [x] `src/homelab_mcp/sitemap.py` exists with `fingerprint: str | None = None` at line 58 — VERIFIED
- [x] `src/homelab_mcp/sitemap.py` parse branch `device.fingerprint = json.dumps(discovery_data["fingerprint"])` at line 132 — VERIFIED
- [x] `src/homelab_mcp/database.py` `CREATE TABLE devices` includes `fingerprint TEXT,` at line 143 — VERIFIED
- [x] `src/homelab_mcp/migration.py` Phase 38 D-08 ALTER block exists with `add_column_fingerprint` at lines 81-91 — VERIFIED
- [x] `src/homelab_mcp/migration.py` schema-rebuild `devices_new` CREATE TABLE includes `fingerprint TEXT,` at line 183 — VERIFIED
- [x] `src/homelab_mcp/migration.py` `target_cols` list contains `"fingerprint",` at line 219 — VERIFIED
- [x] `tests/test_sitemap.py` `test_parse_discovery_output_fingerprint_phase38` defined at line 133 — VERIFIED
- [x] `tests/test_database.py` `test_run_sqlite_migrations_adds_fingerprint_column_idempotently_phase38` defined at line 681 — VERIFIED
- [x] Commit `e837481` (test RED gate) exists — VERIFIED
- [x] Commit `6100dc1` (feat GREEN gate) exists — VERIFIED
- [x] Full unit test suite green (734 passed) — VERIFIED
- [x] mypy on three modified source files clean — VERIFIED
- [x] ruff on src/homelab_mcp/ tests/ clean — VERIFIED
- [x] AST regression guards (Phase 35 D-15, including `test_store_device_matches_on_hostname_alone_phase35` at line 392 and `test_ssh_discover_system_wraps_every_conn_run_phase35` at line 447) still pass — VERIFIED

## Self-Check: PASSED

---
*Phase: 38-sitemap-fingerprint-schema*
*Completed: 2026-04-26*
