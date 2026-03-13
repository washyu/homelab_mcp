# Phase 13: Drift Resource - Research

**Researched:** 2026-03-13
**Domain:** MCP Resources, drift detection wiring, in-memory state, resource notifications
**Confidence:** HIGH

## Summary

Phase 13 exposes the latest drift scan result as a passive MCP Resource (`homelab://drift/latest`). Clients can read the result at any time and receive a push notification after each scan without polling. The implementation follows the exact same Resource + notification pattern already established in this codebase for other resources.

All four requirements (DRFT-07 through DRFT-10) are achievable with small, targeted changes: add one entry to the `HOMELAB_RESOURCES` registry, add a `read_drift_resource` reader function following the existing reader pattern, thread the latest report through a module-level cache variable in `server.py`, and call `session.send_resource_updated(uri)` from `handle_call_tool` when `scan_infrastructure_drift` succeeds.

**Primary recommendation:** Follow the established resource reader pattern exactly. Store the latest drift report in a module-level `_latest_drift_report` dict in `server.py` (same pattern as `_resource_manager`). No database changes needed — in-memory state is correct for a "latest scan result" cache that only lasts for the server's lifetime.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DRFT-07 | `homelab://drift/latest` declared in `resources/list` and readable via `resources/read` | Add to `HOMELAB_RESOURCES` dict; add dispatch branch in `handle_read_resource`; add `read_drift_resource` reader |
| DRFT-08 | Returns `{"drift_detected": null}` before any scan has run | Module-level `_latest_drift_report: dict | None = None`; reader returns empty-state response when None |
| DRFT-09 | `scan_infrastructure_drift` stores its result so resource reflects latest scan | Modify `handle_scan_infrastructure_drift` to set module-level cache; or intercept in `handle_call_tool` after successful scan |
| DRFT-10 | Server emits `notifications/resources/updated` after each drift scan | `session.send_resource_updated(AnyUrl("homelab://drift/latest"))` in `handle_call_tool` for `scan_infrastructure_drift` successes |
</phase_requirements>

---

## Standard Stack

### Core (already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp[cli]` | installed | `session.send_resource_updated()`, `types.Resource`, `AnyUrl` | MCP SDK — the method already exists in the installed version |
| `pydantic` | installed | `AnyUrl` construction for URI | Already used everywhere for resource URIs |

**No new packages required.** All capabilities are already present in the installed MCP SDK.

Verified: `send_resource_updated(self, uri: AnyUrl)` exists in `.venv/lib/python3.12/site-packages/mcp/server/session.py` at line 196. It sends `notifications/resources/updated` with `ResourceUpdatedNotificationParams(uri=uri)`.

### Installation

```bash
# Nothing to install — all required APIs already in the virtual environment
uv sync  # ensure lock is current
```

---

## Architecture Patterns

### Recommended Project Structure

Phase 13 adds/modifies:
```
src/homelab_mcp/
├── server.py                   # MODIFY: add HOMELAB_RESOURCES entry, _latest_drift_report cache, dispatch branch, post-scan notification
├── resource_readers.py         # MODIFY: add read_drift_resource() function
└── tool_handlers/
    └── drift_handlers.py       # MODIFY: store result in server._latest_drift_report after scan_drift()

tests/
└── test_drift_resource.py      # NEW: tests for DRFT-07 through DRFT-10
```

### Pattern 1: Resource Registry Entry

Adding `homelab://drift/latest` to `HOMELAB_RESOURCES` dict in `server.py`:

```python
# Source: existing pattern in src/homelab_mcp/server.py lines 111-124
HOMELAB_RESOURCES: dict[str, dict[str, object]] = {
    "homelab://vms": { ... },
    "homelab://devices": { ... },
    "homelab://services": { ... },
    "homelab://drift/latest": {
        "name": "Drift Report",
        "description": "Latest infrastructure drift scan result from scan_infrastructure_drift",
    },
}
```

`handle_list_resources()` iterates `HOMELAB_RESOURCES` automatically — no other change needed to surface the resource in `resources/list`.

### Pattern 2: In-Memory Latest Report Cache

Store the latest scan result in `server.py` at module level, following the `_resource_manager` pattern:

```python
# Source: server.py pattern (lines 50-61)
_latest_drift_report: dict[str, Any] | None = None

def get_latest_drift_report() -> dict[str, Any] | None:
    """Return the latest drift scan result, or None if no scan has run."""
    return _latest_drift_report

def set_latest_drift_report(report: dict[str, Any]) -> None:
    """Store a completed drift scan result."""
    global _latest_drift_report  # noqa: PLW0603
    _latest_drift_report = report
```

Why in-memory over DB:
- A "latest result" cache does not require persistence across restarts — DRFT-08 specifies `null` before any scan, which is the correct fresh-start state
- Avoids a new DB table / migration for ephemeral data
- Consistent with the project's existing pattern: `_resource_manager` is also module-level state, not persisted
- STATE.md confirms: `INSERT OR REPLACE` + UNIQUE for SQLite upsert is established for baselines, but baselines are intentionally durable; the latest report is not

### Pattern 3: Resource Reader Function

Add `read_drift_resource()` to `resource_readers.py`, following the identical pattern of the three existing readers:

```python
# Source: resource_readers.py pattern (lines 29-72)
async def read_drift_resource() -> dict[str, Any]:
    """Return the latest drift scan result.

    Returns:
        Before any scan: {"drift_detected": null, "scanned_at": null}
        After a scan: full structured report from scan_drift()
    """
    from .server import get_latest_drift_report  # deferred — avoids circular import

    report = get_latest_drift_report()
    if report is None:
        return {"drift_detected": None}
    return report
```

The deferred import pattern (`from .server import ...` inside the function body) is mandatory here, as it is for all existing readers. This avoids the circular import between `server.py` and `resource_readers.py`.

### Pattern 4: Read Resource Dispatch Branch

Add a dispatch branch in `handle_read_resource` in `server.py`:

```python
# Source: server.py handle_read_resource (lines 184-213)
elif uri_str == "homelab://drift/latest":
    payload = await read_drift_resource()
```

Import `read_drift_resource` at the top of `server.py` alongside the existing reader imports:
```python
from .resource_readers import read_devices_resource, read_drift_resource, read_service_resource, read_vms_resource
```

### Pattern 5: Store Result and Emit Notification After Scan

Modify `handle_scan_infrastructure_drift` in `drift_handlers.py` to set the cache:

```python
# Source: drift_handlers.py (all 21 lines) + server.py notification pattern (lines 379-387)
async def handle_scan_infrastructure_drift(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle scan_infrastructure_drift tool."""
    from ..server import get_resource_manager, set_latest_drift_report

    rm = get_resource_manager()
    result = await scan_drift(
        session=rm.proxmox_session,
        db_adapter=rm.db_adapter,
        node=arguments.get("node"),
        vm_type=arguments.get("vm_type", "all"),
    )
    # Store so homelab://drift/latest reflects this scan (DRFT-09)
    set_latest_drift_report(result)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

Notification emission (DRFT-10) belongs in `handle_call_tool` in `server.py`, following the exact same pattern as `send_resource_list_changed` for mutating tools. Add `scan_infrastructure_drift` to a `DRIFT_SCAN_TOOLS` frozenset (or reuse existing pattern inline):

```python
# Source: server.py lines 376-387 — existing notification pattern
DRIFT_SCAN_TOOLS: frozenset[str] = frozenset({"scan_infrastructure_drift"})

# In handle_call_tool, after content = _convert_result(result):
if name in DRIFT_SCAN_TOOLS:
    try:
        session = server.request_context.session
        await session.send_resource_updated(AnyUrl("homelab://drift/latest"))
    except LookupError:
        logger.debug("No request context available for drift resource notification")
```

### Anti-Patterns to Avoid

- **Storing the report in the database:** The latest drift result is ephemeral session state. A DB write on every scan adds I/O and schema complexity for no benefit.
- **Emitting the notification from inside `drift_handlers.py`:** The server session is only accessible via `server.request_context`, which belongs to the server layer. Keep notification dispatch in `handle_call_tool` in `server.py` — consistent with MUTATING_TOOLS notification pattern.
- **Adding `homelab://drift/latest` to `MUTATING_TOOLS`:** That frozenset triggers `send_resource_list_changed`, not `send_resource_updated`. Use a separate `DRIFT_SCAN_TOOLS` frozenset.
- **Returning an empty dict `{}` for the pre-scan state:** DRFT-08 explicitly requires `{"drift_detected": null}` — `null` signals "not yet scanned" vs. `false` which would mean "scanned and no drift found."

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Resource-updated push notification | Custom WebSocket or polling endpoint | `session.send_resource_updated(uri)` | Already in the installed MCP SDK session object |
| "Latest result" persistence | A new `drift_latest_report` DB table + migration | Module-level `_latest_drift_report` dict | Ephemeral data; DB overhead not justified; DRFT-08 requires null reset on restart |
| URI validation | Custom string matching | `AnyUrl("homelab://drift/latest")` from pydantic | Consistent with all other URI handling in server.py |

**Key insight:** The MCP SDK's `ServerSession.send_resource_updated(uri)` is a first-class method that handles the full `notifications/resources/updated` wire protocol. There is nothing to implement in the transport layer.

---

## Common Pitfalls

### Pitfall 1: Wrong Notification Method
**What goes wrong:** Using `send_resource_list_changed()` instead of `send_resource_updated(uri)`. The former tells clients the set of available resources changed; the latter tells clients the content of a specific resource changed.
**Why it happens:** `send_resource_list_changed` is already used in the codebase for MUTATING_TOOLS, making it the familiar reference.
**How to avoid:** DRFT-10 specifies `notifications/resources/updated` — use `send_resource_updated(AnyUrl("homelab://drift/latest"))`.
**Warning signs:** MCP client re-fetches `resources/list` instead of re-reading `homelab://drift/latest`.

### Pitfall 2: Circular Import
**What goes wrong:** Importing `set_latest_drift_report` at the module level in `drift_handlers.py` causes a circular import (`drift_handlers` -> `server` -> `tool_handlers` -> `drift_handlers`).
**Why it happens:** `server.py` imports from `tool_handlers`; if `tool_handlers` imports from `server` at module level, it creates a cycle.
**How to avoid:** Use the established deferred import pattern: `from ..server import set_latest_drift_report` inside the handler function body, not at the top of the file. This is exactly how all existing readers import `get_resource_manager`.
**Warning signs:** `ImportError: cannot import name` at startup.

### Pitfall 3: Pre-scan Response Shape
**What goes wrong:** Returning `{}` or `None` or raising McpError when no scan has run.
**Why it happens:** Empty state is easy to overlook.
**How to avoid:** DRFT-08 is explicit: return `{"drift_detected": null}`. This is a valid JSON object with a null-valued key — not an empty object, not an error.
**Warning signs:** MCP client throws a parse error or treats the pre-scan read as a failure.

### Pitfall 4: Resource URI String vs AnyUrl Comparison
**What goes wrong:** `str(AnyUrl("homelab://drift/latest"))` may normalize the URI differently depending on pydantic version.
**Why it happens:** AnyUrl strips trailing slashes or adds/removes components during validation.
**How to avoid:** Use `uri_str == "homelab://drift/latest"` for comparison in `handle_read_resource`, which compares against `str(uri)` — the same pattern used for `homelab://vms` and `homelab://devices`. Verify `str(AnyUrl("homelab://drift/latest"))` == `"homelab://drift/latest"` in a test.
**Warning signs:** `handle_read_resource` falls through to the `RESOURCE_NOT_FOUND` branch even after adding the dispatch branch.

---

## Code Examples

Verified patterns from the installed codebase:

### MCP SDK: send_resource_updated signature
```python
# Source: .venv/lib/python3.12/site-packages/mcp/server/session.py:196
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

### Existing notification dispatch in handle_call_tool (reference pattern)
```python
# Source: src/homelab_mcp/server.py:376-387
if name in MUTATING_TOOLS and not is_dry_run:
    try:
        session = server.request_context.session
        await session.send_resource_list_changed()
    except LookupError:
        logger.debug("No request context available for resource notification")
```

### Existing module-level state (reference pattern)
```python
# Source: src/homelab_mcp/server.py:50-61
_resource_manager: ResourceManager | None = None

def get_resource_manager() -> ResourceManager:
    if _resource_manager is None:
        raise RuntimeError("ResourceManager not available -- server lifespan not started")
    return _resource_manager
```

### Deferred import inside reader (mandatory pattern for circular-import avoidance)
```python
# Source: src/homelab_mcp/resource_readers.py:38
from .server import get_resource_manager  # deferred to avoid circular import
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled JSON-RPC | MCP SDK `lowlevel.Server` | Phase 4 / v1.0 | All notification APIs now come from SDK session object |
| No resource notifications | `send_resource_list_changed` for device writes | Phase 10 / v1.1 | Pattern now established; `send_resource_updated` is the next tier |

---

## Open Questions

1. **Does `send_resource_updated` require an active subscription?**
   - What we know: `send_resource_list_changed` is sent to all sessions regardless of subscriptions. The SDK method wraps `send_notification` which does not check `_subscriptions`.
   - What's unclear: Whether the SDK session filters `notifications/resources/updated` to only subscribed clients or broadcasts. The server-side `_subscriptions` set is managed by `handle_subscribe_resource` / `handle_unsubscribe_resource` but is not consulted in `send_resource_list_changed`.
   - Recommendation: Emit unconditionally (same approach as `send_resource_list_changed`). The MCP spec says clients that subscribe receive the notification — the server is not required to filter. Unconditional emit is safe: non-subscribed clients can ignore the notification.

2. **Should `set_latest_drift_report` reset to `None` on server shutdown?**
   - What we know: `_resource_manager` is reset to `None` in the `app_lifespan` finally block.
   - What's unclear: Whether the same reset is needed for `_latest_drift_report`.
   - Recommendation: Not required. The module-level variable is process-scoped; it resets automatically when the process exits. Adding lifespan reset is defensive but not necessary for correctness.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest]` |
| Quick run command | `uv run pytest tests/test_drift_resource.py -x` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DRFT-07 | `homelab://drift/latest` appears in `resources/list` with name, description, mimeType | unit | `uv run pytest tests/test_drift_resource.py::TestDriftResourceRegistration -x` | Wave 0 |
| DRFT-07 | `resources/read homelab://drift/latest` dispatches without RESOURCE_NOT_FOUND | unit | `uv run pytest tests/test_drift_resource.py::TestDriftResourceRead -x` | Wave 0 |
| DRFT-08 | Read before any scan returns `{"drift_detected": null}` | unit | `uv run pytest tests/test_drift_resource.py::test_read_drift_resource_empty_state -x` | Wave 0 |
| DRFT-09 | After scan, `resources/read` returns the scan result | unit | `uv run pytest tests/test_drift_resource.py::test_read_drift_resource_after_scan -x` | Wave 0 |
| DRFT-10 | `handle_call_tool` calls `send_resource_updated` after scan_infrastructure_drift | unit | `uv run pytest tests/test_drift_resource.py::test_notification_emitted_after_scan -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_drift_resource.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_drift_resource.py` — covers DRFT-07, DRFT-08, DRFT-09, DRFT-10
- [ ] No new conftest or fixtures needed — existing `unittest.mock` + `pytest-asyncio` pattern is sufficient

---

## Sources

### Primary (HIGH confidence)
- Installed MCP SDK source — `.venv/lib/python3.12/site-packages/mcp/server/session.py:196` — `send_resource_updated` signature and wire format verified directly
- `src/homelab_mcp/server.py` — HOMELAB_RESOURCES registry, handle_read_resource dispatch, MUTATING_TOOLS notification pattern, module-level state pattern
- `src/homelab_mcp/resource_readers.py` — deferred import pattern, reader function structure
- `src/homelab_mcp/tool_handlers/drift_handlers.py` — current scan_drift call flow
- `src/homelab_mcp/database.py` — confirmed no `drift_latest_report` table exists; schema shows `drift_baselines` is durable/intentional

### Secondary (MEDIUM confidence)
- MCP specification: `notifications/resources/updated` is the correct wire method for "resource content changed" vs `notifications/resources/list_changed` for "available resource set changed"

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all APIs verified in installed packages and existing codebase
- Architecture: HIGH — pattern is a direct extension of three already-working readers and one existing notification dispatch
- Pitfalls: HIGH — derived from examining the actual circular import structure and existing code patterns

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (MCP SDK is stable; patterns are internal to codebase)
