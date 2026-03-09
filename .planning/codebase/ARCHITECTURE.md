# Architecture

**Analysis Date:** 2026-03-08

## Pattern Overview

**Overall:** Layered Service Architecture with Tool Registry Pattern

**Key Characteristics:**
- JSON-RPC 2.0 server implementing the Model Context Protocol (MCP)
- Dual transport: stdio (for Claude Desktop) and HTTP/SSE (for OpenWebUI/network clients)
- Tool registry pattern separating schema definitions from handler implementations
- Abstract database adapter pattern supporting SQLite and PostgreSQL
- Strategy pattern for VM providers (Docker, LXD)
- Async-first design using asyncio throughout

## Layers

**Transport Layer:**
- Purpose: Accepts JSON-RPC 2.0 requests over stdio or HTTP, delivers responses
- Location: `src/homelab_mcp/server.py` (stdio + orchestration), `src/homelab_mcp/http_transport.py` (HTTP/SSE/WebSocket)
- Contains: `HomelabMCPServer` class, `MCPHTTPTransport` class, SSE streaming, WebSocket shell relay
- Depends on: Tool execution layer, error handling, auth
- Used by: External MCP clients (Claude Desktop, OpenWebUI)

**Authentication Layer:**
- Purpose: API key bearer token auth for HTTP transport
- Location: `src/homelab_mcp/auth.py`
- Contains: `APIKeyAuth` ASGI middleware wrapping Starlette app
- Depends on: Environment variables (`MCP_API_KEY`)
- Used by: HTTP transport layer

**Tool Registry Layer:**
- Purpose: Maps tool names to JSON schemas and handler functions
- Location: `src/homelab_mcp/tools.py` (entry point), `src/homelab_mcp/tool_schemas/` (schema definitions), `src/homelab_mcp/tool_handlers/` (handler functions)
- Contains: `get_available_tools()` returns merged schema dict; `execute_tool()` dispatches to handler by name
- Depends on: Handler implementations
- Used by: Transport layer via `execute_tool(tool_name, arguments)`

**Handler Layer:**
- Purpose: Thin adapter functions that unpack arguments and call domain logic, then format MCP responses
- Location: `src/homelab_mcp/tool_handlers/*.py`
- Contains: One `handle_*` function per tool, each returning `{"content": [{"type": "text", "text": ...}]}`
- Depends on: Domain logic modules
- Used by: Tool registry layer

**Domain Logic Layer:**
- Purpose: Core business logic for SSH discovery, VM management, infrastructure, services, networking
- Location: `src/homelab_mcp/ssh_tools.py`, `src/homelab_mcp/vm_operations.py`, `src/homelab_mcp/infrastructure_crud.py`, `src/homelab_mcp/service_installer.py`, `src/homelab_mcp/sitemap.py`, `src/homelab_mcp/proxmox_api.py`, `src/homelab_mcp/proxmox_scripts.py`, `src/homelab_mcp/shell_session.py`
- Contains: Manager classes, async functions that execute SSH commands, API calls, service deployments
- Depends on: Database layer, external systems (SSH, Proxmox API, GitHub API)
- Used by: Handler layer

**Database Layer:**
- Purpose: Persistent storage for device tracking, discovery history, SSH credentials
- Location: `src/homelab_mcp/database.py`
- Contains: Abstract `DatabaseAdapter` ABC, `SQLiteAdapter`, `PostgreSQLAdapter`, factory function `get_database_adapter()`
- Depends on: sqlite3 (builtin), psycopg2 (optional)
- Used by: `sitemap.py`, `ssh_tools.py`, domain logic modules

**Configuration Layer:**
- Purpose: Environment-based configuration with validation
- Location: `src/homelab_mcp/config.py`
- Contains: `MCPConfig`, `HTTPConfig`, `DatabaseConfig` classes; `get_config()` factory
- Depends on: Environment variables
- Used by: All layers

**Cross-Cutting: Error Handling:**
- Purpose: Timeout protection, retry logic, SSH error wrapping, health monitoring
- Location: `src/homelab_mcp/error_handling.py`
- Contains: `timeout_wrapper()`, `retry_on_failure()`, `ssh_connection_wrapper()` decorators; `HealthChecker` singleton
- Used by: All layers

## Data Flow

**Tool Execution (stdio):**

1. Client sends JSON-RPC 2.0 request to stdin
2. `HomelabMCPServer.run_stdio()` reads line, parses JSON
3. `handle_request()` routes by method: `initialize`, `tools/list`, `tools/call`
4. For `tools/call`: `execute_tool(tool_name, arguments)` in `tools.py`
5. `get_tool_handler(tool_name)` looks up handler in `TOOL_HANDLERS` dict
6. Handler function unpacks arguments, calls domain logic
7. Domain logic performs SSH/API/DB operations, returns JSON string
8. Handler wraps result in MCP content format `{"content": [{"type": "text", "text": ...}]}`
9. Response sent as JSON-RPC 2.0 to stdout

**Tool Execution (HTTP):**

1. Client sends POST to `/mcp` with JSON-RPC body + Bearer token
2. `APIKeyAuth` middleware validates token
3. `MCPHTTPTransport.handle_mcp_post()` parses body
4. Delegates to `HomelabMCPServer.handle_request()` (same as stdio from step 3)
5. Response returned as HTTP JSON

**SSH Discovery Flow:**

1. `handle_ssh_discover` receives hostname/credentials
2. `ssh_tools.resolve_ssh_credentials()` resolves credentials (explicit > stored > default key)
3. `ssh_discover_system()` connects via asyncssh, runs system commands
4. Hardware info parsed from command output
5. `NetworkSiteMap.update_device()` stores/updates device in database
6. Discovery history stored with hash-based deduplication

**Interactive Shell Flow:**

1. `handle_start_interactive_shell` creates SSH session via `session_manager.create_session()`
2. Returns URL: `http://{host}:{port}/shell/{session_id}`
3. Client opens URL, gets xterm.js HTML page from `shell_terminal.html`
4. Browser opens WebSocket to `/ws/shell/{session_id}`
5. `MCPHTTPTransport.handle_shell_websocket()` relays I/O between WebSocket and SSH PTY

**State Management:**
- Device state persisted in SQLite/PostgreSQL via `DatabaseAdapter`
- SSH credentials stored in `ssh_credentials` table with CRUD operations
- Shell sessions held in memory via `ShellSessionManager` singleton with 30-minute timeout cleanup
- Health metrics tracked by `HealthChecker` singleton (in-memory counters)
- Proxmox script cache held in module-level dict with 1-hour TTL

## Key Abstractions

**DatabaseAdapter:**
- Purpose: Database-agnostic persistence interface
- Examples: `src/homelab_mcp/database.py` - `SQLiteAdapter`, `PostgreSQLAdapter`
- Pattern: Abstract base class with factory function `get_database_adapter()`

**VMProvider:**
- Purpose: Platform-agnostic VM/container lifecycle management
- Examples: `src/homelab_mcp/vm_providers/base.py`, `src/homelab_mcp/vm_providers/docker_provider.py`, `src/homelab_mcp/vm_providers/lxd_provider.py`
- Pattern: Abstract base class with factory function `get_vm_provider(platform)`

**Tool Schema/Handler Split:**
- Purpose: Separates tool JSON schema definitions from execution logic
- Examples: `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` paired with `src/homelab_mcp/tool_handlers/ssh_handlers.py`
- Pattern: Registry pattern - schemas merged in `tool_schemas/__init__.py`, handlers registered in `tool_handlers/__init__.py`

**SSHCredentials:**
- Purpose: Resolved SSH connection parameters with priority resolution
- Examples: `src/homelab_mcp/ssh_tools.py` - `SSHCredentials` dataclass, `resolve_ssh_credentials()` function
- Pattern: Dataclass with resolution priority chain (explicit > stored > default)

**NetworkSiteMap:**
- Purpose: Network device registry and discovery history tracker
- Examples: `src/homelab_mcp/sitemap.py`
- Pattern: Facade over `DatabaseAdapter` with device parsing and change detection

## Entry Points

**CLI Entry Point:**
- Location: `run_server.py`
- Triggers: `uv run python run_server.py` or `python run_server.py`
- Responsibilities: Parse CLI arguments (--http, --host, --port, --no-auth, --ssl-cert, --ssl-key), call `server.main()`

**Server Main:**
- Location: `src/homelab_mcp/server.py` - `main()` function
- Triggers: Called by `run_server.py`
- Responsibilities: Create `HomelabMCPServer`, choose stdio vs HTTP mode, run event loop

**Package Init:**
- Location: `src/homelab_mcp/__init__.py`
- Triggers: Import
- Responsibilities: Exports `__version__` only

## Error Handling

**Strategy:** Decorator-based with structured JSON error responses

**Patterns:**
- `timeout_wrapper(timeout_seconds)` - Wraps async functions with `asyncio.wait_for()`, returns structured error JSON on timeout
- `retry_on_failure(max_retries, delay_seconds, backoff_multiplier)` - Exponential backoff for connection errors only
- `ssh_connection_wrapper(timeout_seconds)` - SSH-specific error handling with categorized error types (timeout, auth, connection, general)
- All error responses follow format: `{"status": "error", "error": "...", "error_type": "...", "timestamp": "..."}`
- Server-level: `handle_request()` catches all exceptions, returns JSON-RPC error responses
- Stdio loop: Tracks consecutive errors, shuts down after 10 consecutive failures

## Cross-Cutting Concerns

**Logging:** Python stdlib `logging` module. Logger per module via `logging.getLogger(__name__)`. Level configurable via `MCP_LOG_LEVEL` env var. Server logs to stderr to avoid polluting stdio transport.

**Validation:** Tool argument validation via JSON Schema in `tool_schemas/`. No runtime schema validation middleware - schemas are declarative for MCP clients. Handler functions receive raw argument dicts.

**Authentication:** API key bearer token via `APIKeyAuth` ASGI middleware on HTTP transport. Excluded paths: `/health`, `/`, `/shell/`, `/ws/shell/`. Stdio transport has no auth (relies on process-level access control). Uses `secrets.compare_digest()` for timing-safe comparison.

**Health Monitoring:** `HealthChecker` singleton in `error_handling.py` tracks request count, error count, timeout count, uptime. Exposed via `health/status` MCP method and `/health` HTTP endpoint. Reports "healthy" or "degraded" based on error rate threshold (50%).

---

*Architecture analysis: 2026-03-08*
