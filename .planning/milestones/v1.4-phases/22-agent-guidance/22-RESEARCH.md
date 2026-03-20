# Phase 22: Agent Guidance - Research

**Researched:** 2026-03-15
**Domain:** MCP tool schema design, SSH credential error messaging, Python keyring introspection
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CRED-01 | `resolve_ssh_credentials` raises actionable error naming `credentials add` and `register_server` when all tiers miss | Change the fallthrough `return SSHCredentials(...)` at the end of `resolve_ssh_credentials` to `raise CredentialNotFoundError(...)` with an exact message; update `ssh_connection_wrapper` to surface that message verbatim |
| CRED-02 | Agent can inspect keyring credential state via `list_keyring_credentials` MCP tool | Add new tool `list_keyring_credentials` that calls the existing `list_credentials()` from `credential_store.py` — no new Python functions needed, just schema + handler wiring |
| CRED-03 | `ssh_discover` and `ssh_execute_command` schema descriptions include credential recovery guidance | In-place string edit to `ssh_tools_schema.py` — 2 description fields, no logic change |
| SHELL-04 | `start_interactive_shell` returns actionable error in stdio mode instead of dead URL | Guard in `handle_start_interactive_shell`: detect stdio mode via `MCP_HTTP_PORT` env var absence (or `args.http` flag context), raise or return early with message naming the `--http` flag |
| SHELL-05 | `start_interactive_shell` schema description states browser-only requirement | In-place string edit to `ssh_tools_schema.py` — 1 description field, no logic change |
</phase_requirements>

---

## Summary

Phase 22 delivers five targeted changes that improve agent self-service: two are pure text edits to tool schema descriptions (CRED-03, SHELL-05), one adds a new zero-logic MCP tool (CRED-02), one changes error handling in `resolve_ssh_credentials` to raise instead of silently returning incomplete credentials (CRED-01), and one adds a stdio-mode guard to `handle_start_interactive_shell` (SHELL-04).

None of these requirements touch core SSH connection logic, asyncssh, or the database layer beyond a read-only call to `list_credentials()`. All five changes are self-contained and testable without live SSH infrastructure.

**Primary recommendation:** Implement as two plans — Plan 1: CRED-01 + CRED-02 (credential error + new tool), Plan 2: CRED-03 + SHELL-04 + SHELL-05 (description edits + stdio guard).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | current (project) | Unit tests | Already used throughout project |
| pytest-asyncio | current (project) | Async test support | All SSH handlers are async |
| unittest.mock (patch) | stdlib | Isolate env vars and credential_store | Same pattern used in test_shell_session.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `os.getenv` | stdlib | Detect `MCP_HTTP_PORT` for stdio guard | In `handle_start_interactive_shell` |
| `credential_store.list_credentials()` | local | Return keyring registry entries | In new `list_keyring_credentials` handler |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `os.getenv("MCP_HTTP_PORT")` stdio check | Server-level flag passed at init | env var check is stateless and already referenced in `config.py` and `ssh_handlers.py` — consistent with existing pattern |
| Raising `CredentialNotFoundError` | Returning incomplete `SSHCredentials` and letting connection fail | Raising surfaces the message before any TCP attempt; returning silently is the current behavior that causes dead-end failures |

---

## Architecture Patterns

### Recommended Project Structure

No new files required. All changes land in existing files:

```
src/homelab_mcp/
├── ssh_tools.py                         # CRED-01: raise instead of return at fallthrough
├── tool_schemas/
│   ├── ssh_tools_schema.py              # CRED-03, SHELL-04 desc, SHELL-05 desc
│   └── credential_tools_schema.py       # CRED-02: new list_keyring_credentials schema
├── tool_handlers/
│   ├── credential_handlers.py           # CRED-02: new handle_list_keyring_credentials
│   └── ssh_handlers.py                  # SHELL-04: stdio guard
└── tool_handlers/__init__.py            # CRED-02: register list_keyring_credentials

tests/
├── test_ssh_credentials.py              # CRED-01 RED test
├── test_tools.py                        # CRED-02 tool count update (56 → 57)
└── test_shell_session.py / test_ssh_handlers.py  # SHELL-04 RED test
```

### Pattern 1: Raise on Credential Miss (CRED-01)

**What:** Replace the final fallthrough `return SSHCredentials(...)` at line 127 of `ssh_tools.py` with a `raise` that names the exact CLI command and MCP tool.

**When to use:** Only when all three tiers (explicit, keyring, DB/mcp_admin key) have all missed.

**Critical constraint from STATE.md:** Before implementation, run `git grep "resolve_ssh_credentials\|get_credential_by_hostname\|mcp_admin" tests/` to audit tests relying on the current fallthrough behavior — those tests must be updated to expect the raise.

**Example:**
```python
# In ssh_tools.py — final else branch (currently line ~127)
raise CredentialNotFoundError(
    f"No credentials found for {hostname}. "
    "To fix: run `homelab-mcp credentials add <hostname> <username>` "
    "or call the `register_server` MCP tool."
)
```

The exception class can be a simple subclass of `RuntimeError` defined in `ssh_tools.py` or `error_handling.py` — no new module needed.

### Pattern 2: New MCP Tool (CRED-02)

**What:** Wire `list_credentials()` from `credential_store.py` into a new `list_keyring_credentials` MCP tool. No new Python logic — just schema definition, handler function, and registry entry.

**The tool returns:** The JSON registry from `~/.homelab_mcp/credential_registry.json`, filtered to `credential_type="ssh"` by default (callers can pass `credential_type` to see proxmox entries).

**Example schema shape:**
```python
"list_keyring_credentials": {
    "description": (
        "List hosts that have credentials stored in the OS keyring registry. "
        "Call this before ssh_discover or ssh_execute_command to check whether "
        "a host has stored credentials. Returns hostname and username per entry."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "credential_type": {
                "type": "string",
                "description": "Credential type to list: 'ssh' (default) or 'proxmox'",
                "default": "ssh",
            }
        },
        "required": [],
    },
}
```

**Handler:**
```python
async def handle_list_keyring_credentials(arguments: dict[str, Any]) -> dict[str, Any]:
    from ..credential_store import list_credentials
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

### Pattern 3: stdio Guard (SHELL-04)

**What:** In `handle_start_interactive_shell`, check whether the server is running in stdio mode before creating a session. In stdio mode, no HTTP endpoint exists, so the URL returned is unreachable.

**Detection:** `MCP_HTTP_PORT` env var absence or value is the server-level signal. The handler already reads `os.getenv("MCP_HTTP_PORT", "8080")`. The guard should check whether the server was started with `--http` by checking `MCP_HTTP_ENABLED`:

```python
# In handle_start_interactive_shell, before session creation:
if os.getenv("MCP_HTTP_ENABLED", "false").lower() != "true":
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "status": "error",
                "error": (
                    "start_interactive_shell requires the HTTP server mode. "
                    "Restart with: uvx homelab-mcp --http --port 8080 "
                    "then open http://localhost:8080/shell/<session_id> in your browser."
                ),
                "error_type": "stdio_mode_unsupported",
            }, indent=2)
        }]
    }
```

`MCP_HTTP_ENABLED` is already the env var used by the `--http` arg default in `server.py` (line 604): `default=os.getenv("MCP_HTTP_ENABLED", "false").lower() == "true"`. This is the correct signal — no new env vars needed.

### Pattern 4: Schema Description Edits (CRED-03, SHELL-05)

**What:** String-only edits in `ssh_tools_schema.py`. No Python logic changes.

**CRED-03 — ssh_discover description (add credential recovery guidance):**
```
"SSH into a system and gather hardware/system information. "
"If authentication fails with 'No credentials found', run "
"`homelab-mcp credentials add <hostname> <username>` in the terminal "
"or call `list_keyring_credentials` to see what is already stored."
```

**CRED-03 — ssh_execute_command description (same pattern):**
Same recovery guidance sentence appended to current description.

**SHELL-05 — start_interactive_shell description:**
Add: `"Requires HTTP server mode (--http flag). In stdio mode, this tool returns an error with instructions."`

### Anti-Patterns to Avoid

- **Don't raise inside `ssh_connection_wrapper`:** The wrapper converts exceptions to JSON error strings — a `CredentialNotFoundError` raised _before_ any connection attempt will be caught there and have its message preserved in `error["error"]`. This is correct. Do not bypass the wrapper by catching the exception in the wrapper's guard.
- **Don't check `MCP_HTTP_PORT` value for stdio detection:** The port is always set (defaulting to `"8080"`), so checking whether the var exists doesn't distinguish stdio from HTTP. Check `MCP_HTTP_ENABLED` instead.
- **Don't import `list_credentials` at module level in handlers:** Follow existing credential_store pattern — import inside the function body is fine; for handlers, a top-level import is also fine since credential_store uses lazy internal imports already.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keyring inspection | Custom keyring reader | `credential_store.list_credentials()` | Already exists, headless-safe, reads the JSON registry |
| Custom exception class | Elaborate exception hierarchy | Simple `class CredentialNotFoundError(RuntimeError): pass` or inline `RuntimeError` | Only needs `str()` readable; `ssh_connection_wrapper` catches all exceptions |
| stdio/HTTP mode detection | New env var or config flag | `MCP_HTTP_ENABLED` env var | Already used in `server.py` for `--http` argument default |

---

## Common Pitfalls

### Pitfall 1: Fallthrough tests relying on mcp_admin SSHCredentials return

**What goes wrong:** `test_ssh_credentials.py::TestResolveSSHCredentials::test_mcp_admin_uses_default_key` and similar tests set up a mock where `get_credential_by_hostname` returns `None` and expect `SSHCredentials` back — they will fail once the fallthrough raises.

**Why it happens:** The current fallthrough returns `SSHCredentials(hostname, username, port)` (incomplete, no key/password). Tests assert on the `SSHCredentials` shape.

**How to avoid:** In Wave 0 (RED phase), write the test that expects the raise. Then update existing tests that mock the mcp_admin key as present — those should still pass because the mcp_admin key path is checked _before_ the raise (line 116-124 in current code). Only the truly empty case (no key, no password, no stored cred) should reach the raise.

**Warning signs:** Existing test `test_mcp_admin_uses_default_key` passes `mock_path.exists.return_value = True` — that test should still pass. The test to audit is any test where `mock_path.exists.return_value = False` and no stored credentials exist.

### Pitfall 2: Tool count in test_tools.py

**What goes wrong:** `test_get_available_tools` asserts `len(tools) == 56`. Adding `list_keyring_credentials` changes the count to 57.

**Why it happens:** Hard-coded count assertion.

**How to avoid:** Update the assertion in the same commit as the schema registration. The RED test for CRED-02 should assert the tool exists in the registry; the count assertion update is a secondary fix.

### Pitfall 3: Keyring unavailable on headless CI

**What goes wrong:** `list_credentials()` reads a JSON file — it does not call the OS keyring directly. The JSON registry at `~/.homelab_mcp/credential_registry.json` may not exist in CI. The function returns `[]` safely (no exception). Tests should mock `list_credentials` or create a temp registry file.

**Why it happens:** CI environments don't have the homelab registry file.

**How to avoid:** Unit tests for `list_keyring_credentials` tool should patch `credential_store.list_credentials` rather than hitting the real file.

### Pitfall 4: `MCP_HTTP_ENABLED` not set in test environment

**What goes wrong:** Tests for SHELL-04 run without `MCP_HTTP_ENABLED=true` set, so they will always hit the stdio guard. This is correct for testing the error path. Tests for the success path must explicitly `patch.dict(os.environ, {"MCP_HTTP_ENABLED": "true"})`.

**Why it happens:** Default is `"false"` in all environments.

**How to avoid:** Use `patch.dict(os.environ, {"MCP_HTTP_ENABLED": "true"})` in the success path test; omit it in the error path test.

---

## Code Examples

Verified patterns from project source:

### Raising in resolve_ssh_credentials (CRED-01)
```python
# Source: src/homelab_mcp/ssh_tools.py lines 114-131 (current fallthrough)
# Current (to be replaced):
resolved_username = username or "mcp_admin"
if resolved_username == "mcp_admin":
    mcp_key = get_mcp_ssh_key_path()
    if mcp_key.exists():
        return SSHCredentials(
            hostname=hostname,
            username=resolved_username,
            port=port,
            key_path=str(mcp_key),
        )
# Return minimal credentials - will need password or explicit key
return SSHCredentials(hostname=hostname, username=resolved_username, port=port)

# Replacement (keep mcp_admin key check, raise at the very end):
resolved_username = username or "mcp_admin"
if resolved_username == "mcp_admin":
    mcp_key = get_mcp_ssh_key_path()
    if mcp_key.exists():
        return SSHCredentials(
            hostname=hostname,
            username=resolved_username,
            port=port,
            key_path=str(mcp_key),
        )
raise CredentialNotFoundError(
    f"No credentials found for {hostname}. "
    "Run `homelab-mcp credentials add <hostname> <username>` in your terminal, "
    "or call the `register_server` MCP tool to store credentials."
)
```

### stdio mode guard (SHELL-04)
```python
# Source: src/homelab_mcp/tool_handlers/ssh_handlers.py (current handle_start_interactive_shell)
# Current: reads MCP_HTTP_PORT but does not guard on HTTP mode
mcp_port = os.getenv("MCP_HTTP_PORT", "8080")

# Add before session creation:
if os.getenv("MCP_HTTP_ENABLED", "false").lower() != "true":
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "status": "error",
                "error": (
                    "start_interactive_shell only works in HTTP server mode. "
                    "Restart the server with: uvx homelab-mcp --http --port 8080\n"
                    "Then open the returned shell URL in your browser."
                ),
                "error_type": "stdio_mode_unsupported",
            }, indent=2)
        }]
    }
```

### list_keyring_credentials handler (CRED-02)
```python
# Pattern: follows handle_list_registered_servers in credential_handlers.py
import json
from typing import Any
from ..credential_store import list_credentials

async def handle_list_keyring_credentials(arguments: dict[str, Any]) -> dict[str, Any]:
    credential_type = arguments.get("credential_type", "ssh")
    entries = list_credentials(credential_type=credential_type)
    result = {
        "status": "success",
        "credential_type": credential_type,
        "count": len(entries),
        "credentials": [
            {"hostname": e["hostname"], "username": e["username"]}
            for e in entries
        ],
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `resolve_ssh_credentials` returns incomplete `SSHCredentials` on miss | Raise `CredentialNotFoundError` with CLI command names | Agent sees exact fix command instead of opaque SSH auth failure |
| `start_interactive_shell` returns unreachable URL in stdio mode | Guard returns actionable error naming `--http` flag | Agent does not falsely report success |
| No tool to inspect keyring registry | `list_keyring_credentials` tool reads registry JSON | Agent can proactively check credential state |

---

## Open Questions

1. **Should `CredentialNotFoundError` be defined in `error_handling.py` or `ssh_tools.py`?**
   - What we know: `ssh_tools.py` is imported by `shell_session.py` and handlers; `error_handling.py` is imported more broadly.
   - What's unclear: Whether future phases will catch this exception class by type anywhere.
   - Recommendation: Define in `ssh_tools.py` as a simple `class CredentialNotFoundError(RuntimeError): pass` — keeps it local to the credential resolution flow. Import into `error_handling.py` if needed later.

2. **Does `ssh_connection_wrapper` catch `CredentialNotFoundError` and preserve the message?**
   - What we know: The wrapper's final `except Exception as e:` block at line 283 catches all exceptions and calls `sanitize_error(e)` to build the error string.
   - What's unclear: Whether `sanitize_error` truncates or rewrites the message in a way that loses the CLI command hint.
   - Recommendation: Check `sanitize_error` implementation before finalizing. If it scrubs the message, the CRED-01 error should be surfaced at the handler level (i.e., catch `CredentialNotFoundError` specifically in `handle_ssh_discover` and return it directly) rather than relying on the wrapper.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (project root) |
| Quick run command | `uv run pytest tests/test_ssh_credentials.py tests/test_tools.py tests/test_shell_session.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRED-01 | `resolve_ssh_credentials` raises `CredentialNotFoundError` with CLI command text when all tiers miss | unit | `uv run pytest tests/test_ssh_credentials.py::TestResolveSSHCredentials -x` | ✅ (file exists, new test case needed) |
| CRED-02 | `list_keyring_credentials` tool exists in registry and returns credential list | unit | `uv run pytest tests/test_tools.py -x -k "keyring"` | ✅ (file exists, new test case needed) |
| CRED-02 | `handle_list_keyring_credentials` calls `list_credentials` and formats result | unit | `uv run pytest tests/test_tools.py -x -k "keyring"` | ✅ (file exists, new test case needed) |
| CRED-03 | `ssh_discover` description contains `list_keyring_credentials` or `credentials add` | unit | `uv run pytest tests/test_tools.py -x -k "schema"` | ✅ (new test case) |
| SHELL-04 | `start_interactive_shell` returns `stdio_mode_unsupported` when `MCP_HTTP_ENABLED` is unset | unit | `uv run pytest tests/test_shell_session.py -x -k "stdio"` | ✅ (file exists, new test case needed) |
| SHELL-05 | `start_interactive_shell` description contains `browser` or `--http` | unit | `uv run pytest tests/test_tools.py -x -k "schema"` | ✅ (new test case) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_ssh_credentials.py tests/test_tools.py tests/test_shell_session.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ssh_credentials.py::TestResolveSSHCredentials::test_no_credentials_raises_actionable_error` — covers CRED-01
- [ ] `tests/test_tools.py::test_list_keyring_credentials_tool_registered` — covers CRED-02 tool count (update count 56→57) and tool existence
- [ ] `tests/test_shell_session.py::TestStartInteractiveShellStdioMode` or similar in `tests/test_tools.py` — covers SHELL-04

*(Existing test infrastructure covers the framework; only new test cases are needed)*

---

## Sources

### Primary (HIGH confidence)
- Direct source read: `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials` fallthrough at lines 114-131
- Direct source read: `src/homelab_mcp/tool_handlers/ssh_handlers.py` — `handle_start_interactive_shell` and `MCP_HTTP_ENABLED` detection at lines 42-79
- Direct source read: `src/homelab_mcp/credential_store.py` — `list_credentials()` function confirmed at line 138
- Direct source read: `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — current `ssh_discover`, `ssh_execute_command`, `start_interactive_shell` descriptions
- Direct source read: `src/homelab_mcp/tool_schemas/credential_tools_schema.py` — existing credential tool shapes
- Direct source read: `src/homelab_mcp/error_handling.py` — `ssh_connection_wrapper` exception handling at lines 283-309
- Direct source read: `src/homelab_mcp/server.py` lines 543-604 — `MCP_HTTP_ENABLED` env var usage and `--http` flag default
- Direct source read: `.planning/STATE.md` — constraint: audit `resolve_ssh_credentials` tests before changing fallthrough behavior
- Direct source read: `tests/test_ssh_credentials.py` — existing test coverage for `resolve_ssh_credentials`
- Direct source read: `tests/test_tools.py` — tool count assertion at line 17 (`len(tools) == 56`)
- Direct source read: `tests/test_shell_session.py` — existing session test pattern using `patch` + `MagicMock`

### Secondary (MEDIUM confidence)
- None required — all research is against local source files.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are already used in the project; no new dependencies
- Architecture: HIGH — all patterns trace directly to existing code in the same files being modified
- Pitfalls: HIGH — derived from reading actual test assertions and source code, not assumptions

**Research date:** 2026-03-15
**Valid until:** Stable (no external dependencies; valid until source changes)
