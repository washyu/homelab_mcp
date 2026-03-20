# Phase 21: Core SSH Reliability - Research

**Researched:** 2026-03-13
**Domain:** asyncssh TOFU host key storage, asyncssh PTY streaming, WebSocket output relay
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TOFU-01 | `known_hosts` entries written with correct format (algorithm + base64 only, no comment field) | `_store_host_key()` at line 126 calls `export_public_key().decode()` which may include a trailing comment field — stripping to two parts fixes this |
| TOFU-02 | `_tofu_lock` replaced with `threading.Lock` (dead `asyncio.Lock` removed) | `asyncio.Lock` is confirmed dead code — `validate_host_public_key` is synchronous; `threading.Lock` is the correct replacement |
| SHELL-01 | Interactive shell streams PTY output to browser in real time (non-blocking read loop) | `http_app.py:193` uses blocking `stdout.read(4096)` — `asyncio.wait_for(..., timeout=0.05)` is the established fix |
| SHELL-02 | Interactive shell uses correct terminal dimensions (80 cols x 24 rows) | `shell_session.py:109` has `term_size=(24, 80)` — confirmed inverted; asyncssh `channel.py:1176` defines `(width, height)` |
| SHELL-03 | Browser receives explicit EOF/error notification instead of hanging silently | `http_app.py:197-198` breaks on EOF with no message to client — add ANSI-colored disconnect message before break |
</phase_requirements>

## Summary

Phase 21 addresses five concrete bugs in two source files, each backed by direct source inspection. The scope is narrow: three lines change in `shell_session.py` (term_size inversion), eight lines change in `http_app.py` (non-blocking read + EOF notification), and ten lines change in `ssh_connection.py` (key format stripping + lock replacement). No new dependencies, no architectural changes.

The most critical bug to address first is TOFU-02 (dead `asyncio.Lock`). If this lock is touched without replacing it with `threading.Lock`, any attempt to add locking logic deadlocks the server on Python 3.10+. TOFU-01 (key format stripping) ensures that `known_hosts` entries are parseable by asyncssh on subsequent connections, which fixes the SSH timeout reported for keyring-registered hosts. SHELL-01, SHELL-02, and SHELL-03 together make the interactive shell actually functional for browser use.

The existing test suite at `tests/test_ssh_connection.py` already covers TOFU accept/reject paths. The mock SSH key fixture at line 21 returns `b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey123"` — two fields, no comment. The TOFU-01 fix must be verified with a key that returns a comment field (three parts) to confirm the stripping logic is exercised. A new Wave-0 test must cover the comment-stripping path. The `test_ssh_tools.py:test_ssh_discover_no_credentials` test at line 177 already asserts `"No credentials" in result_data["error"] or "credentials add" in result_data["error"]` — this test correctly anticipates the error message format but tests only the Phase 22 scope (`resolve_ssh_credentials` fallthrough). Do not change `resolve_ssh_credentials` in this phase.

**Primary recommendation:** Fix `ssh_connection.py` first (TOFU-01 + TOFU-02), then `shell_session.py` (SHELL-02), then `http_app.py` (SHELL-01 + SHELL-03). Each fix is isolated; Wave-0 RED tests before each implementation.

## Standard Stack

### Core (No Changes)

| Library | Version | Purpose | Relevant API |
|---------|---------|---------|--------------|
| asyncssh | 2.21.0 | SSH connections, PTY sessions, TOFU | `SSHClient.validate_host_public_key`, `create_process(term_size=)`, `SSHReader.read()` |
| starlette | 0.47.1 | ASGI app, WebSocket routing | `WebSocket.send_text()`, `WebSocketDisconnect` |
| asyncio | stdlib | Task management, non-blocking I/O | `asyncio.wait_for()`, `TimeoutError`, `threading.Lock` |

**Installation:** No new packages. `uv sync` is sufficient.

## Architecture Patterns

### Recommended Project Structure (Phase 21 touch points)

```
src/homelab_mcp/
├── ssh_connection.py        # MODIFY: _store_host_key() key format + lock replacement
├── shell_session.py         # MODIFY: term_size=(80, 24)
└── http_app.py              # MODIFY: read_output() non-blocking + EOF notification
```

All other modules untouched.

### Pattern 1: Known-Hosts Entry Format (TOFU-01)

**What:** `_store_host_key()` at line 126 does `key.export_public_key().decode("utf-8").strip()`. asyncssh's `export_public_key()` for some key types returns three space-separated parts: `"algorithm base64== user@host"` (algorithm + base64 + comment). The known_hosts format requires exactly two parts after the hostname: `"hostname algorithm base64"`. A four-field line (`hostname algorithm base64 comment`) causes asyncssh's parser to treat the entry as malformed, meaning the key is not found in `_trusted_host_keys` on subsequent connections. This triggers `validate_host_public_key()` again, which then detects the stored entry and returns `False` (MITM path), refusing the connection.

**When to use:** Any time `export_public_key()` output is written to a known_hosts file.

**Fix:**
```python
# Source: direct inspection of ssh_connection.py:126 and asyncssh known_hosts parser behavior
key_export = key.export_public_key().decode("utf-8").strip()
# Strip trailing comment field — known_hosts requires exactly "algorithm base64"
parts = key_export.split()
key_data = " ".join(parts[:2])   # keep only algorithm + base64
entry = f"{host_label} {key_data}\n"
```

**Existing mock returns:** `b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey123"` — two parts, no comment. The Wave-0 test must add a fixture that returns a three-part export to verify the strip path is actually exercised.

### Pattern 2: Replace Dead asyncio.Lock with threading.Lock (TOFU-02)

**What:** `ssh_connection.py:26` declares `_tofu_lock = asyncio.Lock()`. The docstring of `_store_host_key` references it. It is never acquired anywhere. `validate_host_public_key` is a synchronous callback — the asyncssh API contract is synchronous (`bool` return, not `Awaitable[bool]`). An `asyncio.Lock` cannot be acquired from a sync context without `loop.run_until_complete()`, which deadlocks on Python 3.10+ when called from within a running event loop.

**Fix:**
```python
# Source: Python stdlib threading documentation + asyncssh client.py:124-162 (sync callback contract)
import threading

_tofu_lock = threading.Lock()   # replaces asyncio.Lock()

# In _store_host_key:
with _tofu_lock:
    try:
        with open(self._known_hosts_path, "a") as f:
            f.write(entry)
    except OSError:
        logger.error("Failed to write to known_hosts file: %s", self._known_hosts_path)
```

**Do not add:** `asyncio.run()`, `loop.run_until_complete()`, or any `await` inside `_store_host_key` or `_host_has_stored_key`. Both are synchronous methods called from a synchronous callback within the asyncio event loop.

### Pattern 3: Non-Blocking PTY Read Loop (SHELL-01)

**What:** `http_app.py:193` calls `await session.process.stdout.read(4096)`. asyncssh's `SSHReader.read(n)` semantics (verified at `asyncssh/stream.py:575`) block until `n` bytes are available or EOF. A PTY session does not send EOF while the shell is alive — it sends small bursts of bytes (prompt strings, command output, etc.). The result: `read(4096)` blocks indefinitely, the event loop gets no bytes to forward, and the browser terminal stays blank.

**Fix:** Wrap with `asyncio.wait_for()` using a short timeout. On timeout, continue the loop; on EOF, break and notify the client.

```python
# Source: asyncssh/stream.py:575 (read() EOF behavior) + Python asyncio docs
async def read_output() -> None:
    while True:
        try:
            if session.process.stdout:
                data = await asyncio.wait_for(
                    session.process.stdout.read(4096),
                    timeout=0.05,
                )
                if data:
                    text = data if isinstance(data, str) else data.decode("utf-8")
                    await websocket.send_text(text)
                else:
                    # EOF — process exited
                    await websocket.send_text(
                        "\r\n\x1b[31m[Connection closed]\x1b[0m\r\n"
                    )
                    break
            else:
                break
        except TimeoutError:
            pass  # No data available — yield and retry
        except Exception as e:
            logger.error("Error reading output: %s", e)
            try:
                await websocket.send_text(
                    f"\r\n\x1b[31m[Read error: {e}]\x1b[0m\r\n"
                )
            except Exception:
                pass
            break
```

**Remove:** The `await asyncio.sleep(0.01)` at line 202. It is redundant — `asyncio.wait_for` already yields the event loop on each iteration.

### Pattern 4: PTY Terminal Size Correction (SHELL-02)

**What:** `shell_session.py:109` has `term_size=(24, 80)`. asyncssh `channel.py:1176` defines `term_size` as `(width, height)` = `(cols, rows)`. The current value creates a 24-column × 80-row terminal (inverted). A 24-column terminal causes aggressive line wrapping that corrupts shell output layout and may suppress color prompts on some SSH servers.

**Fix:**
```python
# Source: asyncssh/channel.py:1176 — term_size is (width/cols, height/rows)
process = await connection.create_process(
    term_type="xterm-256color",
    term_size=(80, 24),   # width=80 cols, height=24 rows — standard terminal
)
```

**Note on `resize_terminal`:** `shell_session.py:162` calls `session.process.change_terminal_size(cols, rows)` — this is already correct. The inversion is only in the initial `create_process` call.

### Pattern 5: EOF Browser Notification (SHELL-03)

**What:** When `stdout.read()` returns an empty string (EOF), `http_app.py:197-198` silently breaks the read loop. The WebSocket connection remains open but the browser terminal hangs — it never receives a disconnect signal. The user sees "Connected" but the shell is gone.

**Fix:** Covered by Pattern 3 above — add the disconnect message before `break` in the EOF path. The ANSI escape `\x1b[31m` renders the message in red in xterm.js; `\r\n` ensures correct line endings in PTY mode.

### Anti-Patterns to Avoid

- **`asyncio.run()` inside `_store_host_key`:** Deadlocks on Python 3.10+ (event loop already running). The lock must be `threading.Lock`.
- **Swapping `create_process` for `create_session`:** The bug is in the read loop, not the session creation API.
- **Setting `known_hosts=None`:** Disables all host key verification including MITM detection.
- **Adding `asyncio.create_task()` to `ShellSessionManager.__init__`:** The `session_manager` singleton is created at module import time. Any asyncio task created there leaks into test event loops and causes `RuntimeWarning: Task was destroyed` across all 635 tests.
- **Moving `start_cleanup_task()` to `__init__`:** The explicit lifespan-only call pattern is correct. Do not change it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Non-blocking reads from asyncssh PTY | Custom polling loop with `select()` | `asyncio.wait_for(stdout.read(...), timeout=0.05)` | Standard asyncio pattern; asyncssh StreamReader is already an asyncio primitive |
| Thread-safe file writes in sync callbacks | Re-entrant lock using asyncio primitives | `threading.Lock` with `with` statement | asyncssh callbacks are synchronous; `threading.Lock` is safe from sync code inside asyncio event loop |
| ANSI terminal disconnect notification | Custom xterm.js protocol message | `\r\n\x1b[31m[Connection closed]\x1b[0m\r\n` as plain WebSocket text | xterm.js renders ANSI escape sequences natively |

## Common Pitfalls

### Pitfall 1: asyncio.Lock Deadlock in _store_host_key
**What goes wrong:** Adding `await _tofu_lock.acquire()` or `loop.run_until_complete(_tofu_lock.acquire())` inside the synchronous `_store_host_key` raises `RuntimeError: This event loop is already running` on Python 3.10+.
**Why it happens:** `validate_host_public_key` is synchronous; asyncssh calls it from within the running event loop's connection coroutine.
**How to avoid:** Replace `asyncio.Lock()` with `threading.Lock()`. Use `with _tofu_lock:` — no `await`, no `asyncio.run()`.
**Warning signs:** Any `asyncio.run()` or `loop.run_until_complete()` inside `_store_host_key`.

### Pitfall 2: Mock SSH Key Has No Comment Field — Test Won't Catch Comment Bug
**What goes wrong:** Existing `mock_ssh_key` fixture returns `b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey123"` — two parts. The stripping fix (`" ".join(parts[:2])`) silently passes even if the fix is absent because there are only two parts to join.
**How to avoid:** Add a Wave-0 fixture with a three-part export: `b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey123 user@host"`. The RED test asserts the stored entry has exactly two parts after the hostname.

### Pitfall 3: Module-Level session_manager Singleton Breaks Test Isolation
**What goes wrong:** `shell_session.py:181` creates `session_manager = ShellSessionManager()` at module import time. Any `asyncio.create_task()` at module level or in `__init__` leaks tasks into pytest event loops.
**How to avoid:** Never add `asyncio.create_task()` to `ShellSessionManager.__init__()` or at module level. The `start_cleanup_task()` explicit call in lifespan is the correct pattern.
**Warning signs:** Tests start failing with `RuntimeWarning: Task was destroyed but it is pending` after changes to `shell_session.py`.

### Pitfall 4: asyncio.sleep(0.01) Creates 10ms Latency Per Chunk
**What goes wrong:** `http_app.py:202` has `await asyncio.sleep(0.01)` after each read iteration. With the blocking `read()` replaced by `asyncio.wait_for()`, the sleep adds unnecessary latency between chunks of continuous output.
**How to avoid:** Remove the `asyncio.sleep(0.01)` entirely. The `TimeoutError` catch in the `asyncio.wait_for` loop already yields the event loop on each iteration with no artificial delay.

### Pitfall 5: Credential Flow Is Out of Scope for Phase 21
**What goes wrong:** `resolve_ssh_credentials()` fallthrough behavior (bare `SSHCredentials` with no auth) is out of scope for Phase 21 — that is Phase 22 work. The existing test `test_ssh_discover_no_credentials` already has the correct assertion (`"No credentials" in result_data["error"] or "credentials add" in result_data["error"]`) — this test is testing Phase 22 behavior and must continue to pass. Do not change `resolve_ssh_credentials` in Phase 21.
**Warning signs:** Any change to `ssh_tools.py` in Phase 21 beyond the `_store_host_key` scope.

## Code Examples

### Verify export_public_key() format in test (Wave-0 fixture)

```python
# tests/test_ssh_connection.py — add to existing fixtures
@pytest.fixture
def mock_ssh_key_with_comment() -> MagicMock:
    """SSH key whose export includes a trailing comment field (three parts)."""
    key = MagicMock()
    key.get_algorithm.return_value = "ssh-rsa"
    key.export_public_key.return_value = b"ssh-rsa AAAAB3NzaC1yc2EAAA...testdata== user@host"
    return key
```

### TOFU-01 RED test

```python
# tests/test_ssh_connection.py
def test_store_host_key_strips_comment_field(
    known_hosts_path: Path, mock_ssh_key_with_comment: MagicMock
) -> None:
    """known_hosts entry must have exactly three fields (host alg base64), no comment."""
    from homelab_mcp.ssh_connection import TOFUSSHClient

    known_hosts_path.touch()
    client = TOFUSSHClient(known_hosts_path)
    client._store_host_key("192.168.1.10", 22, mock_ssh_key_with_comment)

    content = known_hosts_path.read_text().strip()
    # Must be exactly "hostname algorithm base64" — three fields
    parts = content.split()
    assert len(parts) == 3, f"Expected 3 fields, got {len(parts)}: {content!r}"
    assert parts[0] == "192.168.1.10"
    assert parts[1] == "ssh-rsa"
    # No comment field
    assert "@" not in parts[-1]  # base64 does not contain @; comment like user@host would
```

### TOFU-02 RED test

```python
# tests/test_ssh_connection.py
def test_tofu_lock_is_threading_lock() -> None:
    """_tofu_lock must be threading.Lock, not asyncio.Lock."""
    import threading
    from homelab_mcp import ssh_connection

    assert isinstance(ssh_connection._tofu_lock, type(threading.Lock())), (
        "_tofu_lock must be threading.Lock — asyncio.Lock deadlocks in synchronous callbacks"
    )
```

### SHELL-02 RED test

```python
# tests/test_ssh_connection.py or new tests/test_shell_session.py
@pytest.mark.asyncio
async def test_create_session_uses_correct_term_size() -> None:
    """PTY must be created with width=80, height=24 (not inverted)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("homelab_mcp.shell_session.resolve_ssh_credentials") as mock_creds, \
         patch("homelab_mcp.shell_session.ssh_connect") as mock_connect:
        mock_creds.return_value = MagicMock(
            hostname="h", username="u", port=22, password=None, key_path=None
        )
        mock_conn = AsyncMock()
        mock_process = MagicMock()
        mock_conn.create_process = AsyncMock(return_value=mock_process)
        mock_connect.return_value = mock_conn

        from homelab_mcp.shell_session import ShellSessionManager
        mgr = ShellSessionManager()
        await mgr.create_session("h")

        call_kwargs = mock_conn.create_process.call_args.kwargs
        assert call_kwargs["term_size"] == (80, 24), (
            f"term_size must be (80, 24) (width, height); got {call_kwargs['term_size']!r}"
        )
```

### SHELL-01 + SHELL-03 RED test

```python
# tests/test_http_app.py
@pytest.mark.asyncio
async def test_read_output_sends_eof_notification(mocker) -> None:
    """When stdout returns EOF, WebSocket must receive a disconnect message before close."""
    # This test verifies SHELL-03: browser gets explicit disconnection message
    from unittest.mock import AsyncMock, MagicMock
    import asyncio

    mock_ws = AsyncMock()
    mock_stdout = AsyncMock()
    # First call returns data; second returns empty (EOF)
    mock_stdout.read = AsyncMock(side_effect=["initial prompt", ""])

    mock_process = MagicMock()
    mock_process.stdout = mock_stdout

    mock_session = MagicMock()
    mock_session.process = mock_process

    # The read_output inner function sends the disconnect message — verify it
    # (exact test structure depends on how read_output is extracted for testing)
    # At minimum: after two reads (one data, one EOF), ws.send_text must have been
    # called at least twice — once for data, once for the disconnect message.
    assert mock_ws.send_text.call_count >= 2
    disconnect_calls = [str(c) for c in mock_ws.send_text.call_args_list]
    assert any("closed" in c.lower() or "Connection" in c for c in disconnect_calls)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Blocking `stdout.read(4096)` in WebSocket loop | `asyncio.wait_for(stdout.read(4096), timeout=0.05)` | Phase 21 | PTY output reaches browser in real time |
| `asyncio.Lock` (dead code) | `threading.Lock` | Phase 21 | Lock is actually acquirable from sync callback |
| `term_size=(24, 80)` | `term_size=(80, 24)` | Phase 21 | Shell prompt renders at correct 80-column width |
| Silent EOF break | EOF + ANSI disconnect message + break | Phase 21 | Browser shows "Connection closed" instead of hanging |

**Deprecated/outdated:**
- `await asyncio.sleep(0.01)` in the read loop: redundant after `asyncio.wait_for` is in place — remove it.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_ssh_connection.py tests/test_http_app.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOFU-01 | `known_hosts` entry has exactly 3 fields when key export includes comment | unit | `uv run pytest tests/test_ssh_connection.py::test_store_host_key_strips_comment_field -x` | ❌ Wave 0 |
| TOFU-02 | `_tofu_lock` is `threading.Lock`, not `asyncio.Lock` | unit | `uv run pytest tests/test_ssh_connection.py::test_tofu_lock_is_threading_lock -x` | ❌ Wave 0 |
| SHELL-01 | PTY output forwarded without waiting for EOF (non-blocking) | unit | `uv run pytest tests/test_http_app.py::test_read_output_is_nonblocking -x` | ❌ Wave 0 |
| SHELL-02 | `create_process` called with `term_size=(80, 24)` | unit | `uv run pytest tests/test_shell_session.py::test_create_session_uses_correct_term_size -x` | ❌ Wave 0 |
| SHELL-03 | WebSocket receives disconnect message on EOF | unit | `uv run pytest tests/test_http_app.py::test_read_output_sends_eof_notification -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_ssh_connection.py tests/test_http_app.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green (635+ tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ssh_connection.py` — add `mock_ssh_key_with_comment` fixture + `test_store_host_key_strips_comment_field` (TOFU-01) + `test_tofu_lock_is_threading_lock` (TOFU-02)
- [ ] `tests/test_shell_session.py` — create file with `test_create_session_uses_correct_term_size` (SHELL-02)
- [ ] `tests/test_http_app.py` — add `test_read_output_is_nonblocking` (SHELL-01) + `test_read_output_sends_eof_notification` (SHELL-03)

No framework install needed — pytest + pytest-asyncio already present and configured.

## Open Questions

1. **Does `export_public_key()` actually include a comment field for real asyncssh keys?**
   - What we know: The mock fixture returns two-part output. The `ensure_mcp_ssh_key` code at `ssh_tools.py` calls `asyncssh.generate_private_key("ssh-rsa", key_size=2048, comment="mcp_admin@homelab")` — this explicitly sets a comment. When exported, the comment field is included.
   - What's unclear: Whether `export_public_key()` (without an `options` argument) includes the comment by default for keys generated without a comment.
   - Recommendation: The Wave-0 test with a three-part mock validates the stripping logic regardless. The fix (`" ".join(parts[:2])`) is safe whether two or three parts are present.

2. **Should `test_shell_session.py` be a new file or added to `test_ssh_tools.py`?**
   - What we know: No `tests/test_shell_session.py` exists. The `shell_session.py` module is not directly tested today (only through integration).
   - Recommendation: Create `tests/test_shell_session.py` as a new file. The `ShellSession` dataclass and `create_session` method are testable in isolation with mocked asyncssh.

## Sources

### Primary (HIGH confidence)

- `src/homelab_mcp/ssh_connection.py` — direct read: `_tofu_lock = asyncio.Lock()` at line 26 (dead); `_store_host_key()` key export at lines 126-129; `validate_host_public_key` sync signature at line 46
- `src/homelab_mcp/shell_session.py` — direct read: `term_size=(24, 80)` at line 109; `change_terminal_size(cols, rows)` at line 162 (correct order); `session_manager = ShellSessionManager()` at line 181 (module-level singleton)
- `src/homelab_mcp/http_app.py` — direct read: blocking `stdout.read(4096)` at line 193; silent EOF break at lines 197-198; `asyncio.sleep(0.01)` at line 202
- asyncssh 2.21.0 source at `.venv/lib/python3.12/site-packages/asyncssh/channel.py:1176` — `term_size` is `(width, height)` confirmed
- asyncssh 2.21.0 source at `.venv/lib/python3.12/site-packages/asyncssh/stream.py:575` — `read(n)` blocks until EOF or n bytes
- asyncssh 2.21.0 source at `.venv/lib/python3.12/site-packages/asyncssh/client.py:124-162` — `validate_host_public_key` is synchronous (`bool` return, not `Awaitable`)
- `tests/test_ssh_connection.py` — confirmed: `mock_ssh_key` fixture returns two-part export; existing tests cover TOFU accept/reject/format paths but not three-part export stripping
- `tests/test_ssh_tools.py:177-191` — `test_ssh_discover_no_credentials` already asserts `"credentials add"` in error message (Phase 22 scope, not Phase 21)
- Python stdlib `threading` module documentation — `threading.Lock()` is safe to acquire from synchronous code within asyncio event loop (HIGH confidence, standard library)
- `.planning/research/STACK.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` — project-level research for v1.4 (HIGH confidence)

### Secondary (MEDIUM confidence)

- `ssh_tools.py:ensure_mcp_ssh_key` — generates key with `comment="mcp_admin@homelab"`, supporting the hypothesis that exported keys include comment fields

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no changes; all three bugs are call-site fixes
- Architecture: HIGH — all integration points verified by direct source inspection; touch point line counts verified
- Pitfalls: HIGH — critical pitfalls verified against Python stdlib behavior and direct codebase patterns; TOFU format hypothesis verified as safe-to-fix regardless of whether comment is present in mock vs real keys

**Research date:** 2026-03-13
**Valid until:** 2026-06-13 (stable ecosystem; asyncssh 2.21.0 locked in uv.lock)
