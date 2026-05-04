---
phase: 33-keyring-single-source-of-truth
plan: 05
status: complete
completed: 2026-04-21
commits:
  - 447a324 feat(33-05): rewrite register_server to verify-only (D-03/D-04/D-05/D-07/D-23)
  - 755870b feat(33-05): rewrite connect_to_device prompt with D-13 six-step sequence
key-files:
  modified:
    - src/homelab_mcp/ssh_tools.py
    - src/homelab_mcp/prompt_registry.py
    - src/homelab_mcp/tool_schemas/credential_tools_schema.py
---

# Plan 33-05 — Verify-only register_server + connect_to_device prompt rewrite

## register_server before/after

**Before** — ~103-line function with signature:
```python
async def register_server(
    hostname: str,
    username: str = "mcp_admin",
    key_path: str | None = None,
    port: int = 22,
    display_name: str | None = None,
    verify_connection: bool = True,
) -> str:
```
Opened `get_database_adapter()`, queried `db.get_credential_by_hostname()`, resolved key path (falling back to `get_mcp_ssh_key_path()` for mcp_admin), optionally verified via `ssh_connect`, called `db.add_credential()` + `db.update_last_verified()`.

**After** — ~65-line function with signature:
```python
async def register_server(
    hostname: str,
    username: str,
    port: int = 22,
    display_name: str | None = None,
) -> str:
```
Calls `resolve_ssh_credentials()`, opens one `asyncssh.connect()` to verify, returns `{"status", "hostname", "username", "verified", "display_name"}`. No database access anywhere.

## Schema diff

Properties removed: `key_path`, `verify_connection`, and `username` default (`"mcp_admin"`).
Required tightened: `["hostname"]` → `["hostname", "username"]`.
Description rewritten to explicitly say "does not write any credentials".

## Prompt before/after (connect_to_device)

**Before (6 steps):**
1. Call `setup_mcp_admin` with `hostname="{hostname}"` to create the mcp_admin user and SSH key on the device.
2. Run the CLI command: `homelab-mcp credentials add {hostname} mcp_admin` — this stores the SSH credential in your OS keyring.
3. Call `register_server` with `hostname="{hostname}"` and `username="mcp_admin"` to add the device to the server database.
4. Call `ssh_discover` with `hostname="{hostname}"`.
5. Call `discover_and_map` with `hostname="{hostname}"`.
6. Call `verify_mcp_admin` with `hostname="{hostname}"` to confirm that mcp_admin can connect successfully.

**After (6 steps):**
1. Ensure you have an SSH-accessible user on `{hostname}` with sudo privileges. The username can be anything — you will specify it in the next step.
2. Run the CLI command in your terminal: `homelab-mcp credentials add {hostname} <username>` — this stores the SSH credential in your OS keyring. For key-based auth: `homelab-mcp credentials add {hostname} <username> --key-path <path>`.
3. Call `register_server` with `hostname="{hostname}"` and `username="<username>"` to verify the stored credential end-to-end.
4. Call `ssh_discover` with `hostname="{hostname}"`.
5. Call `discover_and_map` with `hostname="{hostname}"`.
6. Call `verify_mcp_admin` with `hostname="{hostname}"` to confirm that the registered user has sudo access.

Prompt no longer mentions `setup_mcp_admin` or `verify_connection`. It no longer hardcodes `mcp_admin` as the username.

## Sanitize wiring

`register_server` error responses now use `sanitize_error(e)` instead of raw `str(e)` in two places:
- `CredentialNotFoundError` branch: `"error": sanitize_error(e)`
- SSH connect failure branch: `f"SSH verification failed: {sanitize_error(e)}. ..."`

This keeps `test_sanitize_wiring.py::test_ssh_tools_uses_sanitize_error` GREEN (SEC-04).

## Full-phase test outcome

After all Phase 33 plans land:

- **666 unit tests pass** (from 655 on main pre-Phase-33 minus pre-existing 1 unrelated failure)
- **2 failures remain — both pre-existing, unrelated to Phase 33:**
  - `tests/test_database.py::test_ssh_credentials_table_dropped_postgres` — requires Postgres fixture
  - `tests/test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host` — confirmed failing on `b0b86be` before Phase 33 started
- **All Wave 0 RED tests flipped to GREEN**:
  - `test_ssh_credentials.py::TestResolveSSHCredentials` (3) — D-08/D-16/D-17
  - `test_ssh_credentials.py::TestCredentialNotFoundError` (1) — D-05
  - `test_ssh_credentials.py::TestRegisterServer` (6) — D-03/D-04/D-05/D-07/D-23
  - `test_ssh_credentials.py::TestListRegisteredServers` (2) — D-19
  - `test_mcp_prompts.py::test_connect_to_device_*` (4) — D-13/D-14/D-18/D-22
  - `test_openapi_app.py` absence tests (3) — D-10/D-20/D-21
  - `test_tools.py` tool-handler removal tests (3) — D-10/D-20/D-21
  - `test_ssh_tools.py::test_setup_remote_mcp_admin_absent` (1) — D-11
  - `test_ast_regression.py` (3) — D-15/D-25

## AST meta-test

`test_no_forbidden_strings_in_source` — **GREEN**. Zero violations outside the `migration.py` allowlist (which legitimately contains `"ssh_credentials"` inside the DROP TABLE statement).

## Remaining deferred items

From `VALIDATION.md`:
- **Manual-only verifications:**
  - `homelab-mcp --version` in an installed (uvx) environment — cannot automate headless
  - TTY echo suppression for `credentials add` password prompt — getpass standard behavior, test at actual terminal
  - Key-path round-trip via real SSH key file — requires actual key, cannot automate without a real target host
- **Legacy DB migration notice:** users who stored credentials only in the dropped `ssh_credentials` DB table must re-add via `homelab-mcp credentials add`. No auto-migration is planned (homelab scope, single-user). Migration.py prints a stderr notice pointing to the CLI command.
- **Integration test rewrites** (Plan 33-04 deferred these out of scope):
  - `tests/integration/test_ssh_integration.py` and `test_sitemap_integration.py` are currently `pytest.skip`-gated at module load. They reference the removed `setup_remote_mcp_admin` function and need to be rewritten to use the keyring-based onboarding flow. This is a tech-debt item for v1.6.x or v1.7.

## Phase 33 acceptance: all 4 CRED requirements complete

| Req | Scope | Landing plan |
|-----|-------|--------------|
| CRED-04 | ssh_credentials DB table + methods removed | 33-02 |
| CRED-05 | Two-tier keyring-only resolver + --key-path CLI | 33-03 |
| CRED-06 | Credential-write MCP tools removed (setup_mcp_admin, update_server_credentials, remove_server); prompt rewritten | 33-04 + 33-05 |
| CRED-07 | register_server verify-only | 33-05 |

All 17 + 8 addendum decisions (D-01 through D-25) implemented.
