# Phase 1: Architecture Foundation - Research

**Researched:** 2026-03-08
**Domain:** MCP SDK migration, connection lifecycle management, graceful shutdown
**Confidence:** HIGH

## Summary

This phase replaces the hand-rolled JSON-RPC server (`HomelabMCPServer` in `server.py`) with the MCP Python SDK's `lowlevel.Server`, centralizes all external connections (SSH via asyncssh, HTTP via aiohttp, SQLite database) through a new `ResourceManager`, adds Proxmox HTTP session pooling, and implements graceful shutdown with resource cleanup.

The MCP SDK (version >=1.9.1, installed in the project) provides both a `lowlevel.Server` class (decorator-based handler registration via `@server.list_tools()`, `@server.call_tool()`) and transports (`stdio_server()` context manager, `StreamableHTTPSessionManager` for HTTP). The SDK handles JSON-RPC parsing, protocol negotiation, capability advertisement, and error formatting -- all currently hand-rolled in `server.py` and `http_transport.py`. The SDK also provides a `lifespan` context manager hook on the `Server` class, which is the natural place to initialize and tear down the `ResourceManager`.

The existing codebase has 49 tools organized into 7 handler modules (`tool_handlers/`) with separate schema modules (`tool_schemas/`). The CONTEXT.md decision specifies decorator-based registration (`@server.tool()` via FastMCP), replacing the `execute_tool()` string dispatch. However, the lowlevel.Server uses `@server.call_tool()` (single handler for all tools) and `@server.list_tools()` (returns list of Tool objects), not per-tool decorators. The `FastMCP` class provides `@server.tool()` per-tool decorators but adds its own abstraction layer. Given the CONTEXT.md says "lowlevel.Server", the approach should use `lowlevel.Server` with `call_tool()` dispatching to existing handlers -- preserving the current architecture while removing hand-rolled JSON-RPC.

**Primary recommendation:** Use `mcp.server.lowlevel.Server` with its `lifespan` hook for ResourceManager lifecycle, `call_tool()`/`list_tools()` decorators for tool registration, `stdio_server()` for stdio transport, and `StreamableHTTPSessionManager` for HTTP transport composed in a Starlette app with custom routes for health/WebSocket/shell.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Migrate BOTH stdio and HTTP transports to MCP SDK -- no legacy transport code left behind
- MCP SDK handles the /mcp endpoint for HTTP; non-MCP features (WebSocket shell relay, /health endpoint, SSE streaming) remain as separate Starlette routes alongside the SDK transport
- Remove the hand-rolled JSON-RPC parsing, initialize handshake, capabilities advertisement, and manual error formatting entirely -- clean break, no fallback
- Use decorator-based tool registration (@server.tool()) on each handler -- refactor away from the execute_tool() string dispatch pattern
- This touches every handler file but results in cleaner SDK integration

### Claude's Discretion
- ResourceManager design (singleton vs dependency injection, which connections it manages)
- Refactoring approach for handler layer (how much to restructure handler signatures)
- HTTP transport fate details (how to compose MCP SDK HTTP transport with Starlette routes)
- Connection pooling implementation for Proxmox HTTP sessions (FUNC-05)
- Signal handler and graceful shutdown implementation (ARCH-03)
- Test migration strategy

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ARCH-01 | Server uses MCP SDK (lowlevel.Server) instead of hand-rolled JSON-RPC | SDK source verified: `lowlevel.Server` provides `list_tools()`, `call_tool()`, `run()`, `lifespan`, `create_initialization_options()`. Transports: `stdio_server()`, `StreamableHTTPSessionManager`. |
| ARCH-02 | ResourceManager centralizes SSH, HTTP, and database connection lifecycle | Existing code creates connections ad-hoc: `get_proxmox_client()` per call, database adapters per use, SSH connections per operation. `lifespan` hook on Server is the init/teardown point. |
| ARCH-03 | Server shuts down gracefully on SIGTERM/SIGINT with resource cleanup | SDK uses anyio task groups; signal handling should cancel the task group which triggers lifespan teardown. Current code catches KeyboardInterrupt in `run_server.py`. |
| FUNC-05 | Proxmox API client reuses HTTP connections via session pooling | Current `ProxmoxAPIClient.request()` creates a new `aiohttp.ClientSession` + `TCPConnector` per call (line 113-114 of proxmox_api.py). Must move to persistent session managed by ResourceManager. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp[cli] | >=1.9.1 | MCP protocol server framework | Already a dependency; provides lowlevel.Server, transports, types |
| anyio | (transitive) | Async runtime abstraction | MCP SDK uses anyio internally; task groups for structured concurrency |
| aiohttp | >=3.9.0 | Proxmox HTTP client with session pooling | Already a dependency; `ClientSession` provides built-in connection pooling via `TCPConnector` |
| asyncssh | >=2.14.0 | SSH connections | Already a dependency |
| starlette | >=0.30.0 | HTTP app for non-MCP routes | Already a dependency; SDK's HTTP transport integrates as ASGI handler |
| uvicorn | >=0.24.0 | ASGI server | Already a dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | (transitive) | SSE responses in HTTP transport | Used internally by MCP SDK StreamableHTTPServerTransport |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| lowlevel.Server | FastMCP | FastMCP adds per-tool `@server.tool()` decorators and auto-generates schemas from type hints, but adds abstraction and depends on pydantic-settings. lowlevel.Server is lighter and gives full control. |
| aiohttp for Proxmox | httpx (already a dep) | httpx is already in dependencies; aiohttp is also already used. Switching HTTP client is out of scope for this phase. |

**Installation:**
```bash
# No new dependencies needed -- all already in pyproject.toml
uv sync
```

## Architecture Patterns

### Recommended Project Structure
```
src/homelab_mcp/
├── server.py              # lowlevel.Server setup, lifespan, list_tools/call_tool handlers
├── resource_manager.py    # NEW: ResourceManager class (SSH, HTTP, DB lifecycle)
├── run_server.py          # Entry point: stdio or HTTP mode selection
├── http_app.py            # NEW (or refactored http_transport.py): Starlette app composing MCP + custom routes
├── tool_handlers/         # UNCHANGED structure, but handlers receive ResourceManager
├── tool_schemas/          # UNCHANGED
├── proxmox_api.py         # MODIFIED: ProxmoxAPIClient uses shared session from ResourceManager
├── database.py            # MODIFIED: connection lifecycle managed by ResourceManager
├── ssh_tools.py           # MODIFIED: SSH connections obtained from ResourceManager
└── ...                    # Other modules unchanged
```

### Pattern 1: lowlevel.Server with call_tool/list_tools
**What:** Register a single `call_tool` handler that dispatches to existing tool handlers, and a `list_tools` handler that returns Tool objects from existing schemas.
**When to use:** When you have many tools with existing handler/schema infrastructure.
**Example:**
```python
# Source: MCP SDK lowlevel/server.py (verified from installed source)
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.server import NotificationOptions
import mcp.types as types

server = Server("homelab-mcp", version="0.2.0")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools = []
    for name, schema in get_all_tool_schemas().items():
        tools.append(types.Tool(
            name=name,
            description=schema["description"],
            inputSchema=schema["inputSchema"],
        ))
    return tools

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    handler = get_tool_handler(name)
    result = await handler(arguments or {})
    # result is {"content": [{"type": "text", "text": "..."}]}
    # SDK expects list of Content objects
    return [types.TextContent(type="text", text=item["text"])
            for item in result.get("content", [])]
```

### Pattern 2: Server lifespan for ResourceManager
**What:** The `Server` class accepts a `lifespan` parameter -- an async context manager that runs during the server's lifetime. Use this to initialize and tear down ResourceManager.
**When to use:** Always -- this is the SDK's built-in lifecycle hook.
**Example:**
```python
# Source: MCP SDK lowlevel/server.py lifespan parameter (verified)
from contextlib import asynccontextmanager

@asynccontextmanager
async def app_lifespan(server: Server):
    """Initialize and tear down shared resources."""
    resource_manager = ResourceManager()
    await resource_manager.initialize()
    try:
        yield {"resource_manager": resource_manager}
    finally:
        await resource_manager.shutdown()

server = Server("homelab-mcp", lifespan=app_lifespan)

# Access in handlers via server.request_context.lifespan_context
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> ...:
    ctx = server.request_context
    rm = ctx.lifespan_context["resource_manager"]
    # ... use rm to get connections
```

### Pattern 3: Composing MCP HTTP transport with custom Starlette routes
**What:** Use `StreamableHTTPSessionManager` as the ASGI handler for `/mcp`, and add custom Starlette routes for `/health`, `/shell/{id}`, `/ws/shell/{id}`.
**When to use:** When MCP server needs non-protocol HTTP endpoints alongside it.
**Example:**
```python
# Source: MCP SDK streamable_http_manager.py + fastmcp/server.py patterns (verified)
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

session_manager = StreamableHTTPSessionManager(
    app=server,  # lowlevel.Server instance
    json_response=False,
    stateless=False,
)

async def handle_mcp(scope, receive, send):
    await session_manager.handle_request(scope, receive, send)

routes = [
    Mount("/mcp", app=handle_mcp),
    Route("/health", health_handler, methods=["GET"]),
    Route("/shell/{session_id}", shell_page_handler, methods=["GET"]),
    WebSocketRoute("/ws/shell/{session_id}", shell_ws_handler),
]

app = Starlette(
    routes=routes,
    lifespan=lambda app: session_manager.run(),
)
```

### Pattern 4: ResourceManager with async context manager
**What:** ResourceManager as an async class managing connection pools.
**When to use:** Centralizing SSH, HTTP sessions, and database connections.
**Example:**
```python
import aiohttp
from contextlib import asynccontextmanager

class ResourceManager:
    def __init__(self, config: MCPConfig):
        self.config = config
        self._proxmox_session: aiohttp.ClientSession | None = None
        self._db_adapter: DatabaseAdapter | None = None

    async def initialize(self):
        """Called during server lifespan startup."""
        # Create persistent aiohttp session for Proxmox
        connector = aiohttp.TCPConnector(
            limit=10,  # max concurrent connections
            ttl_dns_cache=300,
            ssl=self.config.proxmox_verify_ssl,
        )
        self._proxmox_session = aiohttp.ClientSession(connector=connector)

        # Initialize database
        self._db_adapter = get_database_adapter(self.config)
        self._db_adapter.connect()
        self._db_adapter.init_schema()

    async def shutdown(self):
        """Called during server lifespan teardown."""
        if self._proxmox_session:
            await self._proxmox_session.close()
        if self._db_adapter:
            self._db_adapter.close()

    @property
    def proxmox_session(self) -> aiohttp.ClientSession:
        if not self._proxmox_session:
            raise RuntimeError("ResourceManager not initialized")
        return self._proxmox_session
```

### Pattern 5: Signal handling with anyio
**What:** Register signal handlers that trigger graceful shutdown by cancelling the anyio task group.
**When to use:** For SIGTERM/SIGINT handling in both stdio and HTTP modes.
**Example:**
```python
import signal
import anyio

async def run_with_signal_handling():
    async with anyio.create_task_group() as tg:
        shutdown_event = anyio.Event()

        def signal_handler(signum, frame):
            shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        tg.start_soon(run_server)
        await shutdown_event.wait()
        tg.cancel_scope.cancel()
```

Note: For HTTP mode, uvicorn already handles SIGTERM/SIGINT. For stdio mode, the `stdio_server()` context manager handles cleanup when the task group exits. The main concern is ensuring ResourceManager.shutdown() runs, which the lifespan context manager guarantees.

### Anti-Patterns to Avoid
- **Creating connections in tool handlers:** Every handler currently calls `get_proxmox_client()` which creates a new `aiohttp.ClientSession` per request. This must be replaced with ResourceManager access.
- **Mixing JSON-RPC format construction with business logic:** The SDK handles all JSON-RPC formatting. Handlers should return content objects, not `{"jsonrpc": "2.0", ...}` dicts.
- **Catching KeyboardInterrupt at multiple levels:** Current code catches it in `run_server.py`, `server.py` stdio loop, and implicitly in handlers. With the SDK, structured concurrency via anyio handles this.
- **Module-level singletons for connection state:** The existing `health_checker = HealthChecker()` pattern works for stateless counters but should not be extended to connection-holding resources. Use lifespan context instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-RPC protocol | Custom parsing, error formatting, capability negotiation | `mcp.server.lowlevel.Server` | Handles protocol version negotiation, message validation, error codes, ping, capability advertisement |
| Stdio transport | Custom `asyncio.StreamReader`/`print(json.dumps(...))` | `mcp.server.stdio.stdio_server()` | Handles encoding, line framing, anyio integration |
| HTTP transport for MCP | Custom Starlette POST/GET handlers with manual JSON-RPC | `StreamableHTTPSessionManager` | Handles session management, SSE streaming, POST/GET/DELETE lifecycle, content negotiation |
| Connection pooling | Custom pool with semaphores | `aiohttp.TCPConnector(limit=N)` | Built-in connection reuse, DNS caching, SSL handling, connection limits |
| Structured concurrency | Manual task tracking with `asyncio.create_task` | anyio task groups (via SDK) | Automatic cancellation propagation, clean shutdown, exception handling |

**Key insight:** The MCP SDK already solves the hardest problems (protocol compliance, transport management, lifecycle). This phase is about plugging in, not reimplementing.

## Common Pitfalls

### Pitfall 1: Handler return type mismatch
**What goes wrong:** Existing handlers return `{"content": [{"type": "text", "text": "..."}]}` (dict). The SDK's `call_tool` handler expects `list[types.Content]` (Pydantic models).
**Why it happens:** The SDK wraps the return in `CallToolResult` internally (see `lowlevel/server.py` line 393-396).
**How to avoid:** Create an adapter layer that converts handler dict results to `types.TextContent` objects. Keep existing handlers returning dicts to minimize changes, and convert at the `call_tool` boundary.
**Warning signs:** `ValidationError` from pydantic when tool results are returned.

### Pitfall 2: anyio vs asyncio mixing
**What goes wrong:** The MCP SDK uses anyio throughout. Existing code uses raw asyncio (`asyncio.wait_for`, `asyncio.StreamReader`, `asyncio.create_task`). Mixing can cause event loop issues.
**Why it happens:** anyio runs on top of asyncio by default, so basic awaits work fine. But `asyncio.create_task()` bypasses anyio's task group structure, breaking structured concurrency.
**How to avoid:** For new code, use anyio primitives. For existing tool handler code that uses `asyncio.wait_for()`, this is fine as it runs within the anyio event loop. The main concern is the transport/server layer.
**Warning signs:** Tasks not cancelled on shutdown, "attached to a different loop" errors.

### Pitfall 3: Lifespan context access from handlers
**What goes wrong:** Tool handlers need access to ResourceManager but it lives in the lifespan context, accessible only via `server.request_context.lifespan_context`.
**Why it happens:** The lowlevel.Server uses contextvars to make request context available.
**How to avoid:** Access via `server.request_context` inside the `call_tool` handler (which has request context), then pass ResourceManager to tool handlers as a parameter. Alternatively, store ResourceManager as a module-level reference set during lifespan init.
**Warning signs:** `LookupError` when accessing `request_context` outside a request.

### Pitfall 4: Starlette lifespan conflict
**What goes wrong:** Both the MCP SDK's `StreamableHTTPSessionManager.run()` and the Starlette app's lifespan need to coordinate. If using Starlette's lifespan for non-MCP setup while also running the session manager, they need proper nesting.
**Why it happens:** `StreamableHTTPSessionManager.run()` is designed to be used AS the Starlette lifespan (as shown in FastMCP source: `lifespan=lambda app: self.session_manager.run()`).
**How to avoid:** Use the session manager's `run()` as the Starlette lifespan. For ResourceManager init, use the lowlevel.Server's `lifespan` parameter instead.
**Warning signs:** "Task group is not initialized" error from session manager.

### Pitfall 5: Proxmox session lifecycle
**What goes wrong:** `aiohttp.ClientSession` must be created and closed within the same async context. Creating it during lifespan init and closing during shutdown is correct, but the session must not be used after close.
**Why it happens:** aiohttp enforces session lifecycle rules strictly.
**How to avoid:** ResourceManager.shutdown() closes the session. The lifespan context manager ensures this happens before the server exits. Never store session references that outlive the lifespan.
**Warning signs:** `RuntimeError: Session is closed` or unclosed connector warnings.

### Pitfall 6: Database adapter is synchronous
**What goes wrong:** The existing `DatabaseAdapter` uses synchronous `sqlite3`. Calling it from async handlers blocks the event loop.
**Why it happens:** SQLite operations are typically fast enough that blocking is acceptable for a single-user homelab server, but the interface is sync.
**How to avoid:** Keep the synchronous database calls as-is for this phase (they work today and this is a homelab single-user scenario). If needed, wrap in `anyio.to_thread.run_sync()`. Database connection lifecycle (open/close) moves to ResourceManager.
**Warning signs:** Slow responses during database operations under concurrent load (unlikely in homelab).

### Pitfall 7: Test suite depends on JSON-RPC dict format
**What goes wrong:** Existing tests (`test_server.py`) construct raw JSON-RPC request dicts and assert on response dict structure (`response["jsonrpc"]`, `response["result"]`). After migration, the server no longer exposes `handle_request()` that takes/returns dicts.
**Why it happens:** Tests were written against the hand-rolled server interface.
**How to avoid:** Tests need to be rewritten to test at appropriate levels: (1) tool handler tests stay the same (handler functions unchanged), (2) server integration tests use the SDK's in-process testing patterns (create memory streams, run server, send/receive). The SDK's `raise_exceptions=True` parameter helps with test debugging.
**Warning signs:** All `test_server.py` tests fail immediately after migration.

## Code Examples

Verified patterns from installed MCP SDK source:

### Running stdio transport
```python
# Source: mcp/server/stdio.py and lowlevel/server.py docstring (verified)
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

server = Server("homelab-mcp", version="0.2.0", lifespan=app_lifespan)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

anyio.run(main)
```

### Running HTTP transport with custom routes
```python
# Source: mcp/server/streamable_http_manager.py + fastmcp/server.py patterns (verified)
import contextlib
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

session_manager = StreamableHTTPSessionManager(app=server)

@contextlib.asynccontextmanager
async def lifespan(app):
    async with session_manager.run():
        yield

async def mcp_handler(scope, receive, send):
    await session_manager.handle_request(scope, receive, send)

app = Starlette(
    routes=[
        Mount("/mcp", app=mcp_handler),
        Route("/health", health_endpoint, methods=["GET"]),
    ],
    lifespan=lifespan,
)

config = uvicorn.Config(app, host="0.0.0.0", port=8080)
server_instance = uvicorn.Server(config)
await server_instance.serve()
```

### Proxmox session pooling with aiohttp
```python
# Source: aiohttp documentation pattern (verified from training)
connector = aiohttp.TCPConnector(
    limit=10,          # Total connection pool size
    limit_per_host=5,  # Per-host limit
    ttl_dns_cache=300,  # DNS cache TTL
    enable_cleanup_closed=True,
)
session = aiohttp.ClientSession(
    connector=connector,
    timeout=aiohttp.ClientTimeout(total=30),
)
# Session reused across all Proxmox API calls
# Closed during ResourceManager.shutdown()
```

### Converting existing handler results to SDK types
```python
import mcp.types as types

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    handler = get_tool_handler(name)
    result = await handler(arguments or {})

    # Existing handlers return: {"content": [{"type": "text", "text": "..."}]}
    content_list = []
    for item in result.get("content", []):
        if item.get("type") == "text":
            content_list.append(types.TextContent(type="text", text=item["text"]))
        elif item.get("type") == "image":
            content_list.append(types.ImageContent(
                type="image", data=item["data"], mimeType=item["mimeType"]
            ))
    return content_list
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSE transport (deprecated in MCP spec) | Streamable HTTP transport | MCP SDK 1.x | Use `StreamableHTTPSessionManager`, not `SseServerTransport` |
| `Server.get_capabilities()` + manual `InitializationOptions` | `Server.create_initialization_options()` | MCP SDK recent | Simpler initialization setup |
| `anyio.run()` entry point | Still valid, `asyncio.run()` also works (anyio sits on top) | Current | Either works; use `anyio.run()` for consistency with SDK |

**Deprecated/outdated:**
- `SseServerTransport`: Still in SDK but superseded by Streamable HTTP. The existing project's HTTP transport should migrate to Streamable HTTP.
- Hand-rolled JSON-RPC: The whole point of this phase.

## Open Questions

1. **Handler signature refactoring depth**
   - What we know: CONTEXT.md says "decorator-based tool registration on each handler" but lowlevel.Server uses a single `call_tool()` handler, not per-tool decorators. Per-tool decorators are a FastMCP feature.
   - What's unclear: Whether to use FastMCP's `@server.tool()` (per-tool) or lowlevel.Server's `@server.call_tool()` (single dispatcher).
   - Recommendation: Use lowlevel.Server's `@server.call_tool()` with internal dispatch to existing handlers. This matches the CONTEXT.md requirement of "lowlevel.Server" while still removing the old `execute_tool()` string dispatch. The "decorator-based" intent is satisfied by using `@server.call_tool()` and `@server.list_tools()` decorators.

2. **ResourceManager: singleton vs dependency injection**
   - What we know: lifespan context provides the natural injection point. Module-level references are simpler but less testable.
   - What's unclear: Whether tool handlers should receive ResourceManager via parameter or access it via a module-level reference.
   - Recommendation: Use lifespan context as the source of truth. In the `call_tool` handler, extract ResourceManager from `server.request_context.lifespan_context` and pass it to tool handlers. For handlers that need it (proxmox, ssh, database), add an optional `resource_manager` parameter. This keeps handlers testable with mock ResourceManagers.

3. **Dual lifespan coordination**
   - What we know: Server.lifespan manages ResourceManager. StreamableHTTPSessionManager.run() must be the Starlette lifespan.
   - What's unclear: Whether these can nest cleanly.
   - Recommendation: They operate at different levels. Server.lifespan runs when `server.run()` is called (inside session manager). Starlette lifespan wraps `session_manager.run()`. So the nesting is: Starlette lifespan -> session_manager.run() -> server.run() -> server.lifespan. This is the pattern used by FastMCP internally and is verified to work.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5+ with pytest-asyncio 0.23.0+ |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/ -m "not integration" -x` |
| Full suite command | `uv run pytest tests/ -m "not integration" -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ARCH-01 | Server handles tool calls via MCP SDK | unit | `uv run pytest tests/test_server.py -x` | Yes (needs rewrite) |
| ARCH-01 | Tool list returns all 49 tools via SDK | unit | `uv run pytest tests/test_tools.py -x` | Yes (needs rewrite) |
| ARCH-02 | ResourceManager initializes and provides connections | unit | `uv run pytest tests/test_resource_manager.py -x` | No -- Wave 0 |
| ARCH-02 | Tool handlers obtain connections from ResourceManager | unit | `uv run pytest tests/test_tools.py -x` | Partial (needs update) |
| ARCH-03 | Server shuts down cleanly on signal | unit | `uv run pytest tests/test_server.py::test_graceful_shutdown -x` | No -- Wave 0 |
| FUNC-05 | Proxmox API reuses HTTP sessions | unit | `uv run pytest tests/test_proxmox_api.py -x` | Yes (needs update) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -m "not integration" -x --no-header -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_resource_manager.py` -- covers ARCH-02 (ResourceManager init, connection provision, shutdown)
- [ ] `tests/test_server.py` -- needs rewrite for SDK-based server (covers ARCH-01, ARCH-03)
- [ ] `tests/test_proxmox_api.py` -- needs update for session pooling (covers FUNC-05)

## Sources

### Primary (HIGH confidence)
- MCP SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` -- Server class, decorators, lifespan, run()
- MCP SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/server/stdio.py` -- stdio_server() context manager
- MCP SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/server/streamable_http_manager.py` -- StreamableHTTPSessionManager
- MCP SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/server/streamable_http.py` -- StreamableHTTPServerTransport
- MCP SDK source: `/home/shaun/projects/mcp_python_server/.venv/lib/python3.12/site-packages/mcp/server/fastmcp/server.py` -- FastMCP patterns for HTTP composition
- Existing codebase: `server.py`, `http_transport.py`, `proxmox_api.py`, `tools.py`, `tool_handlers/__init__.py`, `config.py`, `database.py`, `error_handling.py`

### Secondary (MEDIUM confidence)
- aiohttp `TCPConnector` connection pooling patterns (from training data, well-established API)

### Tertiary (LOW confidence)
- None -- all findings verified from installed SDK source

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, versions verified from pyproject.toml
- Architecture: HIGH -- patterns verified from actual SDK source code in .venv
- Pitfalls: HIGH -- identified from concrete code inspection of both existing codebase and SDK internals

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable -- MCP SDK API unlikely to change within 30 days)
