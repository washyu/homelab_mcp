# Phase 33: Keyring Single Source of Truth - Research

**Researched:** 2026-04-20
**Domain:** Python credential architecture — OS keyring, SQLite DB removal, SSH resolver refactor, MCP tool surface cleanup
**Confidence:** HIGH (all findings verified against live source files)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** `migration.py` runs `DROP TABLE IF EXISTS ssh_credentials` as a one-time migration step on both SQLite and Postgres adapters.
**D-02:** Remove credential-specific methods from both DB adapters entirely: `add_credential`, `get_credential_by_hostname`, `get_credential_by_id`, `update_credential`, `delete_credential`, `list_credentials` (DB-side), `is_active` toggle, `update_last_verified`.
**D-02a:** Keep non-credential DB methods (drift_baselines, devices, etc.) unchanged.
**D-03:** `register_server` becomes verify-only. Accepts `hostname`, `username`, `port`, `display_name`. Does NOT accept `password` or `key_path`. Does NOT write anywhere.
**D-04:** `register_server` behavior: calls `resolve_ssh_credentials()` (keyring-only after D-08), opens one SSH verify connection, returns `{status, hostname, username, verified: true|false}`. No `verify_connection=False` escape hatch.
**D-05:** On missing keyring entry OR verify failure, returns actionable error naming `homelab-mcp credentials add <hostname> <username>`.
**D-06:** Passwords never enter chat. The MCP tool surface has zero write paths for credentials after this phase.
**D-07:** `verify_connection` flag parameter and its code path removed from `register_server`.
**D-08:** Remove the implicit `mcp_admin` + default-key fallback from `resolve_ssh_credentials()` entirely. After change: exactly two tiers — explicit args, then keyring.
**D-09:** Extend `credentials add` CLI with `--key-path <path>` flag. Keyring stores the path string under same `(hostname, username, type=ssh)` key. JSON hostname registry gains `auth_type: "password" | "key"` field. Missing `auth_type` defaults to `"password"` (backward compat).
**D-09a:** `~/.ssh/mcp/mcp_admin_key` file is NOT deleted. Users who want it must attach via `credentials add <host> mcp_admin --key-path ~/.ssh/mcp/mcp_admin_key`.
**D-10:** Remove `setup_mcp_admin` from MCP tool surface: schema in `tool_schemas/ssh_tools_schema.py`, handler in `tool_handlers/ssh_handlers.py`, dispatch in `tool_handlers/__init__.py`, annotation in `tool_annotations.py`, two entries in `openapi_app.py`.
**D-11:** Delete `setup_remote_mcp_admin` from `ssh_tools.py` and its solo-support helpers. Keep `update_mcp_admin_groups` and `verify_mcp_admin_access`.
**D-12:** Manual `mcp_admin` bootstrap docs in `docs/` — not a tool. Bootstrap CLI deferred to v1.7+.
**D-13:** Rewrite `_build_connect_to_device_result` in `prompt_registry.py`. New 6-step sequence: (1) manual bootstrap note, (2) `credentials add` CLI, (3) `register_server` verify, (4) `ssh_discover`, (5) `discover_and_map`, (6) `verify_mcp_admin`.
**D-14:** Prompt must not name `setup_mcp_admin` or `register_server --verify_connection=False`.
**D-15:** AST meta-test: scans `src/homelab_mcp/**/*.py`, fails if any non-test file contains `ssh_credentials` or removed DB method names.
**D-16:** Positive keyring-path tests for `resolve_ssh_credentials()` — both password-auth and key-path-auth cases.
**D-17:** Negative `mcp_admin`-fallback test: monkeypatch `list_credentials` to return empty, call `resolve_ssh_credentials(hostname="anything", username="mcp_admin")`, assert `CredentialNotFoundError` raised.

### Claude's Discretion

- Exact layout of DROP TABLE migration (new migration module vs inline in `init_schema`) — must be idempotent.
- Exact error-message wording for `CredentialNotFoundError` variants.
- Documentation page layout for manual `mcp_admin` bootstrap description.
- Whether `--key-path` validation (file exists? readable? 0600?) is strict or permissive — strict preferred.

### Deferred Ideas (OUT OF SCOPE)

- Fresh-device `mcp_admin` bootstrap CLI (`homelab-mcp bootstrap <host>`) — v1.7+.
- Auto-migration of legacy DB rows into the keyring — explicit Out of Scope.
- Encrypted keyring backups / export — homelab user concern.
- `scripts/bootstrap-mcp-admin.sh` provisioning script — v1.7 candidate.
- Per-tool-call credential override via MCP args — rejected permanently by D-06.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CRED-04 | SSH credentials stored exclusively in OS keyring — `ssh_credentials` table removed; no parallel credential storage | D-01/D-02 DB removal; migration.py DROP TABLE; database.py method removal |
| CRED-05 | SSH tools no longer fall back to `mcp_admin` hardcoded defaults — keyring miss raises actionable error | D-08 resolver rewrite; D-16/D-17 regression tests |
| CRED-06 | `setup_mcp_admin` MCP tool removed — onboarding via `credentials add` CLI and `connect_to_device` prompt | D-10/D-11 removal; D-13 prompt rewrite |
| CRED-07 | `register_server` validates credentials via standard `resolve_ssh_credentials()` before accepting registration — no bypass | D-03/D-04/D-07 register_server rewrite; D-05 error shape |
</phase_requirements>

---

## Summary

Phase 33 is a **deletion and simplification phase** — no new features, only removal of dead code paths and hardcoded fallbacks. The codebase currently has three credential tiers stacked in `resolve_ssh_credentials()`: (1) explicit args, (2) keyring lookup, (3) DB `ssh_credentials` table, (4) `mcp_admin` default key. This phase collapses tiers 3 and 4, making tier 2 (keyring) the terminal fallback with a hard error.

Every source file reference in CONTEXT.md has been verified against the live codebase. Line numbers are broadly accurate, though the function `setup_remote_mcp_admin` in `ssh_tools.py` is now at ~lines 170–670 (it is a large function), not lines 700–750 as cited. `register_server` is confirmed at ~lines 870–969. The DB credential methods in SQLiteAdapter run lines 473–635; PostgresAdapter runs lines 1065–1235.

The biggest implementation risk is the **prompt test breakage**: `tests/test_mcp_prompts.py` has two tests (`test_connect_to_device_prompt` at line 96 and `test_connect_to_device_prompt_parameter_names` at line 132) that currently assert `setup_mcp_admin` is present in the prompt text. These tests MUST be updated as part of D-13 — they will go RED if the prompt is rewritten without also updating the test expectations. The phase plan must sequence prompt rewrite and test update together in the same wave.

**Primary recommendation:** Plan five focused work waves: (1) migration DROP TABLE + DB method removal, (2) `resolve_ssh_credentials()` two-tier rewrite + `--key-path` CLI flag, (3) `setup_mcp_admin` full removal across all 7 call sites, (4) `register_server` verify-only rewrite, (5) regression + AST meta-test suite.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Credential storage | OS keyring (via `credential_store.py`) | — (DB tier removed) | Keyring is the single source of truth per CRED-04 |
| Credential resolution | API/Backend (`resolve_ssh_credentials`) | — | Single funnel for all SSH-touching modules |
| Credential CRUD | CLI (`homelab-mcp credentials`) | — | D-06: no MCP tool writes credentials |
| SSH verification | API/Backend (`register_server` → `ssh_connect`) | — | Verify-only, reads keyring |
| Device onboarding prompt | MCP Prompts (`prompt_registry.py`) | — | D-13: prompt drives workflow, tools don't |
| DB schema migration | DB layer (`migration.py`, `database.py init_schema`) | — | DROP TABLE on both adapters |

---

## Standard Stack

This phase uses no new libraries. All dependencies are already installed.

### Core (unchanged)

| Library | Version | Purpose | Role in Phase |
|---------|---------|---------|---------------|
| `keyring` | installed | OS keyring access | Source of truth for secrets — unchanged |
| `asyncssh` | installed | SSH connections | Used in new `register_server` verify flow |
| `sqlite3` | stdlib | SQLite DB | DROP TABLE target only |
| `pytest` / `pytest-asyncio` | installed | Test framework | New regression tests |
| `argparse` | stdlib | CLI | `--key-path` flag extension |

### No New Packages Required

The entire phase is implemented by modifying existing Python files. No `uv add` steps needed.

---

## Architecture Patterns

### Data Flow After Phase 33

```
MCP Tool Call (e.g., ssh_discover)
        |
        v
   resolve_ssh_credentials(hostname, username)
        |
        +---> Explicit args (password or key_path passed in)?
        |         YES --> return SSHCredentials immediately
        |
        +---> list_credentials("ssh")  [keyring registry JSON]
                  |
                  +---> hostname matched?
                  |         YES --> get_credential(hostname, username, "ssh")
                  |                     |
                  |                     +---> password returned?
                  |                     |         YES --> return SSHCredentials(password=...)
                  |                     |
                  |                     +---> key_path returned?
                  |                               YES --> return SSHCredentials(key_path=...)
                  |                               NO  --> log desync WARNING, fall through
                  |
                  +---> hostname not matched?
                            --> raise CredentialNotFoundError(
                                  "homelab-mcp credentials add <hostname> <username>"
                                )
```

```
register_server(hostname, username, port, display_name)
        |
        v
   resolve_ssh_credentials(hostname, username)  [keyring-only tier]
        |
        +---> CredentialNotFoundError? --> return {"status": "error", actionable_message}
        |
        v
   ssh_connect(hostname, username, ...) -- verify connection
        |
        +---> Exception? --> return {"status": "error", "verified": false, actionable_message}
        |
        v
   return {"status": "success", "hostname": ..., "username": ..., "verified": true}
   (NO DB WRITE)
```

```
homelab-mcp credentials add <hostname> <username> [--key-path PATH]
        |
        +---> --key-path given?
        |         YES: validate path exists (strict preferred), store path string as "secret" in keyring
        |              register_credential(hostname, username, auth_type="key")
        |         NO:  getpass.getpass("Password: "), store password in keyring
        |              register_credential(hostname, username, auth_type="password")
        v
   JSON registry entry: {hostname, username, credential_type, auth_type}
```

### Recommended Project Structure (unchanged)

No structural changes. Modifications are within existing files only.

### Pattern 1: Two-Tier `resolve_ssh_credentials()` (D-08 target state)

```python
# Source: D-08 — verified against current ssh_tools.py lines 42-144
def resolve_ssh_credentials(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> SSHCredentials:
    # Tier 1: Explicit args (backward compatible)
    if password or key_path:
        return SSHCredentials(
            hostname=hostname,
            username=username or "mcp_admin",
            port=port,
            key_path=key_path,
            password=password,
        )

    # Tier 2: Keyring — now the ONLY fallback
    registry_entries = list_credentials(credential_type="ssh")
    matched = [e for e in registry_entries if e["hostname"] == hostname]
    if matched:
        entry = matched[0]
        stored_username = entry["username"]
        resolved_username = username or stored_username
        auth_type = entry.get("auth_type", "password")  # D-09 backward compat

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
                return SSHCredentials(
                    hostname=hostname,
                    username=resolved_username,
                    port=port,
                    password=keyring_password,
                )
        # Registry entry exists but keyring returned None — desync
        logger.warning(
            "Credential desync for %s (user: %s): registry entry exists but keyring "
            "returned None — re-run 'homelab-mcp credentials add %s %s' to restore",
            hostname, stored_username, hostname, stored_username,
        )

    raise CredentialNotFoundError(
        f"No credentials found for {hostname}. "
        "Run `homelab-mcp credentials add <hostname> <username>` in your terminal."
    )
```

### Pattern 2: Migration Drop (D-01 target state)

Idempotent drop in `migration.py` `run_sqlite_migrations()` — replaces the current CREATE-IF-NOT-EXISTS block with DROP-IF-EXISTS:

```python
# SQLite path — replaces CREATE TABLE IF NOT EXISTS ssh_credentials block
cursor.execute("DROP TABLE IF EXISTS idx_ssh_credentials_hostname")   # index first
cursor.execute("DROP TABLE IF EXISTS idx_ssh_credentials_device_id")
cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
applied_migrations.append("drop_ssh_credentials_table")
```

And in `PostgreSQLAdapter.init_schema()` (database.py ~line 784):
```python
# Replace CREATE TABLE IF NOT EXISTS ssh_credentials block + indexes
cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_hostname")
cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_device_id")
cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
```

The planner must choose whether to put the Postgres DROP in `run_postgres_migrations()` or directly in `PostgreSQLAdapter.init_schema()`. Both are idempotent with `IF EXISTS`. Inline in `init_schema` ensures it fires on every startup; a dedicated migration function in `run_postgres_migrations()` is more consistent with the SQLite pattern.

### Anti-Patterns to Avoid

- **Don't convert DB methods to stubs returning empty/None.** D-02 requires complete deletion. Stubs would pass the AST meta-test by not containing `ssh_credentials` strings but would leave dead method bodies that could be revived.
- **Don't remove `get_mcp_ssh_key_path()` function.** `ensure_mcp_ssh_key()` and key generation still need it (key file still exists per D-09a). Only the implicit injection in `resolve_ssh_credentials()` is removed.
- **Don't leave `register_server` in `ssh_tools.py` with a different import surface.** `credential_handlers.py` imports `register_server` from `ssh_tools`. If the function is renamed or split, the import in `credential_handlers.py` must track.
- **Don't update prompt test assertions before updating the prompt.** Tests go RED first, then the prompt rewrite makes them GREEN (Wave-0 TDD pattern used in all previous phases).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Key-path storage in keyring | Custom JSON side-file | `keyring.set_password(service, f"{user}@{host}", key_path_string)` | Already using keyring for passwords; storing path as the "secret" is idiomatic for non-secret pointers |
| Idempotent DROP TABLE | Migration-state tracking table | `DROP TABLE IF EXISTS ssh_credentials` | SQLite and Postgres both support IF EXISTS; no migration version ledger needed |
| `--key-path` argparse flag | Custom flag parser | `add_p.add_argument("--key-path", dest="key_path")` in existing `add_p` subparser | `add_p` already exists in `server.py` at line 653 |

---

## Runtime State Inventory

> Phase 33 involves credential-related naming changes and DB table removal. Checked all 5 categories.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | SQLite `ssh_credentials` table at `~/.homelab_mcp/homelab.db` — may contain rows on existing installs | DROP TABLE on startup via migration (code edit); users must re-add via `credentials add` — no auto-migration by design |
| Live service config | None — no external service holds `ssh_credentials` config; keyring entries are OS-managed | None |
| OS-registered state | None — no Task Scheduler, cron, pm2, or systemd refers to `ssh_credentials` by name | None |
| Secrets/env vars | None — no env var or SOPS key references `ssh_credentials`; keyring service names (`homelab-mcp`, `homelab-mcp-proxmox`) are unchanged | None |
| Build artifacts | None — no egg-info, compiled binaries, or installed scripts reference `ssh_credentials` by name | None |

**Key finding:** The only runtime state is the SQLite DB rows. The DROP TABLE on startup handles the schema. Users with credentials in the old table will lose them silently at first startup — this is documented as intentional in REQUIREMENTS.md Out of Scope. The migration should print a notice to stderr on the first run where the drop is applied.

---

## Common Pitfalls

### Pitfall 1: Prompt Tests Go RED Without Test Update

**What goes wrong:** `test_connect_to_device_prompt` (test_mcp_prompts.py line 96) and `test_connect_to_device_prompt_parameter_names` (line 132) both assert `"setup_mcp_admin"` appears in the prompt text. Rewriting the prompt (D-13) without updating these assertions causes CI failure.

**Why it happens:** The prompt regression tests were written to guard against D-14's exact failure mode — prompt re-introducing `setup_mcp_admin`. After D-13, `setup_mcp_admin` must NOT appear, so the test assertion must flip from `assert "setup_mcp_admin" in combined_text` to `assert "setup_mcp_admin" not in combined_text`.

**How to avoid:** Plan D-13 (prompt rewrite) and prompt test update in the same task. The test_mcp_prompts.py changes must be checked in the same commit as prompt_registry.py.

**Warning signs:** Running `uv run pytest tests/test_mcp_prompts.py` after prompt rewrite without test update will show two failures immediately.

### Pitfall 2: `test_ssh_credentials.py` Has DB-Dependent Tests

**What goes wrong:** The entire `TestSSHCredentialsDatabase` class (lines 22–188) tests `adapter.add_credential`, `adapter.get_credential_by_hostname`, etc. These will fail with `AttributeError` after D-02 removes the methods from `SQLiteAdapter`.

**Why it happens:** These tests import from `src.homelab_mcp.database import SQLiteAdapter` and directly call credential methods on it. After D-02, those methods are gone.

**How to avoid:** These tests must be DELETED (not skipped) as part of D-02. They test DB-layer credential methods that are intentionally removed. The `TestRegisterServer` class (lines 362–403) also must be rewritten since it patches `get_database_adapter` — the new `register_server` won't touch the DB at all.

**Warning signs:** `uv run pytest tests/test_ssh_credentials.py` will produce `AttributeError: 'SQLiteAdapter' object has no attribute 'add_credential'` after D-02.

### Pitfall 3: `credential_handlers.py` `handle_remove_server` Has Inline DB Access

**What goes wrong:** `handle_remove_server` in `credential_handlers.py` (lines 37–65) has inline DB calls: `db.get_credential(int(credential_id))` and `db.get_credential_by_hostname(hostname)`. These are used in the dry_run preview path. After D-02 removes these methods, the dry_run preview of `remove_server` breaks.

**Why it happens:** `remove_server` still exists as a function in `ssh_tools.py` (it removes from DB). Its behavior must change after D-02 — it can only remove keyring entries now.

**How to avoid:** D-02 scope includes updating `remove_server` and its associated `list_registered_servers`, `update_server_credentials` functions in ssh_tools.py — these all read from DB. After D-02, `remove_server` should delete from keyring via `delete_credential` and `unregister_credential`, and `list_registered_servers` should read from `list_credentials()` (keyring registry). The `credential_handlers.py` dry_run preview logic must be updated accordingly.

**Warning signs:** If the plan deletes DB methods but doesn't update `remove_server`, `list_registered_servers`, and `update_server_credentials`, the server will crash on those tool calls.

### Pitfall 4: `setup_remote_mcp_admin` Is a Large Function with Internal Helpers

**What goes wrong:** `setup_remote_mcp_admin` in `ssh_tools.py` is NOT at lines 700–750 as CONTEXT.md cites. The actual implementation starts around line 170 and runs through approximately line 660 (it is ~490 lines including all its internal logic). Deleting only "lines 700–750" would not remove the function.

**Why it happens:** CONTEXT.md line numbers were estimated from a different version or were approximate. Research verification found `update_mcp_admin_groups` at line 739 and `register_server` at line 870.

**How to avoid:** The planner must instruct implementers to search for `async def setup_remote_mcp_admin` (which begins around line 170) and delete from that function definition through its closing return statement. Use grep to locate exact current line: `grep -n "async def setup_remote_mcp_admin" src/homelab_mcp/ssh_tools.py`.

**Warning signs:** If `setup_remote_mcp_admin` is still in `ssh_tools.py` but `handle_setup_mcp_admin` is removed from handlers, calling the removed MCP tool will just fail gracefully — but the D-15 AST meta-test won't catch the residual function body since D-15 scans for the string `ssh_credentials` and removed DB method names, not for the function name itself. Plan D-15 to also scan for `setup_remote_mcp_admin`.

### Pitfall 5: `update_mcp_admin_groups` Error Message References Removed Tool

**What goes wrong:** `ssh_tools.py` line 758 contains `"error": "mcp_admin user does not exist. Run setup_mcp_admin first."`. This user-facing error message names a removed tool. After D-10/D-11, the message becomes incorrect.

**Why it happens:** `update_mcp_admin_groups` is kept (D-11 keeps it), but its internal error message still references `setup_mcp_admin`.

**How to avoid:** Update the error message in `update_mcp_admin_groups` to reference the manual bootstrap docs path instead: `"mcp_admin user does not exist. Bootstrap it manually — see docs/mcp_admin_bootstrap.md"` (or similar per D-12 doc location).

### Pitfall 6: AST Meta-test Scope (D-15) Must Cover Residual Function Names

**What goes wrong:** D-15 scans for `ssh_credentials` and DB method names. If `setup_remote_mcp_admin` is only partially removed (function body left but import removed), or if `list_registered_servers` is left pointing at DB, the meta-test won't catch it because it doesn't scan for these.

**How to avoid:** The D-15 AST meta-test must scan for ALL of:
- `ssh_credentials` (DB table name)
- `add_credential` (DB method)
- `get_credential_by_hostname` (DB method)
- `update_credential` (DB method — note: `update_server_credentials` is the MCP tool name, distinct)
- `update_last_verified` (DB method)
- `setup_remote_mcp_admin` (deleted function)
- `verify_connection` (deleted parameter from `register_server`)

The scan must exclude test files (since deleted tests may have been replaced with negative assertions that mention these strings).

---

## Code Examples

### Current `resolve_ssh_credentials()` Three-Tier Structure (VERIFIED)

```python
# Source: src/homelab_mcp/ssh_tools.py lines 42-144 [VERIFIED]
def resolve_ssh_credentials(hostname, username=None, password=None, key_path=None, port=22):
    # Tier 1: explicit args (lines 66-73)
    if password or key_path:
        return SSHCredentials(hostname=hostname, username=username or "mcp_admin", ...)

    # Tier 2: keyring (lines 75-97)
    registry_entries = list_credentials(credential_type="ssh")
    matched = [e for e in registry_entries if e["hostname"] == hostname]
    if matched:
        keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
        if keyring_password:
            return SSHCredentials(... password=keyring_password ...)
        # desync warning logged

    # Tier 3: DB ssh_credentials table (lines 99-126) -- TO BE DELETED
    db = get_database_adapter()
    stored_cred = db.get_credential_by_hostname(hostname, username)
    if stored_cred:
        resolved_key_path = stored_cred.get("key_path")
        # mcp_admin default key injection (lines 112-116) -- TO BE DELETED
        if not resolved_key_path and stored_cred.get("username") == "mcp_admin":
            mcp_key = get_mcp_ssh_key_path()
            if mcp_key.exists():
                resolved_key_path = str(mcp_key)
        return SSHCredentials(...)

    # Tier 4: mcp_admin default key fallback (lines 128-138) -- TO BE DELETED
    resolved_username = username or "mcp_admin"
    if resolved_username == "mcp_admin":
        mcp_key = get_mcp_ssh_key_path()
        if mcp_key.exists():
            return SSHCredentials(... key_path=str(mcp_key) ...)

    raise CredentialNotFoundError(...)
```

### Current `register_server()` (VERIFIED — to be replaced entirely)

```python
# Source: src/homelab_mcp/ssh_tools.py lines 870-969 [VERIFIED]
async def register_server(
    hostname: str,
    username: str = "mcp_admin",
    key_path: str | None = None,        # D-03: REMOVE THIS PARAM
    port: int = 22,
    display_name: str | None = None,
    verify_connection: bool = True,      # D-07: REMOVE THIS PARAM
) -> str:
    db = get_database_adapter()          # D-03: REMOVE all DB access
    db.connect()
    db.init_schema()
    existing = db.get_credential_by_hostname(hostname, username)  # REMOVE
    if existing:
        return json.dumps({"status": "error", "error": "already registered"})
    # ... key injection for mcp_admin (REMOVE)
    # ... conditional verify connection
    credential_id = db.add_credential(...)  # REMOVE
```

### Current `setup_mcp_admin` Schema Entry (VERIFIED)

```python
# Source: src/homelab_mcp/tool_schemas/ssh_tools_schema.py line 33 [VERIFIED]
"setup_mcp_admin": {
    "description": "SSH into a remote system and setup mcp_admin user...",
    ...
}
```

### Current `setup_mcp_admin` in `openapi_app.py` (VERIFIED)

- Line 70: `"setup_mcp_admin",` in `_SSH_TOOLS_WITH_HOSTNAME` tuple
- Line 146: `"setup_mcp_admin",` in `TOOL_CATEGORIES["SSH"]` list

### Current `_build_connect_to_device_result` (VERIFIED — lines 125-147)

```python
# Source: src/homelab_mcp/prompt_registry.py lines 125-147 [VERIFIED]
# Current step 1: "Call setup_mcp_admin with hostname=..." -- D-13 REPLACE
# Current step 2: "Run CLI: homelab-mcp credentials add..." -- KEEP
# Current step 3: "Call register_server with hostname=... and username=..." -- REWORD (no --verify_connection=False)
# Current step 4: "Call ssh_discover..." -- KEEP
# Current step 5: "Call discover_and_map..." -- KEEP
# Current step 6: "Call verify_mcp_admin..." -- KEEP
```

### Current `_cmd_credentials_add` Signature (VERIFIED)

```python
# Source: src/homelab_mcp/server.py lines 491-508 [VERIFIED]
# Existing: add_p.add_argument("--type", choices=["ssh", "proxmox"], ...)
# D-09 ADD: add_p.add_argument("--key-path", dest="key_path", default=None,
#                               help="Path to SSH private key (key-auth instead of password)")
# D-09 ADD: conditional: if key_path → store key_path string as "secret"; if not → getpass
```

### Current DB Credential Methods to Remove (VERIFIED)

SQLiteAdapter (`database.py` ~lines 473–635):
- `add_credential()` — line 474
- `get_credential()` — line 504
- `get_credential_by_hostname()` — line 521
- `update_credential()` — line 552
- `delete_credential()` — line 588
- `list_credentials()` — line 603
- `update_last_verified()` — line 618

PostgreSQLAdapter (`database.py` ~lines 1065–1235):
- Same method names, Postgres SQL syntax

### Tests That Must Be Modified/Deleted (VERIFIED)

`tests/test_ssh_credentials.py`:
- `TestSSHCredentialsDatabase` class (lines 22–188) — **DELETE ENTIRELY** (tests removed DB methods)
- `TestResolveSSHCredentials.test_stored_credentials_used` (line 219) — **DELETE** (tests DB tier)
- `TestResolveSSHCredentials.test_mcp_admin_uses_default_key` (line 242) — **DELETE** (tests removed fallback)
- `TestCredentialNotFoundError.test_no_raise_when_mcp_admin_key_exists` (line 291) — **DELETE** (tests removed fallback)
- `TestCredentialNotFoundError.test_raises_when_no_credentials_exist` (line 269) — **REWRITE** (no DB mock needed; new: no keyring entry → error)
- `TestRegisterServer` class (lines 362–403) — **REWRITE** (new register_server is verify-only, no DB)
- `TestListRegisteredServers`, `TestUpdateServerCredentials`, `TestRemoveServer` — **REWRITE** (now keyring-backed)

`tests/test_mcp_prompts.py`:
- `test_connect_to_device_prompt` line 109: `assert "setup_mcp_admin" in combined_text` → `assert "setup_mcp_admin" not in combined_text`
- `test_connect_to_device_prompt_parameter_names` line 141: remove `"setup_mcp_admin"` from for-loop list

`tests/test_ssh_tools.py`:
- `test_setup_remote_mcp_admin_success` (line 294) and `test_setup_mcp_admin_key_injection_safe` (line 844) — **DELETE** (tests deleted function)
- Import of `setup_remote_mcp_admin` at line 12 — **DELETE**

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DB `ssh_credentials` table as primary store | OS keyring as sole store | This phase (v1.6) | Eliminates credential desync |
| Three-tier resolver (explicit / keyring / DB / default key) | Two-tier resolver (explicit / keyring) | This phase (v1.6) | Hard error on miss — no silent fallback |
| `setup_mcp_admin` MCP tool for bootstrap | Manual docs + `credentials add` CLI | This phase (v1.6) | Passwords never enter chat |
| `register_server` writes to DB | `register_server` verify-only | This phase (v1.6) | No MCP tool writes credentials |

**Deprecated/outdated:**
- `verify_connection: bool = True` parameter on `register_server` — removed by D-07
- `mcp_admin` default key injection in resolver — removed by D-08
- `setup_remote_mcp_admin()` function — removed by D-11
- `handle_setup_mcp_admin()` handler — removed by D-10

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `setup_remote_mcp_admin` starts around line 170 in ssh_tools.py (not lines 700-750 as CONTEXT.md states) | Code Examples | If wrong, planner mis-targets line range — use grep to locate |
| A2 | Postgres adapter is effectively dead code (no production Postgres deployments implied by PROJECT.md noting "SQLite is correct for single-user homelab") | Standard Stack | If Postgres is in use, the DROP TABLE in Postgres init_schema matters more — but `IF EXISTS` makes it safe either way |
| A3 | `update_server_credentials` and `list_registered_servers` in ssh_tools.py need updating to be keyring-backed (not explicitly stated in D-02 but implied since D-02 removes the DB methods they call) | Common Pitfalls | If not updated, those MCP tools crash after DB methods are removed |

---

## Open Questions

1. **What happens to `list_registered_servers` and `update_server_credentials` MCP tools?**
   - What we know: Both currently call DB methods (`db.list_credentials()`, `db.update_credential()`) that D-02 removes. D-02 does not explicitly mention updating these functions.
   - What's unclear: Should they be rewritten to use the keyring registry (`list_credentials()` from credential_store.py) or removed entirely?
   - Recommendation: Rewrite `list_registered_servers` to call `credential_store.list_credentials()` (already returns registry entries). `update_server_credentials` has no keyring equivalent — it should probably be removed from the tool surface or replaced with a CLI-only `credentials update` command. The planner should decide; leaving it as a broken stub is not acceptable.

2. **Does the `remove_server` MCP tool stay or go?**
   - What we know: `remove_server` currently deletes from the DB. After D-02, that path doesn't exist. `credential_store.delete_credential()` + `unregister_credential()` already handle keyring removal via the CLI.
   - What's unclear: D-06 says "no MCP tool writes credentials." Does removing a credential count as a write? If so, `remove_server` should be removed too. If not, it can be rewritten to call `delete_credential` + `unregister_credential`.
   - Recommendation: Treat remove as an exception to D-06 (deletion is not credential injection). Rewrite `remove_server` to be keyring-backed. Flag for explicit user confirmation in planning.

3. **Where do the Phase 33 docs for manual `mcp_admin` bootstrap go?**
   - What we know: D-12 says "docs/ must describe the manual path." There is no existing `docs/` directory visible in the repo listing.
   - What's unclear: Does `docs/` exist? Should this be a new file?
   - Recommendation: Planner creates `docs/mcp_admin_bootstrap.md`. If docs/ doesn't exist, create it. Content: SSH in as root/sudoer, create mcp_admin user, add MCP pubkey to authorized_keys, grant sudoers.

---

## Environment Availability

> Step 2.6: All tools are stdlib or already-installed project dependencies. No external services required.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All code | ✓ | 3.12 (project requirement) | — |
| pytest / pytest-asyncio | New tests | ✓ | installed | — |
| keyring | credential_store.py | ✓ | installed | headless fallback already coded |
| asyncssh | register_server verify | ✓ | installed | — |
| sqlite3 | DROP TABLE migration | ✓ | stdlib | — |

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json` — section required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest]` |
| Quick run command | `uv run pytest tests/test_ssh_credentials.py tests/test_mcp_prompts.py tests/test_ssh_tools.py -x` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRED-04 | `ssh_credentials` table absent from SQLite schema after migration | unit | `uv run pytest tests/test_database.py -k "ssh_credentials" -x` | ❌ Wave 0 |
| CRED-04 | No source file contains `ssh_credentials` string | AST meta | `uv run pytest tests/test_ssh_tools.py -k "ast_scan" -x` | ❌ Wave 0 |
| CRED-04 | `SQLiteAdapter` has no `add_credential` attribute | unit | `uv run pytest tests/test_database.py -k "no_credential_methods" -x` | ❌ Wave 0 |
| CRED-05 | `resolve_ssh_credentials("host", "mcp_admin")` with empty keyring raises `CredentialNotFoundError` | unit | `uv run pytest tests/test_ssh_credentials.py -k "mcp_admin_fallback" -x` | ❌ Wave 0 (D-17) |
| CRED-05 | `resolve_ssh_credentials` with keyring entry (password) returns credential | unit | `uv run pytest tests/test_ssh_credentials.py -k "keyring_password" -x` | ❌ Wave 0 (D-16) |
| CRED-05 | `resolve_ssh_credentials` with keyring entry (key-path) returns credential | unit | `uv run pytest tests/test_ssh_credentials.py -k "keyring_keypath" -x` | ❌ Wave 0 (D-16) |
| CRED-06 | `setup_mcp_admin` not in `TOOL_HANDLERS` | unit | `uv run pytest tests/test_tools.py -k "setup_mcp_admin_removed" -x` | ❌ Wave 0 |
| CRED-06 | `connect_to_device` prompt does not mention `setup_mcp_admin` | unit | `uv run pytest tests/test_mcp_prompts.py -k "connect_to_device" -x` | ✅ (needs assertion flip) |
| CRED-07 | `register_server` with missing keyring entry returns actionable error | unit | `uv run pytest tests/test_ssh_credentials.py -k "register_missing_keyring" -x` | ❌ Wave 0 |
| CRED-07 | `register_server` with valid keyring entry verifies SSH and returns success | unit (async, mocked SSH) | `uv run pytest tests/test_ssh_credentials.py -k "register_verify_success" -x` | ❌ Wave 0 |
| CRED-07 | `register_server` does not accept `password` or `key_path` params | AST meta | in D-15 meta-test | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_ssh_credentials.py tests/test_mcp_prompts.py tests/test_ssh_tools.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

Required before implementation waves begin:

- [ ] `tests/test_ssh_credentials.py` — delete `TestSSHCredentialsDatabase`, rewrite `TestRegisterServer`, add D-16/D-17 tests
- [ ] `tests/test_mcp_prompts.py` — flip `setup_mcp_admin` assertions (lines 109, 141) to negative
- [ ] `tests/test_ssh_tools.py` — delete `test_setup_remote_mcp_admin_success`, `test_setup_mcp_admin_key_injection_safe`, remove import of `setup_remote_mcp_admin`
- [ ] New `tests/test_ssh_credentials.py::test_resolve_keyring_password_auth` — D-16
- [ ] New `tests/test_ssh_credentials.py::test_resolve_keyring_key_path_auth` — D-16
- [ ] New `tests/test_ssh_credentials.py::test_mcp_admin_no_fallback` — D-17
- [ ] New `tests/test_database.py::test_ssh_credentials_table_dropped` — CRED-04 migration test
- [ ] New `tests/test_database.py::test_no_credential_methods_on_adapter` — CRED-04 attribute absence
- [ ] New `tests/test_ssh_tools.py::test_ast_scan_no_ssh_credentials_string` — D-15 meta-test

---

## Security Domain

`security_enforcement` is not explicitly `false` in config — section required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | SSH key / password via OS keyring — no plaintext in MCP protocol |
| V3 Session Management | no | SSH sessions are per-tool-call; no persistent session state |
| V4 Access Control | yes | `mcp_admin` sudo access verified via `verify_mcp_admin_access()` |
| V5 Input Validation | yes | `hostname`, `username`, `port` validated by existing `validate_hostname`/`validate_port` in handlers |
| V6 Cryptography | no | SSH key generation (existing `ensure_mcp_ssh_key`) unchanged; no new crypto |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Password leakage via MCP protocol | Information Disclosure | D-06: no MCP tool accepts `password=` param; `credentials add` CLI uses TTY getpass |
| Credential injection via register_server | Tampering | D-03/D-07: `register_server` accepts no credentials, only verifies existing keyring entry |
| Stale DB credentials used after keyring entry updated | Spoofing | D-01/D-02: DB table dropped entirely; no parallel store to become stale |
| Default key fallback used for unintended hosts | Elevation of Privilege | D-08: fallback removed; explicit keyring entry required per host |

---

## Sources

### Primary (HIGH confidence)

All findings verified by direct source code read in this session:

- `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials` (lines 42-144), `register_server` (lines 870-969), `update_mcp_admin_groups` (line 739), location of `setup_remote_mcp_admin` (~line 170)
- `src/homelab_mcp/database.py` — SQLiteAdapter credential methods (lines 473-635), PostgreSQLAdapter credential methods (lines 1065-1235), `init_schema` ssh_credentials CREATE (lines 222-260 SQLite, lines 784-841 Postgres)
- `src/homelab_mcp/migration.py` — SQLite migration CREATE (lines 27-65), Postgres migration CREATE (lines 110-153)
- `src/homelab_mcp/prompt_registry.py` — `_build_connect_to_device_result` (lines 125-147)
- `src/homelab_mcp/openapi_app.py` — `setup_mcp_admin` in `_SSH_TOOLS_WITH_HOSTNAME` (line 70), `TOOL_CATEGORIES["SSH"]` (line 146)
- `src/homelab_mcp/tool_handlers/__init__.py` — `setup_mcp_admin` dispatch (lines 61, 85)
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` — `handle_setup_mcp_admin` (lines 24-27)
- `src/homelab_mcp/tool_handlers/credential_handlers.py` — `handle_register_server` (lines 15-18), inline DB access in `handle_remove_server` (lines 37-65)
- `src/homelab_mcp/tool_annotations.py` — `setup_mcp_admin` annotation (lines 92-96)
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — `setup_mcp_admin` schema (line 33)
- `src/homelab_mcp/credential_store.py` — full reviewed; `_SERVICE_NAMES`, `register_credential`, `list_credentials` (lines 17-143)
- `src/homelab_mcp/server.py` — `_cmd_credentials_add` (lines 491-508), argparse subparser for `add` (lines 653-657)
- `src/homelab_mcp/shell_session.py` — imports `resolve_ssh_credentials` (line 12), calls it (lines 89-91)
- `tests/test_ssh_credentials.py` — full reviewed (lines 1-577)
- `tests/test_mcp_prompts.py` — `test_connect_to_device_prompt` (lines 96-115), `test_connect_to_device_prompt_parameter_names` (lines 132-143)
- `tests/test_ssh_tools.py` — import of `setup_remote_mcp_admin` (line 12), related tests identified

### Secondary (MEDIUM confidence)

- `.planning/phases/33-keyring-single-source-of-truth/33-CONTEXT.md` — 17 decisions and canonical refs
- `.planning/REQUIREMENTS.md` — CRED-04 through CRED-07 definitions
- `.planning/PROJECT.md` — Key Decisions table for credential_store.py constraints

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified as installed; no new dependencies
- Architecture: HIGH — all code paths read directly from source
- Pitfalls: HIGH — discovered by reading actual test files that will break
- Line numbers: MEDIUM — accurate at research time; planner should use grep to confirm before editing

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (stable codebase; no fast-moving dependencies)
