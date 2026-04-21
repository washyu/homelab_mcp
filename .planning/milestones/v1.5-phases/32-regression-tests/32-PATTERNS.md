# Phase 32: Regression Tests - Pattern Map

**Mapped:** 2026-04-20
**Files analyzed:** 4 existing test files (edits only — no new files)
**Analogs found:** 4 / 4 in-file analogs located + 1 novel pattern (SSH-02 AST meta-test)

## File Classification

All 6 new tests are **edits** to existing pytest modules. No new files. Each test is classified as `test, request-response` unless noted.

| New Test | File to Modify | Role / Data Flow | Closest In-File Analog | Match Quality |
|----------|----------------|------------------|------------------------|---------------|
| `test_ws01_reader_closes_socket_on_pty_eof` | `tests/test_http_app.py` | test, streaming (websocket + EOF) | `TestWebSocketReadOutput.test_read_output_sends_eof_notification` (lines 183-239) | exact (local-copy EOF — the QUAL-02-flagged test this will replace/supplement) |
| `test_ssh01_sudo_run_check_raises_in_password_branch` | `tests/test_ssh_tools.py` | test, async-mock / exception propagation | `test_ssh_discover_success` conn.run mocking (lines 72-106) + `test_ssh_discover_auth_failure` side_effect-raises shape (lines 148-159) | role-match (no existing `_sudo_run` test, but conn.run mocking is identical) |
| `test_ssh02_no_disjunctive_always_true_assertions` | `tests/test_ssh_tools.py` | test, AST meta-lint | **NOVEL — no in-file analog.** Closest cross-file analog: `test_http_app.py::test_read_output_no_sleep_after_wait_for` (lines 241-268) demonstrates `ast.parse` + `ast.walk` on a production function | partial (reuses stdlib AST walker shape from a different file) |
| `test_err01_timeout_message_reports_effective_value` | `tests/test_error_handling.py` | test, decorator-invocation + TimeoutError | `TestTimeoutWrapper.test_timeout_wrapper_timeout` (lines 34-53) | exact (same decorator, same `asyncio.sleep` trigger, same f-string assertion shape) |
| `test_sch01_credential_type_rejects_non_enum_values` | `tests/test_tools.py` | test, schema-shape assertion | `test_sitemap_tool_schemas` (lines 285-315) + `test_service_tools_have_no_phantom_port_property` (lines 835-851) | exact (same `tools[<name>]["inputSchema"]["properties"][...]` lookup pattern) |

## Pattern Assignments

---

### `test_ws01_reader_closes_socket_on_pty_eof` → `tests/test_http_app.py`

**Analog:** `tests/test_http_app.py` class `TestWebSocketReadOutput.test_read_output_sends_eof_notification` (lines 183-239).

This is the exact test flagged by QUAL-02 — it reimplements `read_output` locally instead of driving production `handle_shell_websocket`. D-06/D-09 require the WS-01 regression to drive production end-to-end via `TestClient.websocket_connect()`.

**Imports pattern (header of file, lines 1-13) — already present, reuse and add `WebSocketRoute` + `unittest.mock`:**
```python
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from homelab_mcp.http_app import OriginValidationMiddleware
```

**What to add (imports the WS-01 regression needs):**
```python
from starlette.routing import WebSocketRoute
from unittest.mock import AsyncMock, MagicMock, patch

from homelab_mcp.http_app import handle_shell_websocket
```

**Minimal-app factory pattern to replicate (lines 25-33) — model the E2E app on this exact shape:**
```python
def _make_app(allowed_origins: list[str] | None = None) -> Starlette:
    """Create a minimal Starlette app with OriginValidationMiddleware."""
    middleware = [
        Middleware(OriginValidationMiddleware, allowed_origins=allowed_origins),
    ]
    return Starlette(
        routes=[Route("/mcp", _echo_handler, methods=["POST", "GET"])],
        middleware=middleware,
    )
```

Create an analogous `_make_shell_app()` that registers the production handler via `WebSocketRoute("/ws/shell/{session_id}", handle_shell_websocket)`.

**Local-copy EOF pattern to REPLACE (lines 183-239) — this is the anti-pattern D-06 calls out:**
```python
@pytest.mark.asyncio
async def test_read_output_sends_eof_notification(self) -> None:
    """When stdout returns empty string (EOF), websocket receives a disconnect message.

    This test exercises read_output in isolation by calling the fixed
    http_app.py's logic directly: wrap stdout.read in asyncio.wait_for,
    detect empty-string EOF, send a disconnect notification.
    """
    import asyncio
    from unittest.mock import AsyncMock

    sent_messages: list[str] = []
    read_calls = 0

    async def fake_read(n: int) -> str:
        nonlocal read_calls
        read_calls += 1
        if read_calls == 1:
            return "hello"
        return ""  # EOF

    mock_stdout = AsyncMock()
    mock_stdout.read = fake_read
    # ...
    # Run the read_output logic directly (mirrors the fixed implementation)
    async def read_output() -> None:  # <-- LOCAL COPY of production logic
        while True:
            try:
                data = await asyncio.wait_for(mock_stdout.read(4096), timeout=0.05)
                ...
```

**What to replicate:** the fake-stdout state machine (first call returns data, second returns `""` for EOF), the `sent_messages` capture list.
**What to change:**
1. DO NOT redefine `read_output` locally. Instead patch `homelab_mcp.http_app.shell_session_manager` to return a session whose `process.stdout.read` uses the same fake-read state machine.
2. Drive the handler via `TestClient(app).websocket_connect("/ws/shell/<id>") as ws:` — the handler runs inside Starlette's event loop.
3. Assert the three observables per D-07:
   - `ws.receive_text()` (or accumulated frames) contains `"[Connection closed]"`.
   - `WebSocketDisconnect` is raised on the next `ws.receive_text()` call (catch with `pytest.raises(WebSocketDisconnect)` or verify via `TestClient` context-manager exit).
   - `output_task` is cancelled — observable via a `monkeypatch`-injected flag on an async callback, OR by checking the session_manager mock saw `resize_terminal` no longer being callable (simpler: just assert WebSocketDisconnect is raised; the `finally` block's `output_task.cancel()` is exercised implicitly).

**Session-manager mock shape (new, but follow the AsyncMock convention used throughout this file at line 192):**
```python
mock_session = MagicMock()
mock_session.initial_command = None
mock_session.process = MagicMock()
mock_session.process.stdout = AsyncMock()
mock_session.process.stdout.read = fake_read  # EOF state machine from analog
mock_session.process.stdin = None  # Skip initial_command path

with patch("homelab_mcp.http_app.shell_session_manager") as mock_mgr:
    mock_mgr.get_session.return_value = mock_session
    mock_mgr.resize_terminal = AsyncMock()
    app = _make_shell_app()
    with TestClient(app) as client:
        with client.websocket_connect("/ws/shell/test-session") as ws:
            msg = ws.receive_text()
            assert "[Connection closed]" in msg
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()
```

**Note on `output_task.cancel()` observable (D-07 item 3, per `<specifics>` guidance):** The simplest observable is `WebSocketDisconnect` on the next `receive_text()` — if the `read_output` loop hangs instead of breaking out, the test will time out. A stronger guard: patch `asyncio.create_task` to capture the task and assert `task.cancelled()` after the `with` block, but only if this does not require test-specific hooks in production. Planner picks.

**Decision for D-09:** In the commit message, note that this test closes QUAL-02 and recommend removing or repurposing the old `test_read_output_sends_eof_notification` (lines 183-239). D-09 says "closes QUAL-02 as side effect" — the planner may either delete the old local-copy test or leave it as a unit-level guard alongside the new E2E test.

---

### `test_ssh01_sudo_run_check_raises_in_password_branch` → `tests/test_ssh_tools.py`

**Analog (primary):** `test_ssh_discover_success` mock-conn shape (lines 72-106).
**Analog (exception propagation):** `test_ssh_discover_auth_failure` (lines 148-159).

**Imports pattern (lines 1-14) — already present in file:**
```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from src.homelab_mcp.ssh_tools import (
    ensure_mcp_ssh_key,
    setup_remote_mcp_admin,
    ssh_discover_system,
    verify_mcp_admin_access,
)
```

**What to add:** `_sudo_run` to the import block. Production defines it at `src/homelab_mcp/ssh_tools.py:651-667`.
```python
from src.homelab_mcp.ssh_tools import _sudo_run
```

**Mock-conn shape pattern (lines 72-106) — adapt this for the _sudo_run call:**
```python
# Create mock connection
mock_conn = AsyncMock()
# ...
mock_conn.run = mock_run  # OR mock_conn.run.return_value = mock_result

# ssh_connect is async, returns a connection usable as async context manager
mock_ctx = AsyncMock()
mock_ctx.__aenter__.return_value = mock_conn
mock_ctx.__aexit__.return_value = None
mock_connect.return_value = mock_ctx
```

**Exception-propagation pattern (lines 148-159):**
```python
@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_auth_failure(mock_connect):
    """Test SSH discovery with authentication failure."""
    mock_connect.side_effect = asyncssh.misc.PermissionDenied("Authentication failed")

    result = await ssh_discover_system(hostname="test-host", username="test-user", password="wrong-pass")

    result_data = json.loads(result)
    assert result_data["status"] == "error"
```

**What to replicate:** `@pytest.mark.asyncio` decorator, `AsyncMock` conn, `side_effect` for raising.
**What to change:**
1. Do NOT patch `ssh_connect` — `_sudo_run` takes `conn` as a direct argument, so construct an `AsyncMock()` conn directly and pass it in. No context manager is needed here (that's the caller's concern).
2. Set `mock_conn.run.side_effect = asyncssh.ProcessError(...)` OR return a `MagicMock(exit_status=1)` and let `check=True` in production raise. Per CONTEXT.md `<decisions>` D-05's reference to asyncssh behavior, use `asyncssh.ProcessError`.
3. Use `pytest.raises` to assert the error propagates (D-05 says "Assert the error propagates").

**Target test sketch (follow CONTEXT.md D-05 "positive test only"):**
```python
@pytest.mark.asyncio
async def test_ssh01_sudo_run_check_raises_in_password_branch():
    """SSH-01 regression: _sudo_run(password=..., check=True) forwards check= to conn.run.

    Before the fix, the password branch dropped check= and silently ignored non-zero exits.
    """
    from src.homelab_mcp.ssh_tools import _sudo_run

    mock_conn = AsyncMock()
    mock_conn.run.side_effect = asyncssh.ProcessError(
        env=None, command="sudo -S ls", subsystem=None, exit_status=1,
        exit_signal=None, returncode=1, stdout="", stderr="permission denied",
    )

    with pytest.raises(asyncssh.ProcessError):
        await _sudo_run(mock_conn, "ls", password="pw", check=True)

    # Verify check=True was forwarded to conn.run
    mock_conn.run.assert_called_once()
    assert mock_conn.run.call_args.kwargs.get("check") is True
```

**Note on `asyncssh.ProcessError` constructor:** The exact kwargs may vary by asyncssh version. A simpler and equally valid shape per CONTEXT.md D-05 is: `mock_conn.run.side_effect = asyncssh.ProcessError(...)` — planner should use the minimal ctor args that instantiate cleanly, OR return a MagicMock with `exit_status=1` and let asyncssh raise internally (but that requires the real `check=True` codepath, which mocks short-circuit). Use `side_effect = asyncssh.ProcessError(...)` to stay in test-land.

**Optional negative (deferred per CONTEXT.md):** `_sudo_run(mock_conn, "ls", password="pw", check=False)` returns without raising even when `mock_conn.run.return_value.exit_status == 1`. Skip unless trivially cheap.

---

### `test_ssh02_no_disjunctive_always_true_assertions` → `tests/test_ssh_tools.py` (NOVEL — AST meta-test)

**Analog status:** **No in-file analog.** Closest cross-file analog is `tests/test_http_app.py::test_read_output_no_sleep_after_wait_for` (lines 241-268), which parses production source with `ast.parse` + `ast.walk`. Our use case inverts this: parse a TEST file to lint its own `assert` nodes.

**Cross-file AST walker pattern (test_http_app.py lines 241-268) — imports + ast.walk skeleton:**
```python
def test_read_output_no_sleep_after_wait_for(self) -> None:
    """The read_output function body must NOT contain asyncio.sleep (removed after wait_for fix)."""
    import ast
    import inspect
    import textwrap

    from homelab_mcp import http_app

    source = inspect.getsource(http_app.handle_shell_websocket)

    # Extract read_output inner function body using AST
    tree = ast.parse(textwrap.dedent(source))

    # Flatten all Call nodes in the AST and look for asyncio.sleep calls
    sleep_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "sleep"
                and isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
            ):
                sleep_calls.append(ast.unparse(node))

    assert not sleep_calls, f"asyncio.sleep should be removed from read_output; found: {sleep_calls}"
```

**What to replicate:** `import ast`, `ast.parse(...)`, `ast.walk(tree)`, `isinstance(node, ast.X)` dispatch, final `assert not offenders, f"..."` message shape.
**What to change:**
1. Source is not `inspect.getsource(production_func)` — instead `Path(__file__).read_text()` (the test file itself). Per CONTEXT.md `<code_context>` integration point: `ast.parse(Path("tests/test_ssh_tools.py").read_text())`.
2. Walk for `ast.Assert(test=ast.BoolOp(op=ast.Or(), values=[<lhs>, <rhs_always_true>]))` (per D-03 and `<specifics>` `ast.Assert(test=ast.BoolOp(op=ast.Or(), values=[..., <structurally_always_true>]))`).
3. Keep the structurally-always-true detector CONSERVATIVE (high precision, low recall per `<specifics>`) — non-empty `ast.Constant(value=str)`, `ast.BoolOp(op=ast.Or())` where one value is a literal, or `ast.Compare` over two literal operands.

**Target test sketch (D-03, D-04, D-05):**
```python
def test_ssh02_no_disjunctive_always_true_assertions():
    """SSH-02 meta-guard: no `assert X or <always-true>` anti-patterns in this file.

    The fixed assertion at line ~191 (`assert "No credentials" in result_data["error"]`)
    passes; reintroducing `assert "No credentials" in err or "other" in err` with a
    tautological second operand must fail this guard.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    def _is_structurally_always_true(node: ast.expr) -> bool:
        """Conservative: literal truthy constants and Or-of-literals."""
        if isinstance(node, ast.Constant):
            # Non-empty string/non-zero number/True
            return bool(node.value)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return any(_is_structurally_always_true(v) for v in node.values)
        if isinstance(node, ast.Compare):
            # Compare over two Constants — evaluable at parse time
            if isinstance(node.left, ast.Constant) and all(
                isinstance(c, ast.Constant) for c in node.comparators
            ):
                return True
        return False

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.BoolOp):
            if isinstance(node.test.op, ast.Or):
                # Flag if ANY operand (beyond the first) is structurally always true
                for operand in node.test.values[1:]:
                    if _is_structurally_always_true(operand):
                        offenders.append(
                            f"line {node.lineno}: {ast.unparse(node)}"
                        )
                        break

    assert not offenders, (
        f"Found `assert X or <always-true>` anti-pattern(s) in test_ssh_tools.py:\n"
        + "\n".join(offenders)
    )
```

**D-05 commit-message proof:** The commit message documents the mutation experiment — temporarily changing the line 191 assertion to `assert "No credentials" in result_data["error"] or "other" in result_data["error"]` MUST be caught by this guard (because `"other"` is a non-empty string literal flagged by `_is_structurally_always_true`). The mutation itself is NOT checked in; only the evidence (commit message, plan VERIFICATION step) is preserved.

**D-04 scope:** This guard reads only `Path(__file__).read_text()` — no broader `tests/test_*.py` scan. If a future test-hardening phase wants global coverage, factor the detector into a helper and call it over a glob in a separate test file.

---

### `test_err01_timeout_message_reports_effective_value` → `tests/test_error_handling.py`

**Analog:** `TestTimeoutWrapper.test_timeout_wrapper_timeout` (lines 34-53) — exact-shape match.

**Imports pattern (lines 1-17) — already present:**
```python
import asyncio
import json

import pytest

from src.homelab_mcp.error_handling import (
    HealthChecker,
    MCPConnectionError,
    MCPTimeout,
    health_checker,
    retry_on_failure,
    safe_json_response,
    ssh_connection_wrapper,
    timeout_wrapper,
)
```

**Trigger-timeout pattern (lines 34-53) — copy this shape verbatim and adjust the trigger:**
```python
@pytest.mark.asyncio
async def test_timeout_wrapper_timeout(self):
    """Test timeout wrapper with timeout."""

    @timeout_wrapper(timeout_seconds=0.1)
    async def slow_operation():
        await asyncio.sleep(1.0)  # Will timeout
        return {"status": "success"}

    result = await slow_operation()

    # Should return structured error response
    assert "content" in result
    assert len(result["content"]) == 1
    assert result["content"][0]["type"] == "text"

    error_data = json.loads(result["content"][0]["text"])
    assert error_data["status"] == "error"
    assert error_data["error_type"] == "timeout"
    assert "timed out after 0.1 seconds" in error_data["error"]
```

**What to replicate:** `@timeout_wrapper(timeout_seconds=<decorator_default>)`, an inner `async def` that sleeps past the timeout, unpacking via `json.loads(result["content"][0]["text"])`, the final `"timed out after ... seconds"` substring assertion.
**What to change:**
1. Set the decorator default to `timeout_seconds=10.0` (or similar), then pass a dict arg with `{"timeout": 60}` — production at `error_handling.py:50-53` sets `effective_timeout = max(float(arg["timeout"]) + 5.0, timeout_seconds)`, so the effective value becomes `max(65.0, 10.0) == 65.0`.
2. To still trigger `asyncio.TimeoutError` quickly (without waiting 65s), reverse the override: use `timeout_wrapper(timeout_seconds=60.0)` as the decorator default, pass `{"timeout": 0.05}` (so `effective_timeout = max(0.05 + 5.0, 60.0) = 60.0` — WAIT: the `max(...)` construction means the override ONLY lengthens, never shortens. Re-read production).

Re-reading `error_handling.py:50-53`:
```python
effective_timeout = timeout_seconds
for arg in args:
    if isinstance(arg, dict) and "timeout" in arg:
        effective_timeout = max(float(arg["timeout"]) + 5.0, timeout_seconds)
        break
```

The override only LENGTHENS the timeout. So to exercise the "effective != default" path while still triggering a `TimeoutError` quickly, the slow_operation must `asyncio.sleep` past `effective_timeout`. Simplest construction:
- Decorator: `@timeout_wrapper(timeout_seconds=0.05)` (tiny default)
- Call arg: `{"timeout": 0.2}` → `effective_timeout = max(0.2 + 5.0, 0.05) = 5.2` → slow_operation must sleep > 5.2s, which is too slow.

OR reverse the assertion logic: the point of ERR-01 is that BEFORE the fix, the error message reported the DEFAULT `timeout_seconds` (e.g. `0.05`), not the `effective_timeout` (e.g. `5.2`). AFTER the fix, the message reports `effective_timeout`. Use a fast default and a short-ish override that still triggers:
- Decorator: `@timeout_wrapper(timeout_seconds=0.01)` (essentially zero)
- Call arg: `{"timeout": 0.0}` → `effective_timeout = max(0.0 + 5.0, 0.01) = 5.0` — still too long.

**Simpler target construction (planner refines):** Trigger the timeout trivially and assert the message f-string contains the `effective_timeout` value, not the decorator default. The cheapest mechanism is to mock `asyncio.wait_for` directly to raise `TimeoutError` without sleeping:
```python
@pytest.mark.asyncio
async def test_err01_timeout_message_reports_effective_value(monkeypatch):
    """ERR-01 regression: timeout error f-string uses effective_timeout (override+5), not default."""

    @timeout_wrapper(timeout_seconds=2.0)
    async def op(kwargs: dict):
        return {"ok": True}

    # Force wait_for to raise TimeoutError immediately
    async def fake_wait_for(coro, timeout):
        coro.close()  # Avoid "coroutine was never awaited" warning
        raise TimeoutError()

    monkeypatch.setattr("src.homelab_mcp.error_handling.asyncio.wait_for", fake_wait_for)

    # Pass dict arg with override=30 → effective_timeout = max(30+5, 2.0) = 35.0
    result = await op({"timeout": 30})

    error_data = json.loads(result["content"][0]["text"])
    # BEFORE fix: "timed out after 2.0 seconds" (decorator default)
    # AFTER fix:  "timed out after 35.0 seconds" (effective_timeout = max(30+5, 2.0))
    assert "35.0 seconds" in error_data["error"], (
        f"Expected effective_timeout (35.0) in error msg; got: {error_data['error']!r}"
    )
    assert "2.0 seconds" not in error_data["error"], (
        f"Error msg should NOT report decorator default; got: {error_data['error']!r}"
    )
```

**What to replicate from the analog:** `@timeout_wrapper(...)` decorator usage, `json.loads(result["content"][0]["text"])` response unpacking, `"timed out after X seconds" in error_data["error"]` assertion shape.
**What's new:** the dict-arg override + monkeypatch `asyncio.wait_for` to skip the actual sleep (per CONTEXT.md `<decisions>` "Claude's Discretion" ERR-01 test mechanics: "Exercise `timeout_wrapper` with a dict-arg override (so `effective_timeout != timeout_seconds`)...").

---

### `test_sch01_credential_type_rejects_non_enum_values` → `tests/test_tools.py`

**Analog (primary):** `test_sitemap_tool_schemas` (lines 285-315) — property/type lookup pattern.
**Analog (schema audit):** `test_service_tools_have_no_phantom_port_property` (lines 835-851) — import-from-schema-module pattern.

**Imports pattern (lines 1-8) — already present:**
```python
import json
from unittest.mock import MagicMock, patch

import pytest

from src.homelab_mcp.tools import execute_tool, get_available_tools
```

**Schema-lookup pattern (lines 285-315):**
```python
def test_sitemap_tool_schemas():
    """Test that all sitemap tools have proper schemas."""
    tools = get_available_tools()

    # Test discover_and_map schema
    discover_tool = tools["discover_and_map"]
    assert "description" in discover_tool
    assert "inputSchema" in discover_tool
    assert "hostname" in discover_tool["inputSchema"]["properties"]
    assert "username" in discover_tool["inputSchema"]["properties"]
    assert discover_tool["inputSchema"]["required"] == ["hostname"]
    assert discover_tool["inputSchema"]["properties"]["username"].get("default") == "mcp_admin"
```

**Module-specific import pattern (lines 843-851):**
```python
from src.homelab_mcp.tool_schemas.service_tools_schema import SERVICE_TOOLS

for tool_name, tool_def in SERVICE_TOOLS.items():
    props = tool_def.get("inputSchema", {}).get("properties", {})
    assert "port" not in props, (
        f"Service tool '{tool_name}' has phantom 'port' property — "
        f"ServiceInstaller has no port parameter (Phase 26-01)"
    )
```

**What to replicate:** `tools = get_available_tools()` → `tools["<name>"]["inputSchema"]["properties"][...]` lookup chain, bare-function `def test_xxx():` (no `@pytest.mark.asyncio`, no class).
**What to change:**
1. Target tool name: `"list_keyring_credentials"`.
2. Target property: `credential_type`.
3. Assert: `enum == ["ssh", "proxmox"]` AND `type == "string"` AND `default == "ssh"`.

**Target test sketch:**
```python
def test_sch01_credential_type_rejects_non_enum_values():
    """SCH-01 regression: list_keyring_credentials.credential_type has enum=['ssh','proxmox'].

    Before the fix, the schema accepted arbitrary strings, so 'bogus' values were
    not rejected by MCP framework validation.
    """
    tools = get_available_tools()
    tool = tools["list_keyring_credentials"]
    prop = tool["inputSchema"]["properties"]["credential_type"]

    assert prop["type"] == "string"
    assert prop["enum"] == ["ssh", "proxmox"], (
        f"credential_type must restrict to enum [ssh, proxmox]; got: {prop.get('enum')!r}"
    )
    assert prop.get("default") == "ssh"
```

**Optional second-layer assertion (per `<decisions>` "Claude's Discretion" SCH-01): call `execute_tool("list_keyring_credentials", {"credential_type": "bogus"})` and verify the MCP framework (or the handler) rejects it. Skip if framework validation happens upstream of `execute_tool`.** Schema-level assertion alone meets REG-01.

---

## Shared Patterns

### Co-location Convention (D-01)
**Source:** CLAUDE.md project convention + Phase 32 CONTEXT.md `<code_context>` "Established Patterns".
**Apply to:** All 6 tests — each regression lives in the test file whose name mirrors its subject module:
- `src/homelab_mcp/http_app.py` ↔ `tests/test_http_app.py`
- `src/homelab_mcp/ssh_tools.py` ↔ `tests/test_ssh_tools.py`
- `src/homelab_mcp/error_handling.py` ↔ `tests/test_error_handling.py`
- `src/homelab_mcp/tools.py` + `tool_schemas/credential_tools_schema.py` ↔ `tests/test_tools.py`

### Bug-ID Prefix Naming (D-02)
**Source:** CONTEXT.md `<decisions>` D-02.
**Apply to:** All 6 tests. Naming: `test_<bug_id_lowercase><no_dash>_<human_slug>`:
- `test_ws01_reader_closes_socket_on_pty_eof`
- `test_err01_timeout_message_reports_effective_value`
- `test_ssh01_sudo_run_check_raises_in_password_branch`
- `test_ssh02_no_disjunctive_always_true_assertions`
- `test_sch01_credential_type_rejects_non_enum_values`

This makes them greppable: `pytest -k ws01`, `pytest -k ssh02`, etc. No custom `@pytest.mark.regression` per D-10 / "Claude's Discretion".

### Regression-guards Section Header (`<specifics>` "Naming")
**Source:** CONTEXT.md `<specifics>`.
**Apply to:** Each of the 4 test files.

Place regression tests at the BOTTOM of each file under a comment header:
```python
# --- Regression guards (v1.5 / PR #39) ---
```

This preserves existing import structure and groups regressions visually without introducing a new class or marker.

### pytest-asyncio Decorator
**Source:** `tests/test_ssh_tools.py:17`, `tests/test_error_handling.py:23`, `tests/test_http_app.py:183`.
**Apply to:** Every async regression test (all except `test_sch01` which is sync schema-shape and `test_ssh02` which is a sync AST walker).
```python
@pytest.mark.asyncio
async def test_xxx():
    ...
```

### AsyncMock + `@patch(..., new_callable=AsyncMock)` Decorator Pattern
**Source:** `tests/test_ssh_tools.py:17-19, 148-152, 163-164` — project convention for mocking async I/O.
**Apply to:** WS-01 (mock `shell_session_manager`), SSH-01 (mock conn inline; no decorator needed since `_sudo_run` takes `conn` directly), ERR-01 (monkeypatch `asyncio.wait_for`).

### Response-Unpacking Pattern for `error_handling` Results
**Source:** `tests/test_error_handling.py:46-53`.
**Apply to:** ERR-01.
```python
error_data = json.loads(result["content"][0]["text"])
assert error_data["status"] == "error"
assert error_data["error_type"] == "timeout"
```

### AST Walker Pattern (stdlib only)
**Source:** `tests/test_http_app.py:241-293` (two existing in-repo examples).
**Apply to:** SSH-02 meta-test.
```python
import ast
# source from Path(__file__).read_text() OR inspect.getsource(func)
tree = ast.parse(source)
offenders: list[str] = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assert):
        ...
assert not offenders, f"... {offenders}"
```

## No Analog Found

| Test | Reason |
|------|--------|
| `test_ssh02_no_disjunctive_always_true_assertions` | Novel AST meta-test on a test file (not a production module). Pattern is cross-pollinated from `test_http_app.py`'s AST-on-production-function guards, but the *target* (a test file walked for `ast.Assert` nodes with tautological disjuncts) is new in this codebase. No existing test lints other tests. |

## Metadata

**Analog search scope:**
- `tests/test_http_app.py` (293 lines) — full read
- `tests/test_ssh_tools.py` (1052 lines) — headers + target regions (1-250, 1030-1053) + grep scan for `conn.run`, `ProcessError`, `_sudo_run`, `check=True`, `PermissionDenied`
- `tests/test_error_handling.py` (414 lines) — first 200 lines + final 35 lines + grep scan for `timeout_seconds`
- `tests/test_tools.py` (872 lines) — first 80 lines + lines 280-316 + lines 840-872 + grep scan for `inputSchema`, `enum`, `credential_type`

**Production files referenced:**
- `src/homelab_mcp/http_app.py:160-248` (`handle_shell_websocket` + `read_output`)
- `src/homelab_mcp/ssh_tools.py:651-667` (`_sudo_run`)
- `src/homelab_mcp/error_handling.py:1-100` (`timeout_wrapper`)
- `src/homelab_mcp/tool_schemas/credential_tools_schema.py:117-135` (`list_keyring_credentials`)

**Files scanned:** 4 test files + 4 production source regions
**Pattern extraction date:** 2026-04-20
