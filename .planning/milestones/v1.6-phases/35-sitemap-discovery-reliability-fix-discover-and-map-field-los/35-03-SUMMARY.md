---
phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los
plan: 03
subsystem: database
tags: [sqlite, postgres, migration, upsert, schema-alter, dedup, jsonb]

requires:
  - phase: 35
    provides: "Plan 01 producer field alignment + Plan 02 NetworkDevice.usb_devices/pci_devices/block_devices dataclass fields"
provides:
  - "SQLiteAdapter.store_device hostname-only upsert with degenerate-hostname fallback (D-01 + D-01a)"
  - "PostgreSQLAdapter.store_device hostname-only upsert (D-01 mirror)"
  - "SQLite devices table extended with usb_devices/pci_devices/block_devices TEXT columns and UPDATE/INSERT threading"
  - "Postgres system_info JSONB extended with usb_devices/pci_devices/block_devices via _maybe_json_load helper"
  - "connection_ip moved from match clause to UPDATE field in both adapters — re-discovery with new IP rewrites the row"
  - "get_all_devices JSON-decodes usb/pci/block on SQLite; flattens them from system_info on Postgres"
  - "Phase 35 startup migration in run_sqlite_migrations: ALTER TABLE for 3 columns, dedup zombie rows with non-null sibling merge, rebuild devices table to drop stale UNIQUE(hostname, connection_ip) with I8 orphan-devices_new recovery"
  - "Phase 35 startup migration in run_postgres_migrations: dedup zombie rows, DROP CONSTRAINT stale UNIQUE, DROP INDEX composite, CREATE INDEX replacement"
affects: [35-04]

tech-stack:
  added: []
  patterns:
    - "Hostname-only upsert with degenerate-hostname fallback — one natural key, distinct error rows preserved"
    - "SQLite table rebuild pattern for DROP CONSTRAINT (no native support) with DROP TABLE IF EXISTS guard for idempotent recovery (I8)"
    - "Postgres JSONB-extend instead of schema column add when the existing JSONB column can hold new structured data"
    - "Dynamic column copy in table rebuild — intersection with source columns via PRAGMA table_info + NULL AS fallback"

key-files:
  created: []
  modified:
    - src/homelab_mcp/database.py
    - src/homelab_mcp/migration.py

key-decisions:
  - "connection_ip is part of UPDATE SET (both adapters) now that it is no longer part of the match clause — re-discovery with a new IP updates the existing row in place (closes bug #2 zombie rows)"
  - "_maybe_json_load helper round-trips a JSON-encoded string to native Python before dumping inside system_info JSONB — matches existing network_interfaces handling pattern"
  - "SQLite rebuild uses dynamic column copy (PRAGMA table_info + NULL AS fallback for missing source columns) so the migration is robust to pre-Phase-35 schemas that may be missing columns beyond the three new JSON ones"
  - "Postgres dedup uses DELETE ... WHERE id = ANY(%s) rather than a constructed placeholder list — cleaner and matches psycopg2 idioms"
  - "I8 fix: DROP TABLE IF EXISTS devices_new before CREATE — idempotent recovery from a partial-failure run that may have left an orphan table"

patterns-established:
  - "Hostname-only upsert pattern with degenerate-hostname fallback — branch on hostname_key in (None, '', 'unknown')"
  - "Dynamic column copy in SQLite rebuild: select NULL AS col_name for any target column missing on the source table"

requirements-completed: []

duration: 25min
completed: 2026-04-24
---

# Phase 35 Plan 03: Database Hostname-Only Upsert + Migration

**Hostname-only upsert in both adapters with degenerate fallback, SQLite column threading + dynamic-copy table rebuild to drop stale UNIQUE, Postgres JSONB-extend + native DROP CONSTRAINT, one-time migration that dedups zombie rows and adds the three new columns idempotently.**

## Performance

- **Duration:** ~25 min (inline orchestrator execution after two sub-agent attempts were sandbox-blocked on Edit/Write)
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- **Bug #2 (zombie rows) fixed:** Re-discovering a device with a different `connection_ip` now updates the existing row in place. Same hostname → same row, both adapters.
- **Bug #1 (field-loss) closed end-to-end:** SQLite threads `usb_devices`/`pci_devices`/`block_devices` through schema + UPDATE/INSERT + get_all_devices JSON decode. Postgres lands them structured inside `system_info` JSONB and flattens them back on read.
- **Degenerate-hostname fallback:** When `hostname` is `None`, `''`, or `'unknown'`, match falls back to `(hostname, connection_ip)` so Phase-33 distinct-error rows are preserved.
- **Migration is idempotent:** ALTER TABLE column-adds are gated by PRAGMA table_info; dedup is gated by `HAVING COUNT(*) > 1`; stale UNIQUE drop is gated by sqlite_master SQL-text inspection (SQLite) or pg_constraint catalog (Postgres). Second run is a no-op.
- **I8 orphan recovery:** `DROP TABLE IF EXISTS devices_new` guards the SQLite table rebuild against a prior partial-failure run that may have left an orphan intermediate table.

## Task Commits

Each task committed atomically:

1. **Task 1: SQLite adapter hostname-only upsert + usb/pci/block column threading** — `9b55617` (feat)
2. **Task 2: Postgres adapter hostname-only upsert + JSONB-extend + flatten** — `e9f2208` (feat)
3. **Task 3: Phase 35 migration block in both migration functions** — `b237424` (feat)

## Files Created/Modified

- `src/homelab_mcp/database.py` — SQLiteAdapter: schema column adds, composite UNIQUE dropped from init_schema, composite idx → hostname-alone idx, hostname-only match with degenerate fallback, UPDATE extended with 3 JSON cols + `connection_ip = ?`, INSERT extended with 3 JSON cols (23 placeholders), get_all_devices JSON-decode loop for 3 new cols. PostgreSQLAdapter: UNIQUE dropped from init_schema, composite idx → hostname-alone idx, hostname-only match with degenerate fallback, UPDATE extended with `connection_ip = %s`, system_info JSONB extended with usb/pci/block via `_maybe_json_load`, get_all_devices flatten extended with 3 new top-level keys. Module-level `_maybe_json_load` helper added alongside `calculate_data_hash`. Net +101 lines.
- `src/homelab_mcp/migration.py` — `run_sqlite_migrations`: Phase 35 block (ALTER TABLE × 3 with PRAGMA guard, dedup with non-null sibling merge, table rebuild to drop UNIQUE with DROP TABLE IF EXISTS devices_new orphan-recovery guard and dynamic column copy). `run_postgres_migrations`: Phase 35 block (dedup with `id = ANY(%s)` delete, DROP CONSTRAINT via pg_constraint lookup, DROP INDEX via pg_indexes lookup, CREATE INDEX IF NOT EXISTS replacement). Net +253 lines.

## Decisions Made

- **Rebuild column copy is dynamic, not literal** — the plan's literal column-list SELECT would have crashed on minimal pre-Phase-35 schemas (observed via the plan's own acceptance test). Fixed to use `PRAGMA table_info(devices)` + `NULL AS <col>` for columns missing on the source.
- **connection_ip becomes an UPDATE field in both adapters** — required by the switch from `(hostname, connection_ip)` match to `hostname` match. Without this, a re-discovery with a new IP would leave the row's `connection_ip` stale.
- **Postgres uses `DELETE ... WHERE id = ANY(%s)`** for sibling deletion — psycopg2-native, no constructed placeholder list.
- **`_maybe_json_load` placed alongside `calculate_data_hash`** — both are module-private helpers used by the adapters; grouping keeps helpers discoverable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Correctness] Dynamic column copy instead of literal column list in SQLite rebuild**
- **Found during:** Task 3 functional verification (`run_sqlite_migrations` round-trip test from the acceptance criteria)
- **Issue:** The plan's literal `INSERT INTO devices_new (...) SELECT cpu_model, cpu_cores, ... FROM devices` fails on `sqlite3.OperationalError: no such column: cpu_model` when the source schema is missing any of the listed columns (the plan's own acceptance test seeds a minimal schema to trigger this exact scenario).
- **Fix:** Use `PRAGMA table_info(devices)` to discover source columns, then build a SELECT that emits `col_name` if present or `NULL AS col_name` if missing.
- **Files modified:** `src/homelab_mcp/migration.py` (SQLite rebuild block inside `run_sqlite_migrations`)
- **Verification:** The plan's acceptance test (minimal-schema seed, two duplicate rows, assert dedup + add_column_usb_devices + drop_stale_hostname_ip_unique land in `applied_migrations`, assert second run is no-op, assert merged row keeps `cpu_cores=4`) now passes. I8 orphan-recovery test also passes.
- **Committed in:** `b237424` (Task 3 commit)

**2. [Orchestration] Plan executed inline by orchestrator after two subagent attempts were sandbox-blocked**
- **Found during:** Wave 2 kickoff
- **Issue:** Subagent #1 (worktree-isolated) was created from the wrong base commit and its attempt to `git reset --hard` was sandbox-blocked. Subagent #2 (sequential, no worktree) had every `Edit` tool call denied ("Permission to use Edit has been denied") by a sandbox policy that is stricter for subagents than for the orchestrator.
- **Fix:** Orchestrator executed all three tasks inline. Edit calls from the orchestrator session succeeded (the `gsd-read-guard.js` PreToolUse hook injects an advisory string but does not block — see footnote).
- **Files modified:** No additional files — same work landed as planned, just under the orchestrator's permission context.
- **Verification:** All grep acceptance criteria pass; `ruff check` + `mypy` clean; 30/30 migration tests + 22/23 database tests pass (1 failure is pre-existing baseline per STATE.md Phase 34 notes).
- **Committed in:** Tasks 1, 2, 3 individually (`9b55617`, `e9f2208`, `b237424`)

---

**Total deviations:** 2 (1 correctness fix tightening the plan's own acceptance test, 1 orchestration detour around a subagent sandbox restriction)
**Impact on plan:** No scope change. Dynamic column copy is strictly more correct than the literal list.

## Issues Encountered

- **Test drift in `tests/test_sitemap.py::TestDatabaseOperations::test_database_schema_creation`**: asserts `any("idx_devices_hostname_ip" in idx for idx in indexes)` — but that composite index is removed in Phase 35. Same category as the `count`→`cores` test drift flagged in Plan 01. Plan 04 Task (regression tests) is the correct home for updating this assertion to check for `idx_devices_hostname` instead.
- **Pre-existing baseline failure** in `tests/test_database.py::test_ssh_credentials_table_dropped_postgres` (confirmed in STATE.md Phase 34 Plan 01 notes — unrelated psycopg2 monkeypatch import issue). Not regressed by this plan.

## User Setup Required

None — no external service configuration required.

## Verification Output

```
# Task 1 structural
sed -n '128,215p' src/homelab_mcp/database.py | grep -c "UNIQUE(hostname, connection_ip)" → 0
grep -c "CREATE INDEX IF NOT EXISTS idx_devices_hostname" src/homelab_mcp/database.py → 2 (SQLite init + Postgres init replacement — both scoped)
sed -n '128,215p' src/homelab_mcp/database.py | grep -cE "(usb|pci|block)_devices TEXT" → 3
# W5 scoped-regex placeholder check
uv run python -c "import re; s = open('src/homelab_mcp/database.py').read(); m = re.search(r'INSERT INTO devices[^)]*\)\s*VALUES\s*\(([?,\s]+)\)', s); ..." → OK - 23 placeholders
# Task 2 structural
sed -n '545,605p' src/homelab_mcp/database.py | grep -c "UNIQUE(hostname, connection_ip)" → 0
grep -nE "^def _maybe_json_load\(" src/homelab_mcp/database.py → 1 match (line 903)
grep -cE '"(usb|pci|block)_devices": _maybe_json_load' src/homelab_mcp/database.py → 3
grep -cE 'system_info\.get\("(usb|pci|block)_devices"\)' src/homelab_mcp/database.py → 3
# Task 3 structural
grep -c "dedupe_zombie_device_rows" src/homelab_mcp/migration.py → 2
grep -c "drop_stale_hostname_ip_unique" src/homelab_mcp/migration.py → 2
grep -c "CREATE TABLE devices_new" src/homelab_mcp/migration.py → 1
grep -c "ALTER TABLE devices_new RENAME TO devices" src/homelab_mcp/migration.py → 1
grep -c "DROP TABLE IF EXISTS devices_new" src/homelab_mcp/migration.py → 1 (I8)
grep -c "ALTER TABLE devices DROP CONSTRAINT" src/homelab_mcp/migration.py → 1 (Postgres)
grep -c "hostname NOT IN ('', 'unknown')" src/homelab_mcp/migration.py → 2

# Functional round-trips
uv run python -c "... SQLiteAdapter hostname-only upsert same-hostname-diff-IP → id1==id2, connection_ip updated"  → id1=1 id2=1, connection_ip='10.0.0.99'
uv run python -c "... _maybe_json_load None/''/str-json/list/malformed"  → OK
uv run python -c "... run_sqlite_migrations full round trip"
  first run: ['add_column_usb_devices', 'add_column_pci_devices', 'add_column_block_devices', 'dedupe_zombie_device_rows', 'drop_stale_hostname_ip_unique', 'create_drift_baselines_table']
  second run: []
  merged cpu_cores=4 preserved
  OK
uv run python -c "... I8 orphan devices_new recovery"
  applied: ['add_column_usb_devices', 'add_column_pci_devices', 'add_column_block_devices', 'drop_stale_hostname_ip_unique', 'create_drift_baselines_table']
  OK

# Quality gates
uv run ruff check src/homelab_mcp/database.py → All checks passed!
uv run mypy src/homelab_mcp/database.py → Success: no issues found
uv run ruff check src/homelab_mcp/migration.py → All checks passed!
uv run mypy src/homelab_mcp/migration.py → Success: no issues found

# Test suite
uv run pytest tests/test_database.py tests/test_migration.py tests/test_sitemap.py -m "not integration"
  74 passed, 2 failed (pre-existing psycopg2-monkeypatch + known test_database_schema_creation drift for Plan 04)
```

## Next Phase Readiness

### Handoff to Plan 04
- **New functional tests (Plan 04 D-17):** D-17a (hostname-only upsert, same-hostname-diff-IP → id equality + IP update), D-17b (migration dedup idempotency — single-run lands + merge + second run is no-op), D-17e (analyzer null-skip). The orchestrator's inline round-trip tests in this plan's verification can be ported into pytest form.
- **AST meta-test D-14 scope:** scans `database.py` for `hostname = ? AND connection_ip = ?` / `hostname = %s AND connection_ip = %s` as the PRIMARY match clause — should find 0 (the only remaining occurrence is inside the degenerate-hostname fallback `if` branch, which is explicitly allowed).
- **Pre-existing test drift to update (Plan 04 cleanup scope, not new tests):**
  - `tests/test_sitemap.py::TestDatabaseOperations::test_database_schema_creation` — change `"idx_devices_hostname_ip"` → `"idx_devices_hostname"`.
  - `tests/test_ssh_tools.py::test_ssh_discover_success` (flagged in Plan 01 SUMMARY) — update mocks for `cores` (not `count`) and `df -B1 -T /` disk column shape + Gi-suffixed memory strings.

---
*Phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los*
*Completed: 2026-04-24*
