# Stack Research — v1.1 Safety & Observability

**Domain:** Safety & observability additions to an existing Python MCP server
**Researched:** 2026-03-11
**Confidence:** HIGH overall (most decisions use already-installed dependencies; no new heavy libraries required)

---

## Scope

This is a **delta research document** for v1.1. The existing stack (Python 3.12+, uv, mcp[cli] 1.9.4, asyncssh, aiohttp, SQLite, lowlevel.Server) is validated and not re-researched here. This covers only what is **added or changed** to implement:

1. Dry-run preview for destructive operations
2. Infrastructure drift detection (config drift + state drift)
3. MCP Resources with subscriptions
4. Tech debt cleanup (proxmox_session wiring, API key auth, vm_providers errors)

---

## Recommended Stack Additions

### No New Runtime Dependencies Required

All three feature areas can be implemented with the current dependency set. The analysis below explains why.

---

## Feature Area 1: Dry-Run Preview

### Approach: Native Python pattern, no library needed

**Confidence: HIGH**

Dry-run for destructive operations is a structural pattern, not a library problem. The project already has:

- `destructiveHint=True` annotations on the 6 destructive tools in `tool_annotations.py`
- A `validate_only` parameter precedent in `infrastructure_crud.py` (`deploy_infrastructure_plan`)

The right pattern for this codebase is a `dry_run: bool` parameter on each destructive tool handler that:

1. Introspects what the operation **would** do (reads state, resolves targets)
2. Returns a structured preview dict instead of executing
3. Never calls the mutating operation

**Why not a dry-run library (drypy, dryable)?**

Both `drypy` and `dryable` are minimal libraries (<200 lines) that intercept calls with a global flag and log them. They assume you can skip the entire function body on dry-run. For this server, dry-run needs to **return a rich preview** (which VMs would be stopped, what IDs, current state), not just log "would have called delete_vm(42)". A library decorator that silences calls is actively harmful — it would return `None` instead of the preview. Custom per-handler logic is the correct approach.

**Pattern:**

```python
# In each destructive tool handler:
async def handle_delete_proxmox_vm(vmid: int, node: str, dry_run: bool = False) -> dict:
    # Always resolve — never skip this:
    vm_info = await proxmox_api.get_vm_status(node, vmid)

    if dry_run:
        return {
            "status": "dry_run",
            "would_delete": {"vmid": vmid, "node": node, "name": vm_info["name"], "status": vm_info["status"]},
            "warning": "This action is irreversible. Re-run with dry_run=False to execute."
        }

    # Actually execute:
    return await proxmox_api.delete_vm(node, vmid)
```

**Tool schema addition** — each destructive tool gets a new `dry_run` boolean property in its `inputSchema`:

```json
"dry_run": {
    "type": "boolean",
    "description": "If true, show what would happen without executing. Default false.",
    "default": false
}
```

**No new dependencies.** No version bumps needed.

---

## Feature Area 2: Drift Detection

### Approach: deepdiff for comparison, stdlib dataclasses for models

**Confidence: HIGH for deepdiff; HIGH for stdlib dataclasses**

Drift detection requires comparing two snapshots of infrastructure state: "what MCP last recorded" (stored in SQLite) vs "what is actually running now" (queried from Proxmox API / SSH).

#### deepdiff — for structural comparison

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| deepdiff | 8.6.1 (latest) | Compare expected vs actual infrastructure state | Handles nested dicts/lists that characterize infrastructure state responses. `ignore_order=True` is essential for list comparison (interface lists, tag lists). Returns structured diff objects that serialize cleanly to JSON. Already handles the "exclude transient fields" use case via `exclude_paths`. |

**Confidence: HIGH** — verified via PyPI (released September 3, 2025). Requires Python 3.9+. Compatible with Python 3.12.

**Why not manual comparison?** Infrastructure state is deeply nested (Proxmox VM status has 30+ fields; network interfaces are lists). Hand-rolling deep comparison for every field type is error-prone and verbose. deepdiff handles this correctly in 10 lines.

**Why not jsondiff or dictdiffer?** deepdiff is the most actively maintained with 8.x releases through 2025. jsondiff (last release 2022) and dictdiffer (last release 2019) are effectively unmaintained.

**Installation:**

```bash
# Add to pyproject.toml [project.dependencies]:
uv add deepdiff
```

**Typical usage pattern for this project:**

```python
from deepdiff import DeepDiff

def compute_drift(expected: dict, actual: dict) -> dict:
    """Compare expected (stored) vs actual (live) infrastructure state."""
    diff = DeepDiff(
        expected,
        actual,
        ignore_order=True,
        exclude_paths=[
            "root['uptime']",       # Transient, always changes
            "root['cpu_usage']",    # Telemetry, not config
            "root['last_seen']",    # Tracking timestamp
        ]
    )
    return {
        "has_drift": bool(diff),
        "changes": diff.to_dict() if diff else {},
    }
```

#### Data models — stdlib dataclasses, no Pydantic needed

Drift scan results are internal data structures serialized to JSON for tool responses. Python 3.12 `dataclasses` with `__post_init__` validation is sufficient. Pydantic is a transitive dependency but adding it as a **direct** dependency for drift models is overengineering for this use case.

**Drift report structure:**

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class DriftItem:
    resource_type: str   # "vm", "lxc", "device", "service"
    resource_id: str     # vmid, device hostname, service name
    drift_type: str      # "config_drift" | "state_drift"
    expected: dict
    actual: dict
    changes: dict        # deepdiff output
    severity: str        # "critical" | "warning" | "info"

@dataclass
class DriftReport:
    scanned_at: datetime
    resources_checked: int
    drift_items: list[DriftItem] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return len(self.drift_items) > 0
```

**No new dependencies beyond deepdiff.** SQLite already stores device/VM state snapshots.

#### What triggers drift detection

- **Config drift**: Compare Proxmox VM config (cores, memory, network) stored in SQLite after last MCP operation vs current Proxmox API response
- **State drift**: Compare expected VM/service status ("running" after `start_vm`) vs current Proxmox task status

Both use the same deepdiff comparison pattern. The `on-demand scan` tool queries all tracked resources via existing Proxmox API client and SSH connections, then diffs each against stored baselines.

---

## Feature Area 3: MCP Resources with Subscriptions

### Approach: mcp[cli] lowlevel.Server built-in handlers (already installed)

**Confidence: HIGH** for Resources API; **MEDIUM** for subscription implementation details

The project already uses `mcp[cli] 1.9.4` with `lowlevel.Server`. The SDK includes built-in support for Resources via the same decorator pattern already in use for tools.

#### MCP SDK resource capability (verified against MCP spec and PyPI 1.26.0 docs)

The MCP protocol defines a full resource lifecycle:

- `resources/list` — client discovers available resources
- `resources/read` — client fetches a resource by URI
- `resources/subscribe` — client subscribes to change notifications for a URI
- `notifications/resources/updated` — server notifies subscribed client of change
- `notifications/resources/list_changed` — server notifies when resource list changes

Server capability declaration (required):

```json
{
  "capabilities": {
    "resources": {
      "subscribe": true,
      "listChanged": true
    }
  }
}
```

#### lowlevel.Server handler registration

```python
@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri=AnyUrl("homelab://vms"),
            name="VM List",
            description="Live list of all VMs and containers across Proxmox nodes",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AnyUrl("homelab://devices"),
            name="Device Inventory",
            description="All discovered devices in the network sitemap",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AnyUrl("homelab://services"),
            name="Service Status",
            description="Installed service health across managed hosts",
            mimeType="application/json",
        ),
    ]

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    uri_str = str(uri)
    if uri_str == "homelab://vms":
        rm = get_resource_manager()
        vms = await proxmox_api.list_all_vms(rm.proxmox_session)
        return json.dumps(vms)
    ...
```

**Confidence: HIGH** — `list_resources` and `read_resource` decorators are confirmed in official API reference (https://anish-natekar.github.io/mcp_docs/api-reference.html) and consistent with the existing `list_tools` / `call_tool` pattern already shipping in `server.py`.

#### Subscription implementation

The `subscribe_resource` decorator and `send_resource_updated` notification are present in the SDK (`ServerSession.send_resource_updated` is confirmed in the API reference). The exact integration with lowlevel.Server requires verification against the installed SDK source.

**Required investigation before implementation** (Phase-specific research flag):

1. Verify `@server.subscribe_resource()` decorator exists in mcp 1.9.4 (check `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py`)
2. Verify how to call `server.request_context.session.send_resource_updated(uri)` or equivalent from within a background notification task
3. Understand whether capability flags (`subscribe: true`) are auto-detected from registered handlers or must be manually declared in `Server()` constructor

**Subscription tracking — stdlib asyncio, no library needed:**

The subscription registry is a simple in-memory dict mapping URI strings to sets of subscriber identifiers. For a single-user homelab server (one MCP client at a time), this is trivially simple:

```python
# In resource_manager.py or a new resources.py module:
_subscriptions: dict[str, set[str]] = {}  # uri -> set of session_ids

def add_subscription(uri: str, session_id: str) -> None:
    _subscriptions.setdefault(uri, set()).add(session_id)

def remove_subscription(uri: str, session_id: str) -> None:
    _subscriptions.get(uri, set()).discard(session_id)

def has_subscribers(uri: str) -> bool:
    return bool(_subscriptions.get(uri))
```

**No asyncio pub/sub library needed.** Libraries like `asyncio-multisubscriber-queue` solve the multi-producer/multi-consumer broadcast problem. This server has one producer (the MCP server process) and one subscriber (the connected MCP client). A plain dict + direct notification call is correct.

**Notification trigger** — subscriptions are passive (notify on read-resource cache miss or explicit tool call). The v1.1 scope explicitly defers "auto-detect drift with periodic background checks." Notifications are sent when:

1. A destructive tool completes → `notifications/resources/updated` for affected resource URIs
2. An on-demand drift scan detects changes → `notifications/resources/updated` for drifted resources

This means notification sends happen synchronously within existing tool handlers, not from a background task. No asyncio background tasks, no polling loops.

#### Resource URIs for this project

| URI | Content | MimeType |
|-----|---------|----------|
| `homelab://vms` | All Proxmox VMs/LXCs with status | `application/json` |
| `homelab://devices` | Network sitemap device inventory | `application/json` |
| `homelab://services` | Service health across managed hosts | `application/json` |
| `homelab://drift/{scan_id}` | Drift scan results (templated) | `application/json` |

Custom URI scheme `homelab://` is valid per MCP spec (RFC 3986 compliant, custom schemes allowed). Prefer this over `file://` since these are not filesystem resources.

---

## Feature Area 4: Tech Debt Cleanup

### proxmox_session wiring

**No new dependencies.** The fix is passing `get_resource_manager().proxmox_session` into `ProxmoxAPIClient` at handler call time, replacing per-request session creation. Already wired in `ResourceManager.proxmox_session` — the bug is that handlers call `ProxmoxAPIClient()` directly and create their own sessions. Fix: inject the pooled session.

### API key authentication

**No new dependencies.** The `auth.py` module already exists. The fix connects the existing `APIKeyMiddleware` (in `http_app.py`) to actually reject unauthenticated requests when `MCP_API_KEY` is set. This is configuration wiring, not a library gap.

### vm_providers error handling

**No new dependencies.** Replace `str(e)` patterns with `sanitize_error()` from `log_filter.py` (already used in `infrastructure_crud.py`). Pure code cleanup.

---

## Summary: Dependencies Delta

| Package | Action | Version | Rationale |
|---------|--------|---------|-----------|
| `deepdiff` | **ADD** | `>=8.0.0` | Drift comparison engine. Current: 8.6.1. No alternative avoids verbose manual deep comparison. |
| Everything else | No change | — | All other v1.1 features are implementable with the current stack. |

**What NOT to add:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `drypy` / `dryable` | Returns None on dry-run; can't return rich preview | Per-handler `dry_run: bool` parameter |
| `asyncio-multisubscriber-queue` | Multi-subscriber broadcast for single-client server is overengineering | `dict[str, set[str]]` subscription registry |
| `apscheduler` / `aiocron` | Periodic background drift checks are explicitly out of scope for v1.1 | On-demand scan tool only |
| `jsondiff` / `dictdiffer` | Unmaintained (2019-2022); no Python 3.12 validation | deepdiff 8.x |
| `pydantic` (as direct dep) | Already transitive; overkill for internal drift models | stdlib dataclasses |
| Redis / message queue | Single-user homelab has one subscriber; no fan-out needed | In-memory dict |

---

## Version Compatibility

| Package | Requires | Compatible With | Notes |
|---------|---------|-----------------|-------|
| deepdiff 8.6.1 | Python 3.9+ | Python 3.12 ✓ | No conflicts with existing deps |
| mcp[cli] 1.9.4 | — | Resources API confirmed present | subscribe_resource decorator needs verification in installed version |

---

## Installation

```bash
# Add deepdiff to pyproject.toml [project.dependencies], then:
uv add deepdiff

# Verify: should show deepdiff 8.x
uv run python -c "import deepdiff; print(deepdiff.__version__)"
```

---

## Phase-Specific Research Flags

| Phase | What Needs Verification | How to Verify |
|-------|------------------------|---------------|
| MCP Resources | `@server.subscribe_resource()` decorator availability in mcp 1.9.4 | `grep -r "subscribe_resource" .venv/lib/python3.12/site-packages/mcp/` |
| MCP Resources | How to send `resource_updated` notification from within tool handler (session reference) | Read `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` directly |
| MCP Resources | Capability flag declaration — auto-detected or manual in `Server()` constructor | Same source inspection |
| Drift Detection | SQLite schema for baseline snapshots (what columns exist, what to add) | Read `src/homelab_mcp/database.py` and migration system |

---

## Sources

- PyPI `mcp` package page — version 1.26.0 (latest), confirmed subscribe/listChanged capabilities exist; v1.9.4 is installed in this project (verified from uv.lock)
- PyPI `deepdiff` package page — version 8.6.1, released September 3, 2025; Python 3.9+ requirement confirmed
- MCP spec resources documentation (https://modelcontextprotocol.io/docs/concepts/resources) — subscribe/listChanged capability JSON structure, protocol messages, notification flow verified
- MCP API reference (https://anish-natekar.github.io/mcp_docs/api-reference.html) — `list_resources()`, `read_resource()` decorator signatures confirmed; `send_resource_updated`, `send_resource_list_changed` confirmed on ServerSession
- Project source inspection: `src/homelab_mcp/server.py`, `src/homelab_mcp/resource_manager.py`, `src/homelab_mcp/tool_annotations.py`, `src/homelab_mcp/infrastructure_crud.py`, `pyproject.toml`, `uv.lock`
- deepdiff GitHub (https://github.com/seperman/deepdiff) — active maintenance, 8.x series through 2025
- `drypy` (https://github.com/dzanotelli/drypy) and `dryable` (https://github.com/haarcuba/dryable) — evaluated and rejected; confirmed via search

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Dry-run pattern (no library) | HIGH | Pattern already present in codebase (`validate_only`); decorator libraries confirmed unsuitable |
| deepdiff selection | HIGH | Version verified via PyPI; no competing maintained alternatives |
| MCP Resources list/read | HIGH | Decorator pattern confirmed in API reference, consistent with existing `list_tools` usage |
| MCP Resources subscriptions | MEDIUM | Protocol spec confirmed; Python SDK subscribe decorator and notification send API needs source verification in installed 1.9.4 |
| Subscription registry (stdlib) | HIGH | Single-client server; fan-out complexity not needed |
| Tech debt fixes (no new deps) | HIGH | All are wiring/pattern fixes in existing modules |

---

*Stack research for: Homelab MCP Server v1.1 Safety & Observability*
*Researched: 2026-03-11*
