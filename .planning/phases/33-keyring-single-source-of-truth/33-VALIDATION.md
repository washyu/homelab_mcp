---
phase: 33
slug: keyring-single-source-of-truth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-20
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `33-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `pyproject.toml [tool.pytest]` |
| **Quick run command** | `uv run pytest tests/test_ssh_credentials.py tests/test_mcp_prompts.py tests/test_ssh_tools.py tests/test_database.py -x` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | quick ~15s · full ~60s |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Task IDs will be finalized by the planner. The table below maps every phase requirement to the regression/positive test that proves it. Planner must assign each row to a task in the produced PLAN.md files; every task gets either an `<automated>` command from this table or a Wave 0 dependency.

| Req | Behavior | Decision | Test Type | Automated Command | File Exists | Status |
|-----|----------|----------|-----------|-------------------|-------------|--------|
| CRED-04 | `ssh_credentials` table absent from SQLite schema after migration | D-01 | unit | `uv run pytest tests/test_database.py -k "ssh_credentials_table_dropped" -x` | ❌ W0 | ⬜ pending |
| CRED-04 | `ssh_credentials` table absent from Postgres schema after migration | D-01 | unit | `uv run pytest tests/test_database.py -k "ssh_credentials_table_dropped_postgres" -x` | ❌ W0 | ⬜ pending |
| CRED-04 | `SQLiteAdapter` has no credential methods (`add_credential`, etc.) | D-02 | unit | `uv run pytest tests/test_database.py -k "no_credential_methods" -x` | ❌ W0 | ⬜ pending |
| CRED-04 | AST scan: no non-test file contains `ssh_credentials` | D-15 | AST meta | `uv run pytest tests/test_ast_regression.py -k "no_ssh_credentials_string" -x` | ❌ W0 | ⬜ pending |
| CRED-04 | AST scan: no non-test file calls removed DB method names | D-15 | AST meta | `uv run pytest tests/test_ast_regression.py -k "no_removed_db_methods" -x` | ❌ W0 | ⬜ pending |
| CRED-05 | `resolve_ssh_credentials(hostname, "mcp_admin")` with empty keyring raises `CredentialNotFoundError` | D-17 | unit | `uv run pytest tests/test_ssh_credentials.py -k "mcp_admin_no_fallback" -x` | ❌ W0 | ⬜ pending |
| CRED-05 | `resolve_ssh_credentials` with password keyring entry returns credential | D-16 | unit | `uv run pytest tests/test_ssh_credentials.py -k "resolve_keyring_password_auth" -x` | ❌ W0 | ⬜ pending |
| CRED-05 | `resolve_ssh_credentials` with key-path keyring entry returns credential | D-16 | unit | `uv run pytest tests/test_ssh_credentials.py -k "resolve_keyring_key_path_auth" -x` | ❌ W0 | ⬜ pending |
| CRED-05 | `resolve_ssh_credentials` error message names `homelab-mcp credentials add <host> <user>` | D-05 | unit | `uv run pytest tests/test_ssh_credentials.py -k "credential_not_found_message" -x` | ❌ W0 | ⬜ pending |
| CRED-06 | `setup_mcp_admin` not in `TOOL_HANDLERS` dispatch | D-10 | unit | `uv run pytest tests/test_tools.py -k "setup_mcp_admin_removed" -x` | ❌ W0 | ⬜ pending |
| CRED-06 | `setup_mcp_admin` not in OpenAPI tool allow-lists | D-10 | unit | `uv run pytest tests/test_openapi_app.py -k "setup_mcp_admin_absent" -x` | ❌ W0 | ⬜ pending |
| CRED-06 | `connect_to_device` prompt does NOT contain `setup_mcp_admin` | D-13/D-14 | unit | `uv run pytest tests/test_mcp_prompts.py -k "connect_to_device" -x` | ✅ (flip assertion) | ⬜ pending |
| CRED-06 | `connect_to_device` prompt does NOT contain `verify_connection=False` | D-14 | unit | `uv run pytest tests/test_mcp_prompts.py -k "no_verify_bypass" -x` | ❌ W0 | ⬜ pending |
| CRED-06 | `setup_remote_mcp_admin` function absent from `ssh_tools` module | D-11 | unit | `uv run pytest tests/test_ssh_tools.py -k "setup_remote_mcp_admin_absent" -x` | ❌ W0 | ⬜ pending |
| CRED-07 | `register_server` schema rejects `password` and `key_path` params | D-03 | unit | `uv run pytest tests/test_ssh_credentials.py -k "register_server_schema_no_write_params" -x` | ❌ W0 | ⬜ pending |
| CRED-07 | `register_server` with missing keyring entry returns actionable error | D-05 | unit | `uv run pytest tests/test_ssh_credentials.py -k "register_missing_keyring_error" -x` | ❌ W0 | ⬜ pending |
| CRED-07 | `register_server` with valid keyring entry verifies SSH and returns success | D-04 | unit (async, mocked SSH) | `uv run pytest tests/test_ssh_credentials.py -k "register_verify_success" -x` | ❌ W0 | ⬜ pending |
| CRED-07 | `register_server` has no `verify_connection` parameter | D-07 | unit | `uv run pytest tests/test_ssh_credentials.py -k "register_no_verify_connection_flag" -x` | ❌ W0 | ⬜ pending |
| CRED-07 | `register_server` performs NO database writes | D-03/D-04 | unit | `uv run pytest tests/test_ssh_credentials.py -k "register_does_not_write_db" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 must land all test file changes BEFORE implementation waves, so every implementation task has a failing (RED) test to drive it green.

- [ ] `tests/test_ssh_credentials.py` — delete `TestSSHCredentialsDatabase` class (lines 22–188), rewrite `TestRegisterServer` (lines 362–403), add D-16 + D-17 cases, delete DB-tier tests (`test_stored_credentials_used` line 219, `test_mcp_admin_uses_default_key` line 242, `test_no_raise_when_mcp_admin_key_exists` line 291)
- [ ] `tests/test_mcp_prompts.py` — flip `setup_mcp_admin` assertions at line 109 (→ `not in`) and line 141 (remove from loop list); add `no_verify_bypass` assertion
- [ ] `tests/test_ssh_tools.py` — delete `test_setup_remote_mcp_admin_success` (line 294), `test_setup_mcp_admin_key_injection_safe` (line 844); remove `setup_remote_mcp_admin` import at line 12
- [ ] `tests/test_database.py` — add `test_ssh_credentials_table_dropped` (CRED-04), `test_no_credential_methods_on_adapter` (CRED-04)
- [ ] `tests/test_ast_regression.py` — new AST meta-test scanning `src/homelab_mcp/**/*.py` (excluding tests) for forbidden strings: `ssh_credentials`, `add_credential`, `get_credential_by_hostname`, `update_credential`, `update_last_verified`, `setup_remote_mcp_admin`, `verify_connection` (in `register_server` context)
- [ ] `tests/test_openapi_app.py` — add `setup_mcp_admin_absent` in `_SSH_TOOLS_WITH_HOSTNAME` and `TOOL_CATEGORIES["SSH"]`
- [ ] `tests/test_tools.py` — add `setup_mcp_admin_removed` from `TOOL_HANDLERS` dispatch

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `homelab-mcp credentials add <host> <user> --key-path <path>` stores key-path, sets `auth_type="key"` in registry, subsequent `ssh_discover` via MCP succeeds | CRED-05 (D-09) | Requires real TTY for getpass-free path and real keyring | Run CLI with `--key-path ~/.ssh/id_ed25519`; inspect JSON registry file for `auth_type: "key"`; call `ssh_discover` against a test host |
| Fresh install on a machine with the old `ssh_credentials` DB table: server startup emits notice + drops table idempotently | CRED-04 (D-01) | Integration-level DB state | Seed `~/.homelab_mcp/homelab.db` with legacy `ssh_credentials` row; start server; confirm stderr notice + table removed |

> **Note (D-18 addendum):** The `docs/mcp_admin_bootstrap.md` manual verification was dropped — `mcp_admin` is no longer a privileged default; any SSH-accessible sudo account works via `credentials add <host> <user>`.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references above
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
