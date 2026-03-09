# Technology Stack

**Project:** Homelab MCP Server - Production 1.0
**Researched:** 2026-03-08
**Mode:** Ecosystem (stack dimension for production-readiness milestone)

## Critical Finding: MCP SDK Not Used

The project lists `mcp[cli]>=1.9.1` as a dependency (locked at v1.9.4) but **does not import or use any of it**. The server implements its own JSON-RPC protocol manually -- raw `asyncio.StreamReader` on stdin, manual JSON parsing, hand-rolled request routing. Meanwhile, the installed MCP SDK ships with:

- **`FastMCP`** -- high-level server with decorator-based tool registration, automatic schema generation, built-in transport support (stdio, SSE, Streamable HTTP)
- **`lowlevel.Server`** -- lower-level server with handler registration pattern
- **`stdio_server`** -- proper stdio transport context manager
- **`StreamableHTTPSessionManager`** -- production HTTP transport with session management
- **Built-in auth middleware** -- OAuth/Bearer auth, not custom API key validation

This is the single most important stack decision for 1.0: **adopt the MCP SDK you already depend on** or continue maintaining a parallel implementation. The recommendation is clear -- use it.

**Confidence:** HIGH (verified by reading installed SDK source at `.venv/lib/python3.12/site-packages/mcp/`)

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.12+ | Runtime | Already pinned, mature async support, type hints. No reason to change. | HIGH |
| mcp[cli] | >=1.9.1 (locked 1.9.4) | MCP protocol framework | **Actually use it.** FastMCP or lowlevel.Server handles JSON-RPC, transport negotiation, protocol versioning, and tool registration. Eliminates ~200 lines of manual protocol code in server.py. The SDK handles stdio, SSE, and Streamable HTTP transports correctly. | HIGH |
| uv | latest | Package management | Already used. Fastest Python resolver/installer. Lockfile present. | HIGH |
| hatchling | latest | Build backend | Already used. Works well with uv. | HIGH |

### SSH & Remote Management

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| asyncssh | >=2.14.0 (locked 2.21.0) | SSH operations | Correct choice. Only serious async SSH library for Python. The version is current. **Must fix `known_hosts=None` across 19 call sites.** asyncssh supports `known_hosts` parameter accepting file paths, `SSHKnownHosts` objects, or callback functions. Use `~/.ssh/known_hosts` as default with a trust-on-first-use (TOFU) pattern. | HIGH |

**Do not use:** paramiko for core SSH -- it's sync-only, would require thread pools. Keep it only in the `[automation]` extra where Ansible requires it.

### Proxmox Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| aiohttp | >=3.9.0 (locked 3.12.13) | Proxmox API HTTP client | Already used. Mature async HTTP client. **Must implement connection pooling** -- currently creates new `ClientSession` + `TCPConnector` per request. Create a single session on `ProxmoxAPIClient.__init__` and reuse it. | HIGH |

**Do not use:** `proxmoxer` -- it's a sync library wrapping `requests`. The project already has a working async Proxmox client; adding a sync wrapper would be a regression.

**Do not use:** `httpx` for Proxmox -- the project already has `aiohttp` doing this work. Having both `aiohttp` and `httpx` as core dependencies adds confusion. Note: `httpx` is pulled in by the MCP SDK anyway (it's a transitive dependency), but for application code, pick one HTTP client. Since aiohttp is already integrated for Proxmox, keep it.

### HTTP Transport

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| starlette | >=0.30.0 (locked 0.47.1) | ASGI framework | Already a dependency (both directly and via MCP SDK). When adopting the MCP SDK's transport layer, the custom `MCPHTTPTransport` class can be replaced by `StreamableHTTPSessionManager` which uses Starlette internally. | HIGH |
| uvicorn | >=0.24.0 (locked 0.34.3) | ASGI server | Standard choice for running Starlette apps. Keep as-is. | HIGH |
| websockets | >=12.0 (locked 16.0) | Interactive shell sessions | Used for WebSocket-based shell sessions (a feature separate from MCP protocol). Keep for this specific feature. | HIGH |

### Data & Validation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pydantic | 2.11.7 (transitive) | Data validation | Already pulled in by MCP SDK. **Use it directly** for input validation (hostnames, IPs, port ranges) instead of hand-rolling validation. Replace `jsonschema` for tool input validation where the SDK handles it. | HIGH |
| SQLite (stdlib) | -- | Device tracking database | Correct for single-user homelab. No need for PostgreSQL at 1.0. Keep the PostgreSQL adapter as optional/future. | HIGH |
| pyyaml | >=6.0 | Service template parsing | Required for YAML service definitions. Keep. | HIGH |

**Consider removing:** `jsonschema>=4.24.0` -- if adopting FastMCP, tool input schemas are handled by pydantic type annotations on tool functions. The explicit JSON Schema validation becomes redundant. Evaluate during migration.

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| aiofiles | >=24.1.0 (locked 24.1.0) | Async file I/O | Reading/writing config files, service templates. Keep. | HIGH |
| rich | >=13.10.5 (locked 14.0.0) | Terminal formatting | CLI output, debug logging. Keep. | HIGH |

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=8.3.5 (locked 8.4.1) | Test runner | Standard. Well-configured with strict markers. | HIGH |
| pytest-asyncio | >=0.23.0 (locked 1.0.0) | Async test support | **Note: locked version jumped to 1.0.0** -- this is a major version bump that changed the default mode to `strict`. Verify tests still work. Should set `asyncio_mode = "auto"` in pyproject.toml for convenience. | MEDIUM |
| pytest-cov | >=6.1.1 (locked 6.2.1) | Coverage | 40% minimum enforced. Should increase to 60%+ for 1.0. | HIGH |
| pytest-mock | >=3.14.0 (locked 3.14.1) | Mocking | Standard fixture-based mocking. | HIGH |
| aioresponses | >=0.7.6 (locked 0.7.8) | HTTP mocking | For mocking aiohttp calls to Proxmox API. Keep. | HIGH |
| docker | >=7.0.0 | Integration tests | For SSH container tests. Keep as dev dependency. | HIGH |

### Code Quality

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| ruff | >=0.8.0 (locked 0.14.0) | Linting + formatting | Current config is good. Consider adding `S` (flake8-bandit) rules to ruff and removing standalone bandit -- ruff's bandit rules are faster and sufficient. | HIGH |
| mypy | >=1.13.0 (locked 1.18.2) | Type checking | Strict mode already configured correctly. | HIGH |
| bandit | >=1.7.0 (locked 1.8.6) | Security linting | **Consider removing** -- ruff's `S` ruleset covers the same checks faster. Currently bandit skips `B101` and `B601`; equivalent ruff ignores can be configured. | MEDIUM |
| safety | >=3.0.0 (locked 3.6.2) | Dependency vulnerability scanning | Keep for CI. Alternative: `pip-audit` is more actively maintained, but safety works fine. | MEDIUM |
| pre-commit | >=4.3.0 | Git hooks | Keep. Enforces quality gates before commit. | HIGH |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| MCP Protocol | Use mcp SDK (FastMCP/lowlevel) | Keep custom JSON-RPC | Custom implementation duplicates SDK functionality, won't get protocol updates (Streamable HTTP, capability negotiation), and is a maintenance burden |
| SSH | asyncssh | paramiko | paramiko is synchronous, would need thread pools; asyncssh is async-native |
| HTTP Client (Proxmox) | aiohttp (keep existing) | httpx | Already integrated; switching gains nothing and costs migration effort |
| HTTP Client (general) | httpx (via MCP SDK) | aiohttp | MCP SDK uses httpx internally; for non-Proxmox HTTP, use what SDK provides |
| Validation | pydantic (via MCP SDK) | jsonschema | pydantic is already a transitive dep, provides better DX with type annotations |
| Security linting | ruff `S` rules | standalone bandit | One tool instead of two; ruff is faster; same underlying ruleset |
| Build | hatchling | setuptools | Already using hatchling; it's simpler for pure-Python projects |
| Python version | 3.12+ | 3.13+ | 3.12 is the right floor -- wide adoption, all needed features. 3.13 would narrow the user base unnecessarily |

## Version Pinning Strategy

The current approach uses `>=` minimum version pins with a `uv.lock` lockfile. This is correct for an application:

- **pyproject.toml**: Keep `>=` for flexibility
- **uv.lock**: Provides reproducible builds
- **CI**: Test against locked versions AND latest to catch breakage early

### Recommended Version Bumps for 1.0

| Package | Current Floor | Recommend | Reason |
|---------|--------------|-----------|--------|
| pytest-asyncio | >=0.23.0 | >=1.0.0 | Locked at 1.0.0 already; floor should match to avoid confusion with breaking API changes between 0.x and 1.0 |
| starlette | >=0.30.0 | >=0.37.0 | 0.30 is very old; if using SDK transports, match what SDK requires |

## Dependencies to Add

| Package | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| structlog | >=24.0.0 | Structured logging | Replace `logging.basicConfig()` calls with structured JSON logging. Critical for debugging production issues. Structured logs with context (tool name, target host, session ID) are far more useful than unstructured text. | MEDIUM |
| pydantic-settings | (already transitive) | Configuration from env | Already pulled in by MCP SDK's FastMCP. Can replace the manual `os.getenv()` config classes with `BaseSettings` subclasses that validate on startup. | HIGH |

## Dependencies to Potentially Remove

| Package | Current | Rationale | Risk |
|---------|---------|-----------|------|
| jsonschema | >=4.24.0 | Redundant if FastMCP handles tool schemas via pydantic | LOW -- only if full SDK migration |
| bandit | >=1.7.0 | Replace with ruff `S` rules | LOW -- same checks, one fewer tool |
| httpx | >=0.28.1 | Transitive via MCP SDK anyway; remove as direct dependency | LOW |

## Installation

```bash
# Core installation (unchanged)
uv sync

# With optional features
uv sync --extra monitoring
uv sync --extra automation
uv sync --extra security

# Dev dependencies
uv sync --group dev

# If adding structlog
# Add to pyproject.toml dependencies first, then:
uv sync
```

## Key Migration Decisions

### 1. FastMCP vs lowlevel.Server

**Recommend: Start with lowlevel.Server, then evaluate FastMCP.**

The lowlevel.Server provides handler registration with `@server.list_tools()` and `@server.call_tool()` decorators. This maps cleanly to the existing `tools.py` TOOLS dict + `execute_tool()` pattern. Migration is mechanical:

```python
# Current pattern (manual JSON-RPC):
class HomelabMCPServer:
    async def handle_request(self, request):
        if method == "tools/list": ...
        elif method == "tools/call": ...

# lowlevel.Server pattern:
server = Server("homelab-mcp")

@server.list_tools()
async def list_tools():
    return [Tool(name=k, description=v["description"], ...) for k, v in TOOLS.items()]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    return await execute_tool(name, arguments)
```

FastMCP would require more refactoring (individual `@mcp.tool()` decorators per tool function) but gives automatic schema generation from type hints. Consider for a future milestone.

### 2. HTTP Transport Migration

Replace custom `MCPHTTPTransport` + `SSEResponse` with SDK's `StreamableHTTPSessionManager`. This gives:
- Proper MCP session management
- Streamable HTTP transport (current standard, replacing SSE)
- Built-in OAuth auth middleware (optional)

### 3. Proxmox Client Session Pooling

Not a library change -- architectural fix. Create `aiohttp.ClientSession` once in `__init__` or via an async context manager, reuse across API calls:

```python
class ProxmoxAPIClient:
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=self.verify_ssl)
        )
        return self

    async def __aexit__(self, *args):
        await self._session.close()
```

## Sources

- MCP SDK source code: `.venv/lib/python3.12/site-packages/mcp/` (v1.9.4) -- direct inspection
- Project pyproject.toml and uv.lock -- direct inspection
- Project source code in `src/homelab_mcp/` -- direct inspection
- asyncssh known_hosts documentation: training data (MEDIUM confidence -- verify asyncssh docs for exact API)
- pytest-asyncio 1.0 migration: training data (MEDIUM confidence -- verify changelog)
- structlog recommendation: training data (HIGH confidence -- well-established library)

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| MCP SDK adoption | HIGH | Directly inspected installed SDK; clear feature overlap with custom code |
| Core dependencies (asyncssh, aiohttp) | HIGH | Verified locked versions in uv.lock; well-established libraries |
| SSH security patterns | MEDIUM | Training data for asyncssh known_hosts API; needs docs verification |
| pytest-asyncio 1.0 changes | MEDIUM | Training data; locked version confirms 1.0.0 but behavior changes need verification |
| structlog recommendation | MEDIUM | Standard in Python ecosystem but not verified for this specific project's needs |
| Dependency removal candidates | MEDIUM | Depends on SDK migration scope; jsonschema removal requires full FastMCP adoption |
