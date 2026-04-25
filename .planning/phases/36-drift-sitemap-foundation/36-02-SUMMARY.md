---
phase: 36-drift-sitemap-foundation
plan: 02
subsystem: database/migration
tags: [migration, sqlite, postgres, drift, footgun-removal]
requirements:
  - DRFT-21
requirements-completed:
  - DRFT-21
dependency-graph:
  requires:
    - migration.py Phase 33 ssh_credentials drop precedent (verbatim shape reuse)
    - migration.py Phase 35 stale-UNIQUE rebuild step (placement anchor in both branches)
  provides:
    - Idempotent DROP TABLE drift_baselines on SQLite startup migration
    - Idempotent DROP TABLE drift_baselines on Postgres startup migration
    - "drop_drift_baselines_table" migration name in applied_migrations on both adapters
  affects:
    - src/homelab_mcp/migration.py
tech-stack:
  added: []
  patterns:
    - Idempotent IF EXISTS startup migration (Phase 33/35 idiom extended)
    - Stderr banner emission on first-run drop, silent on second run
key-files:
  created: []
  modified:
    - src/homelab_mcp/migration.py
decisions:
  - id: D-05
    summary: Replace SQLite auto-create-on-startup block with idempotent DROP step
  - id: D-05-pg
    summary: Add Postgres drop step using information_schema.tables existence check
  - id: D-08
    summary: Emit stderr banner per Phase 33 ssh_credentials shape; no row count
metrics:
  duration: 115s
  completed: "2026-04-25"
  tasks-completed: 2
  files-modified: 1
---

# Phase 36 Plan 02: drift_baselines Migration Drop Summary

Replaced the auto-create-on-startup block for `drift_baselines` in `migration.py` SQLite branch with an idempotent `DROP TABLE IF EXISTS` step that mirrors the Phase 33 `ssh_credentials` cleanup verbatim, and added a parallel drop step to the Postgres branch using `information_schema.tables` for the existence check.

## What Shipped

- **SQLite branch:** the auto-create block (formerly the path that created `drift_baselines` on every start) is gone. In its place is a guarded existence check (`SELECT name FROM sqlite_master WHERE type='table' AND name='drift_baselines'`) followed by `DROP INDEX IF EXISTS idx_drift_baselines_node_vmid` + `DROP TABLE IF EXISTS drift_baselines`. On the run that performs the drop, `applied_migrations.append("drop_drift_baselines_table")` and a two-line stderr banner per D-08 phrasing.
- **Postgres branch:** identical shape using `SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'drift_baselines')`. Same `DROP INDEX` + `DROP TABLE` + applied_migrations append. Banner mentions "from Postgres" explicitly. Block placed after the Phase 35 Postgres stale-UNIQUE drop step (after the `idx_devices_hostname` CREATE INDEX).
- Both branches use the same `drop_drift_baselines_table` migration name — intentional convergence per task spec.

## Implementation Notes

- The SQLite edit was a direct in-place replacement of the existing CREATE block at lines 224-247, leaving the surrounding Phase 33 / 35 migration steps untouched.
- The Postgres edit appends a new block after the existing `CREATE INDEX IF NOT EXISTS idx_devices_hostname` and `conn.commit()`, before the `if own_connection:` cleanup. The Postgres branch never auto-created `drift_baselines` (verified: the only `CREATE TABLE.*drift_baselines` reference outside `migration.py` is in `database.py` SQLite `init_schema`, which is Plan 01's responsibility — not this plan).
- Both drop branches are fully idempotent — second-run finds no table, fetchone returns falsy, the `if` body is skipped silently. Fresh installs have no table, same skip path.
- Banner row counts are intentionally omitted (per D-08 recommendation) — counting requires a `SELECT COUNT(*)` before the DROP that complicates the idempotency proof.

## Acceptance Criteria — All Met

### Task 1 (SQLite drop step + auto-create deletion)

- `grep -c "CREATE TABLE IF NOT EXISTS drift_baselines" src/homelab_mcp/migration.py` = 0 ✓
- `grep -c "create_drift_baselines_table" src/homelab_mcp/migration.py` = 0 ✓
- `grep -c "drop_drift_baselines_table" src/homelab_mcp/migration.py` = 2 ✓ (one in SQLite, one in Postgres)
- `grep -c "DROP TABLE IF EXISTS drift_baselines" src/homelab_mcp/migration.py` = 2 ✓ (one in each branch)
- `grep -c "Dropped legacy drift_baselines table" src/homelab_mcp/migration.py` ≥ 1 ✓
- `grep -c "drop_ssh_credentials_table" src/homelab_mcp/migration.py` = 2 ✓ (Phase 33 step preserved)
- `uv run ruff check src/homelab_mcp/migration.py` exits 0 ✓
- `uv run mypy src/homelab_mcp/migration.py` exits 0 ✓
- `uv run python -c "from src.homelab_mcp.migration import run_sqlite_migrations"` exits 0 ✓

### Task 2 (Postgres drop step)

- `grep -c "DROP TABLE IF EXISTS drift_baselines"` = 2 ✓
- `grep -c "drop_drift_baselines_table"` = 2 ✓
- `grep -c "Dropped legacy drift_baselines table from Postgres"` = 1 ✓
- `information_schema.tables` with `drift_baselines` table_name = 1 match ✓
- New Postgres block placed AFTER the Phase 35 stale-UNIQUE drop and the `idx_devices_hostname` CREATE INDEX ✓
- `uv run ruff check src/homelab_mcp/migration.py` exits 0 ✓
- `uv run mypy src/homelab_mcp/migration.py` exits 0 ✓
- `uv run python -c "from src.homelab_mcp.migration import run_postgres_migrations, run_sqlite_migrations"` exits 0 ✓

## Truths Validated

- On first server start with a pre-existing `drift_baselines` table, the table is dropped and a banner is emitted to stderr — verified via the `if cursor.fetchone()` path performing `DROP TABLE IF EXISTS drift_baselines` + the two `print(..., file=sys.stderr)` calls.
- On second server start (no table present), the migration is a silent no-op — verified via the `if cursor.fetchone()` guard skipping the entire block when the existence check returns falsy.
- Fresh installs never auto-create the `drift_baselines` table — the auto-create block at lines 224-247 was deleted from the SQLite branch and never existed in the Postgres branch.
- Both SQLite and Postgres branches drop the table — verified via grep returning 2 matches each for `DROP TABLE IF EXISTS drift_baselines` and `drop_drift_baselines_table`.

## Deviations from Plan

None — plan executed exactly as written.

## Out-of-Scope Observations (informational, not actioned)

- `src/homelab_mcp/database.py` SQLite `init_schema` still contains a `CREATE TABLE IF NOT EXISTS drift_baselines` block at lines 205-222. Per CONTEXT.md D-06 this removal belongs to Plan 01 (`init_schema` and adapter-method removal scope), not Plan 02. Plan 02 is strictly scoped to `migration.py`. The AST meta-tests in Plan 03/06 will verify cross-plan completeness once Plan 01 ships.
- The `migration.py` file still has two `import sys` statements inside `if` bodies (legacy idiom from Phase 33; the new drop block follows the same convention with `import sys  # noqa: PLC0415`). This is consistent with the Phase 33 precedent and is not a deviation.

## Commits

| Task | Description | Commit |
| ---- | ----------- | ------ |
| 1 | SQLite drop step + delete auto-create block | d24583d |
| 2 | Postgres drop step | c4c5163 |

## Self-Check: PASSED

Verified files exist:
- src/homelab_mcp/migration.py: FOUND (modified)

Verified commits exist:
- d24583d: FOUND ("feat(36-02): replace SQLite drift_baselines auto-create with idempotent drop step")
- c4c5163: FOUND ("feat(36-02): add Postgres drift_baselines drop step to migration")
