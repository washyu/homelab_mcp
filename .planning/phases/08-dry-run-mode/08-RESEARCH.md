# Phase 08: Dry-Run Mode - Research

**Researched:** 2026-03-11
**Domain:** Python tool parameter extension, handler layer interception, structured response contracts
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DRY-01 | User can pass `dry_run: true` to `decommission_device` and see what would be affected | `decommission_network_device` already has a `validate_only` path — wire `dry_run` to build structured preview from existing `_analyze_device_dependencies` result |
| DRY-02 | User can pass `dry_run: true` to `remove_vm` and see what would be affected | `remove_vm` in `vm_operations.py` has no preview path; handler must short-circuit before SSH call using device lookup result |
| DRY-03 | User can pass `dry_run: true` to `remove_server` and see what would be affected | `remove_server` is a **sync** function in `ssh_tools.py` that queries `db.get_credential` before deleting — handler can preview from that read step |
| DRY-04 | User can pass `dry_run: true` to `delete_proxmox_vm` and see what would be affected | `delete_proxmox_vm` calls Proxmox API; handler must short-circuit before `client.delete()` by calling `get_proxmox_vm_status` for preview data |
| DRY-05 | User can pass `dry_run: true` to `destroy_terraform_service` and see what would be affected | `ServiceInstaller.destroy_terraform_service` runs `terraform destroy`; handler short-circuits before that SSH command, reuses `plan_terraform_service` logic |
| DRY-06 | User can pass `dry_run: true` to `rollback_infrastructure_changes` and see what would be affected | `rollback_infrastructure_to_backup` already has a `validate_only` path — wire `dry_run` to use that existing branch |
| DRY-07 | All dry-run responses return structured JSON with `mode`, `would_affect`, `risk_level`, and `reversible` fields | Implemented as a shared helper that wraps tool-specific preview data into the contract shape |
</phase_requirements>

---

## Summary

Phase 8 adds a `dry_run: bool` parameter to six destructive tools. When `dry_run=True`, the tool returns a structured preview describing what would be deleted or modified without performing any mutation. When `dry_run=False` (or absent), the tool executes normally.

The six tools span three modules and three different implementation styles. Two already have a `validate_only` path (`decommission_network_device`, `rollback_infrastructure_to_backup`). The remaining four require new preview logic inserted at the handler layer. All six share a common response contract defined by DRY-07.

The correct implementation strategy is: add `dry_run` to each tool's JSON schema, intercept in the handler function, call read-only checks to gather preview data, then format and return the contract-shaped response. No existing business logic should be modified — the dry-run path is strictly additive.

**Primary recommendation:** Add `dry_run` interception at the handler layer (`tool_handlers/`), not in the underlying business modules. This keeps the mutation-free guarantee clear, avoids altering existing function signatures, and enables straightforward testing.

---

## Standard Stack

No new libraries are required. All work is pure Python within the existing project stack.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12+ | Language | Project baseline |
| pytest | existing | Unit tests | Project test framework |
| pytest-asyncio | existing | Async test support | Required for async handlers |
| unittest.mock | stdlib | Mocking dependencies | Used throughout existing test suite |

### Supporting
| Component | Location | Purpose |
|-----------|----------|---------|
| `tool_schemas/` | `src/homelab_mcp/tool_schemas/` | JSON schema definitions for tool parameters |
| `tool_handlers/` | `src/homelab_mcp/tool_handlers/` | Handler functions — primary extension point |
| `tool_annotations.py` | `src/homelab_mcp/tool_annotations.py` | Already marks the six tools as `destructiveHint=True` |

**Installation:** None required.

---

## Architecture Patterns

### How the Six Tools Are Structured

Each destructive tool follows the same three-layer pattern:

```
tool_schemas/X_tools_schema.py   — JSON schema (inputSchema dict)
     |
tool_handlers/X_handlers.py      — handle_X() function, passes args to module
     |
src/homelab_mcp/X.py             — business logic (SSH, API calls, DB mutations)
```

The handler layer is the correct place to intercept `dry_run`. It has access to `arguments` before any mutation begins.

### Recommended Project Structure Addition

No new directories needed. Add:
- `dry_run.py` — shared helper module with the response builder function
- Schema edits: `infrastructure_tools_schema.py`, `vm_tools_schema.py`, `proxmox_tools_schema.py`, `credential_tools_schema.py`, `service_tools_schema.py`
- Handler edits: `infrastructure_handlers.py`, `vm_handlers.py`, `proxmox_handlers.py`, `credential_handlers.py`, `service_handlers.py`
- Test file: `tests/test_dry_run.py`

### Pattern 1: Shared Response Contract Builder

Create `src/homelab_mcp/dry_run.py` with a single function:

```python
# src/homelab_mcp/dry_run.py
from typing import Any

def build_dry_run_response(
    tool_name: str,
    would_affect: list[dict[str, Any]],
    risk_level: str,      # "high" | "medium" | "low"
    reversible: bool,
    preview_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard dry-run response contract (DRY-07)."""
    response: dict[str, Any] = {
        "mode": "dry_run",
        "tool": tool_name,
        "would_affect": would_affect,
        "risk_level": risk_level,
        "reversible": reversible,
    }
    if preview_details:
        response["preview"] = preview_details
    return response
```

### Pattern 2: Handler Interception (No SSH/API Call)

For tools with no existing preview path (`remove_vm`, `remove_server`, `delete_proxmox_vm`, `destroy_terraform_service`):

```python
# Example: handle_remove_vm in vm_handlers.py
async def handle_remove_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle remove_vm tool."""
    import json
    from ..dry_run import build_dry_run_response

    if arguments.get("dry_run", False):
        # Gather preview data without connecting to SSH
        manager = VMManager()
        connection_info = await manager.get_device_connection_info(arguments["device_id"])
        if not connection_info:
            preview = {"error": f"Device {arguments['device_id']} not found"}
            would_affect = []
        else:
            would_affect = [
                {
                    "resource_type": "vm",
                    "name": arguments["vm_name"],
                    "platform": arguments["platform"],
                    "device_id": arguments["device_id"],
                    "host": connection_info["hostname"],
                }
            ]
        result = build_dry_run_response(
            tool_name="remove_vm",
            would_affect=would_affect,
            risk_level="high",
            reversible=False,
        )
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Normal execution unchanged
    result = await remove_vm(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
        force=arguments.get("force", False),
    )
    return {"content": [{"type": "text", "text": result}]}
```

### Pattern 3: Reuse Existing validate_only Path

`decommission_network_device` and `rollback_infrastructure_to_backup` both have an existing `validate_only` code path. Wire `dry_run` through these, then reformat the response to the contract shape:

```python
# Example: handle_decommission_device in infrastructure_handlers.py
async def handle_decommission_device(arguments: dict[str, Any]) -> dict[str, Any]:
    import json
    from ..dry_run import build_dry_run_response

    if arguments.get("dry_run", False):
        # Call existing validate_only path to get dependency analysis
        raw = await decommission_network_device(
            device_id=arguments["device_id"],
            migration_plan=arguments.get("migration_plan"),
            force_removal=arguments.get("force_removal", False),
            validate_only=True,
        )
        raw_data = json.loads(raw)
        dependencies = raw_data.get("dependencies", {})
        critical = dependencies.get("critical_services", [])
        would_affect = [
            {"resource_type": "device", "device_id": arguments["device_id"]},
        ] + [
            {"resource_type": "service", "name": svc} for svc in critical
        ]
        result = build_dry_run_response(
            tool_name="decommission_device",
            would_affect=would_affect,
            risk_level="high",
            reversible=False,
            preview_details=raw_data,
        )
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Normal execution unchanged
    result = await decommission_network_device(...)
    return {"content": [{"type": "text", "text": result}]}
```

### Pattern 4: Schema Extension

Add `dry_run` to each of the six tools' `inputSchema.properties`. Never add to `required`:

```python
"dry_run": {
    "type": "boolean",
    "default": False,
    "description": "If true, return a preview of what would be affected without executing any changes.",
},
```

### Anti-Patterns to Avoid

- **Modifying underlying business functions:** Do not add `dry_run` params to `decommission_network_device`, `remove_vm`, etc. The handler intercepts first. Adding it to the business layer duplicates logic and risks conditional mutation bugs.
- **Returning HTTP 200 with no data for dry_run=True:** The response must include all four required fields (`mode`, `would_affect`, `risk_level`, `reversible`) — always.
- **Making mutation calls then returning early:** The handler must branch BEFORE any mutating call. Reading state (getting device info, querying DB) is fine in the dry-run path.
- **Silently treating missing `dry_run` as True:** Default must be `False`. Absence of the flag means execute normally.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Risk classification | Custom risk scoring engine | Hardcode per-tool (`high` for all six) | All six tools are explicitly `destructiveHint=True` — they are unconditionally high-risk |
| Preview state capture | Mock execution engine | Read-only pre-flight checks (device lookup, DB query, Proxmox GET) | Sufficient to describe what would be affected without simulating execution |
| Response serialization | Custom encoder | `json.dumps(result, indent=2)` | Existing pattern across all handlers |

**Key insight:** Dry-run for destructive infra tools does not require simulating execution. It requires gathering the same pre-flight information the real operation would gather (resource lookups), then stopping. The preview describes the target resource, not a simulation of all side effects.

---

## Common Pitfalls

### Pitfall 1: `remove_server` is synchronous

**What goes wrong:** `remove_server` in `ssh_tools.py` is a plain `def`, not `async def`. The handler calls it as `result = remove_server(**arguments)` (no `await`). Dry-run preview also needs to call `db.get_credential` — this is synchronous too.

**Why it happens:** `remove_server` only does DB operations (no SSH), so it was written synchronously.

**How to avoid:** In `handle_remove_server`, call `db.get_credential` (or `db.get_credential_by_hostname`) synchronously in the dry-run branch. Do not try to `await` anything here.

**Warning signs:** If a test raises `RuntimeWarning: coroutine was never awaited`, you tried to await a sync function.

### Pitfall 2: `delete_proxmox_vm` stops the VM before deleting

**What goes wrong:** The real `delete_proxmox_vm` calls `manage_proxmox_vm(... "stop" ...)` before the DELETE. A dry-run that blindly calls into the real function would stop the running VM.

**Why it happens:** The stop-then-delete sequence is embedded in the business function, not the handler.

**How to avoid:** The handler intercepts at the handler layer and calls `get_proxmox_vm_status` to gather preview data, never touching `delete_proxmox_vm`. The stop action is never reached.

### Pitfall 3: `destroy_terraform_service` calls `plan_terraform_service` internally

**What goes wrong:** The preview for `destroy_terraform_service` is naturally served by running `terraform plan` (destroy plan). However, `plan_terraform_service` requires the service to already exist at `/opt/terraform/{service_name}`. If the directory is missing, the plan fails with an error, which is the same condition the real destroy would hit.

**Why it happens:** Both plan and destroy check `test -d {tf_dir}`.

**How to avoid:** In the dry-run handler for `destroy_terraform_service`, call `installer.plan_terraform_service(...)` with the same arguments. The plan output serves as the preview. If the plan itself errors, surface that in the `preview` field of the dry-run response.

### Pitfall 4: `would_affect` must be a list, not a dict

**What goes wrong:** DRY-07 requires `would_affect` to be a **list** of affected resources. Returning a nested object instead of a list of resource descriptors fails the contract.

**Why it happens:** Confusion between "preview details" (free-form) and the required `would_affect` shape (list).

**How to avoid:** `would_affect` is always `list[dict[str, Any]]`. Each item should have at minimum a `resource_type` and an identifying field (`name`, `device_id`, `vmid`, etc.). Additional context goes in `preview_details`.

### Pitfall 5: Schema `default` vs handler default

**What goes wrong:** Setting `"default": false` in the JSON schema does not automatically pass `False` to the handler — MCP clients may or may not send the field. Always use `arguments.get("dry_run", False)` in handlers, not `arguments["dry_run"]`.

**Why it happens:** JSON Schema `default` is documentation only in this MCP implementation.

**How to avoid:** All six handlers must use `.get("dry_run", False)`.

---

## Code Examples

Verified patterns from existing codebase:

### Existing Handler Pattern (to follow)
```python
# From proxmox_handlers.py — the pattern all handlers follow
async def handle_delete_proxmox_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)
    result = await delete_proxmox_vm(
        node=arguments["node"],
        vmid=arguments["vmid"],
        host=arguments.get("host"),
        vm_type=arguments.get("vm_type", "qemu"),
        purge=arguments.get("purge", False),
        session=get_resource_manager().proxmox_session,
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

### Existing `validate_only` Pattern in `decommission_network_device`
```python
# From infrastructure_crud.py lines 259-268
if validate_only:
    return json.dumps({
        "status": "success",
        "message": "Decommission plan validated",
        "dependencies": dependencies,
        "migration_required": len(dependencies["critical_services"]) > 0,
        "estimated_migration_time": "30-60 minutes" if migration_plan else "N/A",
    })
```

### Existing Test Pattern (mock approach)
```python
# From test_vm_operations.py — how tests mock SSH/VM providers
@patch("src.homelab_mcp.vm_operations.VMManager")
@patch("src.homelab_mcp.vm_operations.get_vm_provider")
@patch("src.homelab_mcp.vm_operations.ssh_connect", new_callable=AsyncMock)
async def test_remove_vm_success(self, mock_connect, mock_get_provider, mock_manager_class):
    mock_manager = MagicMock()
    mock_manager.get_device_connection_info = AsyncMock(return_value={...})
    mock_manager_class.return_value = mock_manager
    # ...
```

---

## Tool-by-Tool Implementation Map

| Tool | Module | Handler File | Dry-Run Strategy | `risk_level` | `reversible` |
|------|--------|--------------|-----------------|--------------|-------------|
| `decommission_device` | `infrastructure_crud.py` | `infrastructure_handlers.py` | Reuse `validate_only=True` path; reformat output | `"high"` | `False` |
| `remove_vm` | `vm_operations.py` | `vm_handlers.py` | Device lookup only; no SSH | `"high"` | `False` |
| `remove_server` | `ssh_tools.py` | `credential_handlers.py` | DB credential lookup (sync); no delete | `"medium"` | `False` (DB row gone) |
| `delete_proxmox_vm` | `proxmox_api.py` | `proxmox_handlers.py` | Call `get_proxmox_vm_status` via API | `"high"` | `False` |
| `destroy_terraform_service` | `service_installer.py` | `service_handlers.py` | Call `installer.plan_terraform_service()` | `"high"` | `False` |
| `rollback_infrastructure_changes` | `infrastructure_crud.py` | `infrastructure_handlers.py` | Reuse `validate_only=True` path; reformat output | `"high"` | `False` (overwrites current state) |

**Note on `remove_server` risk:** It removes a database credential record, not a live server. The server itself is unaffected. `medium` risk is appropriate; the operation is not reversible since the DB record is gone, but no live infrastructure is destroyed.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `validate_only` boolean (already in two tools) | Standardized `dry_run` parameter added to all six | Consistent UX; all destructive tools behave the same way |
| No preview for `remove_vm`, `remove_server`, `delete_proxmox_vm`, `destroy_terraform_service` | Handler-layer interception with read-only pre-flight | Four tools gain preview capability without modifying business logic |

---

## Open Questions

1. **`remove_server` risk level**
   - What we know: Removes a DB credential record, not live infrastructure
   - What's unclear: Whether the user's mental model considers DB records low or medium risk
   - Recommendation: Use `"medium"` — it is irreversible but causes no infrastructure impact

2. **`destroy_terraform_service` preview when Terraform dir is absent**
   - What we know: `plan_terraform_service` checks `test -d {tf_dir}` first and returns error if missing
   - What's unclear: Should dry-run still return the contract shape even when the service doesn't exist?
   - Recommendation: Yes — return `would_affect: []` with `preview: {"error": "Terraform directory not found: /opt/terraform/{service_name}"}`. This is still a valid dry-run response.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio |
| Config file | `pyproject.toml` (project root) |
| Quick run command | `uv run pytest tests/test_dry_run.py -x -v` |
| Full suite command | `uv run pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DRY-01 | `decommission_device` with `dry_run=True` returns preview without executing | unit | `uv run pytest tests/test_dry_run.py::TestDecommissionDeviceDryRun -x` | ❌ Wave 0 |
| DRY-02 | `remove_vm` with `dry_run=True` returns preview without SSH | unit | `uv run pytest tests/test_dry_run.py::TestRemoveVmDryRun -x` | ❌ Wave 0 |
| DRY-03 | `remove_server` with `dry_run=True` returns preview without DB delete | unit | `uv run pytest tests/test_dry_run.py::TestRemoveServerDryRun -x` | ❌ Wave 0 |
| DRY-04 | `delete_proxmox_vm` with `dry_run=True` returns preview without DELETE | unit | `uv run pytest tests/test_dry_run.py::TestDeleteProxmoxVmDryRun -x` | ❌ Wave 0 |
| DRY-05 | `destroy_terraform_service` with `dry_run=True` returns preview without destroy | unit | `uv run pytest tests/test_dry_run.py::TestDestroyTerraformServiceDryRun -x` | ❌ Wave 0 |
| DRY-06 | `rollback_infrastructure_changes` with `dry_run=True` returns preview without executing | unit | `uv run pytest tests/test_dry_run.py::TestRollbackInfrastructureDryRun -x` | ❌ Wave 0 |
| DRY-07 | All six dry-run responses include `mode`, `would_affect`, `risk_level`, `reversible` | unit | `uv run pytest tests/test_dry_run.py::TestDryRunContract -x` | ❌ Wave 0 |

**Also verify:** Calling each tool without `dry_run` (or `dry_run=False`) still invokes the real business function — regression tests using existing test patterns.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_dry_run.py -x -v`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dry_run.py` — all seven requirements; covers DRY-01 through DRY-07
- [ ] `src/homelab_mcp/dry_run.py` — shared contract builder; must exist before handlers can import it

*(Framework is already installed — no install step needed)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `src/homelab_mcp/tool_schemas/`, `src/homelab_mcp/tool_handlers/`, `src/homelab_mcp/infrastructure_crud.py`, `src/homelab_mcp/vm_operations.py`, `src/homelab_mcp/proxmox_api.py`, `src/homelab_mcp/service_installer.py`, `src/homelab_mcp/ssh_tools.py`, `src/homelab_mcp/tool_annotations.py`
- `.planning/REQUIREMENTS.md` — DRY-01 through DRY-07 specification
- `tests/test_infrastructure_crud.py`, `tests/test_vm_operations.py` — confirmed test patterns

### Secondary (MEDIUM confidence)
- None required — all research derived from direct codebase inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all work is in existing Python modules
- Architecture: HIGH — handler layer is definitively the correct interception point; confirmed by reading all six tool paths end-to-end
- Pitfalls: HIGH — identified from direct code reading (`remove_server` sync, `delete_proxmox_vm` stop-then-delete, `destroy_terraform_service` dir check)

**Research date:** 2026-03-11
**Valid until:** 2026-06-11 (stable domain — dry-run pattern does not depend on external library versions)
