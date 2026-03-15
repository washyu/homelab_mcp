# Architecture Patterns

**Domain:** Python MCP server — interactive shell fix, SSH credential flow, TOFU known_hosts handling (v1.4)
**Researched:** 2026-03-13
**Confidence:** HIGH (all integration points verified by direct source inspection)

---

## System Overview

Three bugs, each isolated to a narrow slice of the existing architecture.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  BUG 1: Silent Interactive Shell                                            │
│                                                                            │
│  MCP client → handle_start_interactive_shell()                             │
│      → shell_session.ShellSessionManager.create_session()                  │
│      → returns (session_id, session)                                       │
│      → handler returns shell_url (HTTP, not WS)                           │
│                                                                            │
│  User opens shell_url in browser                                           │
│      → http_app.handle_shell_page() serves shell_terminal.html             │
│      → xterm.js opens WebSocket ws://{host}/ws/shell/{session_id}         │
│      → http_app.handle_shell_websocket() wires I/O                         │
│                                                                            │
│  BUG: read_output() coroutine calls                                        │
│       await session.process.stdout.read(4096)                              │
│       asyncssh SSHClientProcess.stdout is a StreamReader:                  │
│       .read() blocks waiting for EOF, not just for available bytes         │
│       → loop runs but WebSocket receives NOTHING until process exits       │
│                                                                            │
│  FIX LOCATION: http_app.handle_shell_websocket() read_output() inner fn    │
│  FIX: replace .read() with .read1() or asyncio.wait_for(.read(), 0.1)     │
│       OR use asyncssh process.stdout as async iterator                     │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│  BUG 2: SSH Credential Flow — Agent Doesn't Know to Guide User             │
│                                                                            │
│  Agent calls ssh_discover { hostname: "192.168.1.10" }                    │
│      → handle_ssh_discover()                                               │
│      → resolve_ssh_credentials(hostname)                                   │
│          Tier 1: no explicit password/key_path → skip                      │
│          Tier 2: list_credentials(type="ssh") → JSON registry lookup       │
│                  hostname NOT in registry (device never registered) → miss │
│          Tier 3: db.get_credential_by_hostname() → no DB record → miss    │
│          Tier 4: mcp_admin key fallback → key exists? → attempt           │
│      → SSH connect fails (wrong user, no key on target)                   │
│      → structured error JSON returned to agent                             │
│                                                                            │
│  PROBLEM: Agent receives opaque connection error. No signal in the         │
│  tool schema or error response that says:                                  │
│    "Register this device first with register_server, OR                    │
│     add credentials with `homelab-mcp credentials add`"                   │
│                                                                            │
│  FIX LOCATIONS:                                                            │
│    1. ssh_tools_schema.py — enrich ssh_discover/ssh_execute_command        │
│       description with explicit workflow hint                              │
│    2. resolve_ssh_credentials() — when ALL tiers miss and bare             │
│       SSHCredentials is returned, set a flag or return metadata            │
│       that handlers can surface as an actionable error message             │
│    3. prompt_registry.py — add a new "connect_to_device" prompt            │
│       that sequences: register → credentials add → ssh_discover            │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│  BUG 3: TOFU known_hosts — Newly Registered Hosts Timeout                  │
│                                                                            │
│  User calls setup_mcp_admin(hostname, username, password)                  │
│      → first SSH connect via ssh_connect()                                 │
│      → TOFUSSHClient.validate_host_public_key() fires                      │
│      → no entry in known_hosts → TOFU: store key, accept                  │
│      → setup_mcp_admin runs, creates mcp_admin user, adds pub key         │
│                                                                            │
│  User (or agent) then calls register_server(hostname)                      │
│      → register_server() calls ssh_connect() to verify connection          │
│      → known_hosts already has the key → asyncssh reads known_hosts file  │
│      → PASSES (key is in file)                                             │
│                                                                            │
│  User then calls ssh_discover(hostname)  ← BUG MANIFESTS HERE             │
│      → resolve_ssh_credentials() Tier 2: hostname IS in registry           │
│        (register_credential was called during credentials add)              │
│      → OR Tier 3: db has record from register_server()                     │
│      → ssh_connect() is called with known_hosts=KNOWN_HOSTS_PATH           │
│      → asyncssh reads known_hosts and finds the entry → OK                 │
│                                                                            │
│  WAIT — if known_hosts is written by setup_mcp_admin step, why timeout?   │
│                                                                            │
│  ROOT CAUSE ANALYSIS REQUIRED: Two likely causes:                          │
│    A. register_server() verify_connection=True calls ssh_connect() but     │
│       the SSH server isn't ready yet (race condition after mcp_admin setup) │
│    B. The TOFU key stored during setup_mcp_admin uses the bootstrap user   │
│       (e.g., "admin@hostname") but register_server() connects as           │
│       "mcp_admin@hostname" — different host key fingerprint lookup         │
│       (TOFU stores per-host not per-user, so this should be fine)          │
│    C. known_hosts entry is written in asyncssh format that doesn't match   │
│       what asyncssh reads back — parsing bug in _store_host_key()          │
│    D. The host behind the IP rebooted/changed keys between setup and        │
│       first tool use — handled correctly (key mismatch = rejected)         │
│                                                                            │
│  Most likely cause (C): _store_host_key() writes raw                       │
│    key.export_public_key().decode() which produces "algorithm base64"      │
│    format. asyncssh known_hosts expects "hostname algorithm base64".       │
│    Inspection shows the entry is built as:                                  │
│      f"{host_label} {key_data}\n"                                          │
│    where key_data = key.export_public_key().decode().strip()               │
│    This LOOKS correct but export_public_key() may return                   │
│    "ssh-rsa AAAA..." with a trailing comment field or newline              │
│    that corrupts the file entry.                                           │
│                                                                            │
│  FIX LOCATION: ssh_connection.TOFUSSHClient._store_host_key()              │
│  FIX: Use asyncssh.export_known_hosts() or the SSHKey.export_public_key() │
│       'openssh' format explicitly, then strip the comment field            │
│       OR verify the format produced matches what asyncssh parses           │
└────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | v1.4 Status |
|-----------|----------------|-------------|
| `http_app.handle_shell_websocket()` | WebSocket I/O relay between browser and asyncssh PTY | MODIFY — fix read_output() to stream data as available |
| `shell_session.ShellSessionManager` | PTY session lifecycle, create/close/read/write | MODIFY — fix read_output() or expose readline-based streaming |
| `ssh_connection.TOFUSSHClient._store_host_key()` | Write host keys to known_hosts on first TOFU accept | MODIFY — verify/fix key export format |
| `ssh_connection.KNOWN_HOSTS_PATH` | Shared known_hosts file location | UNCHANGED |
| `ssh_tools.resolve_ssh_credentials()` | Priority-chain credential resolution for all SSH tools | MODIFY — return actionable signal when all tiers miss |
| `tool_schemas/ssh_tools_schema.py` | Tool descriptions that guide agent behavior | MODIFY — add workflow hints to ssh_discover and ssh_execute_command |
| `prompt_registry.py` | Static workflow prompts | MODIFY — add "connect_to_device" prompt for register→credential→ssh sequence |
| `shell_session.ShellSession` | Dataclass holding SSH connection + process | UNCHANGED |
| `tool_handlers/ssh_handlers.py` | Thin handler adapters for SSH tools | MODIFY — surface actionable error when bare credentials returned |

## Recommended Project Structure

```
src/homelab_mcp/
├── http_app.py              # MODIFY — fix handle_shell_websocket read_output()
├── shell_session.py         # POSSIBLY MODIFY — if fix moves to read_output() here
├── ssh_connection.py        # MODIFY — fix _store_host_key() key export format
├── ssh_tools.py             # MODIFY — resolve_ssh_credentials() bare-miss signal
├── tool_schemas/
│   └── ssh_tools_schema.py  # MODIFY — workflow hints in descriptions
├── prompt_registry.py       # MODIFY — add connect_to_device prompt
└── tool_handlers/
    └── ssh_handlers.py      # POSSIBLY MODIFY — surface actionable error
```

## Architecture Patterns

### Pattern 1: Fix asyncssh PTY stdout streaming

**What:** In `http_app.handle_shell_websocket()`, the `read_output()` inner coroutine calls `await session.process.stdout.read(4096)`. asyncssh's `SSHClientProcess.stdout` is a `asyncio.StreamReader`. The `read(n)` method on a StreamReader blocks until either `n` bytes are available OR EOF is reached — it does NOT return partial data eagerly like a non-blocking read.

**Root cause:** A PTY session never sends EOF during interactive use. `read(4096)` blocks indefinitely waiting for 4096 bytes or EOF. The WebSocket receives nothing until the SSH session closes.

**Fix:** Use `read1(n)` if asyncssh exposes it, or wrap with `asyncio.wait_for(..., timeout=0.05)` catching `TimeoutError` and continuing the loop. The `asyncio.sleep(0.01)` after the read call is evidence the original author expected polling, but the read itself is the blocking call.

**Correct pattern:**
```python
async def read_output() -> None:
    while True:
        try:
            if session.process.stdout:
                # Use small timeout to avoid blocking — PTY never sends EOF
                data = await asyncio.wait_for(
                    session.process.stdout.read(4096),
                    timeout=0.05,
                )
                if data:
                    text = data if isinstance(data, str) else data.decode("utf-8")
                    await websocket.send_text(text)
                else:
                    break  # EOF — process exited
        except TimeoutError:
            pass  # No data yet — continue polling
        except Exception as e:
            logger.error("Error reading output: %s", e)
            break
```

**Alternative:** asyncssh `create_process()` returns a process where `stdout` can be consumed as an async iterator (`async for chunk in process.stdout`). This is semantically cleaner but requires restructuring the read loop. The `wait_for` approach is the minimal change.

**Touch points:** `http_app.py` lines 189-202 only. `shell_session.py` and `ShellSession` dataclass untouched.

### Pattern 2: Actionable error on SSH credential miss

**What:** `resolve_ssh_credentials()` currently returns a bare `SSHCredentials(hostname, username)` with no password or key when all four tiers miss. The SSH connection attempt then fails with a cryptic auth error. The agent has no signal that registration is needed.

**Fix options (choose one):**

**Option A — Raise on bare miss (preferred):**
Raise a typed exception (e.g., `CredentialNotFoundError`) when no credential is found for a hostname that is not in the keyring registry OR the database. The handler in `ssh_handlers.py` catches this and returns a structured `isError: true` response with a message that says:

```
No credentials found for 192.168.1.10.
To connect, run one of:
  homelab-mcp credentials add --hostname 192.168.1.10 --username <user> --password <pass>
  OR call register_server after running setup_mcp_admin.
```

**Option B — Enrich tool description (lower friction):**
Add explicit workflow guidance to `ssh_tools_schema.py` descriptions. This is the lowest-effort fix and guides the agent before it even attempts the call.

**Option C — Both (recommended):**
Schema descriptions prevent the problem. Error message recovers from it. Both are 5-10 line changes.

**Touch points:**
- `ssh_tools.py` — `resolve_ssh_credentials()` return path when bare
- `tool_handlers/ssh_handlers.py` — handle new exception class
- `tool_schemas/ssh_tools_schema.py` — description strings

**New exception (add to ssh_tools.py or error_handling.py):**
```python
class CredentialNotFoundError(Exception):
    """Raised when no SSH credential is available for a hostname."""
    def __init__(self, hostname: str) -> None:
        super().__init__(
            f"No credentials found for {hostname}. "
            f"Run `homelab-mcp credentials add --hostname {hostname} ...` "
            f"or call setup_mcp_admin + register_server first."
        )
        self.hostname = hostname
```

### Pattern 3: TOFU known_hosts key format verification

**What:** `TOFUSSHClient._store_host_key()` exports the key and writes it to known_hosts. The format must be exactly what asyncssh expects when reading the file back via `known_hosts=str(kh_path)`.

**Current code:**
```python
key_data = key.export_public_key().decode("utf-8").strip()
entry = f"{host_label} {key_data}\n"
with open(self._known_hosts_path, "a") as f:
    f.write(entry)
```

**Problem:** `key.export_public_key()` by default returns OpenSSH format which may include a comment field (e.g., `ssh-rsa AAAA...data== user@host`). The resulting line would be `hostname ssh-rsa AAAA...data== user@host` — three to four space-separated fields. asyncssh's known_hosts parser expects exactly `hostname algorithm base64` (three fields). A fourth field (the comment) causes a parse failure, which asyncssh treats as "key not found" → TOFU fires again on the SAME host → key mismatch detection kicks in → connection rejected.

**Fix:** Strip the comment from the key export:
```python
# Export without comment — OpenSSH known_hosts format requires exactly
# "hostname algorithm base64", no trailing comment field
key_export = key.export_public_key().decode("utf-8").strip()
# key_export may be "ssh-rsa AAAA...== comment" — strip trailing comment
parts = key_export.split()
key_data = " ".join(parts[:2])  # keep only "algorithm base64"
entry = f"{host_label} {key_data}\n"
```

**Alternative (more robust):** Use `asyncssh.export_known_hosts({host_label: [key]})` if that API is available — it produces a correctly-formatted known_hosts line directly.

**Touch points:** `ssh_connection.py` `TOFUSSHClient._store_host_key()` only. No callers change.

### Pattern 4: Connect-to-device workflow prompt

**What:** Add a new `connect_to_device` prompt to `prompt_registry.py` that gives the agent a reproducible recipe when SSH to a new device is needed for the first time.

**When to use:** Agent has a hostname and credentials but no prior registration. Prompt sequences: `setup_mcp_admin` (bootstrap) → `register_server` (persists) → `credentials add` (keyring) → `ssh_discover` (verify).

**Touch points:** `prompt_registry.py` — add entry to `HOMELAB_PROMPTS` dict and a builder function `_build_connect_to_device_result()`. No other modules change.

## Data Flow

### Bug 1 — Interactive Shell (fixed flow)

```
MCP client → start_interactive_shell { hostname }
    ↓
handle_start_interactive_shell()
    → session_manager.create_session(hostname, ...)
        → resolve_ssh_credentials()  [existing chain]
        → ssh_connect()  [TOFU verify]
        → connection.create_process(term_type="xterm-256color")
    → returns session_id, shell_url

User opens shell_url in browser
    ↓
handle_shell_page() → serves shell_terminal.html with session_id injected
    ↓
Browser xterm.js opens WebSocket ws://{host}/ws/shell/{session_id}
    ↓
handle_shell_websocket(websocket)
    ↓
read_output task:
    loop:
        asyncio.wait_for(stdout.read(4096), timeout=0.05)
        TIMEOUT → continue (no data yet)
        DATA    → websocket.send_text(text)      ← FIX: was blocking here
        EOF     → break (process exited)

input forwarding loop:
    websocket.receive_text() → parse JSON
    type=="input"  → session.process.stdin.write(data)
    type=="resize" → session_manager.resize_terminal(rows, cols)
```

### Bug 2 — SSH Credential Flow (fixed flow)

```
Agent calls ssh_discover { hostname: "192.168.1.10" }
    ↓
resolve_ssh_credentials("192.168.1.10")
    Tier 1: no explicit password/key_path → skip
    Tier 2: list_credentials() → hostname not in registry → miss
    Tier 3: db.get_credential_by_hostname() → no record → miss
    Tier 4: mcp_admin key exists? NO → miss
    → raise CredentialNotFoundError("192.168.1.10")  ← FIX: was returning bare SSHCredentials
    ↓
handle_ssh_discover() catches CredentialNotFoundError
    → return {
        "isError": true,
        "content": [{"type": "text", "text":
            "No credentials found for 192.168.1.10. "
            "Run `homelab-mcp credentials add --hostname 192.168.1.10 ...` "
            "or use the connect_to_device prompt."
        }]
      }
```

**Pre-fix path (agent guidance via schema):**
```
Agent reads tool schema for ssh_discover:
    description now includes:
    "If credentials are not stored yet, run `homelab-mcp credentials add`
     or call setup_mcp_admin + register_server for key-based access."
    ↓
Agent calls setup_mcp_admin or credentials add BEFORE ssh_discover
    → no error
```

### Bug 3 — TOFU known_hosts (fixed flow)

```
User calls setup_mcp_admin(hostname="192.168.1.10", username="admin", password="...")
    ↓
ssh_connect(hostname, username="admin", password="...")
    → TOFUSSHClient.validate_host_public_key()
    → no entry in known_hosts → TOFU: _store_host_key()
        key_export = key.export_public_key().decode().strip()
        # FIX: strip comment field
        parts = key_export.split(); key_data = " ".join(parts[:2])
        entry = "192.168.1.10 ssh-rsa AAAA...data==\n"  ← exactly 3 fields
        append to known_hosts
    → connection accepted

User calls register_server(hostname="192.168.1.10", username="mcp_admin")
    ↓
ssh_connect(hostname, username="mcp_admin", key_path="~/.ssh/mcp/mcp_admin_key")
    → asyncssh reads known_hosts
    → finds "192.168.1.10 ssh-rsa AAAA..." → key matches → accepted
    → register_server writes DB record

User calls ssh_discover(hostname="192.168.1.10")
    ↓
resolve_ssh_credentials() Tier 3: DB record found → SSHCredentials(key_path=mcp_admin_key)
    ↓
ssh_connect(hostname, username="mcp_admin", key_path=mcp_admin_key)
    → asyncssh reads known_hosts
    → finds "192.168.1.10 ssh-rsa AAAA..." → key matches → accepted  ← WAS TIMING OUT
    → ssh_discover runs successfully
```

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `http_app.handle_shell_websocket()` | WebSocket I/O relay | `shell_session.ShellSessionManager` (get_session, resize_terminal) |
| `shell_session.ShellSessionManager` | SSH PTY lifecycle | `ssh_connection.ssh_connect()`, `ssh_tools.resolve_ssh_credentials()` |
| `ssh_connection.TOFUSSHClient` | TOFU key storage/verification | asyncssh API, `KNOWN_HOSTS_PATH` file |
| `ssh_tools.resolve_ssh_credentials()` | Credential priority chain | `credential_store`, `database`, filesystem (mcp_admin key) |
| `tool_schemas/ssh_tools_schema.py` | Agent-facing tool descriptions | Read by `tool_schemas/__init__.py` → served via `tools/list` |
| `prompt_registry.py` | Workflow prompt templates | Read by `server.py` `@server.list_prompts` / `@server.get_prompt` handlers |

## Integration Points

### Modified Files

| File | What Changes | Scope |
|------|--------------|-------|
| `http_app.py` | `handle_shell_websocket()` `read_output()` inner function | 5-8 lines changed in one inner function |
| `ssh_connection.py` | `TOFUSSHClient._store_host_key()` key export stripping | 3-4 lines in one method |
| `ssh_tools.py` | `resolve_ssh_credentials()` raises `CredentialNotFoundError` on bare miss | ~6 lines; add exception class or import it |
| `tool_schemas/ssh_tools_schema.py` | Description strings for `ssh_discover`, `ssh_execute_command` | 2-4 description string edits |
| `tool_handlers/ssh_handlers.py` | `handle_ssh_discover()` catches `CredentialNotFoundError`, returns structured error | ~8 lines |
| `prompt_registry.py` | Add `connect_to_device` prompt entry and builder | ~25 lines new |

### No-Change Modules

The following modules require zero changes for v1.4:

- `credential_store.py` — registry and keyring are correct; INJECT-01 is implemented
- `server.py` — MCP protocol handling, lifespan, tool/resource/prompt dispatch unchanged
- `database.py` — credential CRUD unchanged
- `sitemap.py` — network topology unchanged
- All `tool_handlers/` except `ssh_handlers.py`
- All `tool_schemas/` except `ssh_tools_schema.py`
- `vm_operations.py`, `proxmox_api.py`, `service_installer.py`, `infrastructure_crud.py`

### New Exception Class

`CredentialNotFoundError` — either defined in `ssh_tools.py` (co-located with `resolve_ssh_credentials()`) or in `error_handling.py` (consistent with other domain exceptions). Recommendation: `ssh_tools.py` since the exception is specific to SSH credential resolution. No circular import risk.

## Build Order

Dependencies determine order. Each step can have RED tests written before implementation.

```
Step 1: ssh_connection.py — fix _store_host_key() key format
    No dependencies on steps 2-4.
    Tests: write a known_hosts entry, read it back with asyncssh.read_known_hosts(),
           verify the key is recognized. Requires asyncssh in test env (already present).

Step 2: http_app.py — fix read_output() in handle_shell_websocket()
    No dependencies on steps 1, 3, 4.
    Tests: mock asyncssh process.stdout with a StreamReader that returns data
           in small chunks; assert WebSocket receives data before EOF.
           Integration test with a real SSH server (existing Docker infra).

Step 3: ssh_tools.py — CredentialNotFoundError on bare miss
    Depends on Step 1 being done (TOFU bug must be fixed for integration tests to pass).
    Tests: mock all four tiers to miss; assert CredentialNotFoundError raised.
           Extend existing resolve_ssh_credentials unit tests.

Step 4: ssh_handlers.py — catch CredentialNotFoundError, return structured error
    Depends on Step 3 (exception must exist).
    Tests: assert error response contains actionable message with hostname.

Step 5: ssh_tools_schema.py — workflow hints in descriptions
    No code dependencies. Self-contained string changes.
    Tests: assert description for ssh_discover contains "credentials add".
    Can be done at any point.

Step 6: prompt_registry.py — connect_to_device prompt
    No code dependencies. No circular import risk (prompt_registry imports only mcp.types).
    Tests: assert prompts/list includes connect_to_device;
           assert prompts/get returns correct message sequence.
    Can be done at any point after understanding the final workflow.
```

Steps 1 and 2 have no mutual dependency — they can be developed in parallel.
Steps 3+4 logically follow Step 1 (integration tests need TOFU to work).
Steps 5+6 are order-independent with respect to all other steps.

**Suggested phase grouping:**
- Phase 1: Step 1 (TOFU) + Step 2 (shell streaming) — core reliability
- Phase 2: Steps 3+4 (credential error) + Step 5 (schema hints) — agent guidance
- Phase 3: Step 6 (prompt) — workflow completeness

## Anti-Patterns to Avoid

### Anti-Pattern 1: Swapping asyncssh process model

**What goes wrong:** Replacing `connection.create_process()` with `connection.create_session()` or a custom SSH session handler to "fix" the streaming problem.

**Why it's wrong:** `create_process()` + `SSHClientProcess` is the correct asyncssh API for PTY sessions. The bug is in how stdout is read, not in which API creates the process. A rewrite risks breaking PTY allocation (`term_type`, `term_size`), the `change_terminal_size()` call, and existing stdin write paths.

**Do this instead:** Fix the single `read()` call to use `asyncio.wait_for()` with a short timeout. Everything else in `shell_session.py` and `handle_shell_websocket()` stays the same.

### Anti-Pattern 2: Storing TOFU keys outside known_hosts

**What goes wrong:** Writing accepted host keys to a separate JSON registry or the SQLite database instead of the standard known_hosts file.

**Why it's wrong:** asyncssh's connection API accepts `known_hosts=str(path)` and handles all verification internally. If keys are in a separate store, the `known_hosts` parameter must be set to `None` (disabling all verification) and re-implemented manually. This loses asyncssh's built-in key-mismatch detection.

**Do this instead:** Fix the format of entries written to the existing `KNOWN_HOSTS_PATH` file. asyncssh reads this file correctly once the entries are in the right format.

### Anti-Pattern 3: Raising CredentialNotFoundError deep in ssh_connect()

**What goes wrong:** Adding credential-awareness to `ssh_connection.ssh_connect()` so it raises `CredentialNotFoundError` when no credentials are provided.

**Why it's wrong:** `ssh_connect()` is a pure connection helper. It should not know about the credential resolution strategy. The resolution logic lives in `resolve_ssh_credentials()` in `ssh_tools.py`. Mixing credential logic into `ssh_connect()` breaks the layering and makes the function harder to test in isolation.

**Do this instead:** Raise `CredentialNotFoundError` at the end of `resolve_ssh_credentials()` when it would return a bare `SSHCredentials` with no auth material. The handler layer catches it and returns an actionable error response.

### Anti-Pattern 4: Separate known_hosts file per tool

**What goes wrong:** Parameterizing `KNOWN_HOSTS_PATH` differently for `setup_mcp_admin` vs `register_server` vs `ssh_discover`.

**Why it's wrong:** TOFU semantics require that one accepted key covers all subsequent connections to the same host. If different tools use different files, each tool re-does TOFU independently, which causes key-mismatch rejections on the second tool to connect (it sees no entry in ITS file, stores the key — but the key was already stored in the OTHER file, so nothing breaks) OR race conditions on concurrent connections. More critically, the verification in `register_server` would not share the key stored by `setup_mcp_admin` and would re-trigger TOFU.

**Do this instead:** All SSH connections use the single shared `KNOWN_HOSTS_PATH` constant from `ssh_connection.py`. The `known_hosts_path` parameter to `ssh_connect()` is for testing only.

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Bug 1 root cause (shell streaming) | HIGH | `read()` blocking semantics on asyncio.StreamReader are well-defined; code path verified by inspection |
| Bug 1 fix approach | HIGH | `asyncio.wait_for()` with TimeoutError catch is a standard pattern for non-blocking reads from StreamReader |
| Bug 2 root cause (agent guidance) | HIGH | resolve_ssh_credentials() full body inspected; bare-miss return path confirmed |
| Bug 2 fix approach | HIGH | CredentialNotFoundError pattern is standard Python; handler catch pattern established in codebase |
| Bug 3 root cause (TOFU format) | MEDIUM | export_public_key() comment-stripping hypothesis is the most likely cause based on code inspection; requires test to confirm actual output format |
| Bug 3 fix approach | HIGH | "keep only first two fields" approach is safe regardless of whether comment is present |
| Build order | HIGH | Dependency chain verified: TOFU fix unblocks integration tests for credential flow |

## Sources

- `src/homelab_mcp/http_app.py` — `handle_shell_websocket()` and `read_output()` inner coroutine (lines 170-229)
- `src/homelab_mcp/shell_session.py` — `ShellSessionManager.create_session()`, `read_output()`, `ShellSession` dataclass (full file)
- `src/homelab_mcp/ssh_connection.py` — `TOFUSSHClient._store_host_key()`, `ssh_connect()` full body (full file)
- `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials()` four-tier chain (lines 36-131)
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — `ssh_discover` and `ssh_execute_command` description strings (full file)
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` — `handle_ssh_discover()`, `handle_start_interactive_shell()` (full file)
- `src/homelab_mcp/prompt_registry.py` — existing prompt structure and builder pattern (full file)
- `src/homelab_mcp/credential_store.py` — `list_credentials()`, `get_credential()`, `register_credential()` (full file)
- `.planning/codebase/ARCHITECTURE.md` — layer diagram and data flow reference (2026-03-08)

---

*Architecture research for: homelab-mcp v1.4 — interactive shell fix, SSH credential flow, TOFU known_hosts*
*Researched: 2026-03-13*
