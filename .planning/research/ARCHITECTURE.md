# Architecture Research

**Domain:** MCP Server — Safety & Observability additions to existing Python MCP server
**Researched:** 2026-03-11
**Confidence:** HIGH (based on direct source inspection of SDK source and full existing codebase)

## Existing Architecture (v1.0 Baseline)

Understanding the v1.0 structure is prerequisite to placing new components correctly.

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Clients (stdio / HTTP)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP protocol (JSON-RPC)
┌────────────────────────────▼────────────────────────────────────┐
│                    server.py  (lowlevel.Server)                  │
│  handle_list_tools()   handle_call_tool()   handle_set_level()   │
│       │                      │                                   │
│  get_all_tool_schemas()  get_tool_handler(name)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   tool_handlers/  (dispatch layer)               │
│  ssh_handlers  vm_handlers  infra_handlers  proxmox_handlers     │
│  network_handlers  service_handlers  credential_handlers         │
└──────┬──────────┬──────────┬──────────┬───────────┬────────────┘
       │          │          │          │           │
  ssh_tools  vm_ops/    infra_    proxmox_    service_
  ssh_conn   vm_provs   crud      api         installer
       │          │          │          │           │
└──────┴──────────┴──────────┴──────────┴───────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    sitemap.py / database.py (SQLite)             │
│              NetworkSiteMap  •  DatabaseAdapter                  │
└─────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              resource_manager.py (lifespan-managed)              │
│        proxmox_session (aiohttp)  •  db_adapter (SQLite)         │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities (v1.0)

| Component | Responsibility |
|-----------|---------------|
| `server.py` | lowlevel.Server wiring; lifespan; list_tools / call_tool / set_level handlers |
| `tool_handlers/__init__.py` | TOOL_HANDLERS registry mapping name to async handler fn |
| `tool_handlers/*.py` | Thin adapters: unpack arguments, call domain module, wrap response |
| `tool_schemas/*.py` | JSON schema definitions for all 49 tools |
| `tool_annotations.py` | ToolAnnotations (readOnlyHint, destructiveHint, idempotentHint) per tool |
| `vm_operations.py` | VM/container deploy, control, status, logs, remove |
| `vm_providers/` | Docker and LXD provider implementations |
| `infrastructure_crud.py` | Deploy/update/decommission/backup/rollback lifecycle |
| `proxmox_api.py` | Proxmox REST API calls (nodes, VMs, LXC, tasks) |
| `ssh_tools.py` | SSH-based device discovery and hardware detection |
| `ssh_connection.py` | asyncssh connection factory with TOFU host key verification |
| `sitemap.py` | NetworkSiteMap: device storage and change history |
| `database.py` | DatabaseAdapter ABC; SQLiteAdapter implementation |
| `resource_manager.py` | Lifespan-managed aiohttp session + db_adapter |
| `service_installer.py` | Terraform/Ansible-based service installation |
| `error_handling.py` | timeout_wrapper, MCPTimeout, MCPConnectionError |
| `config.py` | MCPConfig from env/file; get_config() singleton |
| `progress.py` | emit_progress() MCP logging notifications |
| `log_filter.py` | CredentialFilter; sanitize_error() |
| `http_app.py` / `http_transport.py` | Starlette ASGI; Streamable HTTP + WebSocket transport |

---

## v1.1 Target Architecture

Three new capability clusters integrate with the existing structure.

### System Overview (v1.1)

```
┌─────────────────────────────────────────────────────────────────┐
│                          MCP Clients                             │
│  tools/call   tools/list                                         │
│  resources/list   resources/read   resources/subscribe           │
└────────┬──────────────────────┬──────────────────────────────────┘
         │                      │
┌────────▼──────────────────────▼──────────────────────────────────┐
│                           server.py  [MODIFIED]                   │
│  handle_call_tool()            handle_list_resources()  [NEW]     │
│    dry_run arg passed through  handle_read_resource()   [NEW]     │
│    _notify_resource_change()   handle_subscribe()       [NEW]     │
│    called after mutations      handle_unsubscribe()     [NEW]     │
└────────┬──────────────────────┬──────────────────────────────────┘
         │                      │
┌────────▼──────┐    ┌──────────▼──────────────────────────────────┐
│ Domain modules│    │              resources.py  [NEW]              │
│ [MODIFIED]    │    │  RESOURCE_REGISTRY: list of Resource objects  │
│               │    │  ResourceFetcher: URI to content function     │
│ remove_vm()   │    │  SubscriptionTracker: URI to subscribed bool  │
│ delete_prox() │    └──────────┬──────────────────────────────────┘
│ decommission()│               │
│               │    ┌──────────▼──────────────────────────────────┐
│ dry_run=True  │    │           drift.py  [NEW]                     │
│ returns plan  │    │  DriftDetector.scan()                         │
│ dry_run=False │    │  compares SQLite baseline vs live SSH/API     │
│ executes      │    │  returns DriftReport dataclass                │
└───────────────┘    └──────────┬──────────────────────────────────┘
                                │
                     ┌──────────▼──────────────────────────────────┐
                     │   Existing: sitemap, proxmox_api, vm_ops,    │
                     │   ssh_tools  (all read-only query paths)      │
                     └──────────────────────────────────────────────┘
```

---

## New and Modified Components

| Component | New / Modified | What Changes |
|-----------|---------------|-------------|
| `dry_run.py` | **NEW** (optional) | If preview logic grows complex, extract to own module |
| `drift.py` | **NEW** | DriftDetector, DriftReport, ConfigDrift, StateDrift |
| `resources.py` | **NEW** | RESOURCE_REGISTRY, ResourceFetcher, SubscriptionTracker |
| `server.py` | **MODIFIED** | Add four Resource handler decorators; add `_notify_resource_change()` helper |
| `resource_manager.py` | **MODIFIED** | Add SubscriptionTracker; fix proxmox_session wiring to handler chain |
| `tool_handlers/vm_handlers.py` | **MODIFIED** | Pass `dry_run` arg; call `_notify_resource_change()` after successful mutations |
| `tool_handlers/proxmox_handlers.py` | **MODIFIED** | Call `_notify_resource_change()` after successful mutations |
| `tool_handlers/infrastructure_handlers.py` | **MODIFIED** | Pass `dry_run` arg; call `_notify_resource_change()` after mutations |
| `tool_handlers/network_handlers.py` | **MODIFIED** | Call `_notify_resource_change()` after discover_and_map |
| `tool_handlers/__init__.py` | **MODIFIED** | Register `scan_infrastructure_drift` handler |
| `tool_schemas/drift_tools_schema.py` | **NEW** | Schema for `scan_infrastructure_drift` |
| `tool_annotations.py` | **MODIFIED** | Add `scan_infrastructure_drift` as read-only |
| `vm_operations.py` | **MODIFIED** | Add `dry_run: bool = False` to remove_vm, control_vm_state |
| `infrastructure_crud.py` | **MODIFIED** | Add `dry_run: bool = False` to decommission, rollback, scale |
| `proxmox_api.py` | **MODIFIED** | Add `dry_run: bool = False` to delete_proxmox_vm |

---

## Feature 1: Dry-Run Mode

### Design Decision

Dry-run is implemented at the **domain function level**, not as an interceptor in server.py. Each destructive domain function gains a `dry_run: bool = False` parameter. When True, it returns a structured preview without executing.

Why not intercept generically in server.py: The preview content is domain-specific. `delete_proxmox_vm` preview must list the VMID, its snapshots, and disk images. `decommission_device` preview must list services that would be migrated. A generic interceptor can only echo back the tool name and arguments — useless for operator safety.

### Integration Points

**Tool schemas** (six destructive tools gain the `dry_run` property):

```python
# Added to each destructive tool's inputSchema.properties:
"dry_run": {
    "type": "boolean",
    "description": "If true, return a preview of what would happen without executing.",
    "default": False,
}
```

**Domain function pattern:**

```python
# vm_operations.py
async def remove_vm(
    device_id: int,
    platform: str,
    vm_name: str,
    force: bool = False,
    dry_run: bool = False,   # NEW parameter
) -> str:
    if dry_run:
        return json.dumps({
            "status": "dry_run",
            "operation": "remove_vm",
            "would_affect": {
                "vm_name": vm_name,
                "device_id": device_id,
                "platform": platform,
            },
            "warning": "Irreversible. Use dry_run=false to execute.",
        })
    # existing execution path unchanged below this point
    ...
```

**Handler passes dry_run through:**

```python
# tool_handlers/vm_handlers.py
async def handle_remove_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    result = await remove_vm(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
        force=arguments.get("force", False),
        dry_run=arguments.get("dry_run", False),   # NEW
    )
    return {"content": [{"type": "text", "text": result}]}
```

**Affected destructive tools** (from tool_annotations.py `_DESTRUCTIVE_TOOLS`):
- `decommission_device` — infrastructure_crud.py
- `remove_vm` — vm_operations.py
- `remove_server` — credential domain
- `delete_proxmox_vm` — proxmox_api.py
- `destroy_terraform_service` — service_installer.py
- `rollback_infrastructure_changes` — infrastructure_crud.py

---

## Feature 2: Drift Detection

### Design Decision

Drift detection runs as a **tool call** (`scan_infrastructure_drift`), not a background task and not a resource read. The result is surfaced as a structured JSON tool response. The `homelab://drift/report` resource caches the last result so subscribed clients get notified.

Why a tool, not a background task: PROJECT.md explicitly defers "Auto-detect drift with periodic background checks" to a future milestone. On-demand keeps asyncio task management out of v1.1.

Why not a resource read: SSH discovery across 10+ devices takes seconds per device. Resource reads are expected to be fast (clients may call them frequently). The tool call model communicates that the operation is slow and deliberate.

### New Module: drift.py

```
src/homelab_mcp/drift.py
```

**Data structures:**

```python
@dataclass
class ConfigDrift:
    device_id: int
    hostname: str
    field: str           # e.g. "cpu_cores", "memory_total"
    expected: Any        # value stored in SQLite last-seen record
    actual: Any          # value from live SSH query

@dataclass
class StateDrift:
    resource_id: str     # e.g. "proxmox:pve:100" or "device:42:nginx"
    resource_type: str   # "vm" | "lxc" | "service"
    expected_state: str  # e.g. "running"
    actual_state: str    # e.g. "stopped"

@dataclass
class DriftReport:
    scanned_at: str      # ISO 8601 timestamp
    config_drift: list[ConfigDrift]
    state_drift: list[StateDrift]
    unreachable: list[int]   # device_ids that could not be reached
    drift_detected: bool
    summary: str
```

**DriftDetector class:**

```python
class DriftDetector:
    def __init__(
        self,
        db_adapter: DatabaseAdapter,
        proxmox_session: aiohttp.ClientSession | None,
    ) -> None: ...

    async def scan(self, scope: str = "all") -> DriftReport:
        # 1. Load baseline from SQLite (sitemap devices)
        # 2. For each reachable device: SSH discover, compare vs baseline
        # 3. Query Proxmox API for VM list, compare status vs expected
        # 4. Assemble DriftReport
        ...

    async def _check_config_drift(self) -> list[ConfigDrift]:
        # SSH discover each device, compare cpu_cores / memory_total /
        # network_interfaces against SQLite record
        ...

    async def _check_state_drift(self) -> list[StateDrift]:
        # proxmox_api.list_proxmox_resources() and get_proxmox_vm_status()
        # compare running/stopped vs last known state
        ...
```

**DriftDetector accesses ResourceManager** via `get_resource_manager()` — same pattern as existing handlers. Does not instantiate its own connections.

### New Tool: scan_infrastructure_drift

**Schema** (`tool_schemas/drift_tools_schema.py`):

```python
DRIFT_TOOLS_SCHEMA = {
    "scan_infrastructure_drift": {
        "description": "Scan for drift between expected infrastructure state and live state. "
                       "Checks both config drift (CPU, memory, network changed outside MCP) "
                       "and state drift (VMs stopped, services offline). Returns a structured report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["all", "devices", "vms", "services"],
                    "default": "all",
                    "description": "Which category of resources to check.",
                },
                "device_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Limit scan to specific device IDs. Omit for all devices.",
                },
            },
            "required": [],
        },
    }
}
```

**Annotation:** `readOnlyHint=True` — scan queries only, never modifies.

**Data flow:**

```
call_tool("scan_infrastructure_drift", {scope: "all"})
    |
    v
tool_handlers/drift_handlers.py: handle_scan_drift(args)
    |
    v
drift.py: DriftDetector(db, proxmox_session).scan("all")
    |
    +-- _check_config_drift():
    |     load devices from SQLite
    |     SSH-discover each (asyncio.gather for parallelism)
    |     diff cpu_cores, memory_total, network_interfaces
    |     --> list[ConfigDrift]
    |
    +-- _check_state_drift():
    |     proxmox_api.list_proxmox_resources()
    |     get_proxmox_vm_status() per VM
    |     diff status vs last_seen
    |     --> list[StateDrift]
    |
    v
DriftReport assembled
    |
    v  (cache last report for homelab://drift/report resource)
_cache_drift_report(report)
    |
    v  (if client subscribed)
_notify_resource_change("homelab://drift/report")
    |
    v
Client receives DriftReport as JSON in tool result
```

---

## Feature 3: MCP Resources

### SDK API (confirmed from source inspection, mcp>=1.9.1)

The `lowlevel.Server` exposes these decorator hooks:

```python
@server.list_resources()
async def handle_list_resources() -> list[types.Resource]: ...

@server.list_resource_templates()
async def handle_list_resource_templates() -> list[types.ResourceTemplate]: ...

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> Iterable[ReadResourceContents]: ...

@server.subscribe_resource()
async def handle_subscribe(uri: AnyUrl) -> None: ...

@server.unsubscribe_resource()
async def handle_unsubscribe(uri: AnyUrl) -> None: ...
```

Capability auto-detection: `get_capabilities()` in the SDK sets `resources_capability.subscribe=True` when both `ListResourcesRequest` and `SubscribeRequest` handlers are registered. No manual capability configuration needed.

Push notification to subscribed client:

```python
session = server.request_context.session
await session.send_resource_updated(uri)   # ServerSession.send_resource_updated()
```

### Resource URI Namespace

| URI | Content | Update Trigger |
|-----|---------|----------------|
| `homelab://infra/vms` | JSON list of all VMs across all hosts | After deploy_vm, remove_vm, control_vm, manage_proxmox_vm, create_proxmox_vm, delete_proxmox_vm, clone_proxmox_vm |
| `homelab://infra/devices` | JSON list of all discovered devices from SQLite | After discover_and_map, bulk_discover_and_map, decommission_device |
| `homelab://infra/services` | JSON service installation status per device | After install_service, destroy_terraform_service |
| `homelab://infra/proxmox/resources` | Proxmox nodes, VMs, storage summary | After create_proxmox_vm, delete_proxmox_vm, clone_proxmox_vm, create_proxmox_lxc |
| `homelab://drift/report` | Latest drift scan result (null if never scanned) | After scan_infrastructure_drift |

### New Module: resources.py

```
src/homelab_mcp/resources.py
```

**RESOURCE_REGISTRY** — static list of Resource descriptors:

```python
from mcp.types import Resource
from pydantic import AnyUrl

RESOURCE_REGISTRY: list[Resource] = [
    Resource(
        uri=AnyUrl("homelab://infra/vms"),
        name="VM List",
        description="All VMs and containers across all managed hosts",
        mimeType="application/json",
    ),
    Resource(
        uri=AnyUrl("homelab://infra/devices"),
        name="Device Inventory",
        description="All discovered network devices with hardware info",
        mimeType="application/json",
    ),
    Resource(
        uri=AnyUrl("homelab://infra/services"),
        name="Service Status",
        description="Service installation status per device",
        mimeType="application/json",
    ),
    Resource(
        uri=AnyUrl("homelab://infra/proxmox/resources"),
        name="Proxmox Resources",
        description="Proxmox nodes, VMs, LXC containers, and storage",
        mimeType="application/json",
    ),
    Resource(
        uri=AnyUrl("homelab://drift/report"),
        name="Drift Report",
        description="Latest infrastructure drift scan result",
        mimeType="application/json",
    ),
]
```

**ResourceFetcher** — maps URI to live query:

```python
class ResourceFetcher:
    """Fetches live content for each resource URI by calling existing domain functions."""

    async def fetch(self, uri: AnyUrl) -> str:
        uri_str = str(uri)
        if uri_str == "homelab://infra/vms":
            return await self._fetch_vms()
        elif uri_str == "homelab://infra/devices":
            return await self._fetch_devices()
        elif uri_str == "homelab://infra/services":
            return await self._fetch_services()
        elif uri_str == "homelab://infra/proxmox/resources":
            return await self._fetch_proxmox_resources()
        elif uri_str == "homelab://drift/report":
            return await self._fetch_drift_report()
        else:
            raise ValueError(f"Unknown resource URI: {uri}")

    async def _fetch_devices(self) -> str:
        db = get_resource_manager().db_adapter
        devices = db.get_all_devices()
        return json.dumps({"devices": devices, "count": len(devices)})

    async def _fetch_proxmox_resources(self) -> str:
        result = await list_proxmox_resources()   # existing function
        return json.dumps(result)
    # ...
```

**SubscriptionTracker** — tracks which URIs the client has subscribed to:

```python
class SubscriptionTracker:
    """Single-client model: one set of subscribed URIs per server instance.

    Homelab is single-operator. No per-client subscription map needed.
    """

    def __init__(self) -> None:
        self._subscriptions: set[str] = set()

    def subscribe(self, uri: AnyUrl) -> None:
        self._subscriptions.add(str(uri))

    def unsubscribe(self, uri: AnyUrl) -> None:
        self._subscriptions.discard(str(uri))

    def is_subscribed(self, uri: AnyUrl) -> bool:
        return str(uri) in self._subscriptions
```

### Wiring into server.py

Four new handler decorators in `server.py`:

```python
from .resources import RESOURCE_REGISTRY, ResourceFetcher, SubscriptionTracker
from mcp.server.lowlevel.helper_types import ReadResourceContents

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return RESOURCE_REGISTRY

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> Iterable[ReadResourceContents]:
    fetcher = ResourceFetcher()
    content = await fetcher.fetch(uri)
    yield ReadResourceContents(content=content, mime_type="application/json")

@server.subscribe_resource()
async def handle_subscribe(uri: AnyUrl) -> None:
    get_resource_manager().subscription_tracker.subscribe(uri)

@server.unsubscribe_resource()
async def handle_unsubscribe(uri: AnyUrl) -> None:
    get_resource_manager().subscription_tracker.unsubscribe(uri)
```

**Notification helper added to server.py:**

```python
async def _notify_resource_change(uri_str: str) -> None:
    """Send ResourceUpdated notification if client is subscribed to this URI."""
    try:
        tracker = get_resource_manager().subscription_tracker
        uri = AnyUrl(uri_str)
        if tracker.is_subscribed(uri):
            session = server.request_context.session
            await session.send_resource_updated(uri)
    except Exception:
        logger.debug("Resource notification skipped (no active session context)")
```

Called from `handle_call_tool()` after successful non-dry-run execution of mutating tools.

### resource_manager.py Changes

Add SubscriptionTracker:

```python
class ResourceManager:
    def __init__(self, config: MCPConfig) -> None:
        ...
        self._subscription_tracker: SubscriptionTracker | None = None

    async def initialize(self) -> None:
        ...
        from .resources import SubscriptionTracker
        self._subscription_tracker = SubscriptionTracker()

    @property
    def subscription_tracker(self) -> SubscriptionTracker:
        if self._subscription_tracker is None:
            raise RuntimeError("ResourceManager not initialized")
        return self._subscription_tracker
```

Also fix the existing v1.0 bug: `proxmox_session` is created but never passed to `proxmox_api.py` functions. The fix is to have proxmox functions call `get_resource_manager().proxmox_session` directly, same pattern used by other handlers. This is a one-time wiring fix, not a new abstraction.

---

## Data Flow Summary

### Dry-Run Flow

```
call_tool("remove_vm", {device_id: 1, vm_name: "test", dry_run: true})
    |
handle_call_tool in server.py
    |
handle_remove_vm(args) in vm_handlers.py
    |
remove_vm(..., dry_run=True) in vm_operations.py
    |
returns JSON preview -- no SSH connection, no side effect
    |
handle_call_tool does NOT call _notify_resource_change  (dry_run = no mutation)
    |
Client receives: CallToolResult with dry_run preview
```

### Drift Scan Flow

```
call_tool("scan_infrastructure_drift", {scope: "all"})
    |
handle_scan_drift(args) in drift_handlers.py
    |
DriftDetector(db, proxmox_session).scan("all")
    |
    +-- SSH discover each device (asyncio.gather)
    |   compare against SQLite record
    |   --> list[ConfigDrift]
    |
    +-- proxmox_api.list_proxmox_resources()
    |   compare status vs last_seen
    |   --> list[StateDrift]
    |
DriftReport assembled and JSON-serialised
    |
    +-- store in module-level cache in resources.py
    +-- _notify_resource_change("homelab://drift/report")
    |     if subscribed: session.send_resource_updated(uri)
    |
Client receives: CallToolResult with DriftReport JSON
```

### Resource Read Flow

```
resources/read {"uri": "homelab://infra/vms"}
    |
handle_read_resource(uri) in server.py
    |
ResourceFetcher.fetch("homelab://infra/vms")
    |
    +-- list_proxmox_resources() for Proxmox VMs
    +-- list_vms_on_device() for Docker/LXD VMs (from sitemap devices)
    |
returns JSON string wrapped in ReadResourceContents
    |
Client receives: ReadResourceResult
```

### Mutation + Notification Flow

```
call_tool("create_proxmox_vm", {...})  [no dry_run on non-destructive tools]
    |
handle_call_tool succeeds (no ToolError raised)
    |
_notify_resource_change("homelab://infra/vms")
_notify_resource_change("homelab://infra/proxmox/resources")
    |
tracker.is_subscribed(uri)?
  YES: session.send_resource_updated(uri)
  NO:  skip silently
    |
Client receives: ResourceUpdatedNotification
    |
Client calls: resources/read {"uri": "homelab://infra/vms"}  to refresh
```

---

## Suggested Build Order

Dependencies between the three v1.1 features determine safe sequencing.

### Phase 1: MCP Resources — Plumbing (no feature dependencies)

Create `resources.py` with RESOURCE_REGISTRY (static list), SubscriptionTracker (no state), and ResourceFetcher stubs (return placeholder JSON). Wire all four SDK handler decorators into `server.py`. Add `subscription_tracker` property to `ResourceManager`.

**Why first:** The subscription tracker must exist on ResourceManager before any notification calls can be made. This phase establishes the wiring. ResourceFetcher stubs let clients exercise the protocol path immediately, before real data is connected. Tests verify the SDK integration is correct.

**Deliverable:** Clients can call resources/list and get the URI catalog. Resources/read returns placeholder data. Subscribe/unsubscribe work without error.

### Phase 2: Dry-Run Mode (no dependencies on Phase 1)

Add `dry_run: bool = False` parameter to six destructive domain functions. Update their JSON schemas. Update the six handler thin-adapters to pass through the argument. Write tests for each dry_run path.

**Why second:** Lowest coupling of the three features. Each domain function change is independent. No new modules. Immediately user-visible safety value. Can be done in parallel with Phase 1 since there are no shared touchpoints.

**Deliverable:** All six destructive tools accept `dry_run: true` and return a structured preview.

### Phase 3: MCP Resources — Live Data (depends on Phase 1)

Implement `ResourceFetcher.fetch()` for each URI using existing read functions: `db_adapter.get_all_devices()` for devices, `list_proxmox_resources()` for Proxmox, etc. Write tests that verify the JSON shape of each resource.

**Why third:** ResourceFetcher calls existing read-only query functions — no new persistence. Once real data flows, adding notifications (Phase 4) is straightforward.

**Deliverable:** Resources/read returns real live data for all five URIs.

### Phase 4: Resource Subscriptions + Notification Wiring (depends on Phase 1 + Phase 3)

Add `_notify_resource_change()` to `server.py`. Wire it into each mutating handler after successful non-dry-run execution. Identify which tool mutates which resource URIs (tool-to-URI mapping).

**Why fourth:** Requires live data to be meaningful (Phase 3). Requires knowing exactly which tools mutate which URIs — this knowledge is confirmed during Phase 3 implementation.

**Deliverable:** After any successful mutating tool call, subscribed clients receive ResourceUpdated notifications for the affected URIs.

### Phase 5: Drift Detection (depends on Phase 3 for drift report resource)

Implement `drift.py`: DriftDetector with `_check_config_drift()` and `_check_state_drift()`, DriftReport dataclass. Add schema, annotation, handler. Wire the drift report into `homelab://drift/report` fetch path in ResourceFetcher. Cache last report in a module-level variable.

**Why last:** Most complex feature. Requires SSH connectivity patterns (SSH is well-understood from Phase 1 tests) and Proxmox API integration (confirmed working in Phase 3 proxmox resource). Building after Phases 1-4 means the notification infrastructure already exists for the drift/report resource.

**Deliverable:** `scan_infrastructure_drift` runs a full config + state drift scan and returns a structured DriftReport. If subscribed, client receives ResourceUpdated on homelab://drift/report after each scan.

### Phase 6: Tech Debt Cleanup (parallel to any phase)

- Fix proxmox_session wiring in resource_manager.py (needed for Phase 5 anyway)
- Wire API key auth into HTTP transport (`auth.py`)
- Replace `str(e)` in vm_providers with structured errors

**Why any phase:** These are isolated bug fixes with no dependencies on the new features.

### Dependency Graph

```
Phase 1: Resources Plumbing ──────────────────────────────────┐
    |                                                         |
    +─── Phase 3: Resources Live Data ─── Phase 4: Notifs    |
                                               |              |
Phase 2: Dry-Run (independent)                 |              |
                                               v              |
                                     Phase 5: Drift ──────────┘
                                     (uses Phase 3 + Phase 4)

Phase 6: Tech Debt (anytime, no dependencies)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Generic Dry-Run Interceptor in server.py

**What people do:** Add a `dry_run` check in `handle_call_tool()` that short-circuits all destructive tools with a generic "would execute: {tool_name} with {args}" message.

**Why it's wrong:** The preview must be meaningful. "Would execute remove_vm with device_id=1" tells the operator nothing about disk space freed or dependent services affected. Each domain module knows its own impact surface.

**Do this instead:** Each destructive domain function has its own `dry_run` path that queries affected resources and returns a structured, human-readable preview specific to what that operation does.

### Anti-Pattern 2: Polling in Resource Subscriptions

**What people do:** Implement subscriptions as a background asyncio task that polls live state every N seconds and pushes ResourceUpdated notifications.

**Why it's wrong:** PROJECT.md explicitly defers periodic background checks. Polling adds asyncio task lifecycle complexity, may overwhelm homelab hardware, and creates noisy notifications for state that has not changed.

**Do this instead:** Subscriptions fire only when a mutating tool call completes successfully. Clients that want proactive drift detection call `scan_infrastructure_drift` on demand.

### Anti-Pattern 3: Slow Resource Reads

**What people do:** ResourceFetcher.fetch() performs SSH discovery across all devices every time a resource is read.

**Why it's wrong:** SSH discovery takes seconds per device. Resource reads are expected to be fast — clients may call them frequently for context. A slow resource read blocks the request handler.

**Do this instead:** Resources read from SQLite (devices) or existing cached/fast API responses (Proxmox). Drift detection is the slow operation and runs as a tool call, not a resource read. The `homelab://drift/report` resource returns the cached last report, which is always fast.

### Anti-Pattern 4: Expanding ResourceManager into a God Object

**What people do:** Add every new shared state (SubscriptionTracker, ResourceFetcher, drift cache, per-URI locks) as properties on ResourceManager.

**Why it's wrong:** ResourceManager's stated responsibility is connection lifecycle (aiohttp session, db adapter). Adding application-level logic blurs this boundary.

**Do this instead:** `resources.py` owns ResourceFetcher and SubscriptionTracker. ResourceManager only gains a `subscription_tracker` property because SubscriptionTracker must survive for the server lifetime (it tracks active subscriptions). ResourceFetcher is stateless and can be instantiated per-call or as a lightweight singleton in resources.py.

---

## Sources

- MCP SDK lowlevel.Server source (mcp>=1.9.1 installed): `list_resources`, `read_resource`, `subscribe_resource`, `unsubscribe_resource` decorators confirmed; `get_capabilities()` auto-sets `subscribe=True` from SubscribeRequest handler presence — HIGH confidence
- MCP SDK ServerSession source: `send_resource_updated(uri)` and `send_resource_list_changed()` confirmed — HIGH confidence
- MCP SDK lowlevel helper_types: `ReadResourceContents` return type for `read_resource` handlers confirmed — HIGH confidence
- Existing source inspection (all modules read directly): server.py, resource_manager.py, tool_handlers/, tool_annotations.py, vm_operations.py, infrastructure_crud.py — all v1.0 patterns confirmed — HIGH confidence
- PROJECT.md v1.1 milestone and out-of-scope decisions: no periodic drift, no full workflow simulation — HIGH confidence

---

*Architecture research for: Homelab MCP Server v1.1 Safety & Observability*
*Researched: 2026-03-11*
