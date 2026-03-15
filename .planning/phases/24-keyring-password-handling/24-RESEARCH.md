# Phase 24: keyring-password-handling - Research

**Researched:** 2026-03-15
**Domain:** SSH credential resolution, MCP tool schema design, Python keyring integration
**Confidence:** HIGH

## Summary

Phase 24 fixes two tools — `setup_mcp_admin` and `update_mcp_admin_groups` — that require a plaintext password as a mandatory argument when they could instead resolve credentials from the keyring the same way `ssh_discover_system` and `ssh_execute_command` already do. The audit also covers all other tools with password fields to classify each one as a legitimate anti-pattern or an acceptable optional parameter.

The core fix is mechanical: both functions must call `resolve_ssh_credentials()` (which already handles keyring, DB, and explicit override tiers) instead of wiring a bare `password` straight into `ssh_connect`. The tool schemas must change `"required"` lists to remove `"password"` from `setup_mcp_admin` and `update_mcp_admin_groups`.

**Primary recommendation:** Refactor `setup_remote_mcp_admin` and `update_mcp_admin_groups` to call `resolve_ssh_credentials()` before `ssh_connect`. Remove `password` from both schemas' `required` arrays. Leave all other password fields as optional documentation hints.

---

## Problem Analysis

### The Two Broken Tools

#### `setup_mcp_admin`

**Location:** `src/homelab_mcp/ssh_tools.py`, function `setup_remote_mcp_admin` (line 178)

```python
async def setup_remote_mcp_admin(
    hostname: str,
    username: str,
    password: str,          # <-- non-optional, no keyring fallback
    force_update_key: bool = True,
    port: int = 22,
) -> str:
    ...
    async with await ssh_connect(
        hostname=hostname,
        username=username,
        port=port,
        password=password,  # <-- direct pass-through, skips resolve_ssh_credentials
    ) as conn:
```

Schema (line 61 of `ssh_tools_schema.py`):
```python
"required": ["hostname", "username", "password"],
```

Agent must supply the password explicitly. There is no keyring fallback path.

#### `update_mcp_admin_groups`

**Location:** `src/homelab_mcp/ssh_tools.py`, function `update_mcp_admin_groups` (line 692)

```python
async def update_mcp_admin_groups(hostname: str, username: str, password: str, port: int = 22) -> str:
    ...
    async with await ssh_connect(
        hostname=hostname,
        username=username,
        port=port,
        password=password,  # <-- same problem
    ) as conn:
```

Schema (line 167 of `ssh_tools_schema.py`):
```python
"required": ["hostname", "username", "password"],
```

### The Existing Pattern (Already Correct)

`ssh_discover_system` and `ssh_execute_command` both use the correct pattern:

```python
async def ssh_discover_system(
    hostname: str,
    username: str | None = None,
    password: str | None = None,   # optional
    key_path: str | None = None,
    port: int = 22,
) -> str:
    creds = resolve_ssh_credentials(
        hostname=hostname,
        username=username,
        password=password,
        key_path=key_path,
        port=port,
    )
    # connect with creds.password / creds.key_path
```

`resolve_ssh_credentials` already handles:
1. Explicit `password` or `key_path` — used directly (backward compat)
2. Keyring lookup via `list_credentials` + `get_credential`
3. DB-stored credentials
4. Default mcp_admin key fallback
5. Raises `CredentialNotFoundError` with clear recovery message if all tiers miss

### Full Audit of Password Fields in Tools

| Tool | Schema file | Password field | Mandatory? | Verdict |
|------|-------------|----------------|------------|---------|
| `setup_mcp_admin` | `ssh_tools_schema.py` | SSH auth password | YES - in `required` | **Fix: use `resolve_ssh_credentials`** |
| `update_mcp_admin_groups` | `ssh_tools_schema.py` | SSH auth password | YES - in `required` | **Fix: use `resolve_ssh_credentials`** |
| `ssh_discover` | `ssh_tools_schema.py` | SSH auth password | NO - optional | OK - already uses `resolve_ssh_credentials` |
| `ssh_execute_command` | `ssh_tools_schema.py` | SSH auth password | NO - optional | OK - already uses `resolve_ssh_credentials` |
| `start_interactive_shell` | `ssh_tools_schema.py` | SSH auth password | NO - optional | OK - passed to `create_session`, acceptable |
| `discover_and_map` | `network_tools_schema.py` | SSH auth password | NO - optional | OK - `discover_and_store` calls `ssh_discover_system` which calls `resolve_ssh_credentials` |
| `bulk_discover_and_map` | `network_tools_schema.py` | SSH auth password | NO - optional | OK - same flow |
| `check_service_requirements` | `service_tools_schema.py` | SSH auth password | NO - optional | OK - calls `ssh_execute_command` which calls `resolve_ssh_credentials` |
| `install_service` | `service_tools_schema.py` | SSH auth password | NO - optional | OK - calls `ssh_execute_command` chain |
| `get_service_status` / other service tools | `service_tools_schema.py` | SSH auth password | NO - optional | OK - same chain |
| `create_proxmox_lxc` | `proxmox_tools_schema.py` | LXC root password | NO - optional | DIFFERENT PURPOSE - container root pw, not SSH auth. Leave as-is. |
| Proxmox API tools | `proxmox_api.py` | Proxmox API auth | NO - env var | OK - already reads `PROXMOX_PASSWORD` env var and keyring |

**Conclusion:** Only two tools require code changes. All other password fields are either already optional, route through `resolve_ssh_credentials`, or serve a different purpose (Proxmox API token, LXC root password).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `keyring` | Already installed | OS keyring access | Already in use via `credential_store.py` |
| `asyncssh` | Already installed | SSH connections | Already in use |

No new dependencies needed. This phase uses only existing project infrastructure.

### Existing Infrastructure to Reuse

| Function | Module | Purpose |
|----------|--------|---------|
| `resolve_ssh_credentials()` | `ssh_tools.py` | Multi-tier credential resolution with keyring |
| `get_credential()` | `credential_store.py` | Keyring read (safe, never raises) |
| `list_credentials()` | `credential_store.py` | Registry lookup |
| `CredentialNotFoundError` | `ssh_tools.py` | Error type for missing creds |
| `ssh_connection_wrapper` | `error_handling.py` | Already wraps both target functions |

---

## Architecture Patterns

### Pattern 1: Credential Resolution Before Connection

This is the established pattern in `ssh_discover_system` and `ssh_execute_command`. The fix for both broken tools mirrors this exactly.

**Before (broken):**
```python
async def setup_remote_mcp_admin(
    hostname: str,
    username: str,
    password: str,          # required, no fallback
    force_update_key: bool = True,
    port: int = 22,
) -> str:
    key_path = await ensure_mcp_ssh_key()
    ...
    async with await ssh_connect(
        hostname=hostname,
        username=username,
        port=port,
        password=password,
    ) as conn:
```

**After (fixed):**
```python
async def setup_remote_mcp_admin(
    hostname: str,
    username: str | None = None,    # optional now
    password: str | None = None,    # optional now
    force_update_key: bool = True,
    port: int = 22,
) -> str:
    key_path = await ensure_mcp_ssh_key()
    creds = resolve_ssh_credentials(
        hostname=hostname,
        username=username,
        password=password,
        port=port,
    )
    ...
    async with await ssh_connect(
        hostname=creds.hostname,
        username=creds.username,
        port=creds.port,
        password=creds.password,
        key_path=creds.key_path,    # allow key-based auth too
    ) as conn:
```

**Schema change (`ssh_tools_schema.py`):**
```python
# setup_mcp_admin
"required": ["hostname"],  # was ["hostname", "username", "password"]

# Description update — add keyring guidance matching ssh_discover pattern
"description": "SSH into a remote system and setup mcp_admin user with admin permissions and SSH key access. If credentials were stored with `credentials add`, username and password are auto-injected from the keyring — omit them.",
```

### Pattern 2: `update_mcp_admin_groups` — Same Fix

```python
async def update_mcp_admin_groups(
    hostname: str,
    username: str | None = None,    # optional
    password: str | None = None,    # optional
    port: int = 22,
) -> str:
    creds = resolve_ssh_credentials(
        hostname=hostname,
        username=username,
        password=password,
        port=port,
    )
    async with await ssh_connect(
        hostname=creds.hostname,
        username=creds.username,
        port=creds.port,
        password=creds.password,
        key_path=creds.key_path,
    ) as conn:
```

Schema change mirrors `setup_mcp_admin`.

### Anti-Patterns to Avoid

- **Duplicating resolve logic inside the function:** Do not re-implement keyring lookup directly in `setup_remote_mcp_admin`. Call `resolve_ssh_credentials()` exactly as the other functions do.
- **Keeping `username` required:** Both functions must also make `username` optional — if keyring resolves it from a stored entry, the caller should not need to supply it.
- **Breaking the `key_path` path:** When `resolve_ssh_credentials` returns a key-based credential, the fix must pass `key_path=creds.key_path` into `ssh_connect`. The original code never accepted a key — this is a new capability unlocked for free.
- **Changing `service_installer.py` password args:** Service installer passes `password` as `None` by default to `ssh_execute_command`, which already routes through `resolve_ssh_credentials`. No changes needed there.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Credential resolution | Custom keyring lookup inside each function | `resolve_ssh_credentials()` | Already has 3-tier fallback, desync warning, error message guidance |
| Error on missing creds | Custom ValueError with ad-hoc message | `CredentialNotFoundError` from `resolve_ssh_credentials` | Consistent error type, already tested, already handled by `ssh_connection_wrapper` |
| Schema guidance text | New wording | Copy verbatim from `ssh_discover` description | Consistency across tool descriptions, established phrasing |

---

## Common Pitfalls

### Pitfall 1: Forgetting `key_path` in `ssh_connect` call

**What goes wrong:** Fix adds `resolve_ssh_credentials` but still passes only `password=creds.password` to `ssh_connect`. If keyring stored a key-based credential, the connection fails silently (falls through to wrong error).

**How to avoid:** Always pass both `password=creds.password` and `key_path=creds.key_path` to `ssh_connect`. Look at `ssh_discover_system` lines 429-435 as the reference.

### Pitfall 2: Missing test updates

**What goes wrong:** Existing tests call `setup_remote_mcp_admin("test-host", "admin", "password")` positionally. After making `username` and `password` optional (with default `None`), positional calls still work — but tests that patch `ssh_connect` without mocking `resolve_ssh_credentials` will fail because `resolve_ssh_credentials` will try to hit the DB/keyring.

**How to avoid:** Each test for the fixed functions must either:
- Mock `resolve_ssh_credentials` directly, OR
- Mock `list_credentials` + `get_credential` + `get_database_adapter` (all three resolve tiers)

The simpler approach: patch `resolve_ssh_credentials` to return a pre-built `SSHCredentials` object.

**Warning signs:** Tests error with `sqlite3.OperationalError` or `keyring.errors.NoKeyringError` — means resolve tiers are running for real.

### Pitfall 3: Schema `required` change breaks calling agents silently

**What goes wrong:** Agent prompts built during Phase 23 (`connect_to_device`) reference `setup_mcp_admin` and mention the credential flow. If the schema changes but the prompt text does not update, agents see conflicting guidance.

**How to avoid:** After updating schemas, grep for `setup_mcp_admin` in `prompt_registry.py`. The existing Phase 23 prompt text says "Call setup_mcp_admin with host=..." — it does not mention password, so no update is needed. But verify this after the change.

### Pitfall 4: Treating `create_proxmox_lxc` password as in-scope

**What goes wrong:** The Proxmox LXC tool has a `password` field for the container root password. This is not an SSH auth credential — it sets the LXC container root account. Removing or making it optional would break LXC creation.

**How to avoid:** Leave `create_proxmox_lxc` password field entirely unchanged.

---

## Code Examples

### Correct `resolve_ssh_credentials` call pattern (from `ssh_discover_system`)

```python
# Source: src/homelab_mcp/ssh_tools.py line 413-435
creds = resolve_ssh_credentials(
    hostname=hostname,
    username=username,
    password=password,
    key_path=key_path,
    port=port,
)

if not creds.key_path and not creds.password:
    raise ValueError(
        f"No credentials found for {hostname}. "
        "Store them with `credentials add` or pass password/key_path explicitly."
    )

async with await ssh_connect(
    hostname=creds.hostname,
    username=creds.username,
    port=creds.port,
    password=creds.password,
    key_path=creds.key_path,
) as conn:
```

Note: `setup_remote_mcp_admin` does not need the `if not creds.key_path and not creds.password` guard — `resolve_ssh_credentials` already raises `CredentialNotFoundError` for the total-miss case. The guard is only needed when additional logic follows before connection. Keep it simple: just let `CredentialNotFoundError` propagate; `ssh_connection_wrapper` catches it.

### Test pattern for fixed functions

```python
@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.resolve_ssh_credentials")
@patch("src.homelab_mcp.ssh_tools.ensure_mcp_ssh_key")
@patch("src.homelab_mcp.ssh_tools.Path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_setup_remote_mcp_admin_uses_keyring(
    mock_connect, mock_path, mock_ensure_key, mock_resolve
):
    from src.homelab_mcp.ssh_tools import SSHCredentials
    mock_resolve.return_value = SSHCredentials(
        hostname="test-host",
        username="admin",
        port=22,
        password="resolved-from-keyring",
    )
    mock_ensure_key.return_value = "/home/user/.ssh/mcp/mcp_admin_key"
    # ... rest of test
    result = await setup_remote_mcp_admin("test-host")  # no password needed
    mock_resolve.assert_called_once_with(
        hostname="test-host",
        username=None,
        password=None,
        port=22,
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All tools required explicit password | `ssh_discover` + `ssh_execute_command` auto-inject from keyring | Phase 22 | Agents no longer need to supply creds for common tools |
| `setup_mcp_admin` requires password | (this phase) auto-inject from keyring | Phase 24 | Agents can bootstrap new hosts without re-typing credentials |

---

## Open Questions

1. **Should `update_mcp_admin_groups` also accept a `key_path` schema parameter?**
   - What we know: The function currently lacks a `key_path` parameter entirely
   - What's unclear: Whether any callers would need key-based auth to invoke this tool
   - Recommendation: Add `key_path` as an optional schema property for consistency with other SSH tools. `resolve_ssh_credentials` will use it if supplied.

2. **Should `discover_and_map` schema also drop `username` from `required`?**
   - What we know: Schema has `"required": ["hostname", "username"]`. The underlying `ssh_discover_system` can resolve username from keyring.
   - What's unclear: Whether removing `username` from required breaks any documented callers
   - Recommendation: This is OUTSIDE Phase 24 scope. Note as a follow-up. Phase 24 focuses only on tools where password is required.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (asyncio_mode = "auto") |
| Quick run command | `uv run pytest tests/test_ssh_tools.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| ID | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|-------------|
| SETUP-01 | `setup_mcp_admin` resolves creds from keyring when no password arg | unit | `uv run pytest tests/test_ssh_tools.py::test_setup_remote_mcp_admin_uses_keyring -x` | Wave 0 |
| SETUP-02 | `setup_mcp_admin` accepts explicit password (backward compat) | unit | `uv run pytest tests/test_ssh_tools.py::test_setup_remote_mcp_admin_explicit_password -x` | Existing (adapt) |
| SETUP-03 | `setup_mcp_admin` schema no longer has password in `required` | unit | `uv run pytest tests/test_tools.py -k setup_mcp_admin -x` | Wave 0 |
| GROUPS-01 | `update_mcp_admin_groups` resolves creds from keyring | unit | `uv run pytest tests/test_ssh_tools.py::test_update_mcp_admin_groups_uses_keyring -x` | Wave 0 |
| GROUPS-02 | `update_mcp_admin_groups` schema no longer has password in `required` | unit | `uv run pytest tests/test_tools.py -k update_mcp_admin_groups -x` | Wave 0 |
| AUDIT-01 | No other tool schema has password in `required` | unit | `uv run pytest tests/test_tools.py::test_no_tool_has_password_required -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_ssh_tools.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ssh_tools.py::test_setup_remote_mcp_admin_uses_keyring` — covers SETUP-01
- [ ] `tests/test_ssh_tools.py::test_update_mcp_admin_groups_uses_keyring` — covers GROUPS-01
- [ ] `tests/test_tools.py::test_setup_mcp_admin_schema_password_not_required` — covers SETUP-03
- [ ] `tests/test_tools.py::test_update_mcp_admin_groups_schema_password_not_required` — covers GROUPS-02
- [ ] `tests/test_tools.py::test_no_tool_has_password_required` — covers AUDIT-01 (regression guard)

---

## Sources

### Primary (HIGH confidence)

- Source code audit: `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials`, `setup_remote_mcp_admin`, `update_mcp_admin_groups`, `ssh_discover_system`, `ssh_execute_command`
- Source code audit: `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — all 6 SSH tool schemas
- Source code audit: `src/homelab_mcp/credential_store.py` — `get_credential`, `list_credentials` API
- Source code audit: `src/homelab_mcp/tool_schemas/network_tools_schema.py` — password fields audited
- Source code audit: `src/homelab_mcp/tool_schemas/service_tools_schema.py` — password fields audited
- Source code audit: `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` — LXC password field (different purpose, out of scope)
- Source code audit: `src/homelab_mcp/proxmox_api.py` — already uses env var + keyring fallback
- Source code audit: `src/homelab_mcp/service_installer.py` — passes `password=None` to `ssh_execute_command` which routes through `resolve_ssh_credentials`
- Test baseline: `uv run pytest tests/test_ssh_tools.py` — 18 tests pass before changes

### Secondary (MEDIUM confidence)

- Project STATE.md: Phase 24 rationale — "fix setup_mcp_admin and audit all tools for passed-password anti-pattern"

---

## Metadata

**Confidence breakdown:**
- Problem identification: HIGH — direct code audit of all affected files
- Fix approach: HIGH — the pattern is already established in two functions in the same file
- Test strategy: HIGH — existing test patterns show exactly how to mock `resolve_ssh_credentials`
- Scope boundary (LXC password, Proxmox API): HIGH — different concerns confirmed by code inspection

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable internal APIs, no external dependencies)
