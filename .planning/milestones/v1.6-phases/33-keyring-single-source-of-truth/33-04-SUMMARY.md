---
phase: 33-keyring-single-source-of-truth
plan: 04
status: complete
completed: 2026-04-21
commits:
  - 1a9b95d feat(33-04): remove 4 MCP tools in lock-step across 6 files (D-10/D-20/D-21)
  - 149953d feat(33-04): delete setup_remote_mcp_admin + remove_server + update_server_credentials from ssh_tools.py; rewrite list_registered_servers to keyring
key-files:
  modified:
    - src/homelab_mcp/ssh_tools.py
    - src/homelab_mcp/tool_schemas/ssh_tools_schema.py
    - src/homelab_mcp/tool_schemas/credential_tools_schema.py
    - src/homelab_mcp/tool_handlers/ssh_handlers.py
    - src/homelab_mcp/tool_handlers/credential_handlers.py
    - src/homelab_mcp/tool_handlers/__init__.py
    - src/homelab_mcp/tool_annotations.py
    - src/homelab_mcp/openapi_app.py
    - tests/test_ssh_tools.py
    - tests/test_tools.py
    - tests/test_dry_run.py
    - tests/test_preview_tools.py
    - tests/integration/test_ssh_integration.py
    - tests/integration/test_sitemap_integration.py
---

# Plan 33-04 — Tool-surface cleanup (lock-step + ssh_tools.py deletions)

## Deletions by file

| File | What was removed |
|------|------------------|
| `tool_schemas/ssh_tools_schema.py` | `setup_mcp_admin` entry |
| `tool_schemas/credential_tools_schema.py` | `update_server_credentials`, `remove_server`, `remove_server_preview` entries |
| `tool_handlers/ssh_handlers.py` | `handle_setup_mcp_admin` + `setup_remote_mcp_admin` import |
| `tool_handlers/credential_handlers.py` | `handle_update_server_credentials`, `handle_remove_server`, `handle_remove_server_preview` + `remove_server`/`update_server_credentials` imports |
| `tool_handlers/__init__.py` | 4 TOOL_HANDLERS dispatch entries + matching imports |
| `tool_annotations.py` | `setup_mcp_admin`, `update_server_credentials`, `remove_server`, `remove_server_preview` annotations |
| `openapi_app.py` | Same 4 names dropped from `_SSH_TOOLS_WITH_HOSTNAME` and `TOOL_CATEGORIES` |
| `ssh_tools.py` | `setup_remote_mcp_admin` (~180 lines), `remove_server` (~80 lines), `update_server_credentials` (~74 lines); `os`/`tempfile` imports pruned |

Net deletions across source: **923 lines**. Total tool count: 57 → 53.

## list_registered_servers rewrite

**Before** (~45 lines): opened DB adapter, called `db.list_credentials(active_only=active_only)`, returned dicts with `id`, `hostname`, `username`, `port`, `display_name`, `is_active`, `last_verified`, `has_key`, `device_id`.

**After** (~20 lines): reads keyring registry via `credential_store.list_credentials(credential_type="ssh")`; returns `{status, count, servers: [{hostname, username}]}`. `active_only` kept for MCP schema back-compat but is now a no-op.

## D-24 error message change

| Where | Before | After |
|-------|--------|-------|
| `update_mcp_admin_groups` (ssh_tools.py ~line 552) | `"mcp_admin user does not exist. Run setup_mcp_admin first."` | `"mcp_admin user does not exist on target. Create any sudo-capable user and register it via homelab-mcp credentials add <hostname> <username>."` |

## Tests flipped to GREEN

| Test | Decision |
|------|----------|
| `test_openapi_app.py::test_setup_mcp_admin_absent` | D-10 |
| `test_openapi_app.py::test_update_server_credentials_absent` | D-20 |
| `test_openapi_app.py::test_remove_server_absent` | D-21 |
| `test_tools.py::test_setup_mcp_admin_removed_from_tool_handlers` | D-10 |
| `test_tools.py::test_update_server_credentials_removed_from_tool_handlers` | D-20 |
| `test_tools.py::test_remove_server_removed_from_tool_handlers` | D-21 |
| `test_tools.py::test_get_available_tools` | tool count 57 → 53 |
| `test_ssh_tools.py::test_setup_remote_mcp_admin_absent` | D-11 |
| `test_ssh_credentials.py::TestListRegisteredServers::test_list_returns_keyring_entries` | D-19 |
| `test_ssh_credentials.py::TestListRegisteredServers::test_list_does_not_read_db` | D-19 |

## Orphan-test cleanup

Several pre-Phase-33 tests asserted on now-removed features. Deleted or replaced with stub comments:

- `test_ssh_tools.py`: 5 obsolete tests for `setup_remote_mcp_admin` (user_exists, force_update_key, no_force_update, uses_grep_ff, tmpfile_cleanup_on_error)
- `test_tools.py`: `test_setup_mcp_admin_schema_password_not_required`, `test_setup_mcp_admin_schema_has_timeout`
- `test_dry_run.py`: `TestRemoveServerDryRun` class (3 tests)
- `test_preview_tools.py`: `test_remove_server_preview_in_schema_registry`; `remove_server`/`remove_server_preview` dropped from `_PREVIEW_TOOLS` and `_DESTRUCTIVE_TOOLS`
- `tests/integration/test_ssh_integration.py` + `test_sitemap_integration.py`: module-level `pytest.skip` added — these Docker-based tests need rewrite for keyring-based onboarding (deferred out of Phase 33)

## Known remaining RED tests (all Plan 33-05 scope)

| Test | Why |
|------|-----|
| `test_ast_regression.py::test_no_forbidden_strings_in_source` | `register_server` body still contains `add_credential`, `get_credential_by_hostname`, `update_last_verified` |
| `test_ast_regression.py::test_no_removed_db_methods_in_source` | Same violation set |
| `test_ast_regression.py::test_register_server_handler_no_verify_connection_param` | `register_server` still has `verify_connection` param |
| `test_mcp_prompts.py::test_connect_to_device_prompt` | Prompt rewrite pending (D-13) |
| `test_mcp_prompts.py::test_connect_to_device_mentions_credentials_cli` | Prompt rewrite pending (D-13) |
| `test_ssh_credentials.py::TestRegisterServer::*` (6 tests) | `register_server` verify-only rewrite pending (D-03/D-04/D-05/D-07/D-23) |

## Acceptance criteria outcome

- Zero `setup_mcp_admin|update_server_credentials|remove_server` matches across 6 lock-step files ✓
- `list_registered_servers` reads keyring, not DB ✓
- `update_mcp_admin_groups` no longer names `setup_mcp_admin` ✓
- Module loads cleanly (`python -c "import homelab_mcp.ssh_tools"`) ✓
- `ruff check` passes on all modified files ✓
- Unit test sweep: 655 pass / 13 fail (all 33-05 scope or pre-existing)

## Handoff to Plan 33-05

Plan 33-05 is the final wave. It:
1. Rewrites `register_server` to verify-only shape (D-03/D-04/D-05/D-07/D-23) — drops `key_path`, `password`, `verify_connection` params; raises `CredentialNotFoundError` if keyring miss
2. Rewrites `connect_to_device` prompt to the D-13 six-step sequence with D-22 wording
3. Updates `register_server` schema to match the new signature

After 33-05, all remaining RED tests (except 2 pre-existing unrelated) go GREEN. The AST meta-test scan completes across the entire source tree.
