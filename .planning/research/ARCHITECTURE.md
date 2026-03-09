# Architecture Patterns

**Domain:** MCP server for homelab infrastructure management
**Researched:** 2026-03-08
**Confidence:** HIGH (based on codebase analysis and established server architecture patterns)

## Current Architecture Assessment

The existing layered architecture is sound: Transport -> Tool Registry -> Handlers -> Domain Logic -> Database. This is the right pattern for an MCP server. The issues are not structural -- they are about lifecycle management, resource ownership, and connection hygiene. The layers are correct; what sits inside them needs hardening.

### What Works Well

- **Schema/handler split** separates MCP protocol concerns from business logic cleanly
- **Abstract database adapter** allows SQLite for homelab, PostgreSQL if needed later
- **Strategy pattern for VM providers** is extensible without modifying existing code
- **Async-first design** is correct for an I/O-heavy infrastructure tool
- **Tool registry pattern** makes adding new tools mechanical and low-risk

### What Needs Architectural Evolution

The codebase has grown organically. Three modules exceed 1,000 lines (`infrastructure_crud.py` at 1,513, `service_installer.py` at 1,497, `ssh_tools.py` at 1,126). These are doing too much. The architecture needs resource lifecycle management, not more layers.

## Recommended Architecture

### Target State

```
MCP Client
    |
    v
[Transport Layer]  stdio / HTTP+SSE / WebSocket
    |
    v
[Tool Registry]  schema validation + handler dispatch
    |
    v
[Handler Layer]  argument unpacking, response formatting
    |
    v
[Domain Logic]   SSH, Proxmox, VM, Service, Infrastructure, Network
    |       \
    v        v
[Resource     [Database Layer]
 Manager]     SQLite / PostgreSQL
    |
    v
[Connection Pool]  SSH connections, HTTP sessions, DB connections
```

The key addition is a **Resource Manager** that owns long-lived connections and provides them to domain logic on demand, rather than each domain function creating and destroying its own connections.

### Component Boundaries

| Component | Responsibility | Communicates With | Owns |
|-----------|---------------|-------------------|------|
| **Transport** (`server.py`, `http_transport.py`) | Accept JSON-RPC, deliver responses, manage WebSocket shell relay | Tool Registry, Health Checker | Request lifecycle, SSE streams |
| **Auth** (`auth.py`) | API key validation for HTTP transport | Transport (middleware) | Nothing stateful |
| **Tool Registry** (`tools.py`, `tool_schemas/`, `tool_handlers/`) | Map tool names to schemas and handlers, dispatch execution | Handlers | Tool catalog |
| **Handlers** (`tool_handlers/*.py`) | Unpack arguments, call domain logic, format MCP responses | Domain Logic | Nothing -- pure adapters |
| **SSH Domain** (`ssh_tools.py`) | Device discovery, command execution, credential resolution | Resource Manager, Database | Discovery logic, hardware parsing |
| **Proxmox Domain** (`proxmox_api.py`, `proxmox_scripts.py`) | Proxmox VE API integration | Resource Manager (HTTP pool) | API abstraction, script cache |
| **VM Domain** (`vm_operations.py`, `vm_providers/`) | VM/container lifecycle via Docker/LXD | SSH Domain | Provider abstraction |
| **Infrastructure Domain** (`infrastructure_crud.py`) | Deploy, update, decommission infrastructure | SSH Domain, Service Installer, Database | Deployment state |
| **Service Domain** (`service_installer.py`) | Install services via Terraform/Ansible | SSH Domain | Template loading, installation methods |
| **Network Domain** (`sitemap.py`) | Device registry, topology, change tracking | Database | Sitemap queries |
| **Resource Manager** (NEW) | Connection pooling, lifecycle management | SSH connections, HTTP sessions, DB connections | Connection pools, health state |
| **Database** (`database.py`) | Persistent storage abstraction | SQLite/PostgreSQL | Schema, migrations |
| **Config** (`config.py`) | Environment-based configuration | All layers (read-only) | Validated config objects |
| **Error Handling** (`error_handling.py`) | Timeouts, retries, health tracking | Cross-cutting | Health metrics |

### Boundary Rules

1. **Handlers never touch connections directly.** They call domain functions, which get connections from the Resource Manager.
2. **Domain modules do not create `aiohttp.ClientSession` or `asyncssh.connect` directly.** They request connections from pools.
3. **Database access goes through `DatabaseAdapter`.** No raw SQL outside `database.py`.
4. **Configuration flows one direction: Config -> everything.** Modules read config, never write it.
5. **Transport layer never calls domain logic directly.** Always through Tool Registry -> Handler -> Domain.

## Data Flow

### Tool Execution (Primary Path)

```
1. Client sends JSON-RPC 2.0 request
2. Transport parses, validates JSON-RPC envelope
3. Tool Registry looks up handler by tool name
4. Handler unpacks arguments dict -> keyword arguments
5. Domain function executes business logic:
   a. Gets connection from Resource Manager (pooled)
   b. Performs SSH/API/DB operations
   c. Returns structured result (JSON string)
6. Handler wraps result in MCP content format
7. Transport serializes JSON-RPC response
```

### SSH Operations (Connection-Intensive Path)

```
1. Handler calls domain function with hostname + credentials
2. Domain calls resolve_ssh_credentials() -> SSHCredentials
3. Domain requests SSH connection from pool:
   a. Pool checks for existing healthy connection to host
   b. If exists and healthy -> reuse
   c. If not -> create new connection with host key verification
   d. Connection added to pool with TTL
4. Domain executes commands over connection
5. Connection returned to pool (not closed)
6. Pool cleanup task closes idle connections after TTL
```

### Proxmox API (HTTP-Intensive Path)

```
1. Handler calls ProxmoxAPIClient method
2. Client uses shared aiohttp.ClientSession (not per-request)
3. Session handles connection pooling via TCPConnector
4. Auth token cached and reused until expiry
5. Response parsed and returned
6. Session persists for server lifetime
```

### State Management (Current -> Target)

| State | Current Location | Current Problem | Target |
|-------|-----------------|-----------------|--------|
| SSH connections | Created per-call, closed after | No reuse, 19 MITM-vulnerable | Pooled with host key verification |
| HTTP sessions | Created per-call | No connection reuse | Single shared session per Proxmox host |
| DB connections | Opened/closed per operation | Overhead on each query | Persistent connection, reconnect on failure |
| Shell sessions | In-memory dict | Lost on restart | In-memory (acceptable for 1.0, documented) |
| Health metrics | In-memory singleton | Lost on restart | In-memory (acceptable for 1.0) |
| Proxmox auth | Per-client cached | Re-auth on each new client | Cached in shared client instance |
| Script cache | Module-level dict, 1hr TTL | Works fine | Keep as-is |

## Patterns to Follow

### Pattern 1: Resource Manager for Connection Pooling

**What:** A single component that owns all external connections (SSH, HTTP, DB) and provides them to domain logic via context managers.

**When:** Any operation that connects to external systems.

**Why:** The current pattern of creating connections per-call means:
- No connection reuse (TCP handshake overhead on every Proxmox API call)
- No centralized place to enforce host key verification
- No graceful shutdown (connections abandoned, not closed)
- No connection health monitoring

**Example:**
```python
class ResourceManager:
    """Owns and manages all external connections."""

    def __init__(self, config: MCPConfig) -> None:
        self._ssh_pool: dict[str, asyncssh.SSHClientConnection] = {}
        self._http_session: aiohttp.ClientSession | None = None
        self._db: DatabaseAdapter | None = None
        self._config = config

    async def get_ssh_connection(
        self, hostname: str, credentials: SSHCredentials
    ) -> asyncssh.SSHClientConnection:
        """Get or create a pooled SSH connection."""
        key = f"{credentials.username}@{hostname}:{credentials.port}"
        if key in self._ssh_pool:
            conn = self._ssh_pool[key]
            if not conn.is_closed():
                return conn
            del self._ssh_pool[key]

        conn = await asyncssh.connect(
            hostname,
            username=credentials.username,
            known_hosts=self._config.ssh.known_hosts_path,  # NOT None
            client_keys=[credentials.key_path] if credentials.key_path else None,
            password=credentials.password,
        )
        self._ssh_pool[key] = conn
        return conn

    async def get_http_session(self) -> aiohttp.ClientSession:
        """Get or create a shared HTTP session."""
        if self._http_session is None or self._http_session.closed:
            connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
            self._http_session = aiohttp.ClientSession(connector=connector)
        return self._http_session

    async def shutdown(self) -> None:
        """Gracefully close all connections."""
        for conn in self._ssh_pool.values():
            conn.close()
        if self._http_session:
            await self._http_session.close()
        if self._db:
            self._db.close()
```

### Pattern 2: Graceful Startup and Shutdown

**What:** Server has explicit startup and shutdown phases that initialize and tear down resources in order.

**When:** Server start and stop.

**Why:** Currently, resources are initialized lazily and never explicitly cleaned up. This causes:
- SSH key initialization racing with first request
- No cleanup of open connections on SIGTERM
- Database connections left open

**Example:**
```python
class HomelabMCPServer:
    async def startup(self) -> None:
        """Initialize all resources in dependency order."""
        self.config = get_config()
        self.config.validate()  # Fail fast on bad config

        self.resources = ResourceManager(self.config)
        await self.resources.initialize_db()
        await ensure_mcp_ssh_key()

        self.tools = get_available_tools()
        logger.info("Server ready")

    async def shutdown(self) -> None:
        """Clean up all resources."""
        await self.resources.shutdown()
        logger.info("Server stopped")
```

### Pattern 3: Domain Module Decomposition

**What:** Break 1,000+ line modules into focused sub-modules grouped by operation type.

**When:** Modules exceed ~500 lines or handle multiple distinct responsibilities.

**Why:** `infrastructure_crud.py` (1,513 lines) handles deploy, update, decommission, scale, validate, backup, and rollback. These are distinct operations that share some helpers but should be independently testable.

**Target structure:**
```
src/homelab_mcp/
  infrastructure/
    __init__.py          # Public API (re-exports)
    deploy.py            # deploy_infrastructure()
    update.py            # update_device_config()
    decommission.py      # decommission_device()
    scale.py             # scale_services()
    validate.py          # validate_infrastructure_changes()
    backup.py            # create/rollback backups
    _helpers.py          # Shared SSH helpers, formatting

  services/
    __init__.py
    installer.py         # Core installation logic
    terraform.py         # Terraform-specific
    ansible.py           # Ansible-specific
    templates.py         # Template loading
```

**Do this incrementally.** Do not refactor all three large modules at once. Start with `infrastructure_crud.py` because it has the most stub functions that need implementation anyway.

### Pattern 4: Input Validation at Handler Boundary

**What:** Validate semantic correctness of inputs (hostnames, IPs, ports) at the handler layer before calling domain logic.

**When:** Every tool call.

**Why:** JSON Schema validates types and required fields, but does not validate that a hostname is a valid hostname or a port is in range. Currently, bad inputs propagate to SSH/API calls and fail with confusing errors.

**Example:**
```python
import ipaddress
import re

def validate_hostname(hostname: str) -> str:
    """Validate and return hostname, raise ValueError if invalid."""
    # Try as IP address first
    try:
        ipaddress.ip_address(hostname)
        return hostname
    except ValueError:
        pass

    # Validate as hostname
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', hostname):
        raise ValueError(f"Invalid hostname: {hostname}")
    return hostname
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Connection-Per-Call
**What:** Creating a new SSH connection or HTTP session for every single tool invocation.
**Why bad:** TCP handshake overhead, no connection reuse, impossible to enforce security policies centrally, no graceful shutdown.
**Instead:** Pool connections through ResourceManager, reuse until TTL or failure.

### Anti-Pattern 2: Silent Exception Swallowing
**What:** `except Exception: pass` blocks that hide failures.
**Why bad:** Makes debugging impossible. A user calls a tool, gets success, but a side effect (sitemap update, cleanup) silently failed.
**Instead:** Log at debug level minimum. For non-critical failures, log and continue. For critical failures, propagate.

### Anti-Pattern 3: God Modules
**What:** Single files exceeding 1,000 lines handling multiple distinct responsibilities.
**Why bad:** Hard to test individual operations in isolation. Changes to deployment logic risk breaking decommission logic. Merge conflicts when working on different features.
**Instead:** Decompose into sub-packages with clear public APIs (see Pattern 3).

### Anti-Pattern 4: Lazy Security Initialization
**What:** SSH host key verification set to `None`, SSL verification defaulting to `False`.
**Why bad:** Every connection is vulnerable to MITM. Users inherit insecure defaults without knowing.
**Instead:** Secure by default. Known hosts file managed by the server. SSL verification on, with documented override for self-signed certs.

## Scalability Considerations

| Concern | Homelab (1 user) | Small Team (5 users) | Notes |
|---------|-------------------|---------------------|-------|
| Database | SQLite fine | SQLite fine (single writer) | PostgreSQL adapter exists if needed |
| SSH connections | Pool of ~5-20 | Pool of ~5-20 | Same infra, more callers -- pool handles it |
| Proxmox API | Single shared session | Single shared session | Proxmox API is the bottleneck, not the client |
| Concurrent tools | asyncio handles it | asyncio handles it | Tools are I/O-bound, not CPU-bound |
| State persistence | SQLite + in-memory | SQLite + in-memory | Shell sessions lost on restart is acceptable |

The homelab use case does not need horizontal scaling. The architecture should optimize for **reliability** (connections that work, errors that surface, cleanup that happens) not throughput.

## Suggested Build Order

Based on dependency analysis, the architecture hardening should proceed in this order:

### Phase 1: Resource Lifecycle (Foundation)

Build the ResourceManager and wire it into existing code. This is the foundation everything else depends on.

1. **ResourceManager class** -- owns SSH pool, HTTP session, DB connection
2. **Wire into server startup/shutdown** -- explicit lifecycle
3. **Replace direct `asyncssh.connect` calls** with pooled connections
4. **Replace per-request `aiohttp.ClientSession`** with shared session
5. **Add graceful shutdown** via signal handlers (SIGTERM, SIGINT)

**Why first:** Every other improvement (security, stubs, validation) needs a centralized place to manage connections. Without this, fixing SSH host key verification means changing 19 call sites instead of 1.

### Phase 2: Security Hardening (Unblocked by Phase 1)

With ResourceManager in place, security changes happen in one place.

1. **SSH host key verification** -- known_hosts management in ResourceManager
2. **Proxmox SSL verification** -- default True in shared session config
3. **API key validation** -- enforce strength check on startup
4. **Input validation** -- hostname/IP/port validation in handlers

**Why second:** Phase 1 centralizes connection creation, so security policies apply everywhere automatically.

### Phase 3: Stub Implementation and Silent Error Fixes

Now that connections are pooled and secure, implement the missing functionality.

1. **`_update_sitemap_after_deployment()`** -- use pooled SSH + sitemap
2. **`_rediscover_device_after_config()`** -- use pooled SSH + discovery
3. **`_install_with_script()`** -- implement script-based installation
4. **Replace silent `except: pass`** blocks with debug logging

**Why third:** Stubs need working connections (Phase 1) and some need SSH (Phase 2 makes those secure).

### Phase 4: Module Decomposition (Optional for 1.0)

Break large modules into sub-packages. This is the lowest priority because the current structure works -- it is just hard to maintain.

1. **`infrastructure_crud.py`** -> `infrastructure/` sub-package
2. **`service_installer.py`** -> `services/` sub-package
3. **`ssh_tools.py`** -> `ssh/` sub-package

**Why last:** Refactoring file structure is risky and does not add user-facing value. Only do this if test coverage is high enough to catch regressions.

### Dependency Graph

```
Phase 1: Resource Lifecycle
    |
    +---> Phase 2: Security Hardening
    |         |
    |         +---> Phase 3: Stub Implementation
    |
    +---> Phase 4: Module Decomposition (independent, optional)
```

Phase 2 depends on Phase 1 (centralized connection management).
Phase 3 depends on Phase 2 (stubs need secure connections to implement properly).
Phase 4 is independent but lowest priority.

## Sources

- Codebase analysis: `/home/shaun/projects/mcp_python_server/src/homelab_mcp/`
- Architecture mapping: `.planning/codebase/ARCHITECTURE.md`
- Concerns inventory: `.planning/codebase/CONCERNS.md`
- Project context: `.planning/PROJECT.md`
- MCP protocol specification (protocol version 2024-11-05 as referenced in server.py)
- Python asyncio connection pooling patterns (established practice)
- aiohttp ClientSession documentation (known best practice: one session per application)

---

*Architecture research: 2026-03-08*
