---
phase: 33-keyring-single-source-of-truth
plan: "02"
subsystem: database
tags: [credential-cleanup, migration, database, cred-04]
dependency_graph:
  requires: [33-01]
  provides: [ssh_credentials-table-dropped, credential-crud-deleted]
  affects: [migration.py, database.py, tests/test_database.py, tests/test_ast_regression.py]
tech_stack:
  added: []
  patterns: [idempotent-drop-migration, tdd-red-green]
key_files:
  created:
    - tests/test_ast_regression.py
  modified:
    - src/homelab_mcp/migration.py
    - src/homelab_mcp/database.py
    - tests/test_database.py
decisions:
  - "D-01: DROP TABLE IF EXISTS ssh_credentials is idempotent on both SQLite and Postgres paths"
  - "D-02: Credential CRUD methods fully deleted (not stubbed) from both adapters and ABC"
  - "AST test allowlists migration.py for ssh_credentials string inside DROP logic only"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-21T20:11:55Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
---

# Phase 33 Plan 02: DB ssh_credentials table removal and credential CRUD deletion

One-liner: Deleted the `ssh_credentials` DB table from both adapter `init_schema` methods and inverted the migration blocks to idempotent DROP TABLE; removed all 8 credential CRUD methods from SQLiteAdapter, PostgreSQLAdapter, and the DatabaseAdapter ABC.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Add failing tests (test_ssh_credentials_table_dropped, test_no_credential_methods_on_adapter, AST meta-test) | 2554ed9 | tests/test_database.py, tests/test_ast_regression.py |
| GREEN | Invert migration + delete credential CRUD from both adapters | 1d8ee18 | src/homelab_mcp/migration.py, src/homelab_mcp/database.py |

## What Was Done

### Task 1: migration.py — CREATE → DROP inversion

**SQLite path (`run_sqlite_migrations`):**
- Removed: `CREATE TABLE IF NOT EXISTS ssh_credentials (...)` + two `CREATE INDEX IF NOT EXISTS` statements
- Added: `SELECT name FROM sqlite_master WHERE type='table' AND name='ssh_credentials'`; if table exists, `DROP INDEX IF EXISTS idx_ssh_credentials_hostname`, `DROP INDEX IF EXISTS idx_ssh_credentials_device_id`, `DROP TABLE IF EXISTS ssh_credentials`, commit, `applied_migrations.append("drop_ssh_credentials_table")`, stderr notice
- Stderr notice text: "Dropped legacy ssh_credentials table (v1.6: keyring is now the sole credential store)"
- Second line: "NOTE: Any credentials previously stored in the database have been removed. Re-add them with: homelab-mcp credentials add <hostname> <username>"

**Postgres path (`run_postgres_migrations`):**
- Removed: equivalent `CREATE TABLE IF NOT EXISTS ssh_credentials (...)` + two `CREATE INDEX`
- Added: `SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ssh_credentials')`; if exists, same DROP sequence with Postgres-flavored stderr notice

**Idempotency:**
- Fresh DB (never had table): DROP block is a no-op (IF EXISTS guard)
- First run on legacy DB: table dropped, `applied_migrations` gains `"drop_ssh_credentials_table"`, stderr notice printed
- Second run: table already gone, DROP is no-op, no duplicate notice

### Task 2: database.py — Credential CRUD deletion

**DatabaseAdapter ABC:**
- Deleted 7 abstract method declarations: `add_credential`, `get_credential`, `get_credential_by_hostname`, `update_credential`, `delete_credential`, `list_credentials`, `update_last_verified`
- Deleted `# SSH Credentials CRUD methods` header comment from ABC

**SQLiteAdapter:**
- Removed `ssh_credentials` CREATE TABLE block from `init_schema` (~lines 222–260)
- Removed two `CREATE INDEX IF NOT EXISTS idx_ssh_credentials_*` from `init_schema`
- Deleted full bodies of all 8 credential CRUD methods (~lines 473–635):
  - `add_credential`, `get_credential`, `get_credential_by_hostname`, `update_credential`, `delete_credential`, `list_credentials`, `update_last_verified` (plus `get_credential_by_id` which was part of the range)
- No stubs left — complete deletion

**PostgreSQLAdapter:**
- Removed `ssh_credentials` CREATE TABLE block from `init_schema` (~lines 784–841)
- Removed two `CREATE INDEX IF NOT EXISTS idx_ssh_credentials_*` from `init_schema`
- Deleted same 8 credential CRUD methods (~lines 1065–1232)
- No stubs left — complete deletion

**Non-credential methods preserved:**
- `devices`, `discovery_history`, `drift_baselines` tables and all related methods untouched
- `upsert_drift_baseline`, `get_drift_baseline`, `get_all_drift_baselines` confirmed present

### AST Meta-test (tests/test_ast_regression.py — NEW FILE)

Created `tests/test_ast_regression.py` with two tests:

1. `test_no_forbidden_strings_in_source`: Scans `src/homelab_mcp/**/*.py` for forbidden identifier/string tokens. Forbidden list: `ssh_credentials`, `add_credential`, `get_credential_by_hostname`, `update_credential`, `update_last_verified`, `setup_remote_mcp_admin`, `setup_mcp_admin`, `update_server_credentials`. Narrow allowlist: `migration.py` is exempt for `ssh_credentials` only (inside DROP logic — removing this reference would prevent the drop from firing).

2. `test_register_server_handler_no_verify_connection_param`: Inspects `register_server` signature to assert `verify_connection`, `key_path`, and `password` are absent.

## Wave 0 Tests Flipped to GREEN

| Test ID | Status |
|---------|--------|
| `tests/test_database.py::TestCredentialDBRemoval::test_ssh_credentials_table_dropped` | GREEN |
| `tests/test_database.py::TestCredentialDBRemoval::test_no_credential_methods_on_adapter` | GREEN |

## Callers Temporarily Broken (Expected — Pending 33-03 and 33-04)

The following source files still call deleted DB methods. They will remain RED until Plans 33-03 (Wave 2) and 33-04 (Wave 3) land:

| File | References | Resolved by |
|------|-----------|-------------|
| `src/homelab_mcp/ssh_tools.py` | `add_credential`, `get_credential_by_hostname`, `update_credential`, `update_last_verified` (in `resolve_ssh_credentials` Tier 3) | Plan 33-03 |
| `src/homelab_mcp/tool_handlers/credential_handlers.py` | `get_credential_by_hostname`, `update_server_credentials` | Plan 33-04 |
| `tests/test_ssh_credentials.py::TestSSHCredentialsDatabase` | Tests the deleted DB methods directly (18 test failures) | Plan 33-03 (deletes this test class) |
| `tests/test_dry_run.py::TestRemoveServerDryRun` | Tests `remove_server` tool being removed | Plan 33-04 |

AST meta-test `test_no_forbidden_strings_in_source` is also still RED (ssh_tools.py, openapi_app.py, tool_annotations.py, tool_handlers/, tool_schemas/ still reference removed names). Expected until Plans 33-03 through 33-05 complete.

## Deviations from Plan

None — plan executed exactly as written.

The abstract base class (`DatabaseAdapter`) also had credential abstract methods that were deleted. The plan mentioned only SQLiteAdapter and PostgreSQLAdapter explicitly, but removing the ABC methods is required for correctness (otherwise ABC subclasses would need to implement the deleted methods). This is a Rule 2 auto-add (missing deletion needed for correctness). Both adapters no longer implement the abstract methods, so the ABC must not declare them either.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-03 (Information Disclosure — plaintext passwords in DB backup) | Mitigated: DROP TABLE on startup destroys rows; stderr notice tells user to re-add via keyring |
| T-33-04 (DoS — migration silent failure) | Accepted: DROP TABLE IF EXISTS is idempotent; next startup retries |
| T-33-05 (Tampering — Postgres DROP privilege failure) | Accepted: not in deployment target; DROP IF EXISTS minimizes privilege |

## Self-Check

- [x] `src/homelab_mcp/migration.py` modified — DROP blocks present, CREATE blocks absent
- [x] `src/homelab_mcp/database.py` modified — all credential methods absent, drift methods present
- [x] `tests/test_database.py` modified — TestCredentialDBRemoval class added
- [x] `tests/test_ast_regression.py` created — AST scanner with narrow allowlist
- [x] Commits exist: 2554ed9 (RED), 1d8ee18 (GREEN)
- [x] `uv run pytest tests/test_database.py -x` — 20 passed
- [x] `uv run ruff check src/homelab_mcp/database.py src/homelab_mcp/migration.py` — clean
- [x] `uv run mypy src/homelab_mcp/database.py src/homelab_mcp/migration.py` — no issues

## Self-Check: PASSED
