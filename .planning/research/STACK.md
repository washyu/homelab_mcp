# Technology Stack

**Project:** Homelab MCP Server — v1.4 Real-World Reliability
**Researched:** 2026-03-13
**Scope:** Bug-fix milestone. Only the three bugs found during real Mac testing are in scope. Everything else is NOT re-researched.

---

## Summary: What Changes for v1.4

| Bug | Stack Change | Verdict |
|-----|-------------|---------|
| Interactive shell returns nothing silently | No new deps — fix error propagation in WebSocket handler, fix `term_size` arg order | Pure code fix in `shell_session.py` and `http_app.py` |
| SSH workflow requires prior device registration; agent doesn't know this | No new deps — fix `resolve_ssh_credentials` to surface actionable error when no credentials found | Pure code fix in `ssh_tools.py`; possibly add a tool-description update |
| SSH timeout after registration — TOFU known_hosts doesn't include new hosts | No new deps — fix `ssh_connect()` TOFU interaction when `known_hosts` file exists but host is absent | Pure code fix in `ssh_connection.py` |

**Net new runtime dependencies for v1.4: zero.** All three bugs are fixable within the existing stack.

---

## Bug 1: Interactive Shell — Silent Failure

**Confidence: HIGH** — verified by reading asyncssh 2.21.0 source installed at `.venv/lib/python3.12/site-packages/asyncssh/`.

### Root Cause A: `term_size` Argument Order Is Wrong

`asyncssh.create_process(term_type=..., term_size=(24, 80))` passes `(width=24, height=80)`.

asyncssh `term_size` is `(width, height)` = `(cols, rows)`. Source: `channel.py:1176`:

```python
elif len(term_size) == 2:
    width, height = cast(Tuple[int, int], term_size)
```

The current value `(24, 80)` creates a terminal that is **24 columns wide and 80 rows tall** — inverted. Normal terminals are 80 columns × 24 rows.

A 24-column terminal causes the shell's PS1 prompt to wrap aggressively and disrupts output layout. On some SSH servers, an extremely narrow PTY will cause the shell to emit control sequences that confuse the xterm.js client, resulting in blank output even though bytes ARE being sent.

**Fix:** Change `term_size=(24, 80)` to `term_size=(80, 24)` in `shell_session.py:109`.

### Root Cause B: WebSocket `read()` Silently Breaks on EOF Without Notifying Client

`http_app.py:198`:
```python
data = await session.process.stdout.read(4096)
if data:
    ...
else:
    break  # silent exit — WebSocket stays open, no output ever sent
```

When `data` is an empty string (EOF), the `read_output` task silently exits. The WebSocket connection stays open but nothing will ever be sent to the browser. The user sees a blank terminal with "Connected" status.

EOF from `session.process.stdout` happens when:
1. The SSH process exits (connection dropped, shell exited)
2. The SSH channel is closed by the remote end
3. The PTY allocation fails on the remote end (server rejects PTY request)

In all three cases, the browser receives no notification. Silence looks like a bug but is actually an unhandled error path.

**Fix:** On EOF, send an error message to the WebSocket client before closing:
```python
else:
    # EOF — process exited or PTY allocation failed
    await websocket.send_text("\r\n\x1b[31m[Connection closed]\x1b[0m\r\n")
    break
```

Also: wrap the exception handler to send the error text to the terminal rather than only logging it.

### Root Cause C: Exception in `create_session()` Does Not Surface to Browser

If SSH connection fails AFTER `start_interactive_shell` returns a session URL (unlikely but possible in a race), or if `create_process()` raises, the exception propagates to the tool handler and returns an error dict — but the user already has a shell URL from the tool response. Opening that URL returns a 404 (session not found) with no explanation.

This is a secondary UX failure, not the primary silent failure, but it should be addressed: the error should surface in the tool response text, not just as a 404.

### What NOT to Change for Interactive Shell

| Avoid | Why |
|-------|-----|
| Replace asyncssh `create_process` with raw SSH subprocess | `create_process` with `term_type` correctly allocates a PTY and handles encoding. The fundamental approach is correct |
| Add `encoding=None` to `create_process` | Default encoding is `'utf-8'` (verified at `connection.py:8128`). This means stdout returns `str`, which is correct. Switching to `encoding=None` (bytes) would require changing the decode path; no benefit |
| Replace xterm.js CDN with bundled copy | CDN at cdn.jsdelivr.net works fine; not the cause of silence |
| Add explicit `request_pty='force'` | Default `request_pty=True` already enables PTY when `term_type` is set (verified at `connection.py:4359-4360`). No change needed |

---

## Bug 2: SSH Credential Flow — Agent Needs Guidance

**Confidence: HIGH** — verified by reading `ssh_tools.py:resolve_ssh_credentials()` and `credential_store.py`.

### Root Cause: Silent Fallthrough to Keyless Connection

`resolve_ssh_credentials()` has this priority chain:

1. Explicit `password` or `key_path` argument → use immediately
2. Keyring lookup via `list_credentials()` → if hostname found in registry AND password in keyring → use
3. Database `ssh_credentials` table → if stored credential found → use
4. Default `~/.ssh/mcp/mcp_admin_key` → if file exists → use
5. Return minimal `SSHCredentials` with no password and no key

At step 5, the function returns `SSHCredentials(hostname, username)` with no auth method. `ssh_connect()` then attempts connection with no password and no client keys. asyncssh falls back to agent keys (if any) or fails with an auth error.

The agent gets an opaque `PermissionDenied` or `ConnectionResetError` from asyncssh. There is no message saying "you need to run `homelab-mcp credentials add`." The agent knows the tool failed but has no path forward.

**The workflow the agent doesn't know about:**
- User must run `homelab-mcp credentials add --hostname HOST --username USER` before SSH tools will work for that host
- This isn't surfaced in any tool description or error message
- The agent may try ssh_execute_command, get auth failure, and have no idea what to do

**Fix options (pick one or combine):**

**Option A — Error message with action guidance:** At step 5 of `resolve_ssh_credentials`, detect that no auth method is available and raise with an actionable message:

```python
raise ValueError(
    f"No credentials found for {hostname}. "
    f"Run: homelab-mcp credentials add --hostname {hostname} --username <USER> "
    f"and then retry."
)
```

This surfaces in the tool's error response. The agent can read it and guide the user.

**Option B — Tool description update:** Update the `ssh_execute_command` and related SSH tool descriptions in `ssh_tools_schema.py` to mention that `credentials add` must be run first for new hosts.

**Option C — Check-credentials tool or pre-flight:** Add a `check_ssh_credentials(hostname)` tool that returns whether credentials are stored. Prompts workflow before attempting connection.

**Recommended: Option A + Option B.** Option A provides runtime guidance; Option B surfaces it during tool discovery. Option C adds a new tool and is unnecessary if A+B work.

### What NOT to Change for Credential Flow

| Avoid | Why |
|-------|-----|
| Auto-prompt user for password from within MCP tool | MCP tools are server-side; no stdin for interactive prompts. `getpass.getpass()` would block and hang |
| Store credentials in cleartext in `~/.homelab_mcp/` as a fallback | Insecure; explicitly rejected in v1.3 design. OS keyring or nothing |
| Change the credential priority order | The current order (explicit → keyring → DB → mcp_admin_key → bare) is correct |
| Remove the DB fallback path (step 3) | Existing devices may have credentials in the DB from pre-v1.3 registration |

---

## Bug 3: SSH Timeout After Registration — TOFU Known_Hosts Issue

**Confidence: HIGH** — verified by reading asyncssh 2.21.0 source at `connection.py:1329-1348` and `ssh_connection.py`.

### Root Cause: TOFU Logic and `known_hosts` File Check Are Redundant and Conflicting

`ssh_connect()` passes BOTH:
- `known_hosts=str(kh_path)` — asyncssh loads the file and checks the server key against entries
- `client_factory=lambda: TOFUSSHClient(kh_path)` — custom client that implements `validate_host_public_key`

asyncssh's behavior (verified at `connection.py:1334-1344`):

```python
if self._trusted_host_keys is not None:
    if key in self._revoked_host_keys:
        raise ValueError('Host key is revoked')

    if key not in self._trusted_host_keys and \
       not self._owner.validate_host_public_key(host, addr, port, key):
        raise ValueError('Host key is not trusted')
```

**What happens for a NEW host (not yet in known_hosts file):**

1. asyncssh loads the known_hosts file → `_trusted_host_keys` is populated but does NOT contain this host
2. Server sends its host key
3. asyncssh checks: `key not in self._trusted_host_keys` → True
4. asyncssh calls `validate_host_public_key()` on our `TOFUSSHClient`
5. `TOFUSSHClient.validate_host_public_key()` checks `_host_has_stored_key()` → False (not in file yet)
6. TOFU: stores key in file, returns `True`
7. Connection succeeds

**What happens AFTER device registration (host IS in known_hosts file):**

If the device was discovered/registered via `ssh_discover_system` (which internally calls `ssh_connect`), the TOFU flow in step 5-6 ran and the key IS in the file. Subsequent connections load the key from the file at step 1, match at step 3, skip `validate_host_public_key`. Works correctly.

**The actual reported bug: SSH timeouts after registration**

The timeout is not caused by the known_hosts logic per se. Reading the `TOFUSSHClient._host_has_stored_key()` method reveals the actual bug:

```python
for line in content.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.split()
    if len(parts) >= 2 and parts[0] == host_label:
        return True
```

`_host_has_stored_key()` ONLY checks whether a key is already stored (to detect MITM). It does NOT verify the key matches — it just checks host label presence. If the host label IS present, `validate_host_public_key` returns `False` (MITM rejection path):

```python
if self._host_has_stored_key(host, port):
    logger.warning("Host key mismatch for %s -- possible MITM attack...")
    return False
```

So: if the host IS in the known_hosts file but asyncssh loaded a DIFFERENT key format or the key in `_trusted_host_keys` doesn't match, the flow would be:
1. `key not in _trusted_host_keys` → True (key didn't match)
2. `validate_host_public_key()` called
3. `_host_has_stored_key()` → True (host IS in file)
4. Returns False (MITM rejection)
5. asyncssh raises `ValueError('Host key is not trusted')`

**But the reported symptom is "timeout", not authentication error.** A timeout suggests the connection attempt hangs. This points to a different failure mode: the `connect_timeout=10` in `ssh_connect()` is the default, but this timeout applies to the SSH handshake layer. If the device doesn't respond on port 22 (wrong IP after registration, network issue) or if the known_hosts file has a corrupted entry that causes asyncssh to stall, the timeout fires.

**More likely root cause of the timeout**: The `register_credential` CLI flow stores credentials in the keyring and registry, but does NOT trigger an SSH connection test. The device IP stored in the DB may differ from the hostname used in the registry. When `resolve_ssh_credentials()` looks up the registry by `hostname`, it finds the entry, gets the password, and calls `ssh_connect()` with the original hostname. If the hostname doesn't resolve to the correct IP (e.g., hostname was registered as `192.168.1.x` during discovery but the credential was added with a different label), the connection attempt hits a non-responding host and times out.

**The TOFU file interaction bug** (confirmed): When a new device is connected for the FIRST time via `ssh_connect()`, the TOFU code writes the key to the file. But `_format_host_label()` formats non-default ports as `[hostname]:port`. The known_hosts file stores `hostname` for port 22. asyncssh loads the file and checks using the same host label. This is correct behavior.

However, there IS a subtle race: if two simultaneous SSH connections to the same new host fire concurrently, both call `validate_host_public_key` before either writes to the file. Both see `_host_has_stored_key() = False`, both accept the key, and both write to the file. The result is two identical entries in known_hosts. asyncssh handles duplicate entries gracefully (the key IS in the set), so this doesn't cause failures. But the module-level `_tofu_lock = asyncio.Lock()` in `ssh_connection.py` is NEVER USED in the `_store_host_key` or `validate_host_public_key` methods — it's defined but not acquired. This is a latent bug but not the cause of the reported timeout.

**Actual fix for the timeout bug**: The timeout is most likely caused by `credentials add` adding a hostname to the registry that doesn't match any device registered via `ssh_discover_system`. The credential registry stores `hostname` as provided on the CLI, but the DB stores the discovered IP. If the user runs:

```bash
homelab-mcp credentials add --hostname mydevice --username admin
```

But `ssh_discover_system` discovered the device as `192.168.1.100`, then `resolve_ssh_credentials("192.168.1.100")` looks up the registry by hostname `192.168.1.100` — not found. Falls through to DB lookup, finds the device, but no password in DB. Falls through to `mcp_admin_key`. If that key doesn't work, returns bare `SSHCredentials`. No credentials → connection attempt → timeout or auth failure.

**Fix:** Improve `resolve_ssh_credentials()` to also check the registry by IP when the registry entry uses a hostname alias, OR document clearly that `credentials add --hostname` must use exactly the same hostname/IP as used for discovery.

Additionally: add actionable error messages when credentials resolve to "no auth method" (covered by Bug 2 fix).

### asyncssh `known_hosts=None` Option

Setting `known_hosts=None` disables ALL host key checking (verified at `connection.py:3473-3474`: `_trusted_host_keys = None`, and the check block at line 1334 is skipped). This would also skip calling `validate_host_public_key`. So our current `TOFUSSHClient.validate_host_public_key` ONLY runs when `known_hosts` is set to a file path AND the key is NOT in that file.

The TOFU design is architecturally sound. The issue is that first-time TOFU (writing the key) and subsequent connections (reading the key) work correctly. The timeout is a credential mismatch issue, not a TOFU issue.

### What NOT to Change for TOFU

| Avoid | Why |
|-------|-----|
| Set `known_hosts=None` to skip file check | Would disable all host key verification; TOFU would fire for every connection even for known hosts |
| Use `asyncssh.read_known_hosts()` to reload file on each connection | Unnecessary overhead; the current file-path approach causes asyncssh to read the file on each `connect()` call already |
| Move to `SSHKnownHosts` object passed as `known_hosts` | Would need to reload the object on every connection to pick up newly written entries; file-path approach is simpler |
| Fix the unused `_tofu_lock` as a v1.4 priority | The race condition requires concurrent connections to the SAME new host; unlikely in homelab use. Low priority |

---

## Recommended Stack (No Changes)

### Runtime Dependencies — No Changes for v1.4

| Package | Locked Version | Purpose | Change? |
|---------|---------------|---------|---------|
| asyncssh | 2.21.0 | SSH connections, TOFU, PTY processes | None — behavior is correct, bugs are in how we call it |
| mcp[cli] | 1.9.4 | MCP protocol server | None |
| starlette | 0.47.1 | ASGI app, WebSocket routing | None |
| websockets | 16.0 | WebSocket transport layer | None |
| keyring | (installed via core dep) | Credential storage | None |
| All others | as locked | — | None |

### Dev Dependencies — No Changes for v1.4

All dev tools (pytest, ruff, mypy, bandit) unchanged. No new test fixtures required beyond mocking asyncssh `create_process` and `SSHClientProcess.stdout`.

---

## File Changes Required

### `src/homelab_mcp/shell_session.py`

Line 109: Fix `term_size` argument order.

```python
# BEFORE (wrong — 24 cols × 80 rows)
process = await connection.create_process(
    term_type="xterm-256color",
    term_size=(24, 80),
)

# AFTER (correct — 80 cols × 24 rows)
process = await connection.create_process(
    term_type="xterm-256color",
    term_size=(80, 24),
)
```

asyncssh `term_size` is `(width, height)` = `(cols, rows)`. Verified at `channel.py:1176`.

### `src/homelab_mcp/http_app.py`

WebSocket `read_output` coroutine: add error notification to browser on EOF and exception paths.

```python
async def read_output() -> None:
    while True:
        try:
            if session.process.stdout:
                data = await session.process.stdout.read(4096)
                if data:
                    text = data if isinstance(data, str) else data.decode("utf-8")
                    await websocket.send_text(text)
                else:
                    # EOF — process exited or PTY allocation failed
                    await websocket.send_text(
                        "\r\n\x1b[31m[Shell process ended]\x1b[0m\r\n"
                    )
                    break
            else:
                break
        except Exception as e:
            logger.error(f"Error reading output: {e}")
            try:
                await websocket.send_text(
                    f"\r\n\x1b[31m[Read error: {e}]\x1b[0m\r\n"
                )
            except Exception:
                pass
            break
        await asyncio.sleep(0.01)
```

### `src/homelab_mcp/ssh_tools.py`

`resolve_ssh_credentials()`: at the final fallthrough (step 5), raise with an actionable message instead of returning bare credentials.

```python
# At the end of resolve_ssh_credentials(), replace:
return SSHCredentials(
    hostname=resolved_username,
    username=resolved_username,
    port=port,
)

# With:
raise ValueError(
    f"No SSH credentials found for {hostname}. "
    f"Store credentials first: "
    f"homelab-mcp credentials add --hostname {hostname} --username <USER> --type ssh"
)
```

Also update tool descriptions in `ssh_tools_schema.py` to mention that credentials must be registered before use.

### `src/homelab_mcp/ssh_connection.py`

The `_tofu_lock` is module-level but never acquired. The lock should guard `_store_host_key` to prevent duplicate entries on concurrent TOFU. This is a latent defect — not the reported bug, but trivially fixed:

```python
# In _store_host_key, acquire the lock:
# Note: validate_host_public_key is a sync method — cannot use async lock
# Use threading.Lock() instead of asyncio.Lock() for sync context
```

Actually: `validate_host_public_key` is a SYNCHRONOUS method (returns `bool`, not `Awaitable[bool]`). An `asyncio.Lock()` cannot be acquired from a sync context. The correct fix is to use `threading.Lock()` instead. This is a latent bug; whether to fix it in v1.4 is a scope call.

---

## asyncssh Behavior Summary (Verified)

| Scenario | asyncssh Behavior | Source |
|----------|-------------------|--------|
| `known_hosts=str(path)` + `client_factory` with `validate_host_public_key` | File is loaded; callback only fires when key NOT in file | `connection.py:1334-1344` |
| `known_hosts=None` | Host key verification fully disabled; `validate_host_public_key` NEVER called | `connection.py:3473-3474` |
| `term_size=(width, height)` | `width` = cols, `height` = rows (not rows, cols) | `channel.py:1176` |
| `change_terminal_size(width, height)` | Same order: cols then rows | `process.py:1456` |
| Default `encoding` for `create_session` / `create_process` | `'utf-8'` — stdout.read() returns `str` | `connection.py:8128` |
| `read(n)` on asyncssh SSHReader | Blocks until n bytes arrive OR EOF. Returns `''` (empty str) on EOF with encoding set | `stream.py:575` |
| PTY request with `request_pty=True` (default) and `term_type` set | PTY is requested (truthy `term_type` → `request_pty=True`) | `connection.py:4359-4360` |

---

## Installation

No new packages. All bugs are code-level fixes.

```bash
# Verify asyncssh version matches what was analyzed
uv run python -c "import asyncssh; print(asyncssh.__version__)"
# Expected: 2.21.0

# Run existing tests after fixes
uv run pytest tests/ -m "not integration" -v

# Verify term_size is correct after fix
uv run python -c "
import asyncssh
# term_size=(80, 24) means width=80 (cols), height=24 (rows) — correct
print('term_size order: (width/cols, height/rows)')
"
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Interactive shell fix | Fix `term_size` order + add error notification | Replace with paramiko-based PTY | asyncssh is already in use; paramiko would be a new dep; not the cause of silence |
| Interactive shell fix | Fix error notification on EOF | Add heartbeat/ping from server | EOF notification is the correct signal; heartbeats complicate the protocol |
| SSH credential guidance | Raise `ValueError` with actionable message at no-auth fallthrough | Add `check_credentials` tool | New tool adds complexity; actionable error in existing tool is simpler for the agent |
| TOFU timeout fix | Document hostname/IP matching requirement + add error message | Auto-scan registry by IP range | Auto-scan is complex and out of scope for v1.4 |
| `_tofu_lock` fix | Replace `asyncio.Lock` with `threading.Lock` | Leave as-is | Concurrent TOFU to same new host is unlikely in homelab; low risk |

---

## Sources

- asyncssh 2.21.0 source, `.venv/lib/python3.12/site-packages/asyncssh/connection.py` lines 1334-1344, 3473-3491, 4355-4388, 8128 — host key validation flow, `known_hosts` behavior, `create_session` defaults (HIGH confidence — direct source read)
- asyncssh 2.21.0 source, `.venv/lib/python3.12/site-packages/asyncssh/channel.py` lines 1170-1184 — `term_size` argument order (HIGH confidence — direct source read)
- asyncssh 2.21.0 source, `.venv/lib/python3.12/site-packages/asyncssh/process.py` lines 1456-1480 — `change_terminal_size` argument order (HIGH confidence — direct source read)
- asyncssh 2.21.0 source, `.venv/lib/python3.12/site-packages/asyncssh/client.py` lines 124-162 — `validate_host_public_key` contract and default (HIGH confidence — direct source read)
- `src/homelab_mcp/ssh_connection.py` — TOFUSSHClient implementation (HIGH confidence — direct source read)
- `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials` priority chain (HIGH confidence — direct source read)
- `src/homelab_mcp/shell_session.py` — `create_process` call with `term_size=(24, 80)` (HIGH confidence — direct source read)
- `src/homelab_mcp/http_app.py` — WebSocket `read_output` handler (HIGH confidence — direct source read)
- `uv.lock` — asyncssh 2.21.0, mcp 1.9.4, starlette 0.47.1, websockets 16.0 confirmed (HIGH confidence)

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| `term_size` order bug | HIGH | Directly verified in asyncssh `channel.py` source |
| WebSocket silent failure on EOF | HIGH | Direct code analysis of `http_app.py` read loop |
| `validate_host_public_key` / `known_hosts` interaction | HIGH | Directly verified in asyncssh `connection.py` source |
| TOFU timeout root cause | MEDIUM | Inferred from credential flow analysis; specific network conditions not reproduced |
| `resolve_ssh_credentials` fallthrough behavior | HIGH | Direct code read of `ssh_tools.py` |
| No new deps needed | HIGH | All three bugs are call-site or error-handling issues |

---

*Stack research for: Homelab MCP Server v1.4 Real-World Reliability*
*Researched: 2026-03-13*
