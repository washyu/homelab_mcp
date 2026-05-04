# Phase 33: Keyring Single Source of Truth - Pattern Map

**Mapped:** 2026-04-20
**Files analyzed:** 17 source/test files to be modified + 1 new test file
**Analogs found:** 17 / 18 (1 novel — AST meta-test for D-15)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/homelab_mcp/migration.py` | migration | DB | same file `create_drift_baselines_table` block (lines 68–93) | exact |
| `src/homelab_mcp/database.py` | adapter | DB | same file `init_schema` drift_baselines section (SQLiteAdapter) | exact |
| `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials` | service | keyring/request-response | same file Tier 2 keyring block (lines 75–97) | exact |
| `src/homelab_mcp/ssh_tools.py` — `register_server` | service | keyring/request-response | same file `verify_mcp_admin_access` (verify-only async function) | role-match |
| `src/homelab_mcp/ssh_tools.py` — `update_mcp_admin_groups` error string | service | request-response | same file existing error dict returns | exact |
| `src/homelab_mcp/ssh_tools.py` — `list_registered_servers` | service | keyring | `credential_store.list_credentials` call in `handle_list_keyring_credentials` | role-match |
| `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` | schema | MCP protocol | same file `ssh_discover` schema entry (lines 6–32) | exact |
| `src/homelab_mcp/tool_handlers/ssh_handlers.py` | tool-handler | MCP protocol | same file `handle_verify_mcp_admin` (lines 30–33) | exact |
| `src/homelab_mcp/tool_handlers/credential_handlers.py` | tool-handler | keyring/MCP protocol | same file `handle_list_keyring_credentials` (lines 72–82) | exact |
| `src/homelab_mcp/tool_handlers/__init__.py` | registry | MCP protocol | same file — existing dispatch dict removals (pattern: delete import + dict entry) | exact |
| `src/homelab_mcp/tool_annotations.py` | config | MCP protocol | same file `update_mcp_admin_groups` annotation block (lines 97–101) | exact |
| `src/homelab_mcp/openapi_app.py` | config | MCP protocol | same file `_SSH_TOOLS_WITH_HOSTNAME` tuple + `TOOL_CATEGORIES["SSH"]` list | exact |
| `src/homelab_mcp/prompt_registry.py` | prompt | MCP protocol | same file `_build_deploy_service_workflow_result` (lines 108–122) | exact |
| `src/homelab_mcp/server.py` — `_cmd_credentials_add` | CLI | keyring/CLI | same file `_cmd_credentials_remove` (lines 524–540) + `add_p` argparse block (lines 653–657) | exact |
| `tests/test_ssh_credentials.py` | test | keyring/unit | `tests/test_credential_store.py` keyring-mock pattern (lines 13–80) | role-match |
| `tests/test_mcp_prompts.py` | test | MCP protocol/unit | same file `test_connect_to_device_prompt` (lines 96–115) — assertion flip only | exact |
| `tests/test_ssh_tools.py` | test | unit | same file — delete import + delete test classes | exact |
| `tests/test_database.py` | test | DB/unit | same file `TestSQLiteAdapter.test_init_schema` (lines 35–51) | role-match |
| `tests/test_ast_regression.py` (NEW) | test | AST meta-lint | `tests/test_http_app.py` AST walker in `test_read_output_no_sleep_after_wait_for` (lines 241–268) + Phase 32 PATTERNS.md SSH-02 AST meta-test sketch | partial (novel scan target; AST walk structure is identical) |

---

## Pattern Assignments

---

### `src/homelab_mcp/migration.py` (migration, DB)

**Change:** Replace the `CREATE TABLE IF NOT EXISTS ssh_credentials` block (lines 27–65 SQLite, lines 110–153 Postgres) with idempotent DROP statements. The table-check `if not cursor.fetchone()` guard inverts — fire the DROP unconditionally with `IF EXISTS` (which is already idempotent).

**Analog:** `run_sqlite_migrations` — `drift_baselines` table creation block (lines 68–93). The shape is: check table → if not exists → execute DDL → commit → `applied_migrations.append(...)` → `print(...)`.

**Structural pattern to follow (lines 68–93):**
```python
# Check if drift_baselines table exists
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='drift_baselines'
""")
if not cursor.fetchone():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drift_baselines (...)
    """)
    ...
    adapter.connection.commit()
    applied_migrations.append("create_drift_baselines_table")
```

**Target pattern for D-01 (invert the guard — DROP fires when table DOES exist):**
```python
# D-01: Drop legacy ssh_credentials table if it still exists (v1.6 cleanup)
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='ssh_credentials'
""")
if cursor.fetchone():
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_hostname")
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_device_id")
    cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
    adapter.connection.commit()
    applied_migrations.append("drop_ssh_credentials_table")
    print("Dropped legacy ssh_credentials table (v1.6: keyring is now sole credential store)")
    import sys
    print(
        "NOTE: Any credentials previously stored in the database have been removed.\n"
        "Re-add them with: homelab-mcp credentials add <hostname> <username>",
        file=sys.stderr,
    )
```

**For `run_postgres_migrations` (lines 110–153):** Same inversion. Replace the `if not cursor.fetchone()[0]:` CREATE block with a `if cursor.fetchone()[0]:` DROP block using `DROP INDEX IF EXISTS` + `DROP TABLE IF EXISTS`.

**Postgres check query stays the same:**
```python
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ssh_credentials'
    )
""")
if cursor.fetchone()[0]:   # table exists → drop it
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_hostname")
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_device_id")
    cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
    adapter.connection.commit()
    applied_migrations.append("drop_ssh_credentials_table")
```

---

### `src/homelab_mcp/database.py` — credential method deletion (adapter, DB)

**Change:** Delete `add_credential`, `get_credential`, `get_credential_by_hostname`, `update_credential`, `delete_credential`, `list_credentials` (DB-side), `update_last_verified` from both `SQLiteAdapter` (lines 473–635) and `PostgreSQLAdapter` (lines 1065–1235). The `# SSH Credentials CRUD methods` comment block and the `is_active` toggle helper go with them.

**No replacement needed** — complete deletion. The analog to confirm the correct deletion boundary is the preceding method `get_device_changes` (which stays) and the `drift_baselines` methods (which also stay). Delete from `# SSH Credentials CRUD methods` comment through the last credential method's closing line, leaving no stub bodies.

**Verification pattern from `test_database.py` to guide deletion scope:**
```python
# test_init_schema (lines 35–51) shows the non-credential tables that must REMAIN:
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
assert cursor.fetchone() is not None
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='discovery_history'")
assert cursor.fetchone() is not None
```

---

### `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials` rewrite (service, keyring)

**Change:** Delete Tier 3 (DB lookup, lines 99–126) and Tier 4 (`mcp_admin` default key fallback, lines 128–138). Extend existing Tier 2 keyring block to handle `auth_type: "key"` (D-09).

**Existing Tier 2 pattern to extend (lines 75–97) — the production code to keep and grow:**
```python
# Tier 2: Keyring lookup
registry_entries = list_credentials(credential_type="ssh")
matched = [e for e in registry_entries if e["hostname"] == hostname]
if matched:
    stored_username = matched[0]["username"]
    resolved_username = username or stored_username
    keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
    if keyring_password:
        logger.debug("Auto-injected keyring credential for %s", hostname)
        return SSHCredentials(
            hostname=hostname,
            username=resolved_username,
            port=port,
            password=keyring_password,
        )
    logger.warning(
        "Credential desync for %s (user: %s): registry entry exists but keyring "
        "returned None — re-run 'homelab-mcp credentials add %s %s' to restore",
        hostname, stored_username, hostname, stored_username,
    )
```

**D-09 extension — add `auth_type` branch inside the `if matched:` block, before the desync warning:**
```python
if matched:
    stored_username = matched[0]["username"]
    resolved_username = username or stored_username
    auth_type = matched[0].get("auth_type", "password")  # D-09 backward compat

    if auth_type == "key":
        key_path_stored = get_credential(hostname, stored_username, credential_type="ssh")
        if key_path_stored:
            return SSHCredentials(
                hostname=hostname,
                username=resolved_username,
                port=port,
                key_path=key_path_stored,
            )
    else:
        keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
        if keyring_password:
            logger.debug("Auto-injected keyring credential for %s", hostname)
            return SSHCredentials(
                hostname=hostname,
                username=resolved_username,
                port=port,
                password=keyring_password,
            )
    # Desync: registry entry exists but keyring returned None
    logger.warning(
        "Credential desync for %s (user: %s): registry entry exists but keyring "
        "returned None — re-run 'homelab-mcp credentials add %s %s' to restore",
        hostname, stored_username, hostname, stored_username,
    )
```

**After the `if matched:` block, replace the Tier 3+4 code with a single raise (lines 140–144 become the new terminal):**
```python
raise CredentialNotFoundError(
    f"No credentials found for {hostname}. "
    "Run `homelab-mcp credentials add <hostname> <username>` in your terminal."
)
```

**D-23 — `username` default removal in function signature (line 44):**
```python
# BEFORE:
def resolve_ssh_credentials(
    hostname: str,
    username: str | None = None,  # keep None; this is fine — no forced default
    ...

# D-23 applies to register_server, not resolve_ssh_credentials
# resolve_ssh_credentials can keep username: str | None = None (None triggers keyring lookup)
```

---

### `src/homelab_mcp/ssh_tools.py` — `register_server` rewrite (service, keyring/request-response)

**Change:** Remove `key_path`, `verify_connection` params; remove all DB access; make verification mandatory. Analog for verify-only async pattern: `verify_mcp_admin_access` in the same file.

**Analog for verify-only result shape (any existing verify function that returns JSON dict):**
```python
# Pattern: async def returning json.dumps({status, hostname, verified})
# Analog: credential_handlers.py handle_register_server thin wrapper
async def handle_register_server(arguments: dict[str, Any]) -> dict[str, Any]:
    result = await register_server(**arguments)
    return {"content": [{"type": "text", "text": result}]}
```

**Target `register_server` signature (D-03, D-07, D-23):**
```python
async def register_server(
    hostname: str,
    username: str,           # D-23: required, no default
    port: int = 22,
    display_name: str | None = None,
    # key_path REMOVED (D-03)
    # verify_connection REMOVED (D-07)
) -> str:
```

**Target body pattern — resolve → verify → return (D-04, D-05):**
```python
async def register_server(
    hostname: str,
    username: str,
    port: int = 22,
    display_name: str | None = None,
) -> str:
    """Verify SSH connectivity using keyring credentials. Does NOT write credentials."""
    try:
        creds = resolve_ssh_credentials(hostname=hostname, username=username, port=port)
    except CredentialNotFoundError as e:
        return json.dumps({
            "status": "error",
            "hostname": hostname,
            "username": username,
            "verified": False,
            "error": str(e),
        })

    try:
        async with ssh_connect(
            hostname,
            username=creds.username,
            password=creds.password,
            client_keys=[creds.key_path] if creds.key_path else [],
            port=creds.port,
            known_hosts=None,
        ) as _conn:
            pass  # connection opened and closed — verification successful
    except Exception as e:
        return json.dumps({
            "status": "error",
            "hostname": hostname,
            "username": username,
            "verified": False,
            "error": (
                f"SSH verification failed: {e}. "
                "Re-add credentials with: "
                f"homelab-mcp credentials add {hostname} {username}"
            ),
        })

    return json.dumps({
        "status": "success",
        "hostname": hostname,
        "username": username,
        "verified": True,
        "display_name": display_name,
    })
```

---

### `src/homelab_mcp/ssh_tools.py` — `update_mcp_admin_groups` error string (service, request-response)

**Change:** Single string replacement at line ~758. D-24 dictates the new wording.

**Current pattern (line ~758):**
```python
"error": "mcp_admin user does not exist. Run setup_mcp_admin first."
```

**Target pattern (D-24):**
```python
"error": (
    "mcp_admin user does not exist on target. "
    "Create any sudo-capable user and register it via "
    "`homelab-mcp credentials add <hostname> <username>`."
)
```

---

### `src/homelab_mcp/ssh_tools.py` — `list_registered_servers` rewrite (service, keyring)

**Change:** Remove DB access; read from `list_credentials()` in `credential_store`. D-19.

**Analog:** `credential_handlers.py::handle_list_keyring_credentials` (lines 72–82):
```python
async def handle_list_keyring_credentials(arguments: dict[str, Any]) -> dict[str, Any]:
    credential_type = arguments.get("credential_type", "ssh")
    entries = list_credentials(credential_type=credential_type)
    result = {
        "status": "success",
        "credential_type": credential_type,
        "count": len(entries),
        "credentials": [{"hostname": e["hostname"], "username": e["username"]} for e in entries],
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

**Target `list_registered_servers` pattern (sync, returns JSON string):**
```python
def list_registered_servers() -> str:
    """List servers registered in the keyring credential registry."""
    entries = list_credentials(credential_type="ssh")
    result = {
        "status": "success",
        "count": len(entries),
        "servers": [
            {"hostname": e["hostname"], "username": e["username"]}
            for e in entries
        ],
    }
    return json.dumps(result, indent=2)
```

---

### `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` (schema, MCP protocol)

**Change:** Delete the `"setup_mcp_admin"` entry (lines 33–~80), `"update_server_credentials"` entry, and `"remove_server"` entry from the `SSH_TOOLS` dict. D-10, D-20, D-21.

**Analog for what a remaining schema entry looks like (lines 6–32 for `ssh_discover`):**
```python
"ssh_discover": {
    "description": "SSH into a system and gather hardware/system information...",
    "inputSchema": {
        "type": "object",
        "properties": {
            "hostname": {"type": "string", "description": "Hostname or IP address"},
            ...
        },
        "required": ["hostname"],
    },
},
```

The deletion leaves no stub — simply remove the entire `"setup_mcp_admin": {...}` key-value pair. Same for `"update_server_credentials"` and `"remove_server"`.

---

### `src/homelab_mcp/tool_handlers/ssh_handlers.py` (tool-handler, MCP protocol)

**Change:** Delete `handle_setup_mcp_admin` (lines 24–27) and its import of `setup_remote_mcp_admin`. D-10.

**Current handler pattern (lines 24–27) — to delete entirely:**
```python
async def handle_setup_mcp_admin(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle setup_mcp_admin tool."""
    result = await setup_remote_mcp_admin(**arguments)
    return {"content": [{"type": "text", "text": result}]}
```

**Remaining handlers following the same shape (lines 30–33 — do not touch):**
```python
async def handle_verify_mcp_admin(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle verify_mcp_admin tool."""
    result = await verify_mcp_admin_access(**arguments)
    return {"content": [{"type": "text", "text": result}]}
```

**Import line to remove from lines 8–14:**
```python
from ..ssh_tools import (
    setup_remote_mcp_admin,   # DELETE THIS LINE
    ssh_discover_system,
    ssh_execute_command,
    update_mcp_admin_groups,
    verify_mcp_admin_access,
)
```

---

### `src/homelab_mcp/tool_handlers/credential_handlers.py` (tool-handler, keyring/MCP protocol)

**Change:** Delete `handle_update_server_credentials` (lines 27–30), `handle_remove_server` (lines 33–69), `handle_remove_server_preview` (lines 85–91); remove `update_server_credentials`, `remove_server` from the import block (lines 7–12). Update `handle_register_server` if needed to match new `register_server` signature. D-20, D-21.

**Import block before (lines 6–12):**
```python
from ..credential_store import list_credentials
from ..ssh_tools import (
    list_registered_servers,
    register_server,
    remove_server,            # DELETE
    update_server_credentials, # DELETE
)
```

**Import block after:**
```python
from ..credential_store import list_credentials
from ..ssh_tools import (
    list_registered_servers,
    register_server,
)
```

**`handle_register_server` stays as-is (lines 15–18) — the thin wrapper pattern requires no change:**
```python
async def handle_register_server(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle register_server tool."""
    result = await register_server(**arguments)
    return {"content": [{"type": "text", "text": result}]}
```

**`handle_remove_server` dry_run DB access pattern (lines 33–69) — DELETE entirely.** No replacement. The `dry_run` and DB-access logic was specific to the removed tool.

---

### `src/homelab_mcp/tool_handlers/__init__.py` (registry, MCP protocol)

**Change:** Remove three imports and three dispatch dict entries. D-10, D-20, D-21.

**Import block edit (lines 6–13):**
```python
from .credential_handlers import (
    handle_list_keyring_credentials,
    handle_list_registered_servers,
    handle_register_server,
    handle_remove_server,           # DELETE
    handle_remove_server_preview,   # DELETE
    handle_update_server_credentials, # DELETE
)
```

**Import block from ssh_handlers (lines 60–67):**
```python
from .ssh_handlers import (
    handle_setup_mcp_admin,         # DELETE
    handle_ssh_discover,
    handle_ssh_execute_command,
    handle_start_interactive_shell,
    handle_update_mcp_admin_groups,
    handle_verify_mcp_admin,
)
```

**TOOL_HANDLERS dict entries to delete (lines 82–148):**
```python
# DELETE these three lines from the dict:
"setup_mcp_admin": handle_setup_mcp_admin,        # line 85
"update_server_credentials": handle_update_server_credentials,  # line 130
"remove_server": handle_remove_server,             # line 131
"remove_server_preview": handle_remove_server_preview,         # line 132
```

**`__all__` line (line 158) — remove any exported names that are deleted.**

---

### `src/homelab_mcp/tool_annotations.py` (config, MCP protocol)

**Change:** Delete the `"setup_mcp_admin"` annotation entry (lines 92–96). D-10.

**Entry to delete:**
```python
"setup_mcp_admin": ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
),
```

**Surrounding entries that stay (for boundary reference):**
```python
"bulk_discover_and_map": ToolAnnotations(...),  # line 87–91 — stays
# "setup_mcp_admin" block deleted here
"update_mcp_admin_groups": ToolAnnotations(...),  # line 97–101 — stays
```

Also check if `update_server_credentials` and `remove_server` have annotation entries (D-20, D-21) — delete those too if present.

---

### `src/homelab_mcp/openapi_app.py` (config, MCP protocol)

**Change:** Remove `"setup_mcp_admin"` from `_SSH_TOOLS_WITH_HOSTNAME` tuple (line 70) and from `TOOL_CATEGORIES["SSH"]` list (line 146). D-10. Also remove `"update_server_credentials"` and `"remove_server"` from wherever they appear. D-20, D-21.

**`_SSH_TOOLS_WITH_HOSTNAME` before (lines 68–86):**
```python
_SSH_TOOLS_WITH_HOSTNAME = (
    "ssh_discover",
    "setup_mcp_admin",      # DELETE THIS LINE
    "verify_mcp_admin",
    "ssh_execute_command",
    ...
)
```

**`TOOL_CATEGORIES["SSH"]` before (lines 143–151):**
```python
"SSH": [
    "ssh_discover",
    "setup_mcp_admin",      # DELETE THIS LINE
    "verify_mcp_admin",
    "ssh_execute_command",
    "start_interactive_shell",
    "update_mcp_admin_groups",
],
```

---

### `src/homelab_mcp/prompt_registry.py` — `_build_connect_to_device_result` (prompt, MCP protocol)

**Change:** Rewrite the `text` f-string in `_build_connect_to_device_result` (lines 128–143). D-13, D-22.

**Current text block (lines 128–143) — to replace:**
```python
text = f"""Follow these steps to onboard {hostname} into your homelab:

1. Call setup_mcp_admin with hostname="{hostname}" to create the mcp_admin user and \
SSH key on the device.
2. Run the CLI command: homelab-mcp credentials add {hostname} mcp_admin — \
this stores the SSH credential in your OS keyring.
3. Call register_server with hostname="{hostname}" and username="mcp_admin" to \
add the device to the server database.
...
```

**Target text block (D-13 six-step sequence, D-22 step 1 wording):**
```python
text = f"""Follow these steps to onboard {hostname} into your homelab:

1. Ensure you have an SSH-accessible user on {hostname} with sudo privileges. \
The username can be anything — you will specify it in the next step.
2. Run the CLI command in your terminal: \
homelab-mcp credentials add {hostname} <username> — \
this stores the SSH credential in your OS keyring. \
For key-based auth: homelab-mcp credentials add {hostname} <username> --key-path <path>.
3. Call register_server with hostname="{hostname}" and username="<username>" to \
verify the stored credential end-to-end.
4. Call ssh_discover with hostname="{hostname}" to collect hardware and system info \
and record it in the database.
5. Call discover_and_map with hostname="{hostname}" to add the device to the network \
sitemap.
6. Call verify_mcp_admin with hostname="{hostname}" to confirm that the registered \
user has sudo access.

If any step fails, fix the issue before proceeding to the next step."""
```

**Function wrapper stays unchanged (lines 125–127, 144–147):**
```python
def _build_connect_to_device_result(args: dict[str, str]) -> types.GetPromptResult:
    """Build the connect_to_device prompt result (TOFU-03)."""
    hostname = args.get("hostname", "<hostname>")
    text = f"""..."""
    return types.GetPromptResult(
        description="Full device onboarding workflow",
        messages=[_make_user_message(text)],
    )
```

---

### `src/homelab_mcp/server.py` — `_cmd_credentials_add` + argparse (CLI, keyring/CLI)

**Change:** Add `--key-path` flag to `add_p` subparser (lines 653–657); update `_cmd_credentials_add` to branch on `key_path` vs password. D-09.

**Existing `add_p` argparse block to extend (lines 653–657):**
```python
add_p = cred_sub.add_parser("add", help="Store a credential")
add_p.add_argument("hostname")
add_p.add_argument("username")
add_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh", dest="credential_type")
add_p.set_defaults(func=_cmd_credentials_add)
```

**Add `--key-path` flag (new line after `--type`):**
```python
add_p.add_argument(
    "--key-path",
    dest="key_path",
    default=None,
    help="Path to SSH private key file (key-auth instead of password prompt)",
)
```

**Existing `_cmd_credentials_add` (lines 491–509) — analog for the branch pattern is `_cmd_credentials_remove` (lines 524–540):**
```python
def _cmd_credentials_remove(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials remove <hostname> [--type ssh|proxmox]`."""
    import sys

    credential_type: str = args.credential_type
    entries = [e for e in list_credentials(credential_type=credential_type) if e["hostname"] == args.hostname]
    if not entries:
        print(f"No {credential_type} credential found for {args.hostname}", file=sys.stderr)
        sys.exit(1)

    for entry in entries:
        delete_credential(entry["hostname"], entry["username"], credential_type=credential_type)
    unregister_credential(args.hostname, credential_type=credential_type)
    print(f"Removed {credential_type} credential for {args.hostname}")
```

**Target `_cmd_credentials_add` with `--key-path` branch (D-09):**
```python
def _cmd_credentials_add(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials add <hostname> <username> [--type ssh|proxmox] [--key-path PATH]`."""
    import getpass  # noqa: PLC0415
    import sys  # noqa: PLC0415

    credential_type: str = args.credential_type
    key_path: str | None = getattr(args, "key_path", None)

    if key_path is not None:
        # Key-path auth: validate file exists then store path string as "secret"
        import pathlib  # noqa: PLC0415
        key_file = pathlib.Path(key_path)
        if not key_file.exists():
            print(f"Error: key file not found: {key_path}", file=sys.stderr)
            sys.exit(1)
        secret = str(key_file.expanduser().resolve())
        auth_type = "key"
    else:
        prompt = "Token/Password: " if credential_type == "proxmox" else "Password: "
        secret = getpass.getpass(prompt)
        auth_type = "password"

    ok = store_credential(args.hostname, args.username, secret, credential_type=credential_type)
    if ok:
        register_credential(
            args.hostname,
            args.username,
            credential_type=credential_type,
            auth_type=auth_type,  # D-09: registry gains auth_type field
        )
        print(f"Stored {credential_type} credential for {args.username}@{args.hostname}")
    else:
        print(
            f"Warning: OS keyring unavailable — credential not persisted for {args.hostname}",
            file=sys.stderr,
        )
        sys.exit(1)
```

**Note:** `register_credential` in `credential_store.py` (line 116) currently does not accept `auth_type`. The planner must also update `register_credential` to accept and store `auth_type` in the JSON registry entry. The registry entry dict (line 127) gains `"auth_type": credential_type`-style field.

---

## Test File Patterns

---

### `tests/test_ssh_credentials.py` (test, keyring/unit)

**Change:** Delete `TestSSHCredentialsDatabase` class (lines 22–188). Delete three test methods from `TestResolveSSHCredentials` (`test_stored_credentials_used` line 219, `test_mcp_admin_uses_default_key` line 242). Delete `test_no_raise_when_mcp_admin_key_exists` from `TestCredentialNotFoundError` (line 291). Rewrite `TestRegisterServer` class. Add D-16/D-17 tests.

**Analog for new keyring-mock unit tests:** `tests/test_credential_store.py` monkeypatching pattern (lines 13–79):
```python
def test_store_credential_success(mocker):
    """store_credential returns True when keyring.set_password succeeds."""
    from homelab_mcp.credential_store import store_credential

    mocker.patch("keyring.set_password", return_value=None)
    result = store_credential("192.168.1.1", "root", "secret")
    assert result is True
```

**D-16 positive keyring test — copy this monkeypatch shape:**
```python
# tests/test_ssh_credentials.py — new tests at bottom of TestResolveSSHCredentials class

@patch("src.homelab_mcp.ssh_tools.list_credentials")
@patch("src.homelab_mcp.ssh_tools.get_credential")
def test_resolve_keyring_password_auth(self, mock_get_cred, mock_list_creds):
    """D-16: resolve_ssh_credentials returns keyring-backed password credential."""
    mock_list_creds.return_value = [
        {"hostname": "192.168.1.100", "username": "admin", "credential_type": "ssh", "auth_type": "password"}
    ]
    mock_get_cred.return_value = "secret_password"

    creds = resolve_ssh_credentials(hostname="192.168.1.100", username="admin")

    assert isinstance(creds, SSHCredentials)
    assert creds.password == "secret_password"
    assert creds.key_path is None

@patch("src.homelab_mcp.ssh_tools.list_credentials")
@patch("src.homelab_mcp.ssh_tools.get_credential")
def test_resolve_keyring_key_path_auth(self, mock_get_cred, mock_list_creds):
    """D-16: resolve_ssh_credentials returns key-path credential when auth_type='key'."""
    mock_list_creds.return_value = [
        {"hostname": "192.168.1.100", "username": "admin", "credential_type": "ssh", "auth_type": "key"}
    ]
    mock_get_cred.return_value = "/home/user/.ssh/my_key"

    creds = resolve_ssh_credentials(hostname="192.168.1.100", username="admin")

    assert creds.key_path == "/home/user/.ssh/my_key"
    assert creds.password is None
```

**D-17 negative mcp_admin fallback test:**
```python
@patch("src.homelab_mcp.ssh_tools.list_credentials")
def test_mcp_admin_no_fallback(self, mock_list_creds):
    """D-17: resolve_ssh_credentials raises CredentialNotFoundError for mcp_admin with empty keyring."""
    mock_list_creds.return_value = []  # keyring registry is empty

    with pytest.raises(CredentialNotFoundError) as exc_info:
        resolve_ssh_credentials(hostname="any-host", username="mcp_admin")

    assert "credentials add" in str(exc_info.value)
```

**Rewritten `TestRegisterServer` — no DB mock, async SSH mock:**
```python
class TestRegisterServer:
    """Test register_server verify-only behavior (D-03/D-04)."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.ssh_tools.resolve_ssh_credentials")
    @patch("src.homelab_mcp.ssh_tools.ssh_connect")
    async def test_register_server_verify_success(self, mock_ssh_connect, mock_resolve):
        """register_server returns verified=true when keyring resolves and SSH connects."""
        mock_resolve.return_value = SSHCredentials(
            hostname="192.168.1.100", username="admin", port=22, password="pw"
        )
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = AsyncMock()
        mock_ctx.__aexit__.return_value = None
        mock_ssh_connect.return_value = mock_ctx

        result = await register_server(hostname="192.168.1.100", username="admin")
        result_dict = json.loads(result)

        assert result_dict["status"] == "success"
        assert result_dict["verified"] is True
        assert result_dict["hostname"] == "192.168.1.100"

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.ssh_tools.resolve_ssh_credentials")
    async def test_register_server_missing_keyring_returns_error(self, mock_resolve):
        """register_server returns actionable error when keyring has no entry."""
        mock_resolve.side_effect = CredentialNotFoundError(
            "No credentials found for 192.168.1.100. "
            "Run `homelab-mcp credentials add 192.168.1.100 admin`"
        )

        result = await register_server(hostname="192.168.1.100", username="admin")
        result_dict = json.loads(result)

        assert result_dict["status"] == "error"
        assert result_dict["verified"] is False
        assert "credentials add" in result_dict["error"]
```

**Import block update for test file:** Remove `SQLiteAdapter` import (no longer needed). Remove `update_server_credentials`, `remove_server` from ssh_tools imports.

---

### `tests/test_mcp_prompts.py` (test, MCP protocol/unit)

**Change:** Two assertion flips. D-13, D-14.

**Line 109 — current assertion:**
```python
assert "setup_mcp_admin" in combined_text
```
**Target (flip to negative):**
```python
assert "setup_mcp_admin" not in combined_text
```

**Line 141 — current for-loop list:**
```python
for tool in ("setup_mcp_admin", "ssh_discover", "discover_and_map", "verify_mcp_admin"):
    assert f"{tool}" in combined, f"Missing tool reference: {tool}"
```
**Target (remove `setup_mcp_admin` from the tuple):**
```python
for tool in ("ssh_discover", "discover_and_map", "verify_mcp_admin"):
    assert f"{tool}" in combined, f"Missing tool reference: {tool}"
```

**Also add a new positive assertion after the for-loop (D-14):**
```python
assert "credentials add" in combined, "Prompt must reference 'credentials add' CLI command"
assert "register_server" in combined, "Prompt must reference register_server for verification"
```

---

### `tests/test_ssh_tools.py` (test, unit)

**Change:** Delete import of `setup_remote_mcp_admin` (line 12), delete `test_setup_remote_mcp_admin_success` (line 294), delete `test_setup_mcp_admin_key_injection_safe` (line 844).

**Import line to remove:**
```python
from src.homelab_mcp.ssh_tools import (
    _sudo_run,
    ensure_mcp_ssh_key,
    setup_remote_mcp_admin,   # DELETE THIS LINE
    ssh_discover_system,
    verify_mcp_admin_access,
)
```

**No replacement needed** — the two tests test a deleted function. Simply remove them.

---

### `tests/test_database.py` (test, DB/unit)

**Change:** Add two new tests asserting the post-migration state. D-15 (CRED-04 coverage).

**Analog for `test_init_schema` table-existence check (lines 35–51):**
```python
def test_init_schema(self, temp_db):
    """Test schema initialization."""
    adapter = SQLiteAdapter(temp_db)
    adapter.init_schema()
    cursor = adapter.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
    assert cursor.fetchone() is not None
    adapter.close()
```

**New test 1 — DB table is absent after migration (CRED-04):**
```python
def test_ssh_credentials_table_absent(self, temp_db):
    """CRED-04: ssh_credentials table must not exist after init_schema (v1.6)."""
    adapter = SQLiteAdapter(temp_db)
    adapter.init_schema()
    cursor = adapter.connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ssh_credentials'"
    )
    assert cursor.fetchone() is None, (
        "ssh_credentials table must not be created by init_schema after v1.6 migration"
    )
    adapter.close()
```

**New test 2 — adapter has no credential methods (CRED-04, D-02):**
```python
def test_no_credential_methods_on_adapter(self, temp_db):
    """CRED-04: SQLiteAdapter must not expose credential CRUD methods after D-02."""
    adapter = SQLiteAdapter(temp_db)
    for method_name in (
        "add_credential",
        "get_credential_by_hostname",
        "update_credential",
        "delete_credential",
        "update_last_verified",
    ):
        assert not hasattr(adapter, method_name), (
            f"SQLiteAdapter must not have {method_name!r} after Phase 33 credential DB removal"
        )
```

---

### `tests/test_ast_regression.py` (NEW FILE — test, AST meta-lint)

**Role:** D-15 + D-25. Scans `src/homelab_mcp/**/*.py` for forbidden strings proving no source file re-introduces the deleted DB table name, removed DB methods, or deleted function/tool names.

**Primary analog:** `tests/test_http_app.py` AST walker pattern (`test_read_output_no_sleep_after_wait_for`, lines 241–268 of that file). The Phase 32 PATTERNS.md section "AST Walker Pattern" documents this canonical shape:

```python
# From tests/test_http_app.py (Phase 32 analog)
def test_read_output_no_sleep_after_wait_for(self) -> None:
    import ast
    import inspect
    import textwrap

    from homelab_mcp import http_app
    source = inspect.getsource(http_app.handle_shell_websocket)
    tree = ast.parse(textwrap.dedent(source))

    sleep_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "sleep"
                ...
            ):
                sleep_calls.append(ast.unparse(node))

    assert not sleep_calls, f"asyncio.sleep should be removed from read_output; found: {sleep_calls}"
```

**Target file — use `Path.glob` over source files instead of `inspect.getsource`:**

```python
"""D-15 + D-25 AST meta-test: no source file re-introduces removed credential DB paths.

Scans src/homelab_mcp/**/*.py for forbidden strings that indicate a regression.
Test files are excluded (they may mention removed names in negative assertions).
"""

from __future__ import annotations

import ast
from pathlib import Path


# Strings whose presence in source AST (as Name, Attribute, or string literals) indicates regression
FORBIDDEN_SOURCE_STRINGS: list[str] = [
    "ssh_credentials",           # D-15: DB table name
    "add_credential",            # D-15: removed DB method
    "get_credential_by_hostname", # D-15: removed DB method
    "update_credential",         # D-15: removed DB method
    "update_last_verified",      # D-15: removed DB method
    "setup_remote_mcp_admin",    # D-25: deleted function
    "setup_mcp_admin",           # D-25: removed MCP tool name
    "update_server_credentials", # D-25: removed MCP tool name
]

# verify_connection is forbidden only in register_server handler context
# (the string appears legitimately in other modules) — handled by targeted check below


def _collect_string_literals(tree: ast.AST) -> list[str]:
    """Walk AST and collect all string constant values."""
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _collect_name_and_attr_ids(tree: ast.AST) -> list[str]:
    """Walk AST and collect all Name.id and Attribute.attr values."""
    ids: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            ids.append(node.id)
        elif isinstance(node, ast.Attribute):
            ids.append(node.attr)
    return ids


def test_no_forbidden_strings_in_source() -> None:
    """D-15 + D-25: No source file contains removed credential DB names or deleted tool references."""
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    assert src_root.exists(), f"Source root not found: {src_root}"

    violations: list[str] = []

    for py_file in sorted(src_root.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")

        # Fast pre-check: skip files that don't contain any forbidden string
        if not any(forbidden in source for forbidden in FORBIDDEN_SOURCE_STRINGS):
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            violations.append(f"{py_file}: SyntaxError during AST parse: {e}")
            continue

        all_strings = _collect_string_literals(tree)
        all_ids = _collect_name_and_attr_ids(tree)
        all_tokens = set(all_strings + all_ids)

        for forbidden in FORBIDDEN_SOURCE_STRINGS:
            if forbidden in all_tokens:
                violations.append(
                    f"{py_file.relative_to(src_root.parent.parent)}: "
                    f"contains forbidden identifier/string {forbidden!r}"
                )

    assert not violations, (
        "Phase 33 regression: found removed DB/tool references in source files.\n"
        "These strings must not appear outside test files:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_register_server_handler_no_verify_connection_param() -> None:
    """D-25: register_server in ssh_tools.py must not have verify_connection parameter."""
    import inspect

    from homelab_mcp.ssh_tools import register_server

    sig = inspect.signature(register_server)
    assert "verify_connection" not in sig.parameters, (
        "register_server must not accept verify_connection parameter after Phase 33 (D-07)"
    )
    assert "key_path" not in sig.parameters, (
        "register_server must not accept key_path parameter after Phase 33 (D-03)"
    )
    assert "password" not in sig.parameters, (
        "register_server must not accept password parameter after Phase 33 (D-06)"
    )
```

**File placement:** `tests/test_ast_regression.py` — standalone new file, not appended to an existing module. This matches the Phase 32 convention of placing meta-tests in a dedicated file named for the thing being guarded.

---

## Shared Patterns

### Lazy Keyring Import
**Source:** `src/homelab_mcp/credential_store.py` lines 32–33, 52–53, 80–81
**Apply to:** Any new code in `_cmd_credentials_add` or `register_credential` that touches keyring
```python
import keyring  # noqa: PLC0415
import keyring.errors  # noqa: PLC0415
```
These imports MUST stay inside function bodies, never at module level. This is a project-hard rule (headless Linux D-Bus safety).

### JSON Return Shape for SSH Tool Functions
**Source:** `credential_handlers.py::handle_list_keyring_credentials` (lines 72–82)
**Apply to:** `list_registered_servers`, `register_server`
```python
result = {
    "status": "success",
    ...
}
return json.dumps(result, indent=2)
```

### Monkeypatch Pattern for Keyring Tests
**Source:** `tests/test_credential_store.py` (lines 13–80) and `tests/test_ssh_credentials.py` `@patch("src.homelab_mcp.ssh_tools.list_credentials")` shape
**Apply to:** All new D-16/D-17 tests in `test_ssh_credentials.py`
```python
@patch("src.homelab_mcp.ssh_tools.list_credentials")
@patch("src.homelab_mcp.ssh_tools.get_credential")
def test_xxx(self, mock_get_cred, mock_list_creds):
    mock_list_creds.return_value = [{"hostname": ..., "username": ..., "auth_type": "password"}]
    mock_get_cred.return_value = "secret"
    ...
```

### `@pytest.mark.asyncio` for Async Tests
**Source:** `tests/test_ssh_credentials.py` line 365, `tests/test_ssh_tools.py` line 18
**Apply to:** All new async tests in `TestRegisterServer`
```python
@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.resolve_ssh_credentials")
async def test_xxx(self, mock_resolve):
    ...
```

### `AsyncMock` SSH Connect Context Manager
**Source:** Phase 32 PATTERNS.md SSH-01 pattern + `tests/test_ssh_tools.py` lines 72–106
**Apply to:** New `TestRegisterServer.test_register_server_verify_success`
```python
from unittest.mock import AsyncMock
mock_ctx = AsyncMock()
mock_ctx.__aenter__.return_value = AsyncMock()
mock_ctx.__aexit__.return_value = None
mock_ssh_connect.return_value = mock_ctx
```

### Tool Removal Lock-Step Rule
**Source:** `src/homelab_mcp/code_context` (CONTEXT.md lines 128–130): "schema/annotation parity enforced"
**Apply to:** All three removed tools (`setup_mcp_admin`, `update_server_credentials`, `remove_server`)

For each removed tool, ALL FIVE of these must be updated in the same commit:
1. `tool_schemas/ssh_tools_schema.py` — schema entry deleted
2. `tool_handlers/ssh_handlers.py` or `credential_handlers.py` — handler deleted
3. `tool_handlers/__init__.py` — import + dict entry deleted
4. `tool_annotations.py` — annotation entry deleted
5. `openapi_app.py` — string in `_SSH_TOOLS_WITH_HOSTNAME` and/or `TOOL_CATEGORIES` deleted

Breaking this 5-way lock-step causes the existing schema/annotation parity CI check to fail — which is the intended safety net.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_ast_regression.py` | test | AST meta-lint | Novel scan target: walks `src/homelab_mcp/**/*.py` glob for forbidden identifier strings. No existing test scans the production source tree this way. Cross-file AST walker pattern is borrowed from `test_http_app.py` but the glob-over-source-tree approach is new. |

---

## Metadata

**Analog search scope:**
- `src/homelab_mcp/migration.py` (491 lines) — full read
- `src/homelab_mcp/server.py` lines 480–671 — `_cmd_credentials_*` and argparse setup
- `src/homelab_mcp/tool_handlers/credential_handlers.py` (92 lines) — full read
- `src/homelab_mcp/tool_handlers/__init__.py` (159 lines) — full read
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` lines 1–67
- `src/homelab_mcp/tool_annotations.py` lines 80–110
- `src/homelab_mcp/openapi_app.py` lines 60–160
- `src/homelab_mcp/prompt_registry.py` lines 115–164
- `src/homelab_mcp/credential_store.py` (144 lines) — full read
- `src/homelab_mcp/ssh_tools.py` lines 42–150 (`resolve_ssh_credentials`)
- `src/homelab_mcp/database.py` lines 470–510 (credential method boundary)
- `tests/test_ssh_credentials.py` lines 1–80 + lines 200–403
- `tests/test_credential_store.py` lines 1–80
- `tests/test_mcp_prompts.py` lines 90–154
- `tests/test_ssh_tools.py` lines 1–50
- `tests/test_database.py` lines 1–60
- `tests/test_packaging.py` (139 lines) — AST/meta-test structure reference
- `.planning/milestones/v1.5-phases/32-regression-tests/32-PATTERNS.md` — Phase 32 AST meta-test canonical shape

**Files scanned:** 18 files
**Pattern extraction date:** 2026-04-20
