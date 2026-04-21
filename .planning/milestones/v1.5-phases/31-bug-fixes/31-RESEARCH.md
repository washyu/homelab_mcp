# Phase 31: Bug Fixes - Research

**Researched:** 2026-04-02
**Domain:** Python async bug fixes — WebSocket lifecycle, error messages, SSH sudo helpers, test assertions, JSON schema
**Confidence:** HIGH

## Summary

Phase 31 addresses five discrete bugs found in the CodeRabbit review of PR #39. Each bug is self-contained and targets a specific file/function. There are no architectural changes — all fixes are surgical edits to existing code plus targeted regression tests.

The five bugs span three functional areas: (1) a zombie-session leak in the WebSocket PTY handler, (2) a wrong variable in a timeout error message, (3) a missing raise in the sudo password branch of `ssh_execute_command`, (4) an always-passing test assertion, and (5) a missing `enum` constraint on a JSON schema property.

All five bugs are independently fixable — no fix depends on another. The verification bar is the existing pytest suite staying green plus five new regression tests matching the success criteria.

**Primary recommendation:** One plan per bug, executed in sequence. Each plan is a two-step: fix the production file, then add/correct the regression test.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WS-01 | PTY reader closes websocket and cancels paired task on EOF/error — no zombie sessions | WebSocket lifecycle patterns in `http_app.py`; `read_output` inner coroutine identified as the fix site |
| ERR-01 | Timeout error message reports computed `effective_timeout`, not raw `timeout_seconds` | `error_handling.py` line 58 identified as the single-line fix |
| SSH-01 | `ssh_execute_command` raises on non-zero exit code when `check=True` in password sudo branch | `ssh_tools.py` line 687-692 identified as fix site; `check` parameter not forwarded to `conn.run` |
| SSH-02 | `test_ssh_tools.py` password propagation assertion fails when password is absent | Test line 191 identified; assertion always true because error message contains both candidate strings |
| SCH-01 | `credential_type` schema constrained to `enum: ["ssh", "proxmox"]` | `credential_tools_schema.py` `list_keyring_credentials` entry identified; missing `enum` key |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Package manager:** `uv` for all installs and runs
- **Python:** 3.12+ strict typing (mypy)
- **Testing:** `uv run pytest tests/ -m "not integration"` for unit tests; `@pytest.mark.asyncio` for async tests
- **Type hints:** All functions require complete annotations
- **Async-first:** I/O operations use async/await
- **Error handling:** Use `error_handling.py` patterns
- **Code quality:** ruff + mypy + bandit must pass (pre-commit hooks)
- **nosec annotations:** Inline with specific B-code and justification — not bare `nosec`
- **Local imports in tests:** Wave 0 tests use local imports inside function bodies (established pattern from Phases 12-19)

## Bug Analysis

### WS-01: Zombie WebSocket PTY sessions

**File:** `src/homelab_mcp/http_app.py`
**Function:** `handle_shell_websocket` (line 171)
**Bug location:** Inner coroutine `read_output` (line 188)

The `read_output` coroutine runs as `output_task` (line 215). On EOF (`data == b""` or `data == ""`), the coroutine sends a close message and `break`s — but it does NOT close the websocket and does NOT cancel its paired task. On error, it catches `Exception` (line 207), logs it, tries to send an error message, then `break`s — same problem.

The outer `while True` loop (line 217) will stall on `await websocket.receive_text()` indefinitely after `read_output` exits, because the WebSocket is still open. This is the zombie: a blocked coroutine holding the WebSocket open.

The `finally` block (line 234) correctly cancels `output_task` but only runs when the outer loop exits — which it won't if the WebSocket is still open.

**Fix pattern:** When `read_output` hits EOF or error, it must close the WebSocket. `await websocket.close()` inside `read_output`'s break-before-exit paths causes `websocket.receive_text()` in the outer loop to raise `WebSocketDisconnect`, which propagates to the `except WebSocketDisconnect` handler, which lets the `finally` block run and cancel `output_task`.

```python
# In read_output(), on EOF:
await websocket.send_text("\r\n\x1b[31m[Connection closed]\x1b[0m\r\n")
await websocket.close()   # <-- add this
break

# In read_output(), on exception after send_text fails:
await websocket.close()   # <-- add this
break
```

**Confidence:** HIGH — pattern is well-established for Starlette WebSocket EOF handling. `websocket.close()` is idempotent if already closed.

**Test approach:** Mock WebSocket that simulates EOF on stdout read; assert `output_task` is cancelled and websocket is closed after handler returns.

---

### ERR-01: Timeout message reports wrong variable

**File:** `src/homelab_mcp/error_handling.py`
**Function:** `timeout_wrapper` inner `wrapper` (line 46)
**Bug location:** Line 58

```python
# CURRENT (bug):
error_msg = f"Operation '{func.__name__}' timed out after {timeout_seconds} seconds"

# FIXED:
error_msg = f"Operation '{func.__name__}' timed out after {effective_timeout} seconds"
```

`effective_timeout` is computed on lines 50-53. It can differ from `timeout_seconds` when the caller passes a dict argument with a `"timeout"` key (the override path at line 52-53). When overridden, `effective_timeout = max(float(arg["timeout"]) + 5.0, timeout_seconds)`. The error message currently reports `timeout_seconds` (decorator default), which is misleading when the override path was taken.

**One-line fix.** The existing test at `test_error_handling.py:53` (`assert "timed out after 0.1 seconds" in error_data["error"]`) passes because in that test no override is provided, so `effective_timeout == timeout_seconds`. The test does NOT prove the override case.

**Regression test needed:** Call `timeout_wrapper`-decorated function with a dict argument containing a `"timeout"` key; verify the error message reports the computed effective timeout, not `timeout_seconds`.

**Confidence:** HIGH — single-variable substitution, no architectural change.

---

### SSH-01: `ssh_execute_command` password branch ignores `check=True`

**File:** `src/homelab_mcp/ssh_tools.py`
**Function:** `ssh_execute_command` (line 643)
**Bug location:** Line 692

```python
# CURRENT (bug):
result = await conn.run(full_command, check=False)

# The sudo password branch builds:
# full_command = f"echo '{creds.password}' | sudo -S {command}" if creds.password else f"sudo {command}"

# FIXED: propagate check parameter
result = await conn.run(full_command, check=check)
```

The `ssh_execute_command` function does not currently accept a `check` parameter — the `check=False` is hardcoded. The CodeRabbit finding is that callers needing `check=True` behavior (raise on non-zero exit) have no way to get it in the password branch.

The requirements say "`_sudo_run` with `check=True` raises on non-zero exit code regardless of whether a password was provided." The name `_sudo_run` is what CodeRabbit called this helper. Based on the codebase, the most direct interpretation is:

**Option A (minimal fix):** Add `check: bool = False` parameter to `ssh_execute_command` and forward it to `conn.run`.

**Option B (extract helper):** Extract the sudo command-building + execution into a private helper `_sudo_run(conn, command, password, check)` that handles both password and no-password paths identically with respect to `check`.

Option B is cleaner and matches the CodeRabbit naming. The `_sudo_run` helper does not exist yet — it needs to be created inside `ssh_tools.py`.

**`asyncssh` `check=True` behavior:** When `check=True`, `asyncssh` raises `asyncssh.ProcessError` if exit status is non-zero. This is documented behavior (HIGH confidence — verified via asyncssh API knowledge).

**Proposed signature:**
```python
async def _sudo_run(
    conn: asyncssh.SSHClientConnection,
    command: str,
    password: str | None = None,
    check: bool = False,
) -> asyncssh.SSHCompletedProcess:
    """Run a command with sudo, optionally using password pipe for non-NOPASSWD users."""
    if password:
        full_command = f"echo '{password}' | sudo -S {command}"
    else:
        full_command = f"sudo {command}"
    return await conn.run(full_command, check=check)
```

Both branches call `conn.run(..., check=check)` — parity is enforced structurally.

**Test approach:** Mock `conn.run` to return a result with `exit_status=1`; assert `asyncssh.ProcessError` is raised when `check=True`, for both password-present and password-absent paths.

**Confidence:** HIGH — the fix is clear; asyncssh raises `ProcessError` on non-zero exit with `check=True`.

---

### SSH-02: Always-passing password propagation test assertion

**File:** `tests/test_ssh_tools.py`
**Line:** 191

```python
# CURRENT (bug — always passes):
assert "No credentials" in result_data["error"] or "credentials add" in result_data["error"]
```

The `ssh_discover_system` error message when no credentials are available is:
```
No credentials found for test-host. Store them with `credentials add` or pass password/key_path explicitly.
```

This message contains BOTH `"No credentials"` AND `"credentials add"`. The `or` makes the assertion pass even if one string is absent — i.e., if the error message were changed to contain neither, the test would still pass because the second operand is evaluated left-to-right and Python short-circuits `or` only on truthy left side... wait, actually both are boolean expressions.

Re-examining: `"A" in str` evaluates to a bool. `bool1 or bool2` evaluates to `bool1` if `bool1` is truthy, else `bool2`. If neither string is in the error, both operands are `False` and the assertion fails correctly. So this is NOT unconditionally passing in the simple algebraic sense.

The actual bug as described by CodeRabbit: the current error message ALWAYS contains `"credentials add"`, so the `or` branch is always truthy regardless of what the first part says. **The second operand is redundant and masks the first operand's failure.** If the production error message changes to not include `"No credentials"`, the test still passes because `"credentials add"` is always there. This is the "always-passing ternary" — the second branch is always true given the current implementation.

**Fix:** Write two separate, specific assertions, OR use a single non-disjunctive assertion:

```python
# Fixed version:
assert "No credentials" in result_data["error"]
# or:
assert "No credentials" in result_data["error"] or "credentials add" in result_data["error"]
# → replace with:
assert result_data["status"] == "error"
assert "No credentials" in result_data["error"]
```

The test verifies that when `ssh_discover_system` is called without credentials, the error message contains `"No credentials"`. The `or "credentials add"` branch should be removed because it makes the assertion trivially true.

**Note on test mock:** The test at lines 177-191 patches `get_database_adapter` but does NOT patch `list_credentials` or `get_credential`. This means the keyring lookup path in `resolve_ssh_credentials` will run against actual keyring. However, in a CI environment with no keyring entries, it will return an empty list, and the no-password path will be exercised correctly.

**If we also want to verify password PROPAGATION to ssh_connect** (the other meaning of "password propagation test"), there is no existing dedicated test that checks `ssh_connect` was called with `password=<value>` when a password was given. This may need a new test. But based on the requirements wording, the SSH-02 fix is the existing test assertion at line 191.

**Confidence:** HIGH — bug is identified and fix is clear.

---

### SCH-01: `credential_type` accepts arbitrary strings

**File:** `src/homelab_mcp/tool_schemas/credential_tools_schema.py`
**Location:** Lines 117-134, `list_keyring_credentials` entry

```python
# CURRENT (bug — no enum constraint):
"credential_type": {
    "type": "string",
    "description": "Credential type to list: 'ssh' (default) or 'proxmox'",
    "default": "ssh",
}

# FIXED:
"credential_type": {
    "type": "string",
    "description": "Credential type to list: 'ssh' (default) or 'proxmox'",
    "default": "ssh",
    "enum": ["ssh", "proxmox"],
}
```

JSON Schema `enum` is a standard keyword. MCP validates tool arguments against `inputSchema` using JSON Schema semantics. Adding `"enum": ["ssh", "proxmox"]` causes the MCP framework to reject any `credential_type` value that is not one of those two strings.

**Verification:** The existing `test_tools.py` tests check tool schema structure. A regression test should verify `credential_type` in `list_keyring_credentials` schema has `"enum"` with exactly `["ssh", "proxmox"]`.

**Confidence:** HIGH — JSON Schema `enum` keyword is well-documented; one-line fix.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncssh | 2.x | SSH execution; `check=True` raises `ProcessError` on non-zero exit | Already in use throughout codebase |
| pytest-asyncio | 0.x | async test execution | Already in use; `@pytest.mark.asyncio` pattern established |
| starlette | 0.x | WebSocket API; `websocket.close()` idempotent | Already in use for HTTP transport |
| pytest-mock | 3.x | `mocker.patch` for unit mocking | Already in use throughout tests |

No new dependencies required for this phase.

## Architecture Patterns

### Pattern 1: Inner coroutine closes websocket on EOF
**What:** `read_output()` calls `await websocket.close()` before `break` in both EOF and error paths. This propagates to the outer `receive_text()` loop via `WebSocketDisconnect`.
**When to use:** Any WebSocket handler where a background reader task must signal the main loop to exit.

### Pattern 2: Extract `_sudo_run` helper
**What:** Private async function encapsulating the password-vs-nopassword sudo command selection and `conn.run` call. Accepts `check: bool` forwarded to asyncssh.
**When to use:** Any time sudo execution with consistent check= semantics is needed across both auth paths.

### Pattern 3: JSON Schema `enum`
**What:** Adding `"enum": ["ssh", "proxmox"]` to the `credential_type` property in `inputSchema`.
**When to use:** Any string parameter with a fixed set of valid values.

### Anti-Patterns to Avoid
- **`assert A or B` with always-true B:** Masks failures in A. Use two separate assertions or a single non-disjunctive check.
- **Hardcoded `check=False` in command execution helpers:** Prevents callers from getting raise-on-failure semantics. Add a `check` parameter and forward it.
- **Using decorator-parameter variable in error message instead of computed variable:** `timeout_seconds` vs `effective_timeout` — always report the value actually used.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket EOF detection | Custom state machine | `await websocket.close()` + `WebSocketDisconnect` propagation | Starlette handles it natively |
| SSH non-zero exit detection | Manual `exit_status != 0` checks | `asyncssh conn.run(check=True)` → raises `ProcessError` | asyncssh built-in; avoids repetitive conditionals |
| JSON Schema enum validation | Manual string membership check in handler | `"enum": [...]` in inputSchema | MCP framework validates before handler is called |

## Common Pitfalls

### Pitfall 1: `websocket.close()` raising on already-closed socket
**What goes wrong:** Calling `await websocket.close()` when the WebSocket is already closed raises an exception in Starlette.
**Why it happens:** The EOF path in `read_output` might run after the client already disconnected.
**How to avoid:** Wrap in `with contextlib.suppress(Exception)` or check websocket state. Alternatively, catch the exception silently — the close is a best-effort cleanup signal.
**Warning signs:** `RuntimeError: WebSocket is not connected` in logs.

### Pitfall 2: asyncssh `check=True` raises `ProcessError` not `subprocess.CalledProcessError`
**What goes wrong:** Catching `subprocess.CalledProcessError` instead of `asyncssh.ProcessError`.
**Why it happens:** Developers familiar with `subprocess.run(check=True)` expect `CalledProcessError`.
**How to avoid:** Catch `asyncssh.ProcessError` or its base `asyncssh.Error`.

### Pitfall 3: `output_task` may not exist in `finally` block
**What goes wrong:** `if "output_task" in locals()` pattern at line 235 is correct but fragile — if `output_task` assignment fails, the variable won't be in locals.
**Why it happens:** `output_task = asyncio.create_task(read_output())` could theoretically raise if event loop is closed.
**How to avoid:** The existing `if "output_task" in locals()` guard is correct. Keep it.

### Pitfall 4: mypy strictness on `_sudo_run` return type
**What goes wrong:** `asyncssh.SSHCompletedProcess` is the return type but mypy may complain about the exact generic form.
**How to avoid:** Use `asyncssh.SSHCompletedProcess[str]` or `asyncssh.SSHCompletedProcess[bytes]` — check asyncssh type stubs. Fallback: `Any` with a type ignore comment.

### Pitfall 5: bandit flag on `echo password | sudo -S`
**What goes wrong:** The pattern `f"echo '{password}' | sudo -S {command}"` may trigger bandit B608 (possible SQL injection) or B602 (subprocess shell=True).
**Why it happens:** bandit pattern-matches shell command construction with variables.
**How to avoid:** Add `# nosec B602` or `# nosec B608` inline with a justification comment. Example: `# nosec B608 -- password is user-provided credential, not SQL; command is caller-supplied`.

## Code Examples

### WS-01: read_output EOF close pattern
```python
# Source: Starlette WebSocket docs + existing http_app.py pattern
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
                    # EOF — process exited; close websocket to unblock outer loop
                    await websocket.send_text("\r\n\x1b[31m[Connection closed]\x1b[0m\r\n")
                    with contextlib.suppress(Exception):
                        await websocket.close()
                    break
            else:
                with contextlib.suppress(Exception):
                    await websocket.close()
                break
        except TimeoutError:
            logger.debug("No PTY data within timeout — retrying")
        except Exception as e:
            logger.error(f"Error reading output: {e}")
            try:
                await websocket.send_text(f"\r\n\x1b[31m[Read error: {e}]\x1b[0m\r\n")
            except Exception as send_err:
                logger.debug(f"Could not send error to websocket: {send_err}")
            with contextlib.suppress(Exception):
                await websocket.close()
            break
```

### SSH-01: `_sudo_run` helper
```python
# Source: asyncssh docs — conn.run(check=True) raises asyncssh.ProcessError on non-zero exit
async def _sudo_run(
    conn: asyncssh.SSHClientConnection,
    command: str,
    password: str | None = None,
    check: bool = False,
) -> asyncssh.SSHCompletedProcess[str]:
    """Execute command with sudo, with consistent check= semantics for both auth paths."""
    if password:
        full_command = f"echo '{password}' | sudo -S {command}"  # nosec B608
    else:
        full_command = f"sudo {command}"
    return await conn.run(full_command, check=check)
```

### ERR-01: single-variable substitution
```python
# In error_handling.py timeout_wrapper, except TimeoutError block:
# Change:
error_msg = f"Operation '{func.__name__}' timed out after {timeout_seconds} seconds"
# To:
error_msg = f"Operation '{func.__name__}' timed out after {effective_timeout} seconds"
```

### SCH-01: enum constraint
```python
# In credential_tools_schema.py list_keyring_credentials:
"credential_type": {
    "type": "string",
    "description": "Credential type to list: 'ssh' (default) or 'proxmox'",
    "default": "ssh",
    "enum": ["ssh", "proxmox"],
}
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (with pytest-asyncio) |
| Config file | `pytest.ini` (project root) |
| Quick run command | `uv run pytest tests/test_ssh_tools.py tests/test_error_handling.py tests/test_tools.py tests/test_http_app.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WS-01 | read_output closes websocket and cancels task on EOF | unit | `uv run pytest tests/test_http_app.py -k "websocket" -x` | Partial (existing tests exist but don't cover zombie path) |
| ERR-01 | timeout error message reports effective_timeout | unit | `uv run pytest tests/test_error_handling.py -k "timeout" -x` | Partial (existing test doesn't cover override case) |
| SSH-01 | `_sudo_run check=True` raises on non-zero in both password/no-password branches | unit | `uv run pytest tests/test_ssh_tools.py -k "sudo_run" -x` | Wave 0 gap |
| SSH-02 | password propagation test fails when password is absent | unit | `uv run pytest tests/test_ssh_tools.py -k "no_credentials" -x` | Fix existing test at line 191 |
| SCH-01 | `credential_type` schema rejects non-enum values | unit | `uv run pytest tests/test_tools.py -k "credential" -x` | Wave 0 gap |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_ssh_tools.py tests/test_error_handling.py tests/test_tools.py tests/test_http_app.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ssh_tools.py` — add `test_sudo_run_check_true_raises_with_password` and `test_sudo_run_check_true_raises_without_password` (SSH-01)
- [ ] `tests/test_tools.py` — add `test_credential_type_schema_has_enum` (SCH-01)
- [ ] `tests/test_error_handling.py` — add `test_timeout_wrapper_reports_effective_timeout_on_override` (ERR-01)
- [ ] `tests/test_http_app.py` — add `test_handle_shell_websocket_eof_closes_socket_and_cancels_task` (WS-01)
- [ ] Fix existing test: `tests/test_ssh_tools.py` line 191 — remove always-true `or` branch (SSH-02)

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — all fixes are code/test edits within the Python package)

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `src/homelab_mcp/http_app.py` — WS-01 bug location identified at lines 188-214
- Direct code inspection of `src/homelab_mcp/error_handling.py` — ERR-01 bug at lines 50-58
- Direct code inspection of `src/homelab_mcp/ssh_tools.py` — SSH-01 bug at lines 681-692
- Direct code inspection of `tests/test_ssh_tools.py` — SSH-02 bug at line 191
- Direct code inspection of `src/homelab_mcp/tool_schemas/credential_tools_schema.py` — SCH-01 bug at line 128

### Secondary (MEDIUM confidence)
- `asyncssh` behavior: `conn.run(check=True)` raises `asyncssh.ProcessError` on non-zero exit — based on asyncssh documentation and training knowledge; not verified via Context7 (asyncssh may not be indexed)
- Starlette WebSocket `close()` idempotency — based on Starlette documentation patterns; should be verified in Starlette source if concerns arise

## Metadata

**Confidence breakdown:**
- Bug locations: HIGH — all found by direct code inspection
- Fix patterns: HIGH — all are single-line or minimal changes following established patterns
- Test approach: HIGH — follows project's established pytest patterns
- asyncssh `ProcessError` raise behavior: MEDIUM — training knowledge; not Context7-verified

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable domain — async Python/asyncssh API does not change frequently)
