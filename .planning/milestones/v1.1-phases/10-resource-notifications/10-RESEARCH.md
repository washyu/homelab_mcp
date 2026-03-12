# Phase 10: Resource Notifications - Research

**Researched:** 2026-03-11
**Domain:** MCP SDK notification dispatch — `notifications/resources/list_changed` and `notifications/resources/updated`
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RES-07 | Server emits `notifications/resources/list_changed` after `ssh_discover` adds new devices | `ServerSession.send_resource_list_changed()` is the send path; the device-writing tool is `discover_and_map` (not `ssh_discover`); hook must be placed in `handle_call_tool` after a successful mutation — see Critical Clarification below |

</phase_requirements>

---

## Summary

Phase 10 wires up MCP resource notifications so connected clients learn about inventory changes without polling. The MCP SDK (mcp 1.9.4, already installed) ships `ServerSession.send_resource_list_changed()` and `ServerSession.send_resource_updated(uri)` — both are async, no-argument and single-uri-argument methods respectively that send the correct JSON-RPC notification method strings over the active transport.

The session is reachable inside any handler through `server.request_context.session`, which is set by `Server._handle_request()` before calling the handler. The `_subscriptions` set in `server.py` already tracks which URIs a client has subscribed to. No new MCP SDK features or new dependencies are needed.

The single implementation site is `handle_call_tool` in `server.py`. After the tool handler returns a non-error result, `handle_call_tool` calls `session.send_resource_list_changed()` for tools that write new devices to the database. Dry-run calls are excluded because `_is_error_result()` already sees their `mode: dry_run` flag as a non-error, so a separate `dry_run` argument check is required.

**Critical clarification on tool naming:** RES-07 mentions `ssh_discover`, but that tool (`ssh_discover_system`) only collects hardware info — it does NOT write to the database. The tool that actually inserts/updates device rows is `discover_and_map` (and `bulk_discover_and_map`), which call `discover_and_store()` → `sitemap.store_device()` → `db_adapter.store_device()`. The notification must fire after `discover_and_map` / `bulk_discover_and_map`, not after `ssh_discover`. The phase success criterion should be interpreted as: "after the tool that stores discovered devices runs successfully."

**Primary recommendation:** In `handle_call_tool`, after a successful result, check tool name against a `MUTATING_TOOLS` set and emit `send_resource_list_changed()` on the session.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` | 1.9.4 (installed) | `ServerSession.send_resource_list_changed()`, `ServerSession.send_resource_updated()` | Already installed; these methods exist and are verified |
| `mcp.server.session` | 1.9.4 | `ServerSession` — the object holding the active transport connection | Accessed via `server.request_context.session` inside handler scope |
| `mcp.types` | 1.9.4 | `ResourceListChangedNotification`, `ResourceUpdatedNotification`, `ResourceUpdatedNotificationParams` | Already imported; used internally by the session methods |
| `pydantic.AnyUrl` | installed | Argument type for `send_resource_updated(uri)` | Already used throughout server.py |

### No New Dependencies

```bash
# All required types and methods exist in the installed mcp 1.9.4.
# No new packages needed.
```

---

## Architecture Patterns

### Recommended Change Set

```
src/homelab_mcp/
└── server.py   # MODIFY: handle_call_tool gains post-success notification dispatch
                #         Add MUTATING_TOOLS constant (set of tool names that add devices)

tests/
└── test_mcp_resources.py  # MODIFY: add notification dispatch tests
```

No new files required. This is a targeted addition to `handle_call_tool`.

### Pattern 1: Post-Mutation Notification in `handle_call_tool`

**What:** After a successful (non-error) tool result, check if the tool name is in a `MUTATING_TOOLS` set and, if so, call `session.send_resource_list_changed()`.
**When to use:** Only for tools that write new devices (list-changing mutations). Not for read-only tools.

```python
# Source: mcp 1.9.4 ServerSession — verified via inspect.getsource()

# Constant: tools that add/remove devices from the DB (list-changing)
MUTATING_TOOLS: frozenset[str] = frozenset({
    "discover_and_map",
    "bulk_discover_and_map",
})

@server.call_tool()  # type: ignore[misc]
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    handler = get_tool_handler(name)
    result = await handler(arguments or {})
    if _is_error_result(result):
        raise ToolError(_extract_error_text(result))
    content = _convert_result(result)

    # Notify subscribed clients when a tool writes new devices
    if name in MUTATING_TOOLS:
        try:
            session = server.request_context.session
            await session.send_resource_list_changed()
        except LookupError:
            # No active request context (e.g. called outside MCP lifecycle in tests)
            logger.debug("No request context available for resource notification")

    return content
```

### Pattern 2: Dry-Run Exclusion

The phase requires "dry-run executions do not trigger notifications." Dry-run results flow through the handler as a normal (non-error) dict with `mode: dry_run`. They will NOT pass `_is_error_result()` — the `ToolError` branch is skipped. The notification guard must therefore also exclude dry-run calls.

The `arguments` dict passed to `handle_call_tool` contains `dry_run: true` for dry-run calls. The check is:

```python
# Inside handle_call_tool, before the notification block:
is_dry_run = bool((arguments or {}).get("dry_run", False))
if name in MUTATING_TOOLS and not is_dry_run:
    try:
        session = server.request_context.session
        await session.send_resource_list_changed()
    except LookupError:
        logger.debug("No request context available for resource notification")
```

Note: None of the device-discovery tools (`discover_and_map`, `bulk_discover_and_map`) currently have a `dry_run` parameter in their schemas, so this guard is defensive future-proofing. It costs one dict lookup and is correct behavior.

### Pattern 3: Accessing Session from Within Handler Scope

`server.request_context` is a Python `@property` wrapping a `contextvars.ContextVar`. It is set by `Server._handle_request()` before any handler is invoked, and reset in the `finally` block after. Therefore, it is always valid inside `handle_call_tool`. The property raises `LookupError` if called outside a request context (e.g., in tests that invoke the handler directly without going through `_handle_request`). Always guard with `try/except LookupError`.

```python
# Source: mcp.server.lowlevel.server — verified via inspect.getsource()
# request_ctx is a ContextVar set per-request in _handle_request()
session = server.request_context.session  # type: ServerSession
await session.send_resource_list_changed()  # sends notifications/resources/list_changed
```

### Anti-Patterns to Avoid

- **Calling `send_resource_list_changed` from inside `discover_and_store` (sitemap.py):** The session object only exists during an active MCP request context. Pushing it into domain logic creates a tight coupling and makes the function un-callable from background tasks. Keep notification dispatch in `server.py` only.
- **Using `send_resource_updated` instead of `send_resource_list_changed`:** `send_resource_updated(uri)` is for content changes to an already-known resource. A newly discovered device changes the _list_ of resources (new entry in `homelab://devices`), so `list_changed` is the correct notification.
- **Emitting notifications on every tool call:** Only `MUTATING_TOOLS` membership should trigger the notification. Read-only tools (list_vms, get_service_status, etc.) must not emit.
- **Forgetting `try/except LookupError` around `server.request_context`:** In tests that call handlers directly (not through the MCP request loop), there is no `ContextVar` token set. Without the guard, unit tests crash with `LookupError`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sending `notifications/resources/list_changed` | Custom JSON-RPC message construction | `session.send_resource_list_changed()` | SDK method handles framing, method string, and transport write in 4 lines |
| Sending `notifications/resources/updated` | Direct `write_stream.send()` calls | `session.send_resource_updated(uri)` | SDK handles `ResourceUpdatedNotificationParams`, JSON encoding, wrapping in `ServerNotification` |
| Tracking subscribed clients | Custom subscriber registry | `_subscriptions` set already in `server.py` | Already implemented in Phase 7 |

**Key insight:** The notification send path is a one-liner method call on the session object. The complexity is entirely in (1) identifying the right moment to call it and (2) not calling it when dry-run is active.

---

## Common Pitfalls

### Pitfall 1: `ssh_discover` vs `discover_and_map` Confusion
**What goes wrong:** Implementing the hook after `ssh_discover` calls, which never writes to the database.
**Why it happens:** RES-07 text uses the name `ssh_discover`, but that tool only gathers hardware data and returns a JSON string — it does not call `store_device()`. Device database writes happen only in `discover_and_map` → `discover_and_store` → `sitemap.store_device()`.
**How to avoid:** Attach the notification to `discover_and_map` and `bulk_discover_and_map` in `MUTATING_TOOLS`. Verify by tracing the call chain: `handle_discover_and_map` → `discover_and_store` → `sitemap.store_device` → `db_adapter.store_device`.
**Warning signs:** If adding a device via `ssh_discover` and then checking `homelab://devices` shows the device was not stored, the wrong tool was targeted.

### Pitfall 2: No Guard on `server.request_context` in Tests
**What goes wrong:** Unit tests that call `handle_call_tool(...)` directly (bypassing the MCP `_handle_request` machinery) raise `LookupError: <ContextVar>` when the notification code runs.
**Why it happens:** `request_ctx` is a `contextvars.ContextVar` with no default. It is only set inside `_handle_request`. Direct handler invocations skip that path.
**How to avoid:** Wrap the session access in `try/except LookupError`. In tests, mock `server.request_context` or ensure the `LookupError` path is silently swallowed.
**Warning signs:** Test failures with `LookupError` in the notification block.

### Pitfall 3: Notification Fires on Error Results
**What goes wrong:** A tool call fails (e.g., SSH timeout), `_is_error_result` returns True, `ToolError` is raised — but the notification code runs before the raise.
**Why it happens:** Misplacing the notification block before the `_is_error_result` check.
**How to avoid:** Place the notification block AFTER both `_is_error_result` check and `_convert_result` call — i.e., only on the success path that reaches `return content`.

### Pitfall 4: `send_resource_list_changed` called during dry-run
**What goes wrong:** A dry-run call to a mutating tool triggers a spurious `list_changed` notification, causing clients to re-fetch the resource list unnecessarily.
**Why it happens:** Dry-run results are not error results — they are valid non-error dicts with `mode: dry_run`. They pass the `_is_error_result` check silently.
**How to avoid:** Check `arguments.get("dry_run", False)` before emitting the notification.

---

## Code Examples

Verified patterns from installed mcp 1.9.4 source:

### `ServerSession.send_resource_list_changed` — actual source

```python
# Source: mcp.server.session (verified via inspect.getsource)
async def send_resource_list_changed(self) -> None:
    """Send a resource list changed notification."""
    await self.send_notification(
        types.ServerNotification(
            types.ResourceListChangedNotification(
                method="notifications/resources/list_changed",
            )
        )
    )
```

### `ServerSession.send_resource_updated` — actual source

```python
# Source: mcp.server.session (verified via inspect.getsource)
async def send_resource_updated(self, uri: AnyUrl) -> None:
    """Send a resource updated notification."""
    await self.send_notification(
        types.ServerNotification(
            types.ResourceUpdatedNotification(
                method="notifications/resources/updated",
                params=types.ResourceUpdatedNotificationParams(uri=uri),
            )
        )
    )
```

### Accessing the Session from a Handler

```python
# Source: mcp.server.lowlevel.server RequestContext dataclass (verified)
# server.request_context returns RequestContext[ServerSession, LifespanResultT, RequestT]
# .session is the ServerSession field
session: ServerSession = server.request_context.session
```

### Test Pattern: Mocking Session and Request Context

```python
# Pattern used in existing test_server.py for handle_call_tool tests
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_discover_and_map_sends_list_changed(mocker: MockerFixture) -> None:
    mock_session = MagicMock()
    mock_session.send_resource_list_changed = AsyncMock()

    mock_context = MagicMock()
    mock_context.session = mock_session

    mocker.patch(
        "src.homelab_mcp.server.server.request_context",
        new_callable=lambda: property(lambda self: mock_context),
    )
    # ... or patch via property directly on the server object
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled JSON-RPC notification construction | `ServerSession.send_resource_list_changed()` | mcp 1.x (current) | No custom framing code needed |
| Polling for resource changes | `notifications/resources/list_changed` push | MCP spec current | Clients don't need to poll |

---

## Open Questions

1. **Should `bulk_discover_and_map` emit one notification or N notifications?**
   - What we know: It loops over N targets, calling `discover_and_store` per device. Each is a separate DB write.
   - What's unclear: Emitting one notification after all N writes completes vs. one per write.
   - Recommendation: Emit one notification at the `handle_call_tool` level after the full bulk operation completes. Clients re-fetch the whole `homelab://devices` list anyway; N notifications would cause N re-fetches with no benefit.

2. **Does `discover_and_map` need to distinguish "new device added" vs "existing device updated"?**
   - What we know: `db_adapter.store_device()` returns the device ID regardless of insert/update. `existing = cursor.fetchone()` distinguishes new (INSERT) from existing (UPDATE) internally — but the return value is just `int` (device ID).
   - What's unclear: Whether to emit `list_changed` only for new inserts or also for updates.
   - Recommendation: The requirement says "after `ssh_discover` adds new devices" — emit `list_changed` only when a new device row is inserted (INSERT path, not UPDATE). This requires `store_device` to return a flag. Simplest option: change return type to `tuple[int, bool]` where bool is `is_new`. If that change is too invasive, emit `list_changed` on every successful `discover_and_map` call (conservative, causes harmless extra re-fetches on updates).

3. **`send_resource_list_changed` vs `send_resource_updated` for new devices?**
   - What we know: `list_changed` means "the set of available resources changed"; `updated` means "a specific resource's content changed."
   - Resolution: New device → `homelab://devices` content changes AND the device is a new entry. `list_changed` is correct because the device inventory list grew. `send_resource_updated(AnyUrl("homelab://devices"))` could also be sent as a supplementary signal, but `list_changed` alone satisfies the requirement.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` or `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_mcp_resources.py -x` |
| Full suite command | `uv run pytest tests/ -m "not integration" -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RES-07 | `discover_and_map` success → `send_resource_list_changed()` called | unit | `uv run pytest tests/test_mcp_resources.py::test_discover_and_map_sends_list_changed -x` | ❌ Wave 0 |
| RES-07 | `bulk_discover_and_map` success → `send_resource_list_changed()` called | unit | `uv run pytest tests/test_mcp_resources.py::test_bulk_discover_and_map_sends_list_changed -x` | ❌ Wave 0 |
| RES-07 | `discover_and_map` with `dry_run: true` → notification NOT sent | unit | `uv run pytest tests/test_mcp_resources.py::test_dry_run_does_not_send_notification -x` | ❌ Wave 0 |
| RES-07 | `ssh_discover` (read-only) → notification NOT sent | unit | `uv run pytest tests/test_mcp_resources.py::test_ssh_discover_no_notification -x` | ❌ Wave 0 |
| RES-07 | `send_resource_list_changed` not called when tool returns error | unit | `uv run pytest tests/test_mcp_resources.py::test_error_result_no_notification -x` | ❌ Wave 0 |
| RES-07 | `LookupError` from missing request context is swallowed silently | unit | `uv run pytest tests/test_mcp_resources.py::test_no_context_no_crash -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_mcp_resources.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_mcp_resources.py` — add notification dispatch test cases (file exists, needs 6 new test functions)
- [ ] No new test file needed — extend existing `test_mcp_resources.py`

---

## Sources

### Primary (HIGH confidence)

- `mcp` 1.9.4 installed package — `inspect.getsource(ServerSession.send_resource_list_changed)` and `inspect.getsource(ServerSession.send_resource_updated)` — exact method signatures and bodies verified
- `mcp.server.lowlevel.server` — `inspect.getsource(Server._handle_request)` — confirmed `request_ctx.set(RequestContext(..., session, ...))` is called before handler invocation
- `mcp.server.lowlevel.server` — `inspect.getsource(RequestContext)` — confirmed `session: SessionT` field on the dataclass
- `src/homelab_mcp/server.py` — current server implementation, `_subscriptions` set, `handle_call_tool` structure
- `src/homelab_mcp/sitemap.py` — `discover_and_store` and `store_device` call chain
- `src/homelab_mcp/database.py` lines 236–331 — `store_device` INSERT/UPDATE logic
- `src/homelab_mcp/tool_handlers/network_handlers.py` — confirmed `discover_and_map` calls `discover_and_store`
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` — confirmed `ssh_discover` does NOT call `store_device`

### Secondary (MEDIUM confidence)

- MCP specification via `mcp.types` module — `ResourceListChangedNotification`, `ResourceUpdatedNotification`, `ResourceUpdatedNotificationParams` class definitions verified via `inspect.getsource`

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all relevant SDK methods verified by reading installed source
- Architecture: HIGH — call path traced end-to-end in existing code
- Pitfalls: HIGH — `ssh_discover` vs `discover_and_map` confusion verified by reading both handlers; `LookupError` guard verified by reading `_handle_request` source
- Test patterns: HIGH — follows pattern established in `test_mcp_resources.py` and `test_server.py`

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (mcp SDK is stable; 30-day window)
