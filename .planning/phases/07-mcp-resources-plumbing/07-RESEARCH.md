# Phase 7: MCP Resources Plumbing - Research

**Researched:** 2026-03-11
**Domain:** MCP SDK lowlevel.Server resource protocol wiring (Python)
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RES-01 | Server declares `resources` capability and responds to `resources/list` | `@server.list_resources()` decorator triggers automatic `ResourcesCapability` inclusion in `get_capabilities()`; returns `homelab://` URIs |
| RES-05 | All resources return `application/json` content via `resources/read` | `@server.read_resource()` decorator + `ReadResourceContents(content=json_str, mime_type="application/json")` |
| RES-06 | Server returns error code `-32002` for unknown resource URIs | `raise McpError(ErrorData(code=-32002, message="Resource not found"))` caught by SDK `_handle_request` and returned as JSON-RPC error |

</phase_requirements>

---

## Summary

Phase 7 wires the MCP Resources protocol into the existing `lowlevel.Server` instance in `server.py`. The SDK (mcp 1.9.4) already contains all necessary decorators — `@server.list_resources()`, `@server.read_resource()`, `@server.subscribe_resource()`, and `@server.unsubscribe_resource()` — and activates the `resources` capability automatically as soon as a `list_resources` handler is registered. No new dependencies are required.

The implementation adds three decorators to `server.py` (list, read, subscribe/unsubscribe), a `HOMELAB_RESOURCES` registry of `homelab://` URIs with stub JSON content, and a module-level `_subscriptions: set[str]` tracker. The `read_resource` handler raises `McpError(ErrorData(code=-32002, ...))` for unknown URIs — this exception type is caught natively by the SDK's `_handle_request` dispatch loop and returned as a proper JSON-RPC error object.

**Primary recommendation:** Add all four resource handlers directly in `server.py` following the exact same decorator pattern as `handle_list_tools` and `handle_call_tool`. Keep stub data in a module-level dict. No new modules needed for this phase.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` (installed) | 1.9.4 | Provides all resource decorators and types | Already in use; no new dependency |
| `mcp.server.lowlevel.Server` | 1.9.4 | Decorator-based handler registration | Existing server instance |
| `mcp.types` | 1.9.4 | `Resource`, `TextResourceContents`, `ErrorData` | Protocol types |
| `mcp.shared.exceptions.McpError` | 1.9.4 | Raises structured JSON-RPC errors | Caught by SDK dispatch; maps to wire error |
| `mcp.server.lowlevel.helper_types.ReadResourceContents` | 1.9.4 | Return type for `read_resource` handler | Required by SDK handler signature |
| `pydantic.AnyUrl` | bundled with mcp | Type for URI parameter in read/subscribe handlers | SDK handler receives `AnyUrl`, call `str()` to compare |

### No New Installations Required

```bash
# No new packages. All types are already in the installed mcp==1.9.4
```

---

## Architecture Patterns

### Recommended Project Structure

No new files required. All additions go into `src/homelab_mcp/server.py`:

```
src/homelab_mcp/
└── server.py    # Add: HOMELAB_RESOURCES dict, _subscriptions set,
                 #       handle_list_resources, handle_read_resource,
                 #       handle_subscribe_resource, handle_unsubscribe_resource
```

A new test file is needed:

```
tests/
└── test_mcp_resources.py    # New: unit tests for all four handlers
```

### Pattern 1: List Resources Handler

**What:** Registers `resources/list` handler; auto-activates `resources` capability in `ServerCapabilities`.
**When to use:** Always — registering this handler is what triggers RES-01.

```python
# Source: mcp/server/lowlevel/server.py lines 247-258 (installed SDK)
@server.list_resources()  # type: ignore[misc]
async def handle_list_resources() -> list[types.Resource]:
    """Return all declared homelab:// resources."""
    return [
        types.Resource(
            uri=AnyUrl(uri),       # pydantic AnyUrl — host_required=False
            name=meta["name"],
            description=meta["description"],
            mimeType="application/json",
        )
        for uri, meta in HOMELAB_RESOURCES.items()
    ]
```

**SDK mechanics:** When `types.ListResourcesRequest` is registered in `server.request_handlers`, `get_capabilities()` automatically sets `resources_capability = types.ResourcesCapability(subscribe=False, listChanged=False)`.

### Pattern 2: Read Resource Handler — Happy Path

**What:** Serves stub JSON for known URIs.
**Return type:** `Iterable[ReadResourceContents]` — the non-deprecated return path.

```python
# Source: mcp/server/lowlevel/server.py lines 273-329 (installed SDK)
# Source: mcp/server/lowlevel/helper_types.py (ReadResourceContents dataclass)
from mcp.server.lowlevel.helper_types import ReadResourceContents

@server.read_resource()  # type: ignore[misc]
async def handle_read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
    """Return stub JSON for known URIs; raise McpError for unknown."""
    uri_str = str(uri)
    if uri_str not in HOMELAB_RESOURCES:
        raise McpError(
            ErrorData(code=-32002, message="Resource not found", data={"uri": uri_str})
        )
    stub_data = HOMELAB_RESOURCES[uri_str]["stub"]
    return [ReadResourceContents(content=json.dumps(stub_data), mime_type="application/json")]
```

### Pattern 3: Subscribe / Unsubscribe Handlers

**What:** Accepts subscribe/unsubscribe requests, updates module-level set.
**Note:** The SDK hardcodes `subscribe=False` in `get_capabilities()` even when these handlers are registered (verified in SDK source lines 192-194). For Phase 7, this is acceptable — the requirement is that the calls complete without error and update the tracker, not that the capability advertises `subscribe: true`. Phase 9 can address capability advertisement if needed.

```python
# Source: mcp/server/lowlevel/server.py lines 344-368 (installed SDK)
_subscriptions: set[str] = set()

@server.subscribe_resource()  # type: ignore[misc]
async def handle_subscribe_resource(uri: AnyUrl) -> None:
    """Track resource subscription."""
    _subscriptions.add(str(uri))

@server.unsubscribe_resource()  # type: ignore[misc]
async def handle_unsubscribe_resource(uri: AnyUrl) -> None:
    """Remove resource subscription."""
    _subscriptions.discard(str(uri))
```

### Pattern 4: Resource Registry (Stub Data)

```python
# Module-level constant in server.py
HOMELAB_RESOURCES: dict[str, dict[str, Any]] = {
    "homelab://vms": {
        "name": "Virtual Machines",
        "description": "VM inventory from Proxmox, Docker, and LXD",
        "stub": {"vms": [], "_note": "stub — Phase 9 wires live data"},
    },
    "homelab://devices": {
        "name": "Device Inventory",
        "description": "Discovered devices and last discovery data",
        "stub": {"devices": [], "_note": "stub — Phase 9 wires live data"},
    },
    "homelab://services": {
        "name": "Services",
        "description": "Installed service status",
        "stub": {"services": [], "_note": "stub — Phase 9 wires live data"},
    },
}
```

### Anti-Patterns to Avoid

- **Returning `str` or `bytes` from `read_resource`:** The SDK issues a `DeprecationWarning` for this (verified in SDK source lines 300-307). Always return `Iterable[ReadResourceContents]`.
- **Catching `McpError` before it reaches the SDK:** The SDK's `_handle_request` catches `McpError` at line 546 and converts it to a proper error response. Do not wrap it in a try/except inside the handler.
- **Using `int(-32002)` as a raw literal without `ErrorData`:** `McpError` requires an `ErrorData` instance, not a bare int or string.
- **Assuming `subscribe=True` is advertised:** The installed SDK (1.9.4) hardcodes `subscribe=False` in `get_capabilities()`. Do not test for `subscribe: true` in the capabilities check — test only that the handlers execute and the tracker updates correctly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-RPC error responses | Custom error dict / raise ValueError | `McpError(ErrorData(code=-32002, ...))` | SDK dispatch catches `McpError` natively; `ValueError` becomes code 0 internal error |
| Capability advertisement | Manual `ServerCapabilities` construction | Register `@server.list_resources()` — SDK auto-computes | `get_capabilities()` keys off presence of `ListResourcesRequest` in `request_handlers` |
| URI parsing | Custom regex / string split | Use `str(uri)` on the `AnyUrl` parameter | SDK already validates and parses the URI via pydantic before calling the handler |
| Content encoding | Manual base64 | Return `ReadResourceContents(content=json_str, mime_type="application/json")` | SDK wraps in `TextResourceContents` automatically when content is `str` |

**Key insight:** The entire resources wire-up is additive — four new decorator-registered functions in the existing `server.py`. The SDK handles capability auto-detection, protocol framing, and error routing.

---

## Common Pitfalls

### Pitfall 1: `subscribe=False` Hardcoded in SDK

**What goes wrong:** Tests assert `capabilities.resources.subscribe == True` after registering subscribe/unsubscribe handlers.
**Why it happens:** `get_capabilities()` in the installed SDK (1.9.4 line 193) unconditionally sets `subscribe=False`. The subscribe/unsubscribe handlers are registered but the capability flag doesn't reflect them.
**How to avoid:** Phase 7 tests should NOT assert `subscribe: true` in capabilities. Assert `resources` capability is non-None and `resources/subscribe` + `resources/unsubscribe` handlers execute without error.
**Warning signs:** Test checking `server.get_capabilities(...).resources.subscribe is True` fails.

### Pitfall 2: `AnyUrl` Is Not Directly a String

**What goes wrong:** `if uri not in HOMELAB_RESOURCES` is always False when `uri` is `AnyUrl`.
**Why it happens:** `AnyUrl` is a pydantic URL object; dict keys are plain strings.
**How to avoid:** Always convert: `uri_str = str(uri)` before lookup.
**Warning signs:** All reads return "not found" even for known URIs.

### Pitfall 3: DeprecationWarning Becomes Test Failure

**What goes wrong:** Tests fail or emit noisy warnings if `read_resource` returns `str` or `bytes`.
**Why it happens:** SDK lines 300-307 emit `DeprecationWarning` for str/bytes returns. The project's `pytest.ini_options` converts warnings to errors (`filterwarnings = ["error", ...]`) — except `DeprecationWarning` is explicitly ignored. Still, using the deprecated path is fragile.
**How to avoid:** Always return `list[ReadResourceContents]` (the iterable path, SDK line 308+).
**Warning signs:** `DeprecationWarning: Returning str or bytes from read_resource is deprecated`.

### Pitfall 4: `-32002` Is Not a Named Constant in the SDK

**What goes wrong:** Code imports a nonexistent `types.RESOURCE_NOT_FOUND` constant.
**Why it happens:** The SDK only defines `METHOD_NOT_FOUND = -32601`, `CONNECTION_CLOSED = -32000`, etc. (verified in mcp/types.py lines 141-149). `-32002` has no named constant.
**How to avoid:** Use the literal integer `-32002` in `ErrorData(code=-32002, ...)`. Optionally define a local constant `RESOURCE_NOT_FOUND = -32002` in `server.py`.
**Warning signs:** `ImportError: cannot import name 'RESOURCE_NOT_FOUND' from 'mcp.types'`.

---

## Code Examples

Verified from installed SDK source:

### `ErrorData` Import and Usage

```python
# Source: mcp/types.py (installed)
# Source: mcp/shared/exceptions.py (installed)
from mcp.shared.exceptions import McpError
import mcp.types as types

RESOURCE_NOT_FOUND = -32002  # Not in SDK; define locally

raise McpError(
    types.ErrorData(
        code=RESOURCE_NOT_FOUND,
        message="Resource not found",
        data={"uri": uri_str},
    )
)
```

### `ReadResourceContents` Import and Usage

```python
# Source: mcp/server/lowlevel/helper_types.py (installed)
from mcp.server.lowlevel.helper_types import ReadResourceContents

# Returning the non-deprecated iterable path:
return [ReadResourceContents(content='{"key": "value"}', mime_type="application/json")]
```

### `types.Resource` Construction (for list_resources)

```python
# Source: mcp/types.py lines 369-389 (installed)
# Required fields: uri (AnyUrl), name (str)
# Optional: description, mimeType, size
from pydantic import AnyUrl

types.Resource(
    uri=AnyUrl("homelab://vms"),
    name="Virtual Machines",
    description="VM inventory",
    mimeType="application/json",
)
```

### Capabilities Auto-Detection

```python
# Source: mcp/server/lowlevel/server.py lines 191-194 (installed)
# Registering list_resources triggers:
#   resources_capability = types.ResourcesCapability(subscribe=False, listChanged=False)
# Verified: subscribe ALWAYS False in this SDK version regardless of subscribe_resource handler
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Return `str` from `read_resource` | Return `Iterable[ReadResourceContents]` | mcp 1.x | Deprecated; SDK emits warning for str/bytes |
| Manual `ServerCapabilities` construction | Register `@server.list_resources()`; SDK auto-computes | mcp SDK design | No manual capability management needed |

**Deprecated/outdated:**
- Returning `str | bytes` from `read_resource`: deprecated in installed SDK; use `ReadResourceContents` iterable instead.

---

## Open Questions

1. **`subscribe=False` hardcoded in SDK**
   - What we know: `get_capabilities()` in mcp 1.9.4 line 193 unconditionally passes `subscribe=False` even when `subscribe_resource` handler is registered.
   - What's unclear: Whether this is intentional design (capability advertised separately from handler presence) or a bug.
   - Recommendation: Phase 7 does NOT need to fix this. Requirements RES-01/05/06 don't mention `subscribe: true` in capabilities. If a future phase requires it, override `get_capabilities()` or construct `InitializationOptions` manually. Phase 7 tests should verify handler execution only, not capability advertisement for subscribe.

2. **`homelab://` URI scheme validation**
   - What we know: `AnyUrl` with `UrlConstraints(host_required=False)` accepts custom schemes per RFC 3986.
   - What's unclear: Whether pydantic's AnyUrl stringifies `homelab://vms` as `"homelab://vms"` or `"homelab:///vms"` (scheme + authority).
   - Recommendation: Add a quick test asserting `str(AnyUrl("homelab://vms")) == "homelab://vms"` or adjust the registry keys to match actual pydantic output (e.g., `"homelab:///vms"` with empty host). Verify in Wave 0.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_mcp_resources.py -x -v` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RES-01 | `handle_list_resources()` returns list of `types.Resource` with `homelab://` URIs | unit | `uv run pytest tests/test_mcp_resources.py::test_list_resources_returns_resources -x` | Wave 0 |
| RES-01 | `server.request_handlers` contains `ListResourcesRequest` | unit | `uv run pytest tests/test_mcp_resources.py::test_server_has_list_resources_handler -x` | Wave 0 |
| RES-01 | `server.get_capabilities(...)` returns non-None `resources` capability | unit | `uv run pytest tests/test_mcp_resources.py::test_capabilities_include_resources -x` | Wave 0 |
| RES-05 | `handle_read_resource(uri)` for known URI returns `application/json` content | unit | `uv run pytest tests/test_mcp_resources.py::test_read_known_resource_returns_json -x` | Wave 0 |
| RES-05 | Returned content is valid JSON | unit | `uv run pytest tests/test_mcp_resources.py::test_read_resource_content_is_valid_json -x` | Wave 0 |
| RES-06 | `handle_read_resource(uri)` for unknown URI raises `McpError` with code `-32002` | unit | `uv run pytest tests/test_mcp_resources.py::test_read_unknown_resource_raises_mcp_error -x` | Wave 0 |
| RES-06 | `McpError.error.code == -32002` for unknown URI | unit | included above | Wave 0 |
| (subscribe) | `handle_subscribe_resource(uri)` adds URI to `_subscriptions` | unit | `uv run pytest tests/test_mcp_resources.py::test_subscribe_adds_to_tracker -x` | Wave 0 |
| (subscribe) | `handle_unsubscribe_resource(uri)` removes URI from `_subscriptions` | unit | `uv run pytest tests/test_mcp_resources.py::test_unsubscribe_removes_from_tracker -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_mcp_resources.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_mcp_resources.py` — all nine tests listed above (new file; no equivalent exists)

*(Existing test infrastructure in `tests/test_server.py` covers tools plumbing as the reference pattern. No fixture changes needed — tests call handler functions directly as async functions.)*

---

## Sources

### Primary (HIGH confidence)

- Installed SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` — all decorator APIs, `subscribe=False` hardcoding, McpError dispatch
- Installed SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/types.py` — `Resource`, `TextResourceContents`, `ResourcesCapability`, `ErrorData`, error code constants
- Installed SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/shared/exceptions.py` — `McpError` constructor
- Installed SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/server/lowlevel/helper_types.py` — `ReadResourceContents` dataclass
- [MCP Resources Specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/server/resources) — error code -32002 confirmed as "Resource not found"

### Secondary (MEDIUM confidence)

- [mcpevals.io MCP Error Codes](https://www.mcpevals.io/blog/mcp-error-codes) — confirms -32002 = "Resource not found", corroborated by official spec

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all types and decorators verified directly in installed SDK source
- Architecture: HIGH — exact decorator signatures verified in SDK; pattern mirrors existing `server.py` handlers
- Pitfalls: HIGH — `subscribe=False` hardcoding, `AnyUrl` vs string, and DeprecationWarning all verified in SDK source
- Error code -32002: HIGH — confirmed in official MCP spec (2025-06-18) and SDK dispatch logic

**Research date:** 2026-03-11
**Valid until:** 2026-06-11 (mcp 1.9.4 API is stable; re-verify if upgrading past 1.x)
