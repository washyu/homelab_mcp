---
phase: 33-keyring-single-source-of-truth
plan: "01"
subsystem: tests
tags: [tdd, red-tests, wave-0, credential-cleanup, regression-guards]
dependency_graph:
  requires: []
  provides: [wave-0-red-tests]
  affects: [tests/test_ast_regression.py, tests/test_database.py, tests/test_openapi_app.py, tests/test_tools.py, tests/test_ssh_credentials.py, tests/test_mcp_prompts.py, tests/test_ssh_tools.py]
tech_stack:
  added: []
  patterns: [wave-0-tdd, ast-meta-test, monkeypatch-keyring, inspect-signature-check]
key_files:
  created:
    - tests/test_ast_regression.py
    - tests/test_openapi_app.py
  modified:
    - tests/test_database.py
    - tests/test_tools.py
    - tests/test_ssh_credentials.py
    - tests/test_mcp_prompts.py
    - tests/test_ssh_tools.py
decisions:
  - "Local imports used for setup_remote_mcp_admin in remaining test call sites (Wave 0 — function still exists in source; will error at runtime not collection)"
  - "TestSSHCredentialsDatabase, TestUpdateServerCredentials, TestRemoveServer deleted (not skipped) per RESEARCH Pitfall 2"
  - "PostgreSQLAdapter constructor uses connection_params dict (not dsn keyword) — test adjusted from plan template"
metrics:
  duration: "12 minutes"
  completed: "2026-04-21T20:19:24Z"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 7
requirements-completed: [CRED-04, CRED-05, CRED-06, CRED-07]
---

# Phase 33 Plan 01: Wave 0 RED Regression Tests Summary

Wave 0 TDD tests landed before any implementation. All new tests fail with assertion errors (not SyntaxError or ImportError) — expected pre-implementation RED state.

## One-liner

Wave 0 RED regression tests: AST meta-scan + DB table absence + openapi/tool dispatch clean + resolver/register_server keyring shape + prompt assertion flip.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | AST meta-test + DB + openapi + tools scaffold | 94c1de5 | Done |
| 2 | Resolver + register_server + ssh_tools cleanup | c1a4d00 | Done |
| 3 | Flip prompt assertions + no_verify_bypass guards | 40e1789 | Done |
| - | Lint fixes (ruff) | 36b2755 | Done |

## Test Files Modified/Created

| File | Action | New Tests Added | Tests Deleted |
|------|--------|----------------|---------------|
| `tests/test_ast_regression.py` | CREATED | test_no_forbidden_strings_in_source, test_no_removed_db_methods_in_source, test_register_server_handler_no_verify_connection_param | — |
| `tests/test_database.py` | MODIFIED | test_ssh_credentials_table_dropped, test_no_credential_methods_on_adapter, test_ssh_credentials_table_dropped_postgres | — |
| `tests/test_openapi_app.py` | CREATED | test_setup_mcp_admin_absent, test_update_server_credentials_absent, test_remove_server_absent | — |
| `tests/test_tools.py` | MODIFIED | test_setup_mcp_admin_removed_from_tool_handlers, test_update_server_credentials_removed_from_tool_handlers, test_remove_server_removed_from_tool_handlers | — |
| `tests/test_ssh_credentials.py` | REWRITTEN | test_resolve_keyring_password_auth, test_resolve_keyring_key_path_auth, test_mcp_admin_no_fallback, test_credential_not_found_message, TestRegisterServer (6 methods), TestListRegisteredServers (2 methods) | TestSSHCredentialsDatabase, TestUpdateServerCredentials, TestRemoveServer, test_stored_credentials_used, test_mcp_admin_uses_default_key, test_no_raise_when_mcp_admin_key_exists |
| `tests/test_mcp_prompts.py` | MODIFIED | test_connect_to_device_no_verify_bypass, test_connect_to_device_mentions_credentials_cli | — |
| `tests/test_ssh_tools.py` | MODIFIED | test_setup_remote_mcp_admin_absent | test_setup_remote_mcp_admin_success, test_setup_mcp_admin_key_injection_safe |

## Classes/Tests Deleted (exact names)

- `TestSSHCredentialsDatabase` (entire class, 13 methods) — D-02: no DB credential methods
- `TestUpdateServerCredentials` (entire class, 4 methods) — D-20: removed MCP tool
- `TestRemoveServer` (entire class, 4 methods) — D-21: removed MCP tool
- `test_stored_credentials_used` — DB-tier resolver test
- `test_mcp_admin_uses_default_key` — removed fallback test
- `test_no_raise_when_mcp_admin_key_exists` — removed fallback test
- `test_setup_remote_mcp_admin_success` — deleted function test
- `test_setup_mcp_admin_key_injection_safe` — deleted function test

## New Tests Added (exact names)

### test_ast_regression.py (NEW)
- `test_no_forbidden_strings_in_source` — D-15+D-25 AST scan
- `test_no_removed_db_methods_in_source` — D-15 DB method focus
- `test_register_server_handler_no_verify_connection_param` — D-25 signature check

### test_database.py
- `test_ssh_credentials_table_dropped` — CRED-04/D-01 SQLite
- `test_no_credential_methods_on_adapter` — CRED-04/D-02
- `test_ssh_credentials_table_dropped_postgres` — CRED-04/D-01 Postgres (mocked)

### test_openapi_app.py (NEW)
- `test_setup_mcp_admin_absent` — D-10
- `test_update_server_credentials_absent` — D-20
- `test_remove_server_absent` — D-21

### test_tools.py
- `test_setup_mcp_admin_removed_from_tool_handlers` — D-10
- `test_update_server_credentials_removed_from_tool_handlers` — D-20
- `test_remove_server_removed_from_tool_handlers` — D-21

### test_ssh_credentials.py
- `test_resolve_keyring_password_auth` — D-16
- `test_resolve_keyring_key_path_auth` — D-16/D-09
- `test_mcp_admin_no_fallback` — D-17
- `test_credential_not_found_message` — D-05
- `TestRegisterServer.test_register_verify_success` — D-04
- `TestRegisterServer.test_register_missing_keyring_error` — D-05
- `TestRegisterServer.test_register_server_schema_no_write_params` — D-03
- `TestRegisterServer.test_register_no_verify_connection_flag` — D-07
- `TestRegisterServer.test_register_username_required` — D-23
- `TestRegisterServer.test_register_does_not_write_db` — D-03/D-04
- `TestListRegisteredServers.test_list_returns_keyring_entries` — D-19
- `TestListRegisteredServers.test_list_does_not_read_db` — D-19

### test_mcp_prompts.py
- `test_connect_to_device_no_verify_bypass` — D-14/D-07
- `test_connect_to_device_mentions_credentials_cli` — D-22

### test_ssh_tools.py
- `test_setup_remote_mcp_admin_absent` — D-11

## Count of RED Tests (Wave 0)

All new tests + flipped assertions = RED until implementation plans land:

| Failing test | Fails until |
|-------------|-------------|
| test_no_forbidden_strings_in_source | Plans 33-02/03/04 remove source strings |
| test_no_removed_db_methods_in_source | Plans 33-02/03/04 remove source strings |
| test_register_server_handler_no_verify_connection_param | Plan 33-05 rewrites register_server |
| test_ssh_credentials_table_dropped | Plan 33-02 DROP TABLE |
| test_no_credential_methods_on_adapter | Plan 33-02 removes DB methods |
| test_ssh_credentials_table_dropped_postgres | Plan 33-02 DROP TABLE Postgres |
| test_setup_mcp_admin_absent (openapi) | Plan 33-04 removes from openapi_app.py |
| test_update_server_credentials_absent | Plan 33-04 removes from openapi_app.py |
| test_remove_server_absent | Plan 33-04 removes from openapi_app.py |
| test_setup_mcp_admin_removed_from_tool_handlers | Plan 33-04 removes from dispatch |
| test_update_server_credentials_removed | Plan 33-04 removes from dispatch |
| test_remove_server_removed | Plan 33-04 removes from dispatch |
| test_resolve_keyring_password_auth | Plan 33-03 resolver rewrite |
| test_resolve_keyring_key_path_auth | Plan 33-03 resolver + auth_type |
| test_mcp_admin_no_fallback | Plan 33-03 removes mcp_admin fallback |
| test_credential_not_found_message | Plan 33-03 resolver rewrite |
| test_register_verify_success | Plan 33-05 register_server rewrite |
| test_register_missing_keyring_error | Plan 33-05 register_server rewrite |
| test_register_server_schema_no_write_params | Plan 33-05 register_server rewrite |
| test_register_no_verify_connection_flag | Plan 33-05 register_server rewrite |
| test_register_username_required | Plan 33-05 register_server rewrite |
| test_register_does_not_write_db | Plan 33-05 register_server rewrite |
| test_list_returns_keyring_entries | Plan 33-03/05 list_registered_servers rewrite |
| test_list_does_not_read_db | Plan 33-03/05 list_registered_servers rewrite |
| test_setup_remote_mcp_admin_absent | Plan 33-04 deletes function |
| test_connect_to_device_prompt (flipped) | Plan 33-05 prompt rewrite |
| test_connect_to_device_no_verify_bypass | Plan 33-05 prompt rewrite |
| test_connect_to_device_mentions_credentials_cli | Plan 33-05 prompt rewrite |
| test_connect_to_device_prompt_parameter_names | Plan 33-05 prompt rewrite |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stray `prop` reference in test_tools.py**
- **Found during:** Post-task lint check
- **Issue:** Line `assert prop.get("default") == "ssh"` was appended to `test_remove_server_removed_from_tool_handlers` — `prop` undefined in that scope
- **Fix:** Removed stray line (leftover from adjacent SCH-01 test context)
- **Files modified:** tests/test_tools.py
- **Commit:** 36b2755

**2. [Rule 3 - Blocking] F821 undefined `setup_remote_mcp_admin` in test_ssh_tools.py**
- **Found during:** Lint check after removing module-level import
- **Issue:** Remaining test functions (`test_setup_remote_mcp_admin_user_exists`, etc.) called `setup_remote_mcp_admin` which was no longer imported
- **Fix:** Added local `from src.homelab_mcp.ssh_tools import setup_remote_mcp_admin` inside each calling function; these tests remain RED at runtime (function still exists in source during Wave 0) but now collect cleanly
- **Files modified:** tests/test_ssh_tools.py
- **Commit:** 36b2755

**3. [Rule 2 - Deviation] PostgreSQLAdapter constructor uses `connection_params=` dict not `dsn=`**
- **Found during:** Task 1 database test implementation
- **Issue:** Plan template showed `PostgreSQLAdapter(dsn="postgresql://fake/fake")` but actual constructor signature is `PostgreSQLAdapter(connection_params: dict | None = None)`
- **Fix:** Used `connection_params={"host": "fake", "database": "fake", "user": "fake", "password": "fake"}` instead
- **Files modified:** tests/test_database.py
- **Commit:** 94c1de5

## Known Stubs

None — this plan creates test-only files with no stubs.

## Threat Flags

None — test files only; no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED
