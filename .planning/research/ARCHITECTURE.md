# Architecture Patterns — v1.2 Protocol Completeness

**Domain:** MCP Prompts + dry-run tool split + PyPI distribution + drift MCP Resource
**Researched:** 2026-03-12
**Confidence:** HIGH (all SDK mechanics verified against installed source at `.venv/lib/python3.12/site-packages/mcp/`)

---

## Verified SDK Mechanics

All four integration points were verified directly against the installed MCP SDK source (`mcp[cli] 1.9.1`, installed version confirmed present in `.venv`).

### 1. MCP Prompts — `@server.list_prompts()` / `@server.get_prompt()`

**Confidence: HIGH** — Both decorators are confirmed in `mcp/server/lowlevel/server.py` lines 219–245.

**Decorator signatures (from SDK source):**

```python
@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    ...

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    ...
```

**Key SDK types (from `mcp/types.py`):**

```python
class PromptArgument(BaseModel):
    name: str
    description: str | None = None
    required: bool | None = None

class Prompt(BaseModel):
    name: str
    description: str | None = None
    arguments: list[PromptArgument] | None = None

class PromptMessage(BaseModel):
    role: Role   # "user" | "assistant"
    content: TextContent | ImageContent | EmbeddedResource

class GetPromptResult(Result):
    description: str | None = None
    messages: list[PromptMessage]
```

**Capability auto-detection:** `get_capabilities()` in `lowlevel/server.py` lines 181–210 automatically sets `prompts_capability` when `types.ListPromptsRequest` is registered. Registering `@server.list_prompts()` is sufficient — no manual `Server()` constructor argument needed.

**Notification method (from `mcp/server/session.py` line 309):**

```python
await session.send_prompt_list_changed()
# Sends: notifications/prompts/list_changed
```

Access pattern (consistent with existing resource notification in `server.py` line 372):

```python
session = server.request_context.session
await session.send_prompt_list_changed()
```

---

### 2. Dry-Run Tool Split — `*_preview` variants

**Confidence: HIGH** — Pattern is derived from existing codebase structure, not new SDK mechanics.

**Current state:** All 6 destructive tools already have `dry_run: bool` parameter in their `inputSchema` (confirmed in `tool_schemas/`). When `dry_run=True`, the existing handler returns a `build_dry_run_response()` dict instead of executing. The SDK `call_tool` decorator handles both paths identically — both return `list[types.TextContent]`.

**v1.2 target:** Split each destructive tool into two separate tools:
- `delete_proxmox_vm` (destructive, `readOnlyHint=False`, `destructiveHint=True`)
- `delete_proxmox_vm_preview` (read-only, `readOnlyHint=True`, `destructiveHint=False`)

The `_preview` variant calls the same underlying handler but passes `dry_run=True` implicitly (the caller never supplies a `dry_run` arg — the schema removes it entirely). This is semantically cleaner: the `_preview` tool always previews, the base tool always executes.

**Why split rather than keep the flag?**

The MCP spec's `readOnlyHint=True` is a client-visible signal. An AI assistant should be able to call `delete_proxmox_vm_preview` safely without user confirmation, then call `delete_proxmox_vm` only after showing the preview. The `dry_run` boolean on a destructive tool forces the model to reason about which value to set — `*_preview` makes the safe path a distinct, discoverable tool name.

---

### 3. Drift MCP Resource — `homelab://drift/latest`

**Confidence: HIGH** — Pattern is identical to existing resources; `read_resource` decorator already handles URI dispatch in `server.py`.

**Integration point:** `HOMELAB_RESOURCES` dict in `server.py` (lines 101–114). Adding `homelab://drift/latest` to this dict makes it appear in `resources/list`. The `handle_read_resource` dispatcher calls `read_drift_resource()` from `resource_readers.py`.

The drift scan result lives in `drift_detection.scan_drift()`. The resource reader needs to either:
1. Re-run a lightweight scan on each read, or
2. Serve the most recent scan result cached in SQLite.

Option 2 is correct: add a `drift_latest` column or table in SQLite. The `scan_infrastructure_drift` tool writes to it; `read_drift_resource()` reads from it. This avoids triggering a full Proxmox+SSH scan on every resource read.

**Notification:** After `scan_infrastructure_drift` tool succeeds, send `send_resource_updated(AnyUrl("homelab://drift/latest"))` via the session. The existing `handle_call_tool` notification block (server.py lines 366–376) is the right place to add this — extend `MUTATING_TOOLS` or add a new `DRIFT_UPDATING_TOOLS` frozenset.

---

### 4. PyPI Distribution — `pyproject.toml` changes

**Confidence: HIGH** — verified against pyproject.toml and Python packaging standards.

**Current state:**
- `name = "homelab-mcp-server"` (hyphenated, valid PyPI name)
- `version = "0.2.0"` (needs bump to `1.2.0`)
- `build-backend = "hatchling.build"` (already correct for PyPI)
- Entry point: `homelab-mcp = "homelab_mcp.server:main"` — **`main` does not exist in `server.py`**. This is a live bug. The `__main__.py` module is also absent.

**Required changes for `uvx homelab-mcp`:**

1. Create `src/homelab_mcp/__main__.py` with a `main()` function that bootstraps the server (stdio + HTTP). This is what `uvx homelab-mcp` invokes.
2. Fix entry point in `pyproject.toml` to point at `homelab_mcp.__main__:main` (per `milestone_context` spec) or keep `homelab_mcp.server:main` once `main` is added to `server.py`.
3. Bump `version` to `1.2.0`.
4. Add `[project.urls]` for PyPI metadata (Homepage, Repository, Changelog — optional but expected by PyPI consumers).
5. Verify `[tool.hatch.build.targets.wheel] packages = ["src/homelab_mcp"]` — already correct.

**Note on `uvx`:** `uvx` runs the entry point from the installed package without requiring a virtual environment. The `main()` function must handle the full startup path including argument parsing (stdio vs HTTP mode) and signal handling. Currently this logic lives in `run_server.py` (project root) — the `__main__.py` should consolidate it.

---

## Component Map

### Existing Components (unchanged in v1.2)

| Component | File | Role |
|-----------|------|------|
| MCP server instance | `server.py` | `lowlevel.Server`, all handler decorators, lifespan |
| ResourceManager | `resource_manager.py` | Proxmox session + SQLite lifecycle |
| Tool handler registry | `tool_handlers/__init__.py` | `TOOL_HANDLERS` dict + `get_tool_handler()` |
| Tool schemas | `tool_schemas/__init__.py` | Schema dicts per category |
| Tool annotations | `tool_annotations.py` | `ToolAnnotations` per tool name |
| Resource readers | `resource_readers.py` | `read_vms_resource`, `read_devices_resource`, `read_service_resource` |
| Drift detection | `drift_detection.py` | `scan_drift()`, `update_baseline_after_mutation()` |
| Drift handlers | `tool_handlers/drift_handlers.py` | `handle_scan_infrastructure_drift` |
| HTTP app | `http_app.py` | Starlette + `StreamableHTTPSessionManager` + `OriginValidationMiddleware` + `APIKeyAuth` |

### New Components for v1.2

| Component | File | What It Does |
|-----------|------|--------------|
| Prompt registry | `prompt_registry.py` (new) | `HOMELAB_PROMPTS` dict + `get_all_prompts()` + `get_prompt_by_name()` |
| Preview tool schemas | `tool_schemas/preview_tools_schema.py` (new) | Schemas for all 6 `*_preview` variants |
| Preview tool handlers | `tool_handlers/preview_handlers.py` (new) | Thin wrappers that call existing handlers with `dry_run=True` |
| Drift resource reader | `resource_readers.py` (extend) | `read_drift_resource()` added to existing module |
| Entrypoint | `__main__.py` (new) | `main()` for `uvx homelab-mcp` |

### Modified Components

| Component | File | Change |
|-----------|------|--------|
| MCP server decorators | `server.py` | Add `@server.list_prompts()`, `@server.get_prompt()` decorators; extend `HOMELAB_RESOURCES` + `handle_read_resource` for `homelab://drift/latest`; add drift resource notification trigger in `handle_call_tool` |
| Tool handler registry | `tool_handlers/__init__.py` | Import and register all 6 `*_preview` handlers |
| Tool schema registry | `tool_schemas/__init__.py` | Include `PREVIEW_TOOLS` in `get_all_tool_schemas()` |
| Tool annotations | `tool_annotations.py` | Add `_READ_ONLY` annotations for all 6 `*_preview` tool names |
| Package manifest | `pyproject.toml` | Bump version; fix/add entrypoint; add `[project.urls]` |

---

## Data Flow: MCP Prompts

```
MCP client → prompts/list
  server.py: handle_list_prompts()
    → prompt_registry.get_all_prompts()
    → returns list[types.Prompt]

MCP client → prompts/get { name: "audit_vm_drift", arguments: {"node": "pve1"} }
  server.py: handle_get_prompt(name, arguments)
    → prompt_registry.get_prompt_by_name(name, arguments)
    → messages_fn(arguments) → list[types.PromptMessage]
    → returns types.GetPromptResult
```

`prompt_registry.py` owns prompt definitions and exposes `get_all_prompts()` and `get_prompt_by_name()`, exactly mirroring how `tool_schemas/__init__.py` exposes `get_all_tool_schemas()`. This keeps prompt content out of `server.py`.

### Suggested initial prompts (homelab workflow templates)

| Prompt name | Purpose | Arguments |
|-------------|---------|-----------|
| `audit_vm_drift` | Guides drift scan + review workflow | `node` (optional), `vm_type` (optional) |
| `decommission_device_safe` | Walks through preview → confirm → execute for decommission | `device_id` |
| `deploy_new_vm` | Proxmox VM creation checklist | `node`, `vm_type`, `cores`, `memory` |
| `service_health_check` | Check all services on a host | `hostname` |

Four prompts is sufficient for v1.2. Prompts are static templates — no database or ResourceManager access needed inside `messages_fn`.

---

## Data Flow: Dry-Run Tool Split

```
MCP client → tools/call { name: "delete_proxmox_vm_preview", arguments: {node, vmid} }
  server.py: handle_call_tool("delete_proxmox_vm_preview", arguments)
    → get_tool_handler("delete_proxmox_vm_preview")
    → preview_handlers.handle_delete_proxmox_vm_preview(arguments)
    → proxmox_handlers.handle_delete_proxmox_vm({...arguments, dry_run: True})
    → build_dry_run_response(...) in dry_run.py
    → returns {"mode": "dry_run", "would_affect": [...], ...}
```

Each preview handler in `preview_handlers.py` is a one-liner forwarding to the live handler with `dry_run=True` injected. No new business logic; `build_dry_run_response()` already handles the response contract.

---

## Data Flow: Drift Resource

```
MCP client → tools/call { name: "scan_infrastructure_drift" }
  → drift_handlers.handle_scan_infrastructure_drift(arguments)
  → drift_detection.scan_drift(session, db_adapter)
  → db.upsert_drift_latest(result)          ← NEW
  → server.py: send_resource_updated(homelab://drift/latest)   ← NEW

MCP client → resources/read { uri: "homelab://drift/latest" }
  → server.py: handle_read_resource(uri)
  → resource_readers.read_drift_resource()  ← NEW
  → db.get_drift_latest()                   ← NEW
  → returns JSON payload (last scan result or {"status": "no_scan_run"})
```

### SQLite change required

New single-row table in `database.py`:

```sql
CREATE TABLE IF NOT EXISTS drift_latest_report (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    report_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
```

`upsert_drift_latest()` uses `INSERT OR REPLACE INTO drift_latest_report (id, report_json, recorded_at) VALUES (1, ?, ?)`. This is consistent with the `INSERT OR REPLACE` pattern already used for `drift_baselines`.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Calling scan_drift() inside read_drift_resource()

**What:** Implement `read_drift_resource()` as a direct call to `scan_drift()`.
**Why bad:** Resource reads must be fast. `scan_drift()` makes Proxmox API calls and SSH connections — under load, a resource read could take 10–30 seconds. The MCP spec treats resource reads as synchronous; slow reads block the client.
**Instead:** Cache scan results in SQLite; `read_drift_resource()` reads only from the cache.

### Anti-Pattern 2: Adding `dry_run: bool` parameter to `*_preview` tool schemas

**What:** Copy the live tool's schema verbatim including `dry_run: bool` for the `_preview` variant.
**Why bad:** The `_preview` tool always previews. Exposing `dry_run` on it implies the client can set `dry_run=False` to execute — which contradicts the tool's purpose and confuses the AI assistant.
**Instead:** Remove `dry_run` from the `_preview` schema; the handler injects it implicitly.

### Anti-Pattern 3: Adding prompts to server.py directly

**What:** Define `HOMELAB_PROMPTS` inline in `server.py`.
**Why bad:** `server.py` is already 415 lines. Adding prompt definitions breaks the established pattern where schemas live in `tool_schemas/`, handlers in `tool_handlers/`, and annotations in `tool_annotations.py`. Prompts need the same separation.
**Instead:** `prompt_registry.py` owns prompt definitions and exposes `get_all_prompts()` and `get_prompt_by_name()`.

### Anti-Pattern 4: Keeping run_server.py as a parallel entry point

**What:** Keep `run_server.py` as the development entry point and `__main__.py` only for packaging.
**Why bad:** Two entry points diverge over time and cause "works in dev but not in production" bugs. The project already has this split — it's a liability, not an asset.
**Instead:** `__main__.py` is the single entry point. `run_server.py` at project root becomes a one-liner shim or is deleted.

---

## Build Order

Ordered by implementation dependency:

```
Phase 1: __main__.py + pyproject.toml entrypoint fix
  Prerequisite for PyPI publishing; broken entry point is a live bug.
  New: src/homelab_mcp/__main__.py
  Modifies: pyproject.toml (version bump, entrypoint fix, project.urls)

Phase 2: Drift resource (homelab://drift/latest)
  Prerequisite: drift_detection.py exists (v1.1 done).
  New: drift_latest_report table in database.py + migration
  Extends: resource_readers.py with read_drift_resource()
  Modifies: server.py (HOMELAB_RESOURCES, dispatcher branch, notification trigger)
  Modifies: tool_handlers/drift_handlers.py (write to drift_latest after scan)

Phase 3: MCP Prompts
  No prerequisites; self-contained.
  New: src/homelab_mcp/prompt_registry.py
  Modifies: server.py (two new decorator registrations)

Phase 4: Dry-run tool split (_preview variants)
  Prerequisite: dry_run.py + build_dry_run_response() exists (v1.1 done).
  New: tool_schemas/preview_tools_schema.py
  New: tool_handlers/preview_handlers.py
  Modifies: tool_handlers/__init__.py, tool_schemas/__init__.py, tool_annotations.py
```

Phase 2 before Phase 3 because the drift resource demonstrates end-to-end resource read + notification, which is the riskiest integration point. Phase 4 last because it touches the most files and has no dependents within the milestone.

---

## Integration Point Summary

| Feature | Touch points in server.py | New files | Modified files |
|---------|---------------------------|-----------|----------------|
| MCP Prompts | Two new decorators after line 414 | `prompt_registry.py` | `server.py` |
| Drift resource | `HOMELAB_RESOURCES` + dispatcher branch + notification | — | `server.py`, `resource_readers.py`, `database.py`, `tool_handlers/drift_handlers.py` |
| Preview tools | None directly | `tool_handlers/preview_handlers.py`, `tool_schemas/preview_tools_schema.py` | `tool_handlers/__init__.py`, `tool_schemas/__init__.py`, `tool_annotations.py` |
| PyPI + entrypoint | None directly | `__main__.py` | `pyproject.toml` |

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| `@server.list_prompts()` / `@server.get_prompt()` decorators | HIGH | Verified in installed SDK source `lowlevel/server.py` lines 219–245 |
| `types.Prompt`, `types.PromptArgument`, `types.GetPromptResult` | HIGH | Verified in installed `mcp/types.py` |
| Capability auto-detection for prompts | HIGH | Verified in `get_capabilities()` lines 181–210 of SDK source |
| `session.send_prompt_list_changed()` | HIGH | Verified in `mcp/server/session.py` line 309 |
| `session.send_resource_updated()` | HIGH | Verified in `mcp/server/session.py` line 196 |
| Dry-run tool split pattern | HIGH | `build_dry_run_response()` + handler patterns established in v1.1 |
| SQLite cache for drift report | MEDIUM | Requires new table + migration; no technical risk, but schema change needs care |
| PyPI packaging mechanics | HIGH | `hatchling` build backend already configured; `uvx` install path is standard Python packaging |
| Missing `main()` in `server.py` bug | HIGH | Confirmed: `pyproject.toml` entry point is `homelab_mcp.server:main` but no `def main` exists in `server.py` |

---

## Sources

- `mcp/server/lowlevel/server.py` (installed, `.venv`) — `list_prompts()`, `get_prompt()` decorators at lines 219–245; `get_capabilities()` auto-detection logic at lines 181–210
- `mcp/types.py` (installed, `.venv`) — `Prompt`, `PromptArgument`, `GetPromptResult`, `PromptMessage` class definitions
- `mcp/server/session.py` (installed, `.venv`) — `send_resource_updated()` line 196, `send_resource_list_changed()` line 289, `send_prompt_list_changed()` line 309
- `src/homelab_mcp/server.py` — existing handler patterns, `HOMELAB_RESOURCES` dict (lines 101–114), notification block (lines 366–376)
- `src/homelab_mcp/resource_readers.py` — existing reader pattern (deferred import to avoid circular import, error handling, `scanned_at`)
- `src/homelab_mcp/drift_detection.py` — `scan_drift()` return structure
- `src/homelab_mcp/dry_run.py` — `build_dry_run_response()` contract
- `src/homelab_mcp/tool_annotations.py` — annotation patterns for `_DESTRUCTIVE_TOOLS` and `_READ_ONLY_TOOLS`
- `src/homelab_mcp/tool_handlers/__init__.py` — `TOOL_HANDLERS` dict structure
- `src/homelab_mcp/tool_schemas/__init__.py` — `get_all_tool_schemas()` composition pattern
- `pyproject.toml` — current entry point (confirmed broken), build backend, version

---

*Architecture research for: Homelab MCP Server v1.2 Protocol Completeness*
*Researched: 2026-03-12*
