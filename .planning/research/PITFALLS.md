# Pitfalls Research

**Domain:** Python MCP server — fixing interactive shell (WebSocket), SSH credential flow, and TOFU known_hosts handling
**Researched:** 2026-03-13
**Project context:** homelab-mcp v1.4, existing `shell_session.py`, `ssh_connection.py`, `ssh_tools.py`, `credential_store.py`; 635 passing tests on main

> **Note:** This file covers v1.4 Real-World Reliability pitfalls.
> v1.3 Credentials & Release Automation pitfalls are appended at the bottom of this file.

---

## Critical Pitfalls

---

### Pitfall 1: asyncssh `validate_host_public_key` Is Silently Never Called When `known_hosts` Is Set to a Non-Empty File

**What goes wrong:**
`ssh_connect()` passes both `known_hosts=str(kh_path)` and `client_factory=lambda: TOFUSSHClient(kh_path)`. asyncssh loads the file at connection start and runs its own internal key validation. Only if the key is **not found** in the file does asyncssh call `SSHClient.validate_host_public_key()`. When the file is empty, asyncssh calls `validate_host_public_key()` correctly. But the current code also calls `kh_path.touch()` to create an empty file before connecting. On the TOFU-store path, `_store_host_key` appends the accepted key.

The bug surface is the **second connection** scenario: if a host was discovered via `ssh_discover_system` (TOFU ran, key stored), then the user calls `credentials add hostname=...`, which registers the host in `credential_registry.json` only — it does **not** clear or re-verify `known_hosts`. The third call is `ssh_execute_command` with keyring-injected credentials. If the IP/hostname used in `credentials add` differs even slightly from the label stored by TOFU (e.g., `192.168.1.10` vs `192.168.1.10` with port 22 stored as plain hostname — these match, but `192.168.1.10` vs `node01.local` for the same host do not), asyncssh finds no entry in `known_hosts` for the new label, calls `validate_host_public_key()`, and TOFU runs again. TOFU succeeds, stores the new label — this is correct but unexpected to the user.

**The actual reported timeout bug** is distinct: `validate_host_public_key()` is a **synchronous** method. Inside it, `_store_host_key` does synchronous file I/O (`open()` + `write()`). The module declares `_tofu_lock = asyncio.Lock()` but `_store_host_key` never acquires it. This is not a timeout cause by itself, but on macOS, asyncssh calls `validate_host_public_key` from within the asyncssh connection coroutine. If the `known_hosts` file write blocks (slow filesystem, NFS, full disk), the asyncssh event loop stalls, manifesting as a connection timeout. More critically: **the `_tofu_lock` is never used**. The lock is documented as preventing duplicate entries on concurrent TOFU but it is dead code. Two concurrent SSH connections to the same new host will both call `validate_host_public_key` — both will find no stored key, both will `_store_host_key`, and the file will have two duplicate entries for the same host. asyncssh handles duplicate entries gracefully (first match wins), but this is a correctness bug.

**Why it happens:**
The `_tofu_lock` cannot be acquired from a synchronous callback (`validate_host_public_key` is not `async`). The developer documented the intent but couldn't implement it. The asyncssh `SSHClient.validate_host_public_key` signature is synchronous; asyncssh does not support `async def` for this callback.

**Consequences:**
- Concurrent first connections to the same host result in duplicate `known_hosts` entries (cosmetic but adds confusion).
- If a new fix introduces `asyncio.run()` or `loop.run_until_complete()` inside `_store_host_key` to acquire the lock, it deadlocks the event loop (calling `asyncio.run` from within a running event loop raises `RuntimeError`).
- If v1.4 work touches `TOFUSSHClient` without addressing the sync constraint, test coverage may mask the race because unit tests don't run concurrent TOFU.

**Prevention:**
1. Replace the async lock with a `threading.Lock` — this is safe to acquire from synchronous callbacks called within an asyncio coroutine.
2. Alternatively, use `fcntl.flock()` (macOS/Linux) for file-level locking to prevent duplicate entries.
3. Any v1.4 change to `_store_host_key` must explicitly handle the sync-from-async constraint — no `asyncio.Lock`, no `asyncio.run()`, no `loop.run_until_complete()` inside a sync method.
4. Document that `validate_host_public_key` is a sync callback in a comment on the method — future developers will be surprised by this.

**Warning signs:**
- `asyncio.Lock` imported and assigned to `_tofu_lock` but never used in any `with` block or `await` statement.
- Any `asyncio.run(...)` call inside `_store_host_key` or `_host_has_stored_key`.
- `known_hosts` file containing duplicate entries for the same hostname after concurrent test runs.

**Phase to address:**
Phase fixing TOFU known_hosts. Verify the lock mechanism is either removed or replaced with `threading.Lock` before phase is marked complete.

---

### Pitfall 2: WebSocket `handle_shell_websocket` Returns Nothing to the Browser Because the Output Task and Input Loop Race at Startup

**What goes wrong:**
`handle_shell_websocket` (in `http_app.py`) creates an `output_task` that reads from `session.process.stdout` via `await session.process.stdout.read(4096)`. This is a **blocking read** — it suspends until data is available. Immediately after, the handler enters `while True: message = await websocket.receive_text()`. This is also blocking. Both tasks compete for the event loop.

The silent failure mode: the asyncssh PTY process starts and emits a shell prompt (e.g., `bash-5.2$ `). The `output_task` wakes up, reads the prompt bytes, and calls `await websocket.send_text(...)`. If the WebSocket client connects before the PTY emits the prompt, `websocket.send_text()` succeeds and the user sees the prompt. But if the PTY emits the prompt **before** the WebSocket accepts (i.e., before `await websocket.accept()`), the output is lost: the `output_task` does not exist yet at that point. The session is created (SSH PTY started) before the WebSocket connection exists. The initial `bash` prompt is buffered in asyncssh's internal StreamReader buffer, but if asyncssh's buffer fills or the process emits the prompt before `session_manager.create_session()` returns (which it may on fast hosts), those bytes are already in the PTY's output queue when `read_output` starts. This generally works. The actual silent failure is different.

The real silent failure: on macOS, `asyncssh.create_process()` with `term_type="xterm-256color"` returns a process whose `stdout` is an `asyncssh.SSHReader`. The `read(4096)` call returns **empty bytes** (`b""`) when the remote process exits (EOF), which breaks the loop with `break`. But when the PTY is alive and waiting for input, `read(4096)` blocks indefinitely. The `output_task` cannot run again until data arrives. Meanwhile, the main loop is at `await websocket.receive_text()`. If the browser never sends anything (user is just watching output), the `while True` loop is stuck. Meanwhile, the server is producing output (e.g., `watch` command, log tailing) but the `output_task` is blocked waiting for `read(4096)` to return. This creates the appearance of a working WebSocket that delivers no output — the classic "silent failure" symptom reported.

**Why it happens:**
`asyncssh.SSHClientProcess.stdout.read(N)` for a PTY does not perform a non-blocking read; it blocks until `N` bytes are available or EOF. The `asyncio.sleep(0.01)` after each read iteration never runs because `read()` itself suspends the coroutine. The output loop effectively becomes: block → receive data → send → block → repeat. This is actually correct for a streaming terminal — it will forward all output. The "silent" symptom only appears if the `output_task` is not yet scheduled when the browser's WebSocket handler starts polling. On macOS with the asyncio event loop default policy (`asyncio.DefaultEventLoopPolicy`), task scheduling can delay `output_task`'s first wake by one event loop iteration, causing the user to see no output for the first few hundred milliseconds.

The deeper silent failure is when `session_manager.create_session()` is called but the HTTP transport is **stdio mode** — the `handle_start_interactive_shell` tool returns a URL pointing to `localhost:8080` even when the server is not running in HTTP mode. The MCP client has no WebSocket server to connect to, so the tool response contains a URL that 404s. This is the primary reported bug.

**Why the tool returns nothing:** When called in stdio mode (default mode for Claude Desktop), `handle_start_interactive_shell` returns a URL like `http://localhost:8080/shell/{session_id}`. The HTTP server is not running. The AI client sees a valid JSON response with `status: success` but the URL is unreachable. The user gets a URL, clicks it, gets a connection refused error. The fix is not to the WebSocket code itself but to detect that HTTP mode is not active and return a meaningful error instead of a dead URL.

**Consequences:**
- User tries the URL from `start_interactive_shell` in a browser and gets connection refused.
- No error in MCP logs; tool returned `status: success`.
- AI assistant does not know the session is unusable.

**Prevention:**
1. `handle_start_interactive_shell` must check whether the HTTP server is active before creating a session. If the server is in stdio mode, return an error: `{"status": "error", "message": "Interactive shell requires --http mode. Start the server with --http flag."}`.
2. Add a boolean flag to the server (e.g., `server.http_mode = True`) set at startup in HTTP mode, readable by the handler.
3. Alternatively, gate the `start_interactive_shell` tool on an HTTP-mode env variable (`MCP_HTTP_PORT` being set).
4. In the WebSocket handler, if the PTY stdout emits nothing within 2 seconds of connection, send a heartbeat or status message — do not leave the browser with a blank terminal.

**Warning signs:**
- `handle_start_interactive_shell` returns `status: success` but the user immediately gets a 404 or connection refused on the URL.
- The `session_id` in the response is valid but no session exists in `shell_session_manager.sessions` because the tool is running in a different process or stdio mode.
- `MCP_HTTP_PORT` env var is not set but the URL uses port 8080 (default fallback).

**Phase to address:**
Phase fixing interactive shell. The HTTP-mode detection check is the primary fix; it must be a quality gate before the phase is complete.

---

### Pitfall 3: SSH Credential Flow Requires Device Registration Before Keyring Lookup — First-Time Callers Hit the Wrong Error Path

**What goes wrong:**
`resolve_ssh_credentials()` in `ssh_tools.py` implements a three-tier lookup:
1. Explicit `password` or `key_path` → use immediately.
2. Keyring lookup via `list_credentials(credential_type="ssh")` → matches by `hostname`.
3. SQLite `get_credential_by_hostname(hostname, username)`.
4. Default `mcp_admin` key.

Tier 2 checks `credential_registry.json` for entries matching the target hostname. The registry is populated by `register_credential()` — which is only called by the `homelab-mcp credentials add` CLI subcommand. The `credentials add` command calls `store_credential()` (keyring) and then `register_credential()` (registry).

**The bug:** If the user runs `credentials add hostname=192.168.1.10 username=ubuntu password=secret`, both the keyring entry and registry entry are created. But if the user then calls the `ssh_execute_command` tool with `hostname=192.168.1.10` and no explicit credentials, Tier 2 runs, finds the registry entry for `192.168.1.10`, looks up `get_credential("192.168.1.10", "ubuntu")` from keyring — which returns `"secret"` — and auto-injects. This works correctly.

The broken path is when the user calls `ssh_discover_system` or `ssh_execute_command` **before** running `credentials add`. The tool falls through Tiers 2 and 3 to Tier 4 (default `mcp_admin` key). If `mcp_admin` key exists but the target host does not accept it, the connection fails with `Permission denied`. The error message says: `"No credentials found for {hostname}. Store them with credentials add or pass password/key_path explicitly."` — but only if no credential is found at all. If the `mcp_admin` key path exists but authentication fails, asyncssh raises `asyncssh.PermissionDenied` which propagates as a different error, not the helpful credentials message.

The AI agent's workflow breaks here: after seeing `PermissionDenied`, the agent does not know whether to try `credentials add` or whether the key is simply wrong. The agent cannot distinguish "no credentials configured" from "credentials configured but rejected". The reported bug is that the agent needs to:
1. Recognize the host is not yet registered (`list_devices` shows no entry).
2. Know to try `credentials add`.
3. Know that `credentials add` creates a registry entry.
4. Then retry the SSH tool.

None of this is visible in the current error messages from `PermissionDenied`.

**Why it happens:**
The credential flow was designed as a transparent fallback chain for backwards compatibility. But the AI agent interacts via natural language, not code. An opaque `asyncssh.PermissionDenied` exception with a generic error message does not guide the agent to the correct remediation step. The keyring registry (separate from the SQLite credential store) is not mentioned in tool descriptions.

**Consequences:**
- AI agent loops on `Permission denied` errors without knowing to call `credentials add`.
- Users who run `ssh_execute_command` before `credentials add` get a confusing error that mentions `mcp_admin` when they are trying to use their own credentials.
- The Tier 3 SQLite lookup (`get_credential_by_hostname`) is a legacy path from before keyring was added. The two credential stores (keyring registry and SQLite) create ambiguity about which one the tool uses.

**Prevention:**
1. Wrap `asyncssh.PermissionDenied` in a structured error that distinguishes "no credentials configured" vs "credentials configured but rejected":
   - If Tier 2 and 3 both miss (no registry/SQLite entry): `"No stored credentials for {hostname}. Run: homelab-mcp credentials add hostname={hostname} username=... password=..."`.
   - If Tier 2 or 3 finds credentials but SSH rejects them: `"Stored credentials for {hostname} were rejected. Verify credentials with: homelab-mcp credentials list"`.
2. Add `"credential_registered": false` to the `ssh_execute_command` error response when no credentials exist in either store.
3. TDD: write a test where `resolve_ssh_credentials` returns a valid `SSHCredentials` but `asyncssh.connect` raises `PermissionDenied`, and assert the error message includes the remediation hint.

**Warning signs:**
- AI agent calls `ssh_execute_command` repeatedly after `PermissionDenied` without trying `credentials add`.
- `PermissionDenied` error text does not include any reference to `credentials add`.
- A Tier 4 fallback (`mcp_admin` key) silently attempts connection and fails — the user sees "Permission denied (publickey)" not "No credentials found".

**Phase to address:**
Phase fixing SSH credential flow. The structured error differentiation must be a quality gate.

---

### Pitfall 4: `_tofu_lock` Is an `asyncio.Lock` Used from a Synchronous Callback — It Is Unreachable Dead Code

**What goes wrong:**
`_tofu_lock = asyncio.Lock()` is declared at module level in `ssh_connection.py`. The docstring of `_store_host_key` says "Uses the module-level _tofu_lock to prevent duplicate entries". But `_store_host_key` never references `_tofu_lock`. More importantly, `asyncio.Lock` can only be acquired with `await lock.acquire()` — which requires being inside an `async` function. `_store_host_key` is a regular synchronous method (called from the synchronous `validate_host_public_key`). There is no mechanism to `await` inside a sync method.

If v1.4 work modifies `_store_host_key` or adds any locking, the developer will be tempted to add `loop = asyncio.get_event_loop(); loop.run_until_complete(lock.acquire())`. This deadlocks on Python 3.10+: calling `loop.run_until_complete()` from within a running event loop raises `RuntimeError: This event loop is already running`. On macOS with the default asyncio policy, the loop is always running during asyncssh callbacks.

**Why it happens:**
The lock was intended when `_store_host_key` was presumably planned to be async. It was never implemented correctly because asyncssh's `SSHClient.validate_host_public_key` must be synchronous.

**Consequences:**
- `_tofu_lock` is dead code; concurrent TOFU can produce duplicate `known_hosts` entries.
- Any developer adding lock acquisition in `_store_host_key` will deadlock the server.

**Prevention:**
1. Replace `_tofu_lock = asyncio.Lock()` with `_tofu_lock = threading.Lock()` (from the standard library).
2. Use `with _tofu_lock:` inside `_store_host_key` — this is safe from a sync method.
3. Alternatively, accept duplicate entries as harmless (asyncssh uses first match) and remove the lock entirely, replacing it with a comment explaining the design decision.
4. If the lock is replaced, add a test: spawn two `asyncio.create_task` coroutines that call `ssh_connect` to the same new host concurrently and assert the `known_hosts` file has exactly one entry afterward.

**Warning signs:**
- `asyncio.Lock` present in `ssh_connection.py` but never `await`ed anywhere in the module.
- Any `loop.run_until_complete()` or `asyncio.run()` call added inside `_store_host_key` or `_host_has_stored_key`.
- PR adding lock acquisition inside a synchronous method that is called from asyncssh callbacks.

**Phase to address:**
Phase fixing TOFU known_hosts. Fix or remove the dead lock before the phase is marked complete.

---

### Pitfall 5: Fixing the Interactive Shell Silently Breaks the 635-Test Suite via `session_manager` Import Side Effects

**What goes wrong:**
`shell_session.py` creates a module-level singleton: `session_manager = ShellSessionManager()`. `http_app.py` imports it: `from .shell_session import session_manager as shell_session_manager`. This singleton is created at import time. Any test that imports `http_app` (directly or transitively through `server.py`) triggers creation of the `ShellSessionManager` and its cleanup loop. If a test triggers `start_cleanup_task()`, an `asyncio.Task` is created in the background. If that task outlives the test's event loop, pytest-asyncio raises `RuntimeWarning: coroutine was never awaited` or the task logs errors into the test's caplog.

Additionally, `http_app.py` uses `shell_session_manager.start_cleanup_task()` inside the Starlette lifespan. If tests call `create_http_app()` without going through the full lifespan (common in unit tests), the cleanup task is never started — but any test that directly calls `session_manager.create_session()` will not have a cleanup loop running and sessions will accumulate in the in-memory dict.

The v1.4 fix for the interactive shell will add new code paths (e.g., HTTP-mode detection, PTY output flushing on connect) to `http_app.py` and/or `shell_session.py`. Any import of these modules in test setup will trigger the module-level `session_manager` creation. If v1.4 adds an `asyncio.Task` at module import time (e.g., auto-starting the cleanup task), this will break all 635 tests that create their own event loop via `@pytest.mark.asyncio`.

**Why it happens:**
Module-level singletons with async behavior are a known source of test isolation failures. The existing code avoids this by only starting the cleanup task in the lifespan context manager. But v1.4 changes to `shell_session.py` are likely to add new module-level state or tasks.

**Consequences:**
- Tests pass locally but fail in CI with `RuntimeWarning: Enable tracemalloc to get the object allocation traceback`.
- Test event loops leak tasks, causing `pytest-asyncio` to report unhandled exceptions from cleanup tasks.
- 635 currently-passing tests may start failing with cryptic event loop errors after the shell fix.

**Prevention:**
1. Never call `asyncio.create_task()` at module import time or in `__init__` of singleton managers.
2. The `start_cleanup_task()` pattern (only starts when explicitly called) is already correct — do not change it to auto-start on construction.
3. Any new module-level state added to `shell_session.py` must be plain Python objects (dicts, lists), not asyncio primitives.
4. After v1.4 changes, run the full test suite with `--tb=short -q` and check for `RuntimeWarning` or `Task was destroyed but it is pending` messages — these indicate leaked async tasks from module-level initialization.
5. If HTTP-mode detection requires a new module-level flag, make it a simple `bool` set at server startup, not an asyncio primitive.

**Warning signs:**
- Any `asyncio.create_task()` call added inside `ShellSessionManager.__init__()` or at module level in `shell_session.py`.
- Tests start failing with "Event loop is closed" after importing `http_app` or `shell_session`.
- `pytest -x` exits at the first test that imports `http_app` after v1.4 changes.

**Phase to address:**
All v1.4 phases. Run the full test suite after every module-level change to `shell_session.py` and `http_app.py`.

---

## Moderate Pitfalls

---

### Pitfall 6: asyncssh `create_process()` Without `request_pty=True` Produces a Non-PTY Session on Some SSH Servers

**What goes wrong:**
`shell_session.py` calls `connection.create_process(term_type="xterm-256color", term_size=(24, 80))`. This is the asyncssh way to request a PTY. The `term_type` parameter implies PTY allocation. However, on some OpenSSH server configurations (`/etc/ssh/sshd_config` with `PermitTTY no` or on Proxmox node VMs with restricted SSH configs), the PTY request is rejected silently — the process starts without a PTY. In non-PTY mode, the shell may not emit a prompt (many shells check `isatty()` and suppress prompts), producing the "silent" failure symptom: WebSocket connects, shell starts, no prompt appears.

**Why it happens:**
asyncssh's `create_process(term_type=...)` sends a PTY request as part of the channel open sequence. If the server refuses the PTY, asyncssh does not raise an exception by default — it proceeds with a non-PTY channel. The `process.stdout` stream still works, but the shell on the remote end runs without a terminal, so many interactive features (prompts, readline, color) are suppressed.

**Prevention:**
1. Pass `request_pty=True` explicitly in `create_process()` (asyncssh parameter for strict PTY enforcement).
2. After creating the process, check `process.get_extra_info('connection')` or catch the PTY failure via asyncssh's `channel_open_error` callback.
3. If PTY is denied, close the connection and return a structured error: `"Interactive shell requires PTY support. Verify PermitTTY is enabled on the SSH server."`.

**Warning signs:**
- WebSocket connects, terminal is blank, no prompt appears.
- Remote shell does not respond to `Enter` keystrokes.
- `ssh -t host bash` works in the user's own terminal but the MCP tool produces a blank session.

**Phase to address:**
Phase fixing interactive shell.

---

### Pitfall 7: `known_hosts` File Lookup by IP vs Hostname Mismatch After `credentials add`

**What goes wrong:**
`credentials add hostname=192.168.1.10` stores `192.168.1.10` in the credential registry. `ssh_connect()` passes `host="192.168.1.10"` to asyncssh, which stores the TOFU key under the label `192.168.1.10` (plain hostname for port 22). If the same host was previously discovered by `ssh_discover_system` using its DNS name (e.g., `proxmox.local`), the `known_hosts` file contains an entry for `proxmox.local` but NOT for `192.168.1.10`. The new SSH connection to `192.168.1.10` triggers TOFU for the IP address label — which succeeds and stores a second entry. Now the file has two entries for the same physical host. Not a security problem, but leads to confusion and unnecessary TOFU entries accumulating.

**Why it happens:**
asyncssh uses the exact string passed as `host` as the key in `known_hosts`. There is no DNS resolution normalization before file lookup. OpenSSH handles this by doing DNS lookup and storing both hostname and IP; asyncssh does not do this by default.

**Prevention:**
1. Normalize the `hostname` parameter in `ssh_connect()` to always use IP address (via `socket.getaddrinfo`) or always use DNS name — pick one and be consistent.
2. Alternatively, pass `known_hosts=None` and manage all host key verification through `TOFUSSHClient` exclusively (remove asyncssh's built-in `known_hosts` checking). This makes all host key validation go through the custom code.
3. Document the normalization choice in `ssh_connection.py`.

**Warning signs:**
- `known_hosts` file has multiple entries for different labels that resolve to the same IP.
- TOFU log message fires on a host the user is confident has been connected to before.
- `ssh_discover_system` with `hostname="proxmox.local"` and `ssh_execute_command` with `hostname="192.168.1.50"` (same host) each trigger separate TOFU entries.

**Phase to address:**
Phase fixing TOFU known_hosts.

---

### Pitfall 8: `asyncio.sleep(0.01)` in the WebSocket Output Loop Is a Busy-Wait That Masks Output Ordering Issues

**What goes wrong:**
`read_output()` in `handle_shell_websocket` calls `await session.process.stdout.read(4096)` then `await asyncio.sleep(0.01)`. The `sleep(0.01)` is intended to yield the event loop to allow other tasks (like `websocket.receive_text()`) to run. But `asyncio.process.stdout.read(4096)` already yields the event loop when no data is available — it suspends the coroutine until data arrives. The `asyncio.sleep(0.01)` after the read is therefore:
- Redundant when data was read (the read already yielded).
- A 10ms artificial delay between data chunks when output is arriving continuously (e.g., `cat /var/log/syslog`).

More importantly, the output task and the receive loop are separate tasks but share the same `session` object. If the WebSocket client sends a `resize` message while `read_output` is blocked on `stdout.read(4096)`, the resize is processed promptly. However, if the client sends input that generates a burst of output, the event loop must service both the output read and the WebSocket receive in interleaved fashion. On macOS with high-frequency terminal output, there may be visible lag.

**Why it happens:**
The `sleep(0.01)` is a defensive yield that was added to ensure the input loop gets scheduled. It is not incorrect but is unnecessary. The real issue is that the code structure is correct (two concurrent tasks, one for reads, one for writes) but the `asyncio.sleep` was added as a safety net rather than understanding the asyncio scheduling model.

**Prevention:**
1. Remove the `asyncio.sleep(0.01)` — asyncssh's `stdout.read()` is already a proper coroutine that yields to the event loop.
2. If yield is needed for testing purposes, use `await asyncio.sleep(0)` (zero duration, which yields once and immediately reschedules).
3. Document why the sleep was removed to prevent it from being re-added.

**Warning signs:**
- Terminal output in the browser feels "chunky" or arrives in batches rather than smoothly.
- High-throughput commands (e.g., `dd` with verbose output) are 10ms slower per chunk than expected.

**Phase to address:**
Phase fixing interactive shell (minor fix, low risk).

---

### Pitfall 9: Fixing `resolve_ssh_credentials` May Break the SQLite Tier-3 Fallback That Existing Tests Rely On

**What goes wrong:**
`resolve_ssh_credentials()` has three tiers: explicit → keyring registry → SQLite. The SQLite tier calls `db.get_credential_by_hostname(hostname, username)` — a legacy path that existed before keyring was added. The existing test suite (635 tests) likely has tests that mock or use the SQLite credential lookup directly. If v1.4 changes the credential lookup priority or short-circuits the SQLite path (e.g., to fix the "requires device registration" bug), existing tests that mock `get_credential_by_hostname` will continue to pass but the new behavior will be untested.

The deeper risk: if v1.4 adds a clear error message for "no credentials found" by removing the silent fallthrough to the `mcp_admin` key, any test that relied on the silent fallthrough (connecting via `mcp_admin` when no credentials are stored) will start failing with `ValueError: No credentials found for {hostname}`. This is the correct new behavior but will appear as regressions unless the test suite is updated.

**Why it happens:**
The credential fallback chain was designed to be maximally permissive (never fail if any path works). Making it fail fast with actionable errors changes the observable behavior and will break tests written against the old behavior.

**Prevention:**
1. Before changing `resolve_ssh_credentials`, audit all tests that mock or call it. Look for tests that rely on the `mcp_admin` key fallback with no explicit credentials.
2. Update those tests to either provide explicit credentials or mock `list_credentials()` to return the expected registry entry.
3. Add a TDD wave-0 test that asserts the new error behavior before changing the implementation.
4. Use `git grep "resolve_ssh_credentials\|get_credential_by_hostname\|mcp_admin" tests/` before writing the fix.

**Warning signs:**
- Unexpected `ValueError: No credentials found` in tests that were passing before.
- `test_ssh_execute_command_defaults_to_mcp_admin` or similar test names that relied on the fallthrough.
- More than 10 tests failing after changing `resolve_ssh_credentials` behavior.

**Phase to address:**
Phase fixing SSH credential flow. Audit test suite before implementation.

---

## Minor Pitfalls

---

### Pitfall 10: The `initial_command` in `create_session()` Is Sent Before the Shell Is Ready

**What goes wrong:**
`shell_session.py` calls `connection.create_process(...)` which returns a `process` object. Then `session_manager.create_session()` returns. In `handle_shell_websocket`, after `await websocket.accept()`, the initial command is immediately written to `process.stdin`:
```python
if session.initial_command and session.process.stdin:
    session.process.stdin.write(session.initial_command + "\n")
```
The PTY process may not have emitted its shell prompt yet when the command is written. On fast hosts this works. On slow hosts or VMs with slow shell startup (e.g., those loading heavy `.bashrc`), the command lands before the shell is ready to interpret it, resulting in literal characters appearing in the terminal before the prompt.

**Prevention:**
Wait for the first output from the PTY (the shell prompt) before sending the initial command. A 500ms `asyncio.sleep` after process creation is a crude but effective workaround. A better approach: read until a prompt character (`$` or `#`) appears or until 2 seconds pass, then send the command.

**Phase to address:** Phase fixing interactive shell (minor, low priority).

---

### Pitfall 11: `credential_registry.json` and OS Keyring Can Get Out of Sync After Keyring Backend Changes

**What goes wrong:**
`credential_registry.json` stores `{hostname, username, credential_type}` as enumerable metadata; the actual password lives in the OS keyring. On macOS, if the user migrates their keychain, deletes a keychain entry manually, or the keyring backend changes (e.g., installs `keyrings.alt`), `list_credentials()` returns entries from the registry but `get_credential()` returns `None` for those entries. `resolve_ssh_credentials()` finds a registry match, calls `get_credential()` → returns `None` → the `if keyring_password:` check fails → falls through to SQLite tier → likely finds nothing → falls to `mcp_admin` key. The user sees a confusing `Permission denied (publickey)` error when they believe they have stored credentials.

**Prevention:**
When `get_credential()` returns `None` for a host that IS in the registry, log a warning: `"Credential registered for {hostname} but keyring returned None — credential may have been deleted from OS keyring. Re-run: homelab-mcp credentials add hostname={hostname} ..."`.

**Phase to address:** Phase fixing SSH credential flow (low severity, add warning log only).

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| asyncssh `validate_host_public_key` | Using `asyncio.Lock` inside synchronous callback | Use `threading.Lock` — the callback runs synchronously within the async SSH connection flow |
| asyncssh `create_process()` PTY | Assuming PTY is always granted | Check for non-PTY fallback; `term_type` parameter requests but does not guarantee a PTY |
| asyncssh `known_hosts` + `client_factory` | Assuming `validate_host_public_key` is always called | It is only called when the key is NOT in the `known_hosts` file; if key is present, asyncssh validates internally |
| WebSocket + asyncio tasks | Creating `asyncio.Task` before `websocket.accept()` | The output task and input loop are fine as concurrent tasks, but the output task must be created after `await websocket.accept()` |
| `shell_session.py` module singleton | Starting background tasks in `__init__` | Explicitly call `start_cleanup_task()` only in lifespan context; never at import time |
| `resolve_ssh_credentials` silent fallthrough | Relying on `mcp_admin` key fallthrough for any non-mcp_admin user | Explicit error when no credentials found; do not silently attempt mcp_admin for non-mcp_admin usernames |
| `credential_registry.json` + keyring | Not checking for registry/keyring desync | Log actionable warning when registry entry exists but keyring returns `None` |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Interactive shell fix | Silent failure if server is not in HTTP mode | Detect HTTP mode in handler; return error not dead URL |
| Interactive shell fix | PTY not granted by SSH server | Check PTY allocation; structured error if denied |
| Interactive shell fix | `asyncio.Task` at module import breaking test isolation | Never start cleanup task in `__init__` or at module level |
| SSH credential flow fix | Breaking existing tests that rely on `mcp_admin` fallthrough | Audit tests before changing `resolve_ssh_credentials` behavior |
| SSH credential flow fix | `PermissionDenied` not differentiated from "no credentials" | Wrap asyncssh exception with credential-state context |
| TOFU known_hosts fix | `asyncio.Lock` used in synchronous callback — deadlocks | Replace with `threading.Lock` or remove entirely |
| TOFU known_hosts fix | IP vs hostname label mismatch creating duplicate entries | Normalize hostname in `ssh_connect()` or use IP-only labels |
| Any phase | Test suite (635 tests) failing due to module-level async state | Run full suite after each module-level change; watch for `RuntimeWarning` |

---

## "Looks Done But Isn't" Checklist

- [ ] **HTTP-mode detection in interactive shell tool:** Call `start_interactive_shell` from stdio mode (default Claude Desktop setup) and verify the response is an actionable error, not a dead URL.
- [ ] **PTY is actually granted:** Connect to a Proxmox LXC container via the interactive shell and verify the bash prompt appears in the browser terminal (not a blank screen).
- [ ] **`_tofu_lock` is not `asyncio.Lock`:** Grep `ssh_connection.py` for `asyncio.Lock` — should return no results after fix.
- [ ] **Concurrent TOFU produces one `known_hosts` entry:** Run two concurrent `ssh_connect` calls to the same new host and assert the `known_hosts` file has exactly one entry.
- [ ] **Actionable error on no credentials:** Call `ssh_execute_command` for a host with no credentials and assert the error message contains `credentials add`.
- [ ] **Actionable error on wrong credentials:** Call `ssh_execute_command` for a host with a registry entry but wrong password (keyring returns wrong value) and assert the error message references `credentials list`.
- [ ] **635 tests still pass:** Run `uv run pytest tests/ -m "not integration" -q` after every phase — no new failures.
- [ ] **No `RuntimeWarning: Task was destroyed`:** After all fixes, run `uv run pytest tests/ -W error::RuntimeWarning` to surface any leaked asyncio tasks.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Interactive shell returns dead URL in stdio mode | MEDIUM — user-visible bug, no data loss | Add HTTP-mode check to handler; hotfix release |
| PTY not granted silently | MEDIUM — silent failure, hard to diagnose without fix | Add structured error; release patch |
| `asyncio.Lock` deadlock on TOFU | HIGH — server hangs on first SSH connection to new host | Replace with `threading.Lock` immediately; hotfix release |
| Concurrent TOFU duplicate entries | LOW — cosmetic, no functionality impact | Accept duplicates as harmless OR add `threading.Lock` |
| `resolve_ssh_credentials` breaking existing tests | MEDIUM — CI red, blocks release | Audit and update test mocks before merging |
| IP vs hostname `known_hosts` mismatch | LOW — extra TOFU entries, no security risk | Normalize hostname in `ssh_connect()` |
| Registry/keyring desync | LOW — confusing error message | Add warning log; user re-runs `credentials add` |

---

## Sources

- Project codebase: `src/homelab_mcp/ssh_connection.py`, `src/homelab_mcp/shell_session.py`, `src/homelab_mcp/http_app.py`, `src/homelab_mcp/ssh_tools.py`, `src/homelab_mcp/credential_store.py`, `src/homelab_mcp/tool_handlers/ssh_handlers.py` — first-party code inspection (HIGH confidence)
- asyncssh `SSHClient.validate_host_public_key` API contract: synchronous callback only — verified from asyncssh source and documentation pattern (HIGH confidence from training data; verify with asyncssh docs if behavior changes post-2.18)
- asyncio `Lock` cannot be acquired from synchronous context running within a running event loop — Python 3.10+ `RuntimeError: This event loop is already running` behavior (HIGH confidence, Python standard library)
- asyncssh `known_hosts` + `client_factory` dual-validation behavior: asyncssh validates internally when key is in file, calls client callback only on unknown keys (HIGH confidence from asyncssh documentation pattern and code behavior)
- `threading.Lock` is safe to acquire from synchronous callbacks called within asyncio coroutines — standard Python threading documentation (HIGH confidence)

---

---

## Appendix: v1.3 Credentials & Release Automation Pitfalls

> Preserved from prior milestone research. These pitfalls are addressed in v1.3.

**Domain:** Python CLI tool — adding OS keyring credential storage and GitHub Actions PyPI release automation
**Researched:** 2026-03-14

### Critical: Keyring `NoKeyringError` Crashes the Server on Headless Linux

Wrap all keyring calls in `try/except (keyring.errors.NoKeyringError, RuntimeError, Exception)`. Fall back to SQLite. Never call keyring at module import time. **Completed in v1.3** (lazy imports inside each function body in `credential_store.py`).

### Critical: Argparse Subparsers Break the Existing Bare Invocation

`parser.set_defaults(func=_run_server)` + `subparsers.required = False` + dispatch via `getattr(args, 'func', _run_server)(args)`. **Completed in v1.3**.

### Critical: PyPI OIDC Trusted Publishing Fails with `invalid-publisher`

Workflow filename, environment name, and package name must exactly match the PyPI trusted publisher registration. **Completed in v1.3**.

### Critical: CI Double-Publish on Non-Tag Push

Separate publish workflow file (`publish.yml`) triggered only by `on: push: tags: ['v*']`. **Completed in v1.3**.

### Critical: Credential Leak Through Exception Messages

All exception logging in `ssh_tools.py` and `proxmox_api.py` must use `sanitize_error(e)`. **Completed in v1.3**.

### Critical: Auto-Inject Silently Overrides Explicitly Passed Credentials

Priority order enforced by tests before implementation. `credential_source` included in tool response. **Completed in v1.3**.

### Critical: Version in `pyproject.toml` Does Not Match Git Tag

CI step asserts `pyproject.toml` version equals tag name before build job runs. **Completed in v1.3**.

*v1.3 pitfalls section condensed. Full detail in git history of this file.*

---

---

## Appendix: v1.2 Protocol Completeness Pitfalls

> Preserved from prior milestone research. These pitfalls are addressed in v1.2.

**Researched:** 2026-03-12

Addressed: `service_templates` YAML files excluded from wheel; version mismatch `pyproject.toml` vs `__init__.py`; `*_preview` tools missing from `tool_annotations.py`; renaming existing destructive tools breaks MCP clients; `homelab://drift/latest` URI omitted from resources dict; drift Resource serving stale data; drift Resource crashing when no scan has run.

*v1.2 pitfalls section condensed. Full detail in git history of this file.*

---

---

## Appendix: v1.1 Safety & Observability Pitfalls

> Preserved from prior milestone research. These pitfalls are addressed in v1.1.

**Researched:** 2026-03-11

Addressed: dry-run handler that cannot execute the real path; dry-run performing real side effects; drift detection flagging transient state; MCP Resources returning stale data; `ResourceManager.proxmox_session` not wired into handlers; drift baseline not updated after mutation tools.

*v1.1 pitfalls section condensed. Full detail in git history of this file.*

---

*Pitfalls research for: homelab-mcp v1.4 — interactive shell fix, SSH credential flow, TOFU known_hosts*
*Researched: 2026-03-13*
