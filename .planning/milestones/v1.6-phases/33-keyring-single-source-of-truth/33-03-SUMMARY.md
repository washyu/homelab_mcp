---
phase: 33-keyring-single-source-of-truth
plan: 03
status: complete
completed: 2026-04-21
commits:
  - 96f2d1b feat(33-03): add auth_type field to register_credential + JSON registry (D-09)
  - 0cee9f6 feat(33-03): rewrite resolve_ssh_credentials to two-tier keyring-only (D-08)
  - b795151 feat(33-03): --key-path flag on credentials add; strict validation (D-09, D-21)
key-files:
  modified:
    - src/homelab_mcp/credential_store.py
    - src/homelab_mcp/ssh_tools.py
    - src/homelab_mcp/server.py
    - tests/test_credential_store.py
---

# Plan 33-03 — Keyring-only resolver + --key-path CLI + credentials remove

## What landed

### Task 1 — `credential_store.register_credential` gains `auth_type` (D-09)
- Signature: `register_credential(hostname, username, credential_type="ssh", auth_type="password")`
- Value-validated against `{"password", "key"}` — raises `ValueError` otherwise
- JSON registry entries now carry `"auth_type": "password"|"key"`
- `list_credentials` docstring updated; readers treat missing `auth_type` as `"password"` via `.get("auth_type", "password")`
- Existing `tests/test_credential_store.py` updated to assert the new field (`test_register_and_list`, `test_list_filters_by_type`)
- No keyring import at module level preserved
- No `homelab_mcp` imports inside `credential_store.py` (PROJECT.md invariant)

### Task 2 — `resolve_ssh_credentials` two-tier rewrite (D-08, D-16, D-17)
- Body rewritten: 68 lines → 47 lines (Tier 3 DB + Tier 4 mcp_admin default-key removed)
- Tier 1 (explicit args): unchanged
- Tier 2 (keyring): branches on `matched[0].get("auth_type", "password")`:
  - `"key"` → returns `SSHCredentials(key_path=<stored path>)`
  - `"password"` (default) → returns `SSHCredentials(password=<stored password>)`
- Desync warning preserved when registry has entry but keyring returns None
- Terminal `CredentialNotFoundError` message names `homelab-mcp credentials add <hostname> <username>` (D-05)
- Module-level imports `from .credential_store import list_credentials, get_credential` preserved (pytest-mock monkeypatchability)
- `get_database_adapter` import remains (still used by `list_registered_servers`, `update_server_credentials`, `remove_server` — those are Plan 33-04 scope)
- `get_mcp_ssh_key_path` function remains (still called by `ensure_mcp_ssh_key`)

### Task 3 — `--key-path` flag + strict validation (D-09)
- `add_p.add_argument("--key-path", dest="key_path", default=None, metavar="PATH", ...)` added
- `_cmd_credentials_add` rewrites behavior:
  - `--key-path present` → `credential_type` must be `ssh` (reject proxmox), file must exist and be a regular file (not symlink-to-dir); stores resolved absolute path; `auth_type="key"`
  - `--key-path absent` → `getpass` prompt, rejects empty string; `auth_type="password"`
- Epilog examples updated to document `--key-path`
- `credentials remove` subcommand was already present (lines 524–540 / 665–668); confirmed matches D-21 shape

## Acceptance criteria

- `grep -c 'auth_type: str = "password"' credential_store.py` = 1 ✓
- `grep -c '"auth_type": auth_type' credential_store.py` = 1 ✓
- `uv run ruff check credential_store.py ssh_tools.py server.py` = clean ✓
- `uv run mypy credential_store.py` = clean ✓
- `uv run mypy ssh_tools.py` = **13 attr-defined errors remain** — all in `list_registered_servers` / `update_server_credentials` / `remove_server` / `update_mcp_admin_groups` bodies, which call deleted DB methods. Plan 33-04 removes those callers; the errors are expected transitional state.
- `awk '/resolve_ssh_credentials/...' | grep -c 'get_mcp_ssh_key_path\|get_database_adapter\|get_credential_by_hostname'` = 0 ✓ (resolver body is clean)
- `--key-path` rejects missing file: exit 1 with `"Error: key file not found: ..."` ✓

## Tests flipped to GREEN

| Test | Decision | Status |
|------|----------|--------|
| `test_credential_store.py` (15 tests) | backward compat | all GREEN |
| `test_ssh_credentials.py::TestResolveSSHCredentials::test_mcp_admin_no_fallback` | D-17 | GREEN |
| `test_ssh_credentials.py::TestResolveSSHCredentials::test_resolve_keyring_password_auth` | D-16 | GREEN |
| `test_ssh_credentials.py::TestResolveSSHCredentials::test_resolve_keyring_key_path_auth` | D-16 | GREEN |
| `test_ssh_credentials.py::TestResolveSSHCredentials::test_desync_warning_logged` | D-16 | GREEN |
| `test_ssh_credentials.py::TestCredentialNotFoundError::test_raises_when_no_credentials_exist` | D-05 | GREEN |

## Known remaining RED tests (scoped to later plans)

| Test | Plan | Why still RED |
|------|------|----|
| `TestRegisterServer::*` (6 tests) | 33-05 | `register_server` verify-only rewrite (D-03/D-04/D-05/D-07/D-23) |
| `TestListRegisteredServers::*` (2 tests) | 33-04 | `list_registered_servers` reads DB instead of keyring registry (D-19) |
| `test_ast_regression.py::*` | 33-04/05 | Source strings `add_credential`, `setup_mcp_admin`, `remove_server` still present in call-site files |
| `test_mcp_prompts.py::*` | 33-05 | `connect_to_device` prompt rewrite (D-13, D-22) |
| `test_openapi_app.py::*` | 33-04 | `setup_mcp_admin`, `update_server_credentials`, `remove_server` tools still in openapi surface |
| `test_tools.py::test_*_removed_from_tool_handlers` | 33-04 | Tool handlers still reference deleted tools |
| `test_ssh_tools.py::test_setup_remote_mcp_admin_absent` | 33-04 | `setup_remote_mcp_admin` function deletion |
| `test_dry_run.py::TestRemoveServerDryRun::*` | 33-04 | Depends on `remove_server` tool removal |

## Notes for next wave

Plan 33-04 will:
1. Remove `setup_mcp_admin`, `update_server_credentials`, `remove_server`, `remove_server_preview` MCP tools
2. Delete `setup_remote_mcp_admin` function from `ssh_tools.py`
3. Rewrite `list_registered_servers` to read keyring registry (eliminates `get_database_adapter` usage in ssh_tools.py credentials-related functions)
4. Rephrase `update_mcp_admin_groups` error (D-24)
5. After 33-04 lands, the remaining 13 mypy attr-defined errors in `ssh_tools.py` are fully resolved
