# Phase 9: MCP Resources Live Data - Research

**Researched:** 2026-03-11
**Domain:** MCP Resources protocol wire-up with live data from Proxmox API, SQLite, and SSH service checks
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RES-02 | `homelab://vms` returns live VM list from Proxmox/Docker/LXD | `list_proxmox_resources()` with `get_resource_manager().proxmox_session` for Proxmox; `list_vms_on_device()` via SSH for Docker/LXD; results merged in `handle_read_resource` |
| RES-03 | `homelab://devices` returns device inventory with `last_seen` and `last_discovery_data` | `get_resource_manager().db_adapter.get_all_devices()` returns flat dicts; `last_seen` is a stored column; `last_discovery_data` must be fetched from `discovery_history` table as a separate join |
| RES-04 | `homelab://services/{name}` returns current service status including running state | URI is parametric (template); `handle_read_resource` must parse the name from the URI path; call `ServiceInstaller.get_service_status()` which SSH-checks docker compose status |

</phase_requirements>

---

## Summary

Phase 9 replaces the three stub payloads in `handle_read_resource` with live data calls. The scaffolding (handler registration, URI routing, error code, JSON wrapping) is entirely in place from Phase 7 — all changes in this phase happen inside `handle_read_resource` and a new helper module.

The key architectural challenge is that `handle_read_resource` is a pure async function with no arguments beyond the URI — it cannot receive `hostname` or `session` parameters directly. Live data must be sourced through two channels already wired into the server: `get_resource_manager()` (for `proxmox_session` and `db_adapter`) and `get_database_adapter()` (standalone, if needed outside the lifespan). For service status, the URI template `homelab://services/{name}` requires parsing the service name out of the URI path string before dispatching.

The `homelab://devices` requirement specifies `last_discovery_data` — a field that does NOT exist as a column in the `devices` table. It lives in `discovery_history` as the most-recent `discovery_data` JSON blob for each device. Fetching it requires a supplementary query per device (or a single query joining `discovery_history` with `devices`).

All three resources must include a `scanned_at` ISO timestamp: `datetime.utcnow().isoformat() + "Z"` injected at fetch time.

**Primary recommendation:** Add a `resource_readers.py` module with three async functions (`read_vms_resource`, `read_devices_resource`, `read_service_resource`). Dispatch in `handle_read_resource` based on URI prefix. This keeps `server.py` clean and the readers independently testable.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` (installed) | 1.9.4 | Resource handlers, `ReadResourceContents`, `McpError` | Phase 7 already wired — no changes |
| `aiohttp` (installed) | bundled | Proxmox API HTTP calls via `ResourceManager.proxmox_session` | Already the session layer in `proxmox_api.py` |
| `sqlite3` (stdlib) | stdlib | Device inventory via `DatabaseAdapter.get_all_devices()` | Already in use via `ResourceManager.db_adapter` |
| `datetime` (stdlib) | stdlib | `scanned_at` ISO timestamp | No new dependency |

### No New Installations Required

```bash
# All dependencies already present. No new packages needed.
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/homelab_mcp/
├── server.py              # MODIFY: dispatch live readers in handle_read_resource
└── resource_readers.py    # NEW: read_vms_resource, read_devices_resource, read_service_resource

tests/
├── test_mcp_resources.py  # MODIFY: update existing tests to accept live/stub toggle
└── test_resource_readers.py  # NEW: unit tests for reader functions with mocked dependencies
```

### Pattern 1: Dispatching in `handle_read_resource`

**What:** Replace stub lookup with URI-based dispatch to reader functions.
**When to use:** For all three live URIs plus unchanged error path for unknown URIs.

```python
# In server.py — replaces the stub-serving block
from .resource_readers import read_vms_resource, read_devices_resource, read_service_resource

@server.read_resource()  # type: ignore[misc]
async def handle_read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
    uri_str = str(uri)

    # Unknown URI check (RES-06, already passing)
    if not any(
        uri_str == k or uri_str.startswith("homelab://services/")
        for k in HOMELAB_RESOURCES
        if k != "homelab://services"  # services is a template
    ) and uri_str not in HOMELAB_RESOURCES and not uri_str.startswith("homelab://services/"):
        raise McpError(
            types.ErrorData(code=RESOURCE_NOT_FOUND, message="Resource not found", data={"uri": uri_str})
        )

    try:
        if uri_str == "homelab://vms":
            payload = await read_vms_resource()
        elif uri_str == "homelab://devices":
            payload = await read_devices_resource()
        elif uri_str.startswith("homelab://services/"):
            service_name = uri_str.removeprefix("homelab://services/")
            payload = await read_service_resource(service_name)
        else:
            raise McpError(
                types.ErrorData(code=RESOURCE_NOT_FOUND, message="Resource not found", data={"uri": uri_str})
            )
    except McpError:
        raise
    except Exception as e:
        logger.exception("Error reading resource %s", uri_str)
        payload = {"error": sanitize_error(e), "scanned_at": datetime.utcnow().isoformat() + "Z"}

    return [ReadResourceContents(content=json.dumps(payload), mime_type="application/json")]
```

**Critical note on `homelab://services`:** The stub entry `"homelab://services"` in `HOMELAB_RESOURCES` must be removed or kept as a fallback-only entry. Per RES-04, the live resource is `homelab://services/{name}` — a URI template. Reading the bare `homelab://services` without a name is not a defined requirement. The `HOMELAB_RESOURCES` registry is used by `handle_list_resources` to announce resources to clients; the services entry should become a template declaration. See Pattern 4 for how to handle this without breaking `list_resources`.

### Pattern 2: `read_vms_resource` (RES-02)

**What:** Fetches VM list from Proxmox via `list_proxmox_resources`, plus Docker and LXD via SSH over all known devices.
**Key insight:** Proxmox `list_proxmox_resources()` already returns `vm` and `lxc` type resources from `/cluster/resources`. Docker/LXD require an SSH connection per device — do NOT attempt to SSH all devices in a resource read (latency risk). Instead, query Proxmox API for the full cluster inventory (which includes all VMs/LXCs managed by Proxmox) and call Docker/LXD listing only if a device is known to run them.

**Recommended scope for Phase 9:** Proxmox-managed VMs via API (already has `get_resource_manager().proxmox_session`). Docker/LXD via SSH is a stretch goal — it adds latency and connection management complexity. If PROXMOX_HOST is not configured, return an empty list with a `config_error` flag rather than raising.

```python
# In resource_readers.py
import logging
from datetime import datetime, timezone
from typing import Any

from .proxmox_api import list_proxmox_resources, get_proxmox_client
from .log_filter import sanitize_error

logger = logging.getLogger(__name__)


async def read_vms_resource() -> dict[str, Any]:
    """Return live VM list from Proxmox API (and optionally Docker/LXD)."""
    from .server import get_resource_manager
    scanned_at = datetime.now(timezone.utc).isoformat()

    try:
        rm = get_resource_manager()
        result = await list_proxmox_resources(session=rm.proxmox_session)
    except RuntimeError:
        # Server lifespan not started (e.g., during testing)
        return {"vms": [], "scanned_at": scanned_at, "error": "ResourceManager not available"}
    except ValueError as e:
        # PROXMOX_HOST not configured
        return {"vms": [], "scanned_at": scanned_at, "config_error": sanitize_error(e)}
    except Exception as e:
        logger.exception("Failed to fetch VMs from Proxmox")
        return {"vms": [], "scanned_at": scanned_at, "error": sanitize_error(e)}

    vms = result.get("resources", [])
    return {
        "vms": vms,
        "total": len(vms),
        "scanned_at": scanned_at,
    }
```

### Pattern 3: `read_devices_resource` (RES-03)

**What:** Reads device inventory from SQLite via `db_adapter.get_all_devices()`. Adds `last_discovery_data` by querying `discovery_history` for the most recent record per device.

**Key insight:** `get_all_devices()` returns flat dicts with all device columns. `last_discovery_data` is NOT a column in `devices` — it must come from `discovery_history`. Use `db_adapter.get_device_changes(device_id, limit=1)` to get the latest discovery blob for each device.

```python
async def read_devices_resource() -> dict[str, Any]:
    """Return device inventory from SQLite with last_seen and last_discovery_data."""
    from .server import get_resource_manager
    scanned_at = datetime.now(timezone.utc).isoformat()

    try:
        rm = get_resource_manager()
        db = rm.db_adapter
    except RuntimeError:
        return {"devices": [], "scanned_at": scanned_at, "error": "ResourceManager not available"}

    try:
        raw_devices = db.get_all_devices()
        devices = []
        for d in raw_devices:
            device_id = d.get("id")
            last_discovery_data = None
            if device_id is not None:
                changes = db.get_device_changes(device_id, limit=1)
                if changes:
                    last_discovery_data = changes[0].get("data")
            devices.append({
                **d,
                "last_discovery_data": last_discovery_data,
            })
        return {
            "devices": devices,
            "total": len(devices),
            "scanned_at": scanned_at,
        }
    except Exception as e:
        logger.exception("Failed to fetch devices from database")
        return {"devices": [], "scanned_at": scanned_at, "error": sanitize_error(e)}
```

**Performance note:** Calling `get_device_changes(device_id, limit=1)` for each device is N+1 queries. For a homelab with ~10-50 devices this is fine. If it becomes slow in future, use `db_adapter.execute_query()` with a single `SELECT dh.device_id, dh.discovery_data FROM discovery_history dh INNER JOIN (SELECT device_id, MAX(discovered_at) as max_at FROM discovery_history GROUP BY device_id) latest ON dh.device_id = latest.device_id AND dh.discovered_at = latest.max_at` query.

### Pattern 4: `read_service_resource` (RES-04)

**What:** Parses service name from URI, calls `ServiceInstaller.get_service_status()`.
**Constraint:** `get_service_status(service_name, hostname, username)` requires a `hostname`. The URI `homelab://services/{name}` contains only the service name, not a hostname. The service name alone is insufficient to determine which host to SSH into.

**Resolution options:**
1. Query the database for devices where the service is known to be installed (no schema support for this yet)
2. Accept a "default host" from env var (e.g., `MCP_DEFAULT_SERVICE_HOST`) — simplest for Phase 9
3. If no hostname can be resolved, return `{"status": "unknown", "reason": "no_host_configured"}`

**Recommended for Phase 9:** Option 2 — read `MCP_DEFAULT_SERVICE_HOST` env var (or first device in DB). If absent, return a structured "unconfigured" response rather than an error. This keeps Phase 9 honest and avoids blocking on a schema change.

```python
async def read_service_resource(service_name: str) -> dict[str, Any]:
    """Return status of a named service via SSH."""
    import os
    from .service_installer import ServiceInstaller
    scanned_at = datetime.now(timezone.utc).isoformat()

    hostname = os.getenv("MCP_DEFAULT_SERVICE_HOST")
    if not hostname:
        # Try first device in DB as fallback
        try:
            from .server import get_resource_manager
            devices = get_resource_manager().db_adapter.get_all_devices()
            if devices:
                hostname = devices[0].get("connection_ip") or devices[0].get("hostname")
        except RuntimeError:
            pass

    if not hostname:
        return {
            "service": service_name,
            "status": "unconfigured",
            "reason": "No host available to query. Set MCP_DEFAULT_SERVICE_HOST env var.",
            "scanned_at": scanned_at,
        }

    try:
        installer = ServiceInstaller()
        status = await installer.get_service_status(service_name=service_name, hostname=hostname)
        status["scanned_at"] = scanned_at
        return status
    except Exception as e:
        logger.exception("Failed to get service status for %s on %s", service_name, hostname)
        return {
            "service": service_name,
            "status": "error",
            "hostname": hostname,
            "error": sanitize_error(e),
            "scanned_at": scanned_at,
        }
```

### Pattern 5: `homelab://services` in `HOMELAB_RESOURCES` — Template URI Handling

**Problem:** Phase 7 registered `"homelab://services"` as a concrete URI. Phase 9 requires `homelab://services/{name}` (parametric). The `handle_list_resources` and `handle_read_resource` dispatch must be updated consistently.

**Resolution:** Keep `"homelab://services"` in `HOMELAB_RESOURCES` for `list_resources` purposes (clients see it as a discoverable resource), but update `handle_read_resource` to:
- Match `homelab://services/{name}` (any `homelab://services/` prefix with non-empty path) as a live parametric read
- Match bare `homelab://services` as a legacy path that returns a helpful "specify a service name" response

This avoids breaking the `list_resources` contract while adding template support.

### Anti-Patterns to Avoid

- **SSH-querying all devices during a resource read:** Resource reads are synchronous from the client's perspective. SSH connections to all devices would introduce seconds of latency. Only query pre-indexed data (Proxmox API, SQLite) or a single targeted SSH call.
- **Raising unhandled exceptions from `read_vms_resource` etc.:** A RuntimeError when `ResourceManager` is not started (e.g., during tests) must be caught and converted to a graceful error payload. The handler must never propagate non-`McpError` exceptions unhandled.
- **Hardcoding `hostname` in `read_service_resource`:** The hostname must be configurable. Do not hardcode `"localhost"` or any IP.
- **Using `datetime.utcnow()`:** This is deprecated in Python 3.12. Use `datetime.now(timezone.utc).isoformat()` instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Proxmox VM listing | Custom Proxmox API client | `list_proxmox_resources(session=rm.proxmox_session)` in `proxmox_api.py` | Already handles auth, SSL, session reuse |
| Device DB queries | Direct SQLite calls in server.py | `rm.db_adapter.get_all_devices()` and `rm.db_adapter.get_device_changes()` | DatabaseAdapter handles both SQLite and PostgreSQL |
| Service status SSH check | Custom SSH runner | `ServiceInstaller.get_service_status()` in `service_installer.py` | Already does dir check + docker compose ps |
| ISO timestamp | `time.time()` or manual formatting | `datetime.now(timezone.utc).isoformat()` | Unambiguous UTC with timezone marker |
| URI path parsing | Regex | `str(uri).removeprefix("homelab://services/")` | Sufficient for this simple prefix pattern |

**Key insight:** All the underlying data access is already implemented. Phase 9 is purely plumbing — connecting existing data-fetch functions to the resource read path.

---

## Common Pitfalls

### Pitfall 1: `ResourceManager` Not Available Outside Lifespan

**What goes wrong:** `get_resource_manager()` raises `RuntimeError("ResourceManager not available -- server lifespan not started")` in unit tests because there is no running server lifespan.
**Why it happens:** `_resource_manager` is `None` until `app_lifespan` runs.
**How to avoid:** Reader functions must catch `RuntimeError` from `get_resource_manager()` and return a graceful error payload. Tests should mock `get_resource_manager` or test reader functions directly with injected db/session objects.
**Warning signs:** `RuntimeError: ResourceManager not available` in test logs.

### Pitfall 2: `last_discovery_data` Does Not Exist as a Column

**What goes wrong:** Reading `device["last_discovery_data"]` after `get_all_devices()` raises `KeyError`.
**Why it happens:** The `devices` table has no `last_discovery_data` column. The data lives in `discovery_history`.
**How to avoid:** Always fetch via `db.get_device_changes(device_id, limit=1)` and merge into the dict. Never assume the column exists in the base query.
**Warning signs:** `KeyError: 'last_discovery_data'` or missing field in response.

### Pitfall 3: Proxmox Not Configured in Test/Dev Environment

**What goes wrong:** `get_proxmox_client()` raises `ValueError("Proxmox host must be provided or set in PROXMOX_HOST env var")` when `PROXMOX_HOST` is not set.
**Why it happens:** `list_proxmox_resources()` calls `get_proxmox_client()` which requires env vars.
**How to avoid:** Catch `ValueError` in `read_vms_resource` and return `{"vms": [], "config_error": "...", "scanned_at": ...}`. Tests should mock `list_proxmox_resources`.
**Warning signs:** `ValueError: Proxmox host must be provided` during resource read.

### Pitfall 4: `homelab://services` URI Template vs Concrete Match

**What goes wrong:** `read_resource(AnyUrl("homelab://services/nginx"))` hits the `-32002` unknown-URI branch because `"homelab://services/nginx"` is not a key in `HOMELAB_RESOURCES`.
**Why it happens:** The registry uses exact string matching; template URIs are not registered under `"homelab://services/nginx"`.
**How to avoid:** The dispatch logic in `handle_read_resource` must check `uri_str.startswith("homelab://services/")` BEFORE checking `HOMELAB_RESOURCES` membership.
**Warning signs:** `McpError -32002` for any `homelab://services/` URI.

### Pitfall 5: N+1 Queries Per Device for `last_discovery_data`

**What goes wrong:** For a homelab with 50 devices, `read_devices_resource` executes 51 SQLite queries (1 for all devices + 1 per device for changes).
**Why it happens:** `get_device_changes()` is called in a loop.
**How to avoid:** For Phase 9 this is acceptable (homelab = small scale). Flag in comments for future optimization with a single JOIN query. If needed now, use `db_adapter.execute_query()` with the MAX/JOIN query described in Pattern 3.
**Warning signs:** Slow resource reads (>500ms) with many devices.

### Pitfall 6: `datetime.utcnow()` Deprecation Warning

**What goes wrong:** `DeprecationWarning: datetime.utcnow() is deprecated` in Python 3.12.
**Why it happens:** The method was soft-deprecated in 3.12.
**How to avoid:** Use `datetime.now(timezone.utc).isoformat()` throughout. The project has `filterwarnings = ["error"]` for some categories — check if DeprecationWarning is excluded in `pyproject.toml`.
**Warning signs:** `DeprecationWarning` in test output.

---

## Code Examples

### `scanned_at` Timestamp Pattern

```python
# Use timezone-aware UTC datetime (Python 3.12 style)
from datetime import datetime, timezone

scanned_at = datetime.now(timezone.utc).isoformat()
# Produces: "2026-03-11T15:30:00.000000+00:00"
```

### URI Template Prefix Check

```python
# In handle_read_resource dispatch
uri_str = str(uri)

if uri_str == "homelab://vms":
    payload = await read_vms_resource()
elif uri_str == "homelab://devices":
    payload = await read_devices_resource()
elif uri_str.startswith("homelab://services/"):
    # Extract service name: "homelab://services/nginx" -> "nginx"
    service_name = uri_str.removeprefix("homelab://services/")
    if not service_name:
        raise McpError(types.ErrorData(code=RESOURCE_NOT_FOUND, message="Service name required"))
    payload = await read_service_resource(service_name)
elif uri_str in HOMELAB_RESOURCES:
    # Bare homelab://services or other known URIs without live data
    payload = {"_note": "Use homelab://services/{name} for specific service status", "scanned_at": ...}
else:
    raise McpError(types.ErrorData(code=RESOURCE_NOT_FOUND, message="Resource not found", data={"uri": uri_str}))
```

### Fetching `last_discovery_data` per Device

```python
# In read_devices_resource — using existing DatabaseAdapter API
for device in raw_devices:
    device_id = device.get("id")
    last_discovery_data = None
    if device_id is not None:
        changes = db.get_device_changes(device_id, limit=1)
        if changes:
            last_discovery_data = changes[0].get("data")  # Already parsed JSON dict
    device["last_discovery_data"] = last_discovery_data
```

### Mocking `get_resource_manager` in Tests

```python
# In test_resource_readers.py
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio
async def test_read_devices_resource_returns_scanned_at(mocker):
    mock_rm = MagicMock()
    mock_rm.db_adapter.get_all_devices.return_value = [
        {"id": 1, "hostname": "server1", "connection_ip": "192.168.1.1",
         "last_seen": "2026-03-11T00:00:00", "status": "success"}
    ]
    mock_rm.db_adapter.get_device_changes.return_value = []
    mocker.patch("homelab_mcp.resource_readers.get_resource_manager", return_value=mock_rm)

    from homelab_mcp.resource_readers import read_devices_resource
    result = await read_devices_resource()

    assert "scanned_at" in result
    assert result["total"] == 1
    assert result["devices"][0]["last_discovery_data"] is None
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Stub payloads in `HOMELAB_RESOURCES["homelab://vms"]["stub"]` | Live fetch in `read_vms_resource()` | Phase 9 | Clients get current data on every `resources/read` call |
| `"homelab://services"` as concrete URI | `homelab://services/{name}` as parametric template | Phase 9 | Matches RES-04 requirement; clients must pass service name |
| No `scanned_at` field | `scanned_at` ISO timestamp in every response | Phase 9 | Clients can detect stale data and know when the scan occurred |

**After Phase 9 — Stub note fields to remove:**
- `"_note": "stub - Phase 9 wires live data"` in the three `HOMELAB_RESOURCES` entries

---

## Open Questions

1. **Docker/LXD SSH listing scope for RES-02**
   - What we know: RES-02 says "Proxmox/Docker/LXD providers". `list_proxmox_resources` fetches Proxmox VMs and LXC containers from the Proxmox API. Docker containers running outside Proxmox (direct Docker on a host) require SSH + `list_vms_on_device()`.
   - What's unclear: Whether the planner should include SSH-based Docker listing in the first wave or defer it.
   - Recommendation: Include Proxmox API (which covers Proxmox-managed LXC/qemu) in Wave 1. SSH Docker/LXD listing can be Wave 2 if time allows. The requirement says "from all managed hosts" — Proxmox-managed hosts satisfy this for most homelabs. Document the limitation in the response payload as `"providers": ["proxmox"]`.

2. **`homelab://services/{name}` in `resources/list`**
   - What we know: The MCP spec supports URI templates (`uriTemplate` field on `Resource`). The installed SDK (1.9.4) `types.Resource` does NOT have a `uriTemplate` field — it has `uri` only (verified from Phase 7 research). Advertising a URI template requires the MCP `resourceTemplates` capability, which mcp 1.9.4 may not support.
   - What's unclear: Whether clients can discover `homelab://services/{name}` without a template entry.
   - Recommendation: Keep the concrete `"homelab://services"` entry in `HOMELAB_RESOURCES` as a discoverable anchor. Phase 9 does not need to solve template advertisement — RES-04 only requires that `resources/read` on `homelab://services/{name}` returns live data.

3. **`MCP_DEFAULT_SERVICE_HOST` vs DB-first approach**
   - What we know: `get_service_status()` requires a `hostname`. No standard way exists to go from service name to host without a service-to-host mapping in the DB.
   - What's unclear: Whether users will configure `MCP_DEFAULT_SERVICE_HOST`.
   - Recommendation: Implement DB-first (first online device from `get_all_devices()`) with `MCP_DEFAULT_SERVICE_HOST` as an override. Log a warning if fallback is used. This is the most ergonomic behavior for homelab users with a single server.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_resource_readers.py -x -v` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RES-02 | `read_vms_resource()` returns `{"vms": [...], "scanned_at": "..."}` with mocked Proxmox | unit | `uv run pytest tests/test_resource_readers.py::test_read_vms_resource_returns_scanned_at -x` | Wave 0 |
| RES-02 | `read_vms_resource()` returns graceful error when PROXMOX_HOST not set | unit | `uv run pytest tests/test_resource_readers.py::test_read_vms_resource_no_proxmox_config -x` | Wave 0 |
| RES-02 | `handle_read_resource("homelab://vms")` returns JSON with `scanned_at` field | unit | `uv run pytest tests/test_mcp_resources.py::test_read_vms_resource_has_scanned_at -x` | Wave 0 |
| RES-03 | `read_devices_resource()` returns devices with `last_seen` and `last_discovery_data` fields | unit | `uv run pytest tests/test_resource_readers.py::test_read_devices_resource_includes_last_discovery_data -x` | Wave 0 |
| RES-03 | `read_devices_resource()` returns `scanned_at` in response | unit | `uv run pytest tests/test_resource_readers.py::test_read_devices_resource_returns_scanned_at -x` | Wave 0 |
| RES-03 | `handle_read_resource("homelab://devices")` returns live device JSON | unit | `uv run pytest tests/test_mcp_resources.py::test_read_devices_resource_has_scanned_at -x` | Wave 0 |
| RES-04 | `read_service_resource("nginx")` returns status dict with `scanned_at` | unit | `uv run pytest tests/test_resource_readers.py::test_read_service_resource_returns_status -x` | Wave 0 |
| RES-04 | `handle_read_resource("homelab://services/nginx")` dispatches to service reader | unit | `uv run pytest tests/test_mcp_resources.py::test_read_services_template_uri -x` | Wave 0 |
| RES-04 | Unknown `homelab://services/` with empty name returns -32002 | unit | `uv run pytest tests/test_mcp_resources.py::test_read_services_empty_name_error -x` | Wave 0 |
| ALL | All three resources include `scanned_at` ISO timestamp | unit | `uv run pytest tests/test_resource_readers.py -k scanned_at -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_resource_readers.py tests/test_mcp_resources.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_resource_readers.py` — new file covering all three reader functions with mocked dependencies
- [ ] `src/homelab_mcp/resource_readers.py` — new module (created in Wave 1, not Wave 0, but test stubs/fixtures needed first)
- [ ] Add `test_read_vms_resource_has_scanned_at`, `test_read_devices_resource_has_scanned_at`, `test_read_services_template_uri` to existing `tests/test_mcp_resources.py`

---

## Sources

### Primary (HIGH confidence)

- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/server.py` — confirmed stub structure in `HOMELAB_RESOURCES`, existing `handle_read_resource` dispatch, `get_resource_manager()` accessor
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/resource_manager.py` — `proxmox_session` and `db_adapter` properties, lifecycle management
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/database.py` — `get_all_devices()` returns flat dicts with `last_seen` column; `get_device_changes(device_id, limit)` returns `[{"data": {...}, "discovered_at": "..."}]`; no `last_discovery_data` column exists
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/proxmox_api.py` — `list_proxmox_resources(host, resource_type, session)` fetches `/cluster/resources`; raises `ValueError` when PROXMOX_HOST not configured
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/service_installer.py` — `get_service_status(service_name, hostname, username, password)` requires a hostname; checks `/opt/{name}` dir, runs `docker compose ps`
- `/home/shaun/projects/mcp_python_server/.planning/phases/07-mcp-resources-plumbing/07-RESEARCH.md` — Phase 7 findings on SDK patterns, `AnyUrl` stringification, `ReadResourceContents` usage
- `/home/shaun/projects/mcp_python_server/tests/test_mcp_resources.py` — existing Phase 7 tests confirm AnyUrl stringification behavior and stub content shape

### Secondary (MEDIUM confidence)

- `.planning/REQUIREMENTS.md` lines 37-39 — exact requirement text for RES-02/03/04 defining success criteria

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already installed and in use; no new packages
- Architecture: HIGH — all data access paths traced to existing working code; patterns derived from existing handler implementations
- Pitfalls: HIGH — all pitfalls derived from direct code inspection (missing column, missing env var, URI template mismatch)
- `last_discovery_data` sourcing: HIGH — confirmed by reading both `database.py` schema (no column) and `get_device_changes()` return shape (has `data` key)
- Service hostname problem: HIGH — `get_service_status()` signature read directly; no hostname inference exists in current code

**Research date:** 2026-03-11
**Valid until:** 2026-06-11 (depends on mcp 1.9.4 and existing module APIs; re-verify if either changes)
