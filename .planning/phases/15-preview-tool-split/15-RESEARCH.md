# Phase 15: Preview Tool Split - Research

**Researched:** 2026-03-13
**Domain:** MCP Tool Annotations, Python tool registry pattern, schema/handler parity enforcement
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PREV-01 | User can call `decommission_device_preview` to preview decommission without a confirmation dialog | Dry-run logic already exists in `handle_decommission_device`; delegate to it with `dry_run=True` |
| PREV-02 | User can call `delete_proxmox_vm_preview` to preview VM deletion without a confirmation dialog | Dry-run logic already exists in `handle_delete_proxmox_vm`; delegate to it |
| PREV-03 | User can call `remove_vm_preview` to preview VM removal without a confirmation dialog | Dry-run logic already exists in `handle_remove_vm`; delegate to it |
| PREV-04 | User can call `remove_server_preview` to preview server removal without a confirmation dialog | Dry-run logic already exists in `handle_remove_server`; delegate to it |
| PREV-05 | User can call `destroy_terraform_service_preview` to preview Terraform destroy without a confirmation dialog | Dry-run logic already exists in `handle_destroy_terraform_service`; delegate to it |
| PREV-06 | User can call `rollback_infrastructure_changes_preview` to preview rollback without a confirmation dialog | Dry-run logic already exists in `handle_rollback_infrastructure_changes`; delegate to it |
| PREV-07 | All 6 `*_preview` tools annotated `readOnlyHint=True, destructiveHint=False` | Add 6 entries to `_READ_ONLY_TOOLS` list in `tool_annotations.py` |
| PREV-08 | Original 6 destructive tools retain their `dry_run` parameter for backward compatibility | No change needed — original tools remain exactly as-is |
</phase_requirements>

---

## Summary

Phase 15 splits the existing dry-run capability of six destructive tools into dedicated `*_preview` variants. The dry-run implementation already exists and passes tests for all six handlers — each handler checks `arguments.get("dry_run", False)` and delegates to `build_dry_run_response()`. The preview tools are thin wrappers that inject `dry_run=True` into the argument dict before calling the existing handler, requiring no new business logic.

The key changes are: (1) add six new schemas to the appropriate `tool_schemas/*.py` files, (2) add six new handler stubs in `tool_handlers/*.py` that call the existing handlers with `dry_run=True`, (3) register the new handlers in `tool_handlers/__init__.py`, (4) add six entries to `_READ_ONLY_TOOLS` in `tool_annotations.py`, (5) register the schemas in `tool_schemas/__init__.py`. The existing `test_annotation_count_matches_tool_count` test in `test_server.py` is the parity enforcement mechanism — it asserts `TOOL_ANNOTATIONS.keys() == get_all_tool_schemas().keys()` and will fail CI if any tool lacks an annotation entry.

The success criterion for PREV-07 (PREV-08) requires that original destructive tools remain unchanged. The `test_get_available_tools` test currently asserts `len(tools) == 50` — this must be updated to `56` after adding six preview tools.

**Primary recommendation:** Delegate from `*_preview` handlers to existing `handle_*` functions with `dry_run=True` injected. Zero new business logic. Update tool count assertion from 50 to 56.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp.types.ToolAnnotations` | already installed | Attach `readOnlyHint`, `destructiveHint`, `idempotentHint` to tools | Used by all existing tools; established pattern in `tool_annotations.py` |
| `homelab_mcp.dry_run.build_dry_run_response` | internal | Standard dry-run response contract | Already used by all six destructive handlers |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest`, `pytest-asyncio` | already installed | Wave 0 test scaffold | All tests; Wave 0 stubs are RED at commit, GREEN after implementation |

**Installation:** No new dependencies required.

---

## Architecture Patterns

### Existing Registry Structure

The project uses a split schema/handler/annotation registry pattern:

```
src/homelab_mcp/
├── tool_schemas/
│   ├── __init__.py              # get_all_tool_schemas() aggregates dicts
│   ├── infrastructure_tools_schema.py  # decommission_device, rollback_infrastructure_changes
│   ├── vm_tools_schema.py              # remove_vm
│   ├── credential_tools_schema.py      # remove_server
│   ├── proxmox_tools_schema.py         # delete_proxmox_vm
│   └── service_tools_schema.py         # destroy_terraform_service
├── tool_handlers/
│   ├── __init__.py              # TOOL_HANDLERS dict + get_tool_handler()
│   ├── infrastructure_handlers.py
│   ├── vm_handlers.py
│   ├── credential_handlers.py
│   ├── proxmox_handlers.py
│   └── service_handlers.py
└── tool_annotations.py          # TOOL_ANNOTATIONS dict, _READ_ONLY_TOOLS list
```

Each new preview tool must be registered in all three registries or the parity test fails.

### Pattern 1: Preview Handler Delegation

**What:** Preview handler injects `dry_run=True` and delegates to the existing destructive handler.
**When to use:** For all six `*_preview` handlers — no new business logic needed.

```python
# Source: inferred from existing dry_run patterns in infrastructure_handlers.py
async def handle_decommission_device_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle decommission_device_preview tool — delegates to dry-run path."""
    return await handle_decommission_device({**arguments, "dry_run": True})
```

This pattern is confirmed safe: the existing handlers already branch on `dry_run` before any destructive call occurs, and the six existing dry-run tests (DRY-01..DRY-06) verify no mutation happens.

### Pattern 2: Schema Co-Location

**What:** Add preview schema to the same `*_schema.py` file as its parent tool.
**When to use:** Always — keeps related schemas adjacent, matches team convention.

```python
# Source: existing pattern in infrastructure_tools_schema.py
INFRASTRUCTURE_TOOLS["decommission_device_preview"] = {
    "description": "Preview what decommission_device would affect without executing. Returns a dry-run report. No infrastructure is modified.",
    "inputSchema": {
        # same properties as decommission_device, minus the dry_run property
        # (preview always runs in dry-run mode; the parameter is not exposed)
        ...
    },
}
```

The `dry_run` parameter should NOT be included in the preview schema — the tool is inherently a preview, so exposing `dry_run` would be confusing. The handler injects it transparently.

### Pattern 3: Annotation Registration

**What:** Add all six preview names to `_READ_ONLY_TOOLS` list in `tool_annotations.py`.
**When to use:** All preview tools — they are read-only by definition.

```python
# Source: tool_annotations.py lines 23-46
_READ_ONLY_TOOLS = [
    # ... existing entries ...
    "decommission_device_preview",
    "delete_proxmox_vm_preview",
    "remove_vm_preview",
    "remove_server_preview",
    "destroy_terraform_service_preview",
    "rollback_infrastructure_changes_preview",
]
```

This gives each preview tool `readOnlyHint=True, destructiveHint=False, idempotentHint=True` — satisfying PREV-07.

### Recommended File Change Summary

| File | Change |
|------|--------|
| `tool_schemas/infrastructure_tools_schema.py` | Add `decommission_device_preview`, `rollback_infrastructure_changes_preview` |
| `tool_schemas/vm_tools_schema.py` | Add `remove_vm_preview` |
| `tool_schemas/credential_tools_schema.py` | Add `remove_server_preview` |
| `tool_schemas/proxmox_tools_schema.py` | Add `delete_proxmox_vm_preview` |
| `tool_schemas/service_tools_schema.py` | Add `destroy_terraform_service_preview` |
| `tool_schemas/__init__.py` | No change needed — existing dicts are merged by reference |
| `tool_handlers/infrastructure_handlers.py` | Add `handle_decommission_device_preview`, `handle_rollback_infrastructure_changes_preview` |
| `tool_handlers/vm_handlers.py` | Add `handle_remove_vm_preview` |
| `tool_handlers/credential_handlers.py` | Add `handle_remove_server_preview` |
| `tool_handlers/proxmox_handlers.py` | Add `handle_delete_proxmox_vm_preview` |
| `tool_handlers/service_handlers.py` | Add `handle_destroy_terraform_service_preview` |
| `tool_handlers/__init__.py` | Import and register all six preview handlers in `TOOL_HANDLERS` |
| `tool_annotations.py` | Add all six names to `_READ_ONLY_TOOLS` |
| `tests/test_tools.py` | Update `len(tools) == 50` to `len(tools) == 56` |

### Anti-Patterns to Avoid

- **Duplicating dry-run logic:** Do not copy the dry-run branch from the parent handler into the preview handler. Delegate to the parent — there is one truth about what the dry-run returns.
- **Including `dry_run` in preview schema:** The preview tool is unconditionally a preview; exposing `dry_run` creates confusion about what the parameter does.
- **Adding preview tools to `_DESTRUCTIVE_TOOLS`:** Preview tools must be in `_READ_ONLY_TOOLS`. Placing them in destructive would violate PREV-07 and break the `test_read_only_tools_not_destructive` parity test.
- **Forgetting `__init__.py` registration:** `tool_schemas/__init__.py` does not need changes because it references the existing dicts by name (e.g., `INFRASTRUCTURE_TOOLS`), and new keys added to those dicts are automatically included. However, `tool_handlers/__init__.py` DOES need explicit imports and `TOOL_HANDLERS` entries.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dry-run response format | Custom preview response dict | `build_dry_run_response()` from `dry_run.py` | Existing contract is tested; consistency required |
| Annotation specification | Custom annotation dict | `ToolAnnotations` from `mcp.types` with `_READ_ONLY` preset | Matches existing pattern; planner expects this |
| Schema parity check | Custom parity assertion | Existing `test_annotation_count_matches_tool_count` in `test_server.py` | Already enforces the contract — just add new tools correctly |

**Key insight:** Every piece needed already exists. The phase is purely wiring — six delegating handlers, six schemas, six annotation registrations.

---

## Common Pitfalls

### Pitfall 1: tool_schemas/__init__.py merge gap
**What goes wrong:** Developer adds schema to `INFRASTRUCTURE_TOOLS` dict but `get_all_tool_schemas()` still misses it.
**Why it happens:** Assuming the `__init__.py` needs updating — it does NOT. The `get_all_tool_schemas()` function merges the existing dict objects (`**INFRASTRUCTURE_TOOLS`, etc.), so any new key added to `INFRASTRUCTURE_TOOLS` is automatically included.
**How to avoid:** Only modify the individual schema files. Do not touch `tool_schemas/__init__.py`.
**Warning signs:** `test_annotation_count_matches_tool_count` fails with schema keys not in annotations (means schema was added but annotation was not).

### Pitfall 2: tool_handlers/__init__.py missing import
**What goes wrong:** Preview handler function is defined in `infrastructure_handlers.py` but not imported in `tool_handlers/__init__.py`, so `get_tool_handler("decommission_device_preview")` raises `ValueError`.
**Why it happens:** The pattern requires both (a) defining the function in the module and (b) explicitly importing and registering it in `__init__.py`.
**How to avoid:** After writing each preview handler, immediately add it to the import block and to `TOOL_HANDLERS` in `__init__.py`.
**Warning signs:** `test_call_tool_unknown_tool_raises_value_error` style test for preview tools, or any integration test that calls the tool, raises `ValueError: Unknown tool`.

### Pitfall 3: Schema parity test fails with count mismatch
**What goes wrong:** `test_annotation_count_matches_tool_count` fails or `test_get_available_tools` fails because the tool count assertion (`len(tools) == 50`) was not updated.
**Why it happens:** `test_tools.py` hard-codes `== 50`. Adding six tools makes it 56.
**How to avoid:** Update the count assertion as part of Wave 0.
**Warning signs:** `AssertionError: 56 != 50` in `test_get_available_tools`.

### Pitfall 4: Proxmox preview handler uses `get_resource_manager` at import time
**What goes wrong:** `handle_delete_proxmox_vm_preview` attempts to call `get_resource_manager()` at import or module level.
**Why it happens:** `handle_delete_proxmox_vm` uses a local import (`from ..server import get_resource_manager`) inside the function body — this pattern must be preserved in the preview wrapper since it is a delegation.
**How to avoid:** The delegation pattern `return await handle_delete_proxmox_vm({**arguments, "dry_run": True})` avoids the issue entirely — the local import happens inside the existing handler.
**Warning signs:** `RuntimeError: ResourceManager not available -- server lifespan not started` during test collection.

### Pitfall 5: Wave 0 test fails at collection (not execution)
**What goes wrong:** Wave 0 test imports a symbol that does not exist yet, causing pytest collection to fail for the entire test file.
**Why it happens:** Importing at module level rather than inside test function bodies.
**How to avoid:** Use local imports inside test function bodies, matching the pattern established in Phase 13 and 14 decisions (see STATE.md accumulated context).
**Warning signs:** `ImportError` or `ModuleNotFoundError` during `pytest --collect-only`.

---

## Code Examples

Verified patterns from existing codebase:

### Preview handler delegation (authoritative pattern)
```python
# Based on: handle_decommission_device in infrastructure_handlers.py
async def handle_decommission_device_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle decommission_device_preview tool.

    Delegates to handle_decommission_device with dry_run=True injected.
    No infrastructure is modified.
    """
    return await handle_decommission_device({**arguments, "dry_run": True})
```

### Preview schema (inherit parent's required fields, drop dry_run)
```python
# Based on: decommission_device schema in infrastructure_tools_schema.py
INFRASTRUCTURE_TOOLS["decommission_device_preview"] = {
    "description": (
        "Preview what decommission_device would affect without executing. "
        "Returns a structured dry-run report. No infrastructure is modified."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "Database ID of the device to decommission",
            },
            "migration_plan": {
                "type": "object",
                "description": "Plan for migrating services to other devices",
            },
            "force_removal": {
                "type": "boolean",
                "default": False,
                "description": "Force removal without migration (data loss possible)",
            },
        },
        "required": ["device_id"],
    },
}
```

### Annotation registration
```python
# Source: tool_annotations.py _READ_ONLY_TOOLS list
_READ_ONLY_TOOLS = [
    # ... existing entries ...
    "decommission_device_preview",
    "delete_proxmox_vm_preview",
    "remove_vm_preview",
    "remove_server_preview",
    "destroy_terraform_service_preview",
    "rollback_infrastructure_changes_preview",
]
```

### Handler __init__.py registration
```python
# Source: tool_handlers/__init__.py pattern
from .infrastructure_handlers import (
    # ... existing imports ...
    handle_decommission_device_preview,
    handle_rollback_infrastructure_changes_preview,
)

TOOL_HANDLERS: dict[str, ToolHandler] = {
    # ... existing entries ...
    "decommission_device_preview": handle_decommission_device_preview,
    "rollback_infrastructure_changes_preview": handle_rollback_infrastructure_changes_preview,
    # ... etc for all six
}
```

### Wave 0 test pattern (local imports inside function bodies)
```python
# Source: Phase 13 and 14 decisions in STATE.md
def test_preview_tool_in_schema_registry() -> None:
    """PREV-01: decommission_device_preview schema exists in tool registry."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas  # local import

    schemas = get_all_tool_schemas()
    assert "decommission_device_preview" in schemas
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Expose `dry_run=True` via the destructive tool itself | Dedicated `*_preview` variant with `readOnlyHint=True` | Phase 15 (now) | MCP clients skip confirmation dialog for preview; destructive tool retains its behavior |

**Deprecated/outdated:**
- Using only `dry_run=True` on the destructive tool: still valid for backward compat (PREV-08), but the `*_preview` variant is the preferred path for clients that read annotations.

---

## Open Questions

1. **Should preview schemas include ALL optional parameters from the parent?**
   - What we know: The parent schemas include optional params like `migration_plan`, `force_removal`, etc.
   - What's unclear: Whether the preview response actually uses those params or ignores them.
   - Recommendation: Include the same optional params as the parent (minus `dry_run`). The delegated handler already uses them to build richer `would_affect` responses.

2. **`remove_server_preview` — `dry_run` path uses `get_database_adapter()` synchronously**
   - What we know: `handle_remove_server` with `dry_run=True` opens a DB connection inline via `get_database_adapter().connect()`. This is sync and works in tests with mocked DB.
   - What's unclear: Nothing — the delegation pattern handles this transparently since `handle_remove_server_preview` just calls `handle_remove_server` with `dry_run=True`.
   - Recommendation: Delegation pattern; no special handling needed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (pytest section) |
| Quick run command | `uv run pytest tests/test_server.py tests/test_tools.py -x` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PREV-01 | `decommission_device_preview` returns dry-run response | unit | `uv run pytest tests/test_preview_tools.py::test_decommission_device_preview_returns_dry_run -x` | Wave 0 |
| PREV-02 | `delete_proxmox_vm_preview` returns dry-run response | unit | `uv run pytest tests/test_preview_tools.py::test_delete_proxmox_vm_preview_returns_dry_run -x` | Wave 0 |
| PREV-03 | `remove_vm_preview` returns dry-run response | unit | `uv run pytest tests/test_preview_tools.py::test_remove_vm_preview_returns_dry_run -x` | Wave 0 |
| PREV-04 | `remove_server_preview` returns dry-run response | unit | `uv run pytest tests/test_preview_tools.py::test_remove_server_preview_returns_dry_run -x` | Wave 0 |
| PREV-05 | `destroy_terraform_service_preview` returns dry-run response | unit | `uv run pytest tests/test_preview_tools.py::test_destroy_terraform_service_preview_returns_dry_run -x` | Wave 0 |
| PREV-06 | `rollback_infrastructure_changes_preview` returns dry-run response | unit | `uv run pytest tests/test_preview_tools.py::test_rollback_infrastructure_changes_preview_returns_dry_run -x` | Wave 0 |
| PREV-07 | All 6 preview tools have `readOnlyHint=True, destructiveHint=False` in `tools/list` | unit | `uv run pytest tests/test_preview_tools.py::test_preview_tools_have_readonly_annotation -x` | Wave 0 |
| PREV-07 | Schema/annotation parity enforced by CI | unit | `uv run pytest tests/test_server.py::test_annotation_count_matches_tool_count -x` | ✅ EXISTS |
| PREV-08 | Original destructive tools still present with `dry_run` param | unit | `uv run pytest tests/test_preview_tools.py::test_original_destructive_tools_still_present -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_server.py tests/test_tools.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_preview_tools.py` — covers PREV-01 through PREV-08 (new file, local imports inside test functions)
- [ ] Update `tests/test_tools.py` line 16 assertion: `len(tools) == 50` -> `len(tools) == 56`

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `src/homelab_mcp/tool_annotations.py` — full annotation registry confirmed
- Direct code inspection of `src/homelab_mcp/tool_handlers/` (all six destructive handlers) — dry_run branch pattern confirmed
- Direct code inspection of `src/homelab_mcp/dry_run.py` — `build_dry_run_response()` contract confirmed
- Direct code inspection of `src/homelab_mcp/tool_schemas/` (all six parent schemas) — confirmed `dry_run` is already present in all six
- Direct code inspection of `tests/test_server.py` lines 340-350 — parity enforcement test confirmed

### Secondary (MEDIUM confidence)
- `tests/test_dry_run.py` — full dry-run test coverage for all six handlers confirmed; DRY-01..DRY-06 pass
- `.planning/STATE.md` Accumulated Context — Wave 0 local-import pattern, `build_dry_run_response` flat dict pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; no new dependencies
- Architecture: HIGH — all patterns directly observed in codebase
- Pitfalls: HIGH — derived from direct code inspection and project STATE.md decisions
- Test map: HIGH — existing test infrastructure fully understood

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable codebase; no fast-moving dependencies)
