# Phase 1: Architecture Foundation - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Centralize all external connections (SSH, HTTP, database) through a ResourceManager, migrate the server from hand-rolled JSON-RPC to MCP SDK (lowlevel.Server), and ensure clean shutdown with resource cleanup. This phase does NOT add new tools, change security behavior, or modify tool functionality — it restructures how existing tools are registered, dispatched, and how their connections are managed.

</domain>

<decisions>
## Implementation Decisions

### SDK migration scope
- Migrate BOTH stdio and HTTP transports to MCP SDK — no legacy transport code left behind
- MCP SDK handles the /mcp endpoint for HTTP; non-MCP features (WebSocket shell relay, /health endpoint, SSE streaming) remain as separate Starlette routes alongside the SDK transport
- Remove the hand-rolled JSON-RPC parsing, initialize handshake, capabilities advertisement, and manual error formatting entirely — clean break, no fallback

### Tool registration
- Use decorator-based tool registration (@server.tool()) on each handler — refactor away from the execute_tool() string dispatch pattern
- This touches every handler file but results in cleaner SDK integration

### Claude's Discretion
- ResourceManager design (singleton vs dependency injection, which connections it manages)
- Refactoring approach for handler layer (how much to restructure handler signatures)
- HTTP transport fate details (how to compose MCP SDK HTTP transport with Starlette routes)
- Connection pooling implementation for Proxmox HTTP sessions (FUNC-05)
- Signal handler and graceful shutdown implementation (ARCH-03)
- Test migration strategy

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tool_schemas/` directory: JSON Schema definitions for all 34+ tools — can inform decorator registration
- `tool_handlers/` directory: Thin handler wrappers that call domain logic — pattern to preserve during refactor
- `error_handling.py`: Decorator-based timeout/retry/SSH error handling — should integrate with ResourceManager
- `HealthChecker` singleton in `error_handling.py`: Existing singleton pattern to reference for ResourceManager design
- `config.py`: MCPConfig, HTTPConfig, DatabaseConfig classes — ResourceManager can consume these

### Established Patterns
- Async-first design using asyncio throughout — ResourceManager must be async-compatible
- Tool handler returns `{"content": [{"type": "text", "text": ...}]}` — MCP SDK may change this format
- Relative imports within `src/homelab_mcp/` package
- Module-level `logger = logging.getLogger(__name__)` in every file

### Integration Points
- `run_server.py`: Entry point that creates HomelabMCPServer — will need rewrite for SDK
- `server.py`: HomelabMCPServer class handles both stdio and HTTP dispatch — primary migration target
- `http_transport.py`: MCPHTTPTransport with Starlette/uvicorn — needs to coexist with SDK HTTP transport
- `tools.py`: execute_tool() dispatch function — replaced by decorator registration
- `database.py`: get_database_adapter() factory — connection lifecycle moves to ResourceManager
- `proxmox_api.py`: aiohttp sessions created per-call — pooling moves to ResourceManager

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-architecture-foundation*
*Context gathered: 2026-03-08*
