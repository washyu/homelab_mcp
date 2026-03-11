# Phase 4: MCP Protocol Compliance - Research

**Researched:** 2026-03-11
**Domain:** MCP logging notifications, Streamable HTTP protocol compliance
**Confidence:** HIGH

## Summary

Phase 4 covers two distinct requirements: (1) emitting MCP logging notifications during long-running operations (MCP-03), and (2) ensuring HTTP transport compliance with the Streamable HTTP spec -- specifically Origin header validation, session management, and content-type handling (MCP-04).

The MCP Python SDK (>=1.9.1) already provides all the primitives needed. `ServerSession.send_log_message()` sends `notifications/message` to clients, and the `set_logging_level` decorator on `lowlevel.Server` enables the logging capability in `ServerCapabilities`. The Streamable HTTP transport (`StreamableHTTPServerTransport`) already handles session management, content-type validation, and Accept header checks. The main gap is Origin header validation, which the SDK does NOT implement -- it must be added as Starlette middleware in `http_app.py`.

**Primary recommendation:** Add a `set_logging_level` handler + use `session.send_log_message()` for progress in long-running tool handlers, and add Origin validation middleware to the Starlette app.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MCP-03 | Server emits MCP logging notifications for long-running operations | `ServerSession.send_log_message()` API verified in SDK; `set_logging_level` decorator enables capability; `request_ctx` contextvar provides session access from handlers |
| MCP-04 | HTTP transport complies with Streamable HTTP spec (session management, Origin validation) | Session management already handled by `StreamableHTTPSessionManager`; Origin validation needs custom middleware; content-type handling already in `StreamableHTTPServerTransport` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp[cli] | >=1.9.1 | MCP SDK - logging notifications, Streamable HTTP transport | Already in use; provides `send_log_message()`, `set_logging_level`, `StreamableHTTPSessionManager` |
| starlette | (transitive via mcp) | ASGI framework for HTTP middleware | Already in use for `http_app.py`; Origin validation added as middleware |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | (transitive via mcp) | SSE streaming in HTTP transport | Already used by SDK transport; no changes needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Starlette middleware for Origin | Nginx/reverse proxy Origin check | Middleware keeps it self-contained; reverse proxy adds deployment dependency |

**Installation:**
No new dependencies needed. Everything is already available via `mcp[cli]>=1.9.1`.

## Architecture Patterns

### Pattern 1: MCP Logging Notifications via request_ctx

**What:** Access the `ServerSession` from within tool handlers using the `request_ctx` contextvar, then call `session.send_log_message()` to emit progress notifications.

**When to use:** Any tool handler that iterates over multiple items (bulk discovery, deployment, service installation).

**How it works in this codebase:**
1. Register a `@server.set_logging_level()` handler in `server.py` -- this enables the `logging` capability in `ServerCapabilities`
2. Access session via `request_ctx.get().session` from the `mcp.server.lowlevel.server` module
3. Call `session.send_log_message(level, data, logger=name)` during iteration

**Example:**
```python
# In server.py - enable logging capability
from mcp.server.lowlevel.server import request_ctx
import mcp.types as types

# Module-level minimum log level (client can change via logging/setLevel)
_min_log_level: types.LoggingLevel = "info"

@server.set_logging_level()
async def handle_set_level(level: types.LoggingLevel) -> None:
    global _min_log_level
    _min_log_level = level

# Helper function for tool handlers to emit progress
async def emit_progress(level: types.LoggingLevel, message: str, data: dict | None = None) -> None:
    """Send an MCP logging notification to the client."""
    try:
        ctx = request_ctx.get()
        await ctx.session.send_log_message(
            level=level,
            data=data or message,
            logger="homelab-mcp",
        )
    except LookupError:
        # Not in a request context (e.g., during tests)
        pass
```

```python
# In a handler (e.g., bulk_discover_and_store)
from ..server import emit_progress

async def bulk_discover_and_store(sitemap, targets):
    results = []
    for i, target in enumerate(targets):
        await emit_progress(
            "info",
            f"Discovering {target['hostname']} ({i+1}/{len(targets)})",
        )
        result = await discover_and_store(sitemap, ...)
        results.append(result)
    return results
```

**Source:** Verified from SDK source at `.venv/lib/python3.12/site-packages/mcp/server/session.py` lines 174-194 and `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` lines 331-342, 98.

### Pattern 2: Origin Header Validation Middleware

**What:** Starlette middleware that validates the `Origin` header on all POST/GET requests to `/mcp`. The MCP spec says servers "MUST validate the Origin header on all incoming connections to prevent DNS rebinding attacks."

**When to use:** Always active in HTTP transport mode.

**Example:**
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class OriginValidationMiddleware(BaseHTTPMiddleware):
    """Validate Origin header to prevent DNS rebinding attacks (MCP spec requirement)."""

    def __init__(self, app, allowed_origins: list[str] | None = None):
        super().__init__(app)
        # Default: allow requests with no Origin (non-browser) and localhost
        self.allowed_origins = allowed_origins or [
            "http://localhost",
            "https://localhost",
            "http://127.0.0.1",
            "https://127.0.0.1",
        ]

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        # No Origin header = non-browser request (allow)
        if origin is None:
            return await call_next(request)
        # Check against allowed origins
        if not self._is_allowed(origin):
            return JSONResponse(
                {"error": "Forbidden: Origin not allowed"},
                status_code=403,
            )
        return await call_next(request)

    def _is_allowed(self, origin: str) -> bool:
        for allowed in self.allowed_origins:
            if origin == allowed or origin.startswith(allowed + ":"):
                return True
        return False
```

**Source:** MCP Spec 2025-03-26, Streamable HTTP Security Warning section.

### Pattern 3: Logging Level Filtering

**What:** The MCP spec allows clients to set a minimum log level via `logging/setLevel`. The server should filter notifications below that level.

**Key detail:** `LoggingLevel` values are: `"debug"`, `"info"`, `"notice"`, `"warning"`, `"error"`, `"critical"`, `"alert"`, `"emergency"`. These follow syslog severity ordering.

```python
LOG_LEVEL_ORDER: dict[str, int] = {
    "debug": 0, "info": 1, "notice": 2, "warning": 3,
    "error": 4, "critical": 5, "alert": 6, "emergency": 7,
}

def should_emit(level: str, min_level: str) -> bool:
    return LOG_LEVEL_ORDER.get(level, 0) >= LOG_LEVEL_ORDER.get(min_level, 0)
```

### Anti-Patterns to Avoid
- **Sending log messages from outside request context:** `request_ctx.get()` will raise `LookupError` if called outside a handler. Always wrap in try/except.
- **Flooding clients with log messages:** Only emit for meaningful progress milestones, not every micro-step. One notification per target in a bulk operation is appropriate.
- **Blocking on log message delivery:** `send_log_message` is async but should not block operation progress. The SDK handles backpressure via memory streams.
- **Wildcard Origin allowance:** Never allow `*` for Origin validation. That defeats the purpose of DNS rebinding protection. CORS `Access-Control-Allow-Origin: *` is different from Origin validation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session management | Custom session tracking | `StreamableHTTPSessionManager` | Already handles session ID generation, validation, lifecycle |
| Content-type validation | Manual header parsing | `StreamableHTTPServerTransport._check_content_type()` / `_check_accept_headers()` | Already implemented in SDK transport |
| SSE streaming | Custom SSE implementation | `sse-starlette` via SDK transport | Already wired up in `StreamableHTTPServerTransport` |
| Log message serialization | Manual JSON-RPC notification | `ServerSession.send_log_message()` | Handles proper `notifications/message` format |

**Key insight:** The SDK transport already handles nearly all Streamable HTTP requirements. The only gap is Origin header validation, which must be middleware because it's application-level policy (what origins to allow) not transport-level.

## Common Pitfalls

### Pitfall 1: Forgetting to Register set_logging_level Handler
**What goes wrong:** If no `@server.set_logging_level()` handler is registered, the `logging` capability will be `None` in `ServerCapabilities`. Clients won't know the server supports logging, and `send_log_message()` calls may be silently dropped.
**Why it happens:** The SDK auto-detects capabilities from registered handlers (line 200-202 of lowlevel/server.py).
**How to avoid:** Always register the handler, even if it just stores the level.
**Warning signs:** Client doesn't show any progress notifications.

### Pitfall 2: Origin Validation vs CORS
**What goes wrong:** Confusing CORS (`Access-Control-Allow-Origin`) with Origin validation. CORS is browser-enforced; Origin validation is server-enforced. An attacker's page can still send requests even with CORS restrictions.
**Why it happens:** Both involve the `Origin` header.
**How to avoid:** Origin validation middleware runs server-side and rejects requests. CORS middleware sets response headers. Both are needed but serve different purposes.
**Warning signs:** Only CORS middleware configured, no explicit Origin check.

### Pitfall 3: Accessing request_ctx Outside Handler Scope
**What goes wrong:** `request_ctx.get()` raises `LookupError` when called from code not running inside a tool handler (tests, startup code, background tasks).
**Why it happens:** `request_ctx` is a `contextvars.ContextVar` set by `_handle_request` and reset after.
**How to avoid:** Always guard with try/except LookupError. Make `emit_progress` a helper that gracefully degrades.
**Warning signs:** `LookupError: request_ctx` in test output.

### Pitfall 4: Default Host Binding
**What goes wrong:** MCP spec says servers "SHOULD bind only to localhost (127.0.0.1) rather than all network interfaces (0.0.0.0)" when running locally.
**Why it happens:** Current default in `run_server.py` is `0.0.0.0`.
**How to avoid:** Change default to `127.0.0.1` for local development. Require explicit opt-in for `0.0.0.0` when intentionally serving remotely.
**Warning signs:** Server accessible from other machines without authentication.

## Code Examples

### Accessing ServerSession from Tool Handler
```python
# Source: Verified from mcp/server/lowlevel/server.py line 98
from mcp.server.lowlevel.server import request_ctx

# Inside a tool handler (or code called from one):
ctx = request_ctx.get()
session = ctx.session  # ServerSession instance
await session.send_log_message(
    level="info",
    data="Scanning subnet 192.168.1.0/24...",
    logger="homelab-mcp",
)
```

### send_log_message Signature
```python
# Source: mcp/server/session.py lines 174-194
async def send_log_message(
    self,
    level: types.LoggingLevel,  # "debug"|"info"|"notice"|"warning"|"error"|"critical"|"alert"|"emergency"
    data: Any,  # Can be string, dict, or any JSON-serializable value
    logger: str | None = None,  # Optional logger name
    related_request_id: types.RequestId | None = None,
) -> None:
```

### set_logging_level Decorator
```python
# Source: mcp/server/lowlevel/server.py lines 331-342
@server.set_logging_level()
async def handle_set_level(level: types.LoggingLevel) -> None:
    # This enables logging capability in ServerCapabilities
    # Store level for filtering
    pass
```

### StreamableHTTPSessionManager Already Handles Sessions
```python
# Source: mcp/server/streamable_http_manager.py
# Current http_app.py already uses this correctly:
session_manager = StreamableHTTPSessionManager(app=server)
# This handles:
# - Session ID generation (uuid4().hex)
# - Session ID validation on requests
# - Session lifecycle (create, lookup, terminate via DELETE)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HTTP+SSE transport (2024-11-05) | Streamable HTTP (2025-03-26) | March 2025 | Single endpoint, POST+GET, session management |
| No logging capability | `notifications/message` logging | MCP 2025-03-26 | Servers can emit structured log messages to clients |
| Custom JSON-RPC | SDK `lowlevel.Server` | Phase 1 migration | Already done in this project |

**Deprecated/outdated:**
- `http_transport.py`: Already deprecated in Phase 1, still in codebase. Phase 4 work focuses on `http_app.py`.

## What the SDK Already Handles (No Work Needed)

These Streamable HTTP spec requirements are already implemented by the SDK transport:

1. **Session ID in responses:** `StreamableHTTPServerTransport` sets `Mcp-Session-Id` header automatically
2. **Session validation on requests:** `_validate_session()` checks header on non-init requests
3. **Content-Type validation:** `_check_content_type()` enforces `application/json`
4. **Accept header validation:** `_check_accept_headers()` requires both `application/json` and `text/event-stream`
5. **202 Accepted for notifications:** Returns 202 for non-request messages
6. **SSE streaming for requests:** Opens SSE stream for JSON-RPC requests
7. **Session termination via DELETE:** `_handle_delete_request()` terminates sessions
8. **Resumability support:** `EventStore` interface available (optional)
9. **GET for server-initiated messages:** `_handle_get_request()` opens standalone SSE stream

## What Needs Implementation

| Gap | Spec Requirement | Implementation Location |
|-----|------------------|------------------------|
| Origin header validation | "Servers MUST validate the Origin header on all incoming connections" | New middleware in `http_app.py` |
| MCP logging capability | Emit progress notifications for long-running ops | `set_logging_level` handler in `server.py`, `emit_progress` helper |
| Logging in tool handlers | Actual progress messages during bulk operations | `sitemap.py`, `infrastructure_crud.py`, `service_installer.py` |
| Default bind address | "Servers SHOULD bind only to localhost" | Change default in `run_server.py` |

## Long-Running Operations Inventory

Tools that need progress logging notifications:

| Handler | File | Iteration Pattern | Notification Points |
|---------|------|--------------------|---------------------|
| `bulk_discover_and_store` | `sitemap.py` | Loop over targets list | Per-target: "Discovering {hostname} ({i}/{n})" |
| `deploy_infrastructure_plan` | `infrastructure_crud.py` | Loop over services, then network_changes | Per-service/change: "Deploying {name} ({i}/{n})" |
| `scale_infrastructure_services` | `infrastructure_crud.py` | Loop over scaling operations | Per-operation: "Scaling {service} ({i}/{n})" |
| `install_service` | `service_installer.py` | Multi-step sequential | Per-step: "Step {i}: {description}" |

## Open Questions

1. **Allowed Origins configuration**
   - What we know: Origin validation is required. Localhost origins must be allowed. Remote origins needed for OpenWebUI.
   - What's unclear: Whether to make allowed origins configurable via env var or hardcode localhost-only.
   - Recommendation: Add `MCP_ALLOWED_ORIGINS` env var with default of localhost variants. This matches the existing pattern of env-var configuration.

2. **Default bind address change**
   - What we know: Spec says SHOULD bind to localhost when running locally.
   - What's unclear: Whether changing default from `0.0.0.0` to `127.0.0.1` would break existing users.
   - Recommendation: Change default to `127.0.0.1` but document in the change. Users who need remote access already know to set `--host 0.0.0.0`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/ -m "not integration" -x` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-03 | `set_logging_level` handler registers logging capability | unit | `uv run pytest tests/test_server.py -x -k logging` | Wave 0 |
| MCP-03 | `emit_progress` sends log notification via session | unit | `uv run pytest tests/test_logging_notifications.py -x` | Wave 0 |
| MCP-03 | `emit_progress` gracefully handles missing request context | unit | `uv run pytest tests/test_logging_notifications.py -x -k no_context` | Wave 0 |
| MCP-03 | Bulk discover emits per-target progress | unit | `uv run pytest tests/test_logging_notifications.py -x -k bulk` | Wave 0 |
| MCP-04 | Origin validation rejects unknown origins | unit | `uv run pytest tests/test_http_app.py -x -k origin` | Wave 0 |
| MCP-04 | Origin validation allows configured origins | unit | `uv run pytest tests/test_http_app.py -x -k origin_allowed` | Wave 0 |
| MCP-04 | Origin validation allows no-Origin requests | unit | `uv run pytest tests/test_http_app.py -x -k no_origin` | Wave 0 |
| MCP-04 | Session management works end-to-end | integration | `uv run pytest tests/test_http_app.py -x -k session` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -m "not integration" -x`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_logging_notifications.py` -- covers MCP-03 (emit_progress, level filtering, graceful degradation)
- [ ] `tests/test_http_app.py` -- needs new test cases for Origin validation (MCP-04)

## Sources

### Primary (HIGH confidence)
- MCP Python SDK source code (installed at `.venv/lib/python3.12/site-packages/mcp/`) -- `server/session.py` (send_log_message), `server/lowlevel/server.py` (set_logging_level, request_ctx, get_capabilities), `server/streamable_http.py` (transport implementation), `server/streamable_http_manager.py` (session management)
- [MCP Spec 2025-03-26 - Transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) -- Streamable HTTP requirements, Origin validation, session management

### Secondary (MEDIUM confidence)
- [Auth0 Blog - MCP Streamable HTTP Security](https://auth0.com/blog/mcp-streamable-http/) -- Confirms Origin validation importance for DNS rebinding prevention

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified directly from installed SDK source code
- Architecture: HIGH - `send_log_message()`, `request_ctx`, and `StreamableHTTPSessionManager` APIs verified in SDK source
- Pitfalls: HIGH - identified from actual code analysis of SDK internals and existing codebase

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- SDK API unlikely to change within minor versions)
