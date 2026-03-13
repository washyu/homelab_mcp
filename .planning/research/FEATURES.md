# Feature Research

**Domain:** MCP Protocol Completeness — Prompts, dry-run tool split, PyPI distribution, drift Resource
**Researched:** 2026-03-12
**Confidence:** HIGH (MCP types verified from installed mcp 1.9.4 source; SDK decorators confirmed via lowlevel server source; PyPI distribution verified via pyproject.toml and uv docs; dry-run split tradeoffs derived from MCP spec tool annotations + existing codebase)

---

## Context: What Already Exists (v1.1 baseline)

The server ships in v1.1 with:

- **50 tools** — 6 destructive (with `dry_run=true/false` parameter), 22 read-only, 22 mutating-non-destructive
- **`dry_run` parameter** on the 6 destructive tools: `decommission_device`, `delete_proxmox_vm`, `remove_vm`, `remove_server`, `destroy_terraform_service`, `rollback_infrastructure_changes`
- **MCP Resources** — `homelab://vms`, `homelab://devices`, `homelab://services/{name}` with live data readers and `notifications/resources/list_changed`
- **`scan_infrastructure_drift` tool** returning config and state drift report
- **No MCP Prompts** — `list_prompts` and `get_prompt` handlers not registered; `prompts` capability not advertised
- **No `homelab://drift/latest` resource** — scan_infrastructure_drift stores no result for resource access
- **No PyPI package** — install is clone + uv sync only; `[project.scripts]` entry point `homelab-mcp` exists in pyproject.toml

v1.2 milestone goal: complete MCP protocol surface with Prompts, correct dry-run tool semantics (`*_preview` variants), PyPI distribution, and `homelab://drift/latest` Resource.

---

## MCP Prompts Protocol Behavior

**Source:** mcp 1.9.4 installed source — `mcp/types.py`, `mcp/server/lowlevel/server.py` — HIGH confidence.

### Wire Protocol

`prompts/list` returns an array of `Prompt` objects:

```json
{
  "result": {
    "prompts": [
      {
        "name": "decommission_device_workflow",
        "description": "Walk through safe device decommissioning with backup, dependency check, and confirmation.",
        "arguments": [
          {"name": "device_id", "description": "ID of the device to decommission", "required": true},
          {"name": "check_backups", "description": "Whether to verify backups before proceeding", "required": false}
        ]
      }
    ]
  }
}
```

`prompts/get` takes `name` and `arguments` (flat `dict[str, str]`), returns `GetPromptResult`:

```json
{
  "result": {
    "description": "Decommission device workflow",
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "I want to decommission device 42. First run decommission_device with dry_run=true to preview what would be affected, then confirm with me before executing."
        }
      }
    ]
  }
}
```

### SDK Integration (verified from installed mcp 1.9.4)

The `lowlevel.Server` instance already used in `server.py` has two prompt decorators:

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

Registering `list_prompts` causes `get_capabilities()` to automatically include `prompts: { listChanged: ... }` in the `initialize` response. No separate capability declaration is needed — it mirrors exactly how `list_tools` triggers the `tools` capability and `list_resources` triggers the `resources` capability.

### Types Available (mcp 1.9.4, HIGH confidence)

| Type | Fields | Notes |
|------|--------|-------|
| `types.Prompt` | `name: str`, `description: str \| None`, `arguments: list[PromptArgument] \| None` | Advertised in `list_prompts` response |
| `types.PromptArgument` | `name: str`, `description: str \| None`, `required: bool \| None` | Per-argument in `Prompt.arguments` |
| `types.GetPromptResult` | `description: str \| None`, `messages: list[PromptMessage]` | Returned by `get_prompt` handler |
| `types.PromptMessage` | `role: Role`, `content: Content` | Role is `"user"` or `"assistant"`; content is `TextContent` or `ImageContent` |
| `types.TextContent` | `type: "text"`, `text: str` | Standard text block |
| `types.PromptListChangedNotification` | method `"notifications/prompts/list_changed"` | For dynamic prompt list (not needed in v1.2) |

### What Makes a Good Homelab Workflow Prompt

Prompts are **user-initiated, parameterized conversation starters**. They differ from tools (tools execute; prompts guide a multi-step AI conversation using the server's tools). A good homelab prompt:

1. **Has a clear multi-step workflow** — not a single tool call (that's what calling the tool directly is for)
2. **Chains dry-run preview before destructive action** — the prompt explicitly instructs the AI to call the `*_preview` variant first and confirm with the user
3. **Uses arguments that are natural for the operator** — device hostnames or IDs, not internal UUIDs
4. **Returns `role: "user"` messages** — the returned messages become the first turn(s) in the AI conversation; `role: "user"` is the standard for instruction messages that orient the AI session

Best practice: a prompt message should set the AI's task, reference the tools available on this server, establish constraints (e.g., "always preview destructive operations before executing"), and optionally include context from a Resource.

---

## Dry-Run Tool Split: Parameter vs. Separate Tool Names

### Option A: Keep `dry_run` Boolean Parameter (Current Approach)

The 6 destructive tools accept `dry_run: true/false`. Single tool name for both preview and execution.

**Pros:**
- Fewer tool names in `tools/list` — 50 tools stays 50
- No MCP spec violation — `dry_run` boolean is valid
- Schema documents both modes in one place

**Cons:**
- The tool is annotated `destructiveHint=True, readOnlyHint=False` — but when called with `dry_run=True` it is actually read-only. MCP clients that enforce tool annotations (VS Code shows confirmation dialogs for all non-`readOnlyHint` tools) will prompt for confirmation even on a dry-run call, which is unnecessary friction
- AI models that see `destructiveHint=True` may over-hedge on the tool, adding unnecessary confirmation steps around the preview call itself
- MCP spec tool annotations doc says `readOnlyHint` is used by clients "to present different UIs or confirm before calling" — parameter-based dry-run cannot change the annotation the client sees

**When to use:** If annotation accuracy is not a priority, or if keeping tool count low is important.

### Option B: Separate `*_preview` Tool Names (Target in v1.2)

Add 6 new tools: `decommission_device_preview`, `delete_proxmox_vm_preview`, `remove_vm_preview`, `remove_server_preview`, `destroy_terraform_service_preview`, `rollback_infrastructure_changes_preview`.

Preview tools get `readOnlyHint=True, destructiveHint=False, idempotentHint=True`. The originals keep `destructiveHint=True`.

**Pros:**
- Annotation accuracy: MCP clients see the preview tool as safe (`readOnlyHint=True`) and do not show confirmation dialogs for it
- AI models can call `decommission_device_preview` freely in planning/analysis workflows without triggering safety guards
- Matches the "one job per tool" principle from MCP best practices — preview and execute are distinct operations
- PROJECT.md explicitly targets `*_preview` variants

**Cons:**
- Tool count grows: 50 → 56 tools
- Duplicate schema entries (preview tools share most schema properties with originals)
- Both the preview and original tool must be kept consistent when schema changes

**Recommendation: Option B.** The annotation accuracy is the decisive factor. VS Code and Claude Desktop both use `readOnlyHint` to control confirmation dialogs. A `dry_run=True` call that still shows a "destructive operation" warning is degraded UX. The PROJECT.md milestone spec explicitly says "`*_preview` variants with `readOnlyHint: true`" — this is the target. The tool count increase (50 → 56) is acceptable.

### Implementation Strategy for `*_preview` Tools

- `*_preview` tools have identical `inputSchema.properties` to their originals, **minus** `dry_run` (preview mode is implied; the parameter is redundant)
- `*_preview` tool handlers are thin wrappers: they call the same dry-run logic as the `dry_run=True` path in the original, and can share the `build_dry_run_response()` helper from `dry_run.py`
- The `dry_run` parameter on the originals **should be retained** for backward compatibility — existing clients using `dry_run=true` on the original tool name must not break
- Annotations: register the 6 preview tools in `tool_annotations.py` under `_READ_ONLY_TOOLS` (or a dedicated `_PREVIEW` group for clarity)

---

## PyPI Distribution

### Current State

`pyproject.toml` already has:
- `[project.scripts]` entry `homelab-mcp = "homelab_mcp.server:main"` — defines the CLI command
- `[build-system]` with `hatchling` — ready to build
- `[tool.hatch.build.targets.wheel]` pointing to `src/homelab_mcp`
- Package name: `homelab-mcp-server` (the PyPI name); command: `homelab-mcp`

**Gap:** No `main()` function in `server.py`. The `[project.scripts]` entry points to `homelab_mcp.server:main` but `server.py` has no `main` function defined. This must be added before `uvx homelab-mcp` works.

### What `uvx homelab-mcp` Requires

1. `main()` function in `server.py` (or a `__main__.py`) that calls `mcp.run()` with stdio transport
2. `pyproject.toml` must declare the correct package name (`homelab-mcp`) — the current name is `homelab-mcp-server`. Whether to use `homelab-mcp` (shorter, natural for `uvx`) or `homelab-mcp-server` is a naming decision
3. Version bump: `0.2.0` → appropriate v1.2 release version
4. PyPI publish via `uv publish` (requires PyPI API token in CI or local env)

### Naming Decision

`uvx homelab-mcp` is the natural install path. The PyPI package name should be `homelab-mcp`. The current `homelab-mcp-server` is a mismatch — `uvx homelab-mcp-server` is awkward. **Rename `[project.name]` to `homelab-mcp`** (or keep `homelab-mcp-server` if there's a namespace conflict concern). The CLI command `homelab-mcp` is already correct.

### Distribution Complexity

Medium. No new dependencies needed. Main work:
1. Add `main()` to `server.py`
2. Verify `pyproject.toml` name and entry point consistency
3. Build and test with `uv build` and local `uvx --from ./dist homelab-mcp`
4. Publish with `uv publish`
5. Add CI publish step (optional for v1.2, can be manual first time)

---

## Drift MCP Resource (`homelab://drift/latest`)

### What It Is

A readable MCP Resource at `homelab://drift/latest` that returns the most recent drift scan report without re-running the scan. The scan is still triggered via the `scan_infrastructure_drift` tool; the resource exposes the cached result.

### Why It Adds Value Over the Tool

- Clients can access the last drift report via `resources/read` without requiring tool execution permissions
- Resources are passive (no side effects), while tools signal intent to act
- AI sessions can include `homelab://drift/latest` as context before taking action (e.g., "check drift, then propose remediation steps")
- Enables future `notifications/resources/updated` when drift state changes

### Expected Behavior

1. `scan_infrastructure_drift` tool runs → stores result in-memory (or SQLite) as `_latest_drift_report`
2. `resources/read` on `homelab://drift/latest` → returns the stored report as JSON
3. Before first scan: return `{"drift_detected": null, "reason": "No scan has been run yet", "scanned_at": null}`
4. `resources/list` includes `homelab://drift/latest` as a declared resource (always present; content is null until first scan)

### Storage Approach

In-memory module-level variable in `resource_readers.py` (or `server.py`): `_latest_drift_report: dict[str, Any] | None = None`. Updated by `scan_infrastructure_drift` handler after successful scan. Cleared on server restart. No persistence required for v1.2 — this matches the v1.1 pattern where resources return point-in-time live data.

A SQLite-persisted version is deferred: the in-memory approach is sufficient for a single-operator homelab where the server is typically restarted infrequently.

### Resource URI Declaration

Add to `HOMELAB_RESOURCES` in `server.py`:

```python
"homelab://drift/latest": {
    "name": "Infrastructure Drift Report",
    "description": "Latest infrastructure drift scan result — config and state drift since last MCP-managed baseline",
}
```

Add dispatch case in `handle_read_resource`:

```python
elif uri_str == "homelab://drift/latest":
    payload = await read_drift_resource()
```

Add `read_drift_resource()` to `resource_readers.py`.

### Sending `notifications/resources/updated`

After `scan_infrastructure_drift` runs successfully, emit `session.send_resource_updated(AnyUrl("homelab://drift/latest"))` to notify subscribed clients that the resource content has changed. This mirrors the `list_changed` pattern from Phase 10. The same `try/except LookupError` guard applies.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users expect in v1.2. Missing any of these makes the milestone feel incomplete.

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| `*_preview` tool variants for all 6 destructive tools | `dry_run` parameter exists but annotation is wrong — `destructiveHint=True` even on preview calls. MCP clients show confirmation dialogs for `readOnlyHint=False` tools. Preview should be safe to call. | MEDIUM | Existing `dry_run.py` + handler patterns; new schema entries; `tool_annotations.py` update |
| `prompts/list` and `prompts/get` protocol handlers | MCP Prompts is a first-class protocol primitive alongside Tools and Resources. A server that does not implement prompts does not complete the MCP protocol surface. Clients that support prompts (Claude Desktop, Cursor, VS Code) will show a "no prompts available" state if not implemented. | MEDIUM | `@server.list_prompts()` + `@server.get_prompt()` decorators (verified in mcp 1.9.4); new `prompt_templates.py` module |
| At least 3 meaningful homelab workflow prompts | An empty prompt list defeats the purpose. Prompts must encode real homelab multi-step workflows to be useful. Users expect pre-built guidance for common operations like safe decommissioning, health checks, and drift review. | MEDIUM | Depends on `scan_infrastructure_drift`, `*_preview` tools, `homelab://drift/latest` resource |
| `homelab://drift/latest` Resource | Drift scan data is currently only accessible via tool call. Resources expose it passively for AI context without re-running the scan. Deferred from v1.1 per PROJECT.md — it is due in v1.2. | LOW | `scan_infrastructure_drift` already exists; storage is in-memory; reader function follows existing pattern from `resource_readers.py` |
| `uvx homelab-mcp` install path | Clone + uv sync is a barrier to adoption. PyPI distribution is the standard for Python tools. The milestone explicitly targets this. `[project.scripts]` entry point exists but `main()` function is missing. | MEDIUM | Add `main()` to `server.py`; verify package name; uv build + publish |

### Differentiators (Competitive Advantage)

Features that set this server apart from generic homelab tools.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Prompts chain preview before execution | The `decommission_device_workflow` prompt instructs the AI to always call `decommission_device_preview` first and present results before proceeding. This bakes safety into the workflow, not just into individual tools. | LOW | Implemented in prompt message text; no code changes to tool handlers required |
| Drift-aware workflow prompts | A `homelab_health_check` prompt that reads `homelab://drift/latest` (if available) and `homelab://vms` and `homelab://devices` before summarizing infrastructure health. Combines Resources + Tools in one AI session setup. | LOW | Prompt message can reference resource URIs; depends on `homelab://drift/latest` existing |
| `notifications/resources/updated` on drift scan | When `scan_infrastructure_drift` completes, emit `send_resource_updated(AnyUrl("homelab://drift/latest"))`. Subscribed clients re-fetch the resource without polling. Extends Phase 10 pattern. | LOW | 5-line addition to `scan_infrastructure_drift` handler; same session + LookupError guard as Phase 10 |
| `*_preview` tools discoverable without `dry_run` knowledge | Users don't need to know about the `dry_run` parameter. `decommission_device_preview` is self-describing. AI models can reason about it without reading parameter docs. | LOW | Zero code cost beyond splitting the tool definition |

### Anti-Features (Do Not Build)

| Feature | Why Requested | Why Problematic | What to Do Instead |
|---------|---------------|-----------------|-------------------|
| Dynamic prompts (prompts that change at runtime) | "Generate prompts based on current infra state" | Requires `notifications/prompts/list_changed` dispatch; dynamic prompt generation is complex to test; prompts that change cause clients to show inconsistent UI; single-operator homelab does not need this | Static prompt registry in `prompt_templates.py` — all prompts defined at module load time; no runtime changes |
| Remove `dry_run` parameter from original tools | "The `*_preview` variants make the parameter redundant" | Breaking change for any client using the existing parameter; violates backward compatibility | Keep `dry_run` parameter on originals and add `*_preview` tools; both paths co-exist |
| Prompt message with `role: "assistant"` seeding the AI persona | "Make the AI act as an infra expert by setting its persona in prompts" | `role: "assistant"` messages in `GetPromptResult` inject a fake assistant turn that many clients do not support; spec allows it but client behavior is inconsistent | Use `role: "user"` messages with explicit instructions ("Act as an infra automation assistant. Use the available tools to..."). Higher compatibility. |
| Per-device drift Resources (`homelab://drift/device/{id}`) | "Get drift for one device without running the full scan" | Per-device granularity requires device-scoped scans (not implemented); creates a large resource surface (N devices = N URIs); unclear query semantics | Single `homelab://drift/latest` resource with the full scan report; drill into per-device data by parsing the JSON |
| Prompts that execute tools automatically | "The prompt should just run the decommission for me" | Prompts return messages, not tool calls — they set up an AI conversation; a prompt cannot execute code; clients that render prompts expect conversational setup, not execution | Tools handle execution; prompts set up the conversational context and constraints for the AI session before execution |
| Auto-publish to PyPI on every merge | CI complexity before core features are validated | Premature publish automation risks bad releases; manual publish is appropriate for v1.2 | Add CI build check (uv build); manual publish for v1.2; automate in v1.3+ once release process is proven |

---

## Feature Dependencies

```
[*_preview tool variants]
    └──requires──> [existing dry_run.py build_dry_run_response helper] (already built)
    └──requires──> [existing handler dry-run paths in each of 6 destructive tool handlers]
    └──requires──> [tool_annotations.py update for 6 new preview tool names]
    └──enhances──> [MCP Prompts: decommission_device_workflow prompt] (preview tool is safer to call)

[MCP Prompts: prompts/list + prompts/get]
    └──requires──> [@server.list_prompts() decorator registration in server.py] (1 line)
    └──requires──> [@server.get_prompt() decorator registration in server.py] (1 line)
    └──requires──> [prompt_templates.py module with HOMELAB_PROMPTS registry]
    └──enhances──> [*_preview tools: workflow prompts reference them]
    └──enhances──> [homelab://drift/latest resource: health check prompt reads it]

[homelab://drift/latest resource]
    └──requires──> [scan_infrastructure_drift tool storing result in _latest_drift_report]
    └──requires──> [read_drift_resource() in resource_readers.py]
    └──requires──> [HOMELAB_RESOURCES registration + handle_read_resource dispatch in server.py]
    └──enhances──> [MCP Prompts: homelab_health_check references homelab://drift/latest]
    └──enables──> [notifications/resources/updated after scan_infrastructure_drift runs]

[PyPI distribution: uvx homelab-mcp]
    └──requires──> [main() function in server.py]
    └──requires──> [pyproject.toml name decision: homelab-mcp vs homelab-mcp-server]
    └──requires──> [uv build + uv publish]
    └──no dependency on other v1.2 features] (can be done independently)

[notifications/resources/updated on drift scan]
    └──requires──> [homelab://drift/latest resource]
    └──requires──> [session.send_resource_updated() call in scan_infrastructure_drift handler]
    └──requires──> [existing _subscriptions and request_context pattern from Phase 10]
```

---

## MVP Definition for v1.2

### Must Ship

1. **`*_preview` tool variants** — 6 new tools in `tool_schemas/` and `tool_handlers/`, registered in `tool_annotations.py` as `readOnlyHint=True`; `dry_run` parameter kept on originals for backward compatibility
2. **`homelab://drift/latest` resource** — in-memory storage updated by `scan_infrastructure_drift`; `read_drift_resource()` in `resource_readers.py`; URI registered in `HOMELAB_RESOURCES`; `notifications/resources/updated` emitted after scan
3. **MCP Prompts** — `@server.list_prompts()` + `@server.get_prompt()` registered; `prompt_templates.py` with minimum 3 prompts: `decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`
4. **PyPI distribution** — `main()` function in `server.py`; package name decision made; `uv build` produces a working wheel; `uvx homelab-mcp` installs and runs

### Defer to v1.3

- Auto-publish CI (manual publish for v1.2)
- Per-device drift resources
- Dynamic prompts (prompts that change at runtime based on infra state)
- Background drift polling (explicitly deferred in PROJECT.md)

---

## Domain Behavior: How These Features Work

### MCP Prompts — Protocol Flow

1. Client sends `prompts/list` request
2. Server responds with array of `Prompt` objects (name, description, arguments)
3. User selects a prompt in the client UI
4. Client sends `prompts/get` with the selected prompt name and any arguments (flat `dict[str, str]`)
5. Server returns `GetPromptResult` with `messages: list[PromptMessage]`
6. Client inserts the messages as the start of an AI conversation (the messages become the conversation context)
7. The AI then uses the server's tools (visible via `tools/list`) to fulfill the workflow

**Key distinction:** Prompts do not execute tools. They return messages that *orient* the AI to execute tools correctly during the subsequent conversation.

### Recommended Homelab Workflow Prompts

**Prompt 1: `decommission_device_workflow`**
- Arguments: `device_id` (required), `force` (optional, default false)
- Message role: `user`
- Message text: instructs AI to (a) call `decommission_device_preview` first and present results, (b) ask user to confirm or cancel, (c) only call `decommission_device` after explicit confirmation
- Why: prevents accidental decommission; chains preview → confirm → execute

**Prompt 2: `deploy_service_workflow`**
- Arguments: `service_name` (required), `target_device_id` (required)
- Message role: `user`
- Message text: instructs AI to (a) call `check_service_requirements`, (b) call `validate_infrastructure_changes` with the plan, (c) present the plan and ask for confirmation, (d) call `install_service` after confirmation
- Why: establishes pre-flight checks before installation

**Prompt 3: `homelab_health_check`**
- Arguments: none required; `include_drift` (optional boolean string `"true"/"false"`)
- Message role: `user`
- Message text: instructs AI to read `homelab://vms`, `homelab://devices`, and optionally `homelab://drift/latest`, then summarize the state of the homelab including any offline VMs, devices with errors, and outstanding drift
- Why: single-command infra health report; combines Resources + Prompts

### Dry-Run Tool Split — Before/After

| Before (v1.1) | After (v1.2) |
|---------------|-------------|
| `decommission_device(device_id=42, dry_run=True)` → preview, but annotated `destructiveHint=True` | `decommission_device_preview(device_id=42)` → preview, annotated `readOnlyHint=True` |
| `decommission_device(device_id=42, dry_run=False)` → executes | `decommission_device(device_id=42)` → executes (backward compatible; `dry_run` parameter kept) |
| Client shows confirmation dialog for both preview and execute | Client shows NO confirmation dialog for preview; confirmation dialog only for execute |

### Drift Resource — State Machine

| State | `homelab://drift/latest` content |
|-------|----------------------------------|
| Server started, no scan run | `{"drift_detected": null, "reason": "No scan has been run yet", "scanned_at": null}` |
| Scan ran, no drift detected | `{"drift_detected": false, "devices_checked": N, "vms_checked": M, "drift_items": [], "scanned_at": "..."}` |
| Scan ran, drift found | `{"drift_detected": true, "drift_items": [...], "scanned_at": "..."}` |
| `notifications/resources/updated` | Emitted after each successful scan; subscribed clients re-fetch |

---

## Sources

- [mcp 1.9.4 installed source: `mcp/types.py`] — `Prompt`, `PromptArgument`, `GetPromptResult`, `PromptMessage`, `PromptsCapability` — HIGH confidence, read directly
- [mcp 1.9.4 installed source: `mcp/server/lowlevel/server.py`] — `list_prompts()` and `get_prompt()` decorator signatures; `get_capabilities()` auto-detection logic — HIGH confidence, read directly
- [MCP Prompts specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts) — protocol wire format (MEDIUM confidence, WebSearch confirmed, not directly fetched)
- [MCP tool annotations: `readOnlyHint` usage](https://modelcontextprotocol.io/legacy/concepts/tools) — `readOnlyHint` controls confirmation dialogs in VS Code and other clients — HIGH confidence from tool_annotations.py + MCP spec doc
- [Zuplo MCP Server Prompts](https://zuplo.com/docs/mcp-server/prompts) — workflow prompt design patterns — MEDIUM confidence
- [MCP Prompts Automation blog](http://blog.modelcontextprotocol.io/posts/2025-07-29-prompts-for-automation/) — workflow prompt role:user patterns — MEDIUM confidence
- [uv packaging guide](https://thisdavej.com/packaging-python-command-line-apps-the-modern-way-with-uv/) — uvx entry point and pyproject.toml requirements — MEDIUM confidence (multiple sources agree)
- Direct codebase inspection: `src/homelab_mcp/server.py`, `src/homelab_mcp/tool_annotations.py`, `pyproject.toml`, `src/homelab_mcp/resource_readers.py`, `src/homelab_mcp/dry_run.py` — HIGH confidence

---

*Feature research for: MCP Protocol Completeness (v1.2 milestone)*
*Researched: 2026-03-12*
