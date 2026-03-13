# Phase 14: MCP Prompts - Research

**Researched:** 2026-03-13
**Domain:** MCP Prompts protocol (prompts/list, prompts/get, capability advertisement)
**Confidence:** HIGH

## Summary

The MCP Python SDK version 1.9.4 (already installed) has full native support for prompts.
The `mcp.server.lowlevel.Server` class exposes `@server.list_prompts()` and
`@server.get_prompt()` decorators that work identically to the existing
`@server.list_resources()` and `@server.call_tool()` decorators already in use.
Capability advertisement is automatic: registering a `list_prompts` handler causes
`get_capabilities()` to include a non-None `PromptsCapability` in the `initialize`
response. No manual capability wiring is needed.

The three required prompts (`decommission_device_workflow`, `deploy_service_workflow`,
`homelab_health_check`) are static — they return fixed `PromptMessage` lists with no
runtime state. This matches the REQUIREMENTS.md out-of-scope decision: "Dynamic prompts
(runtime-generated) — complexity without value; static registry is correct."

**Primary recommendation:** Add a `prompt_registry.py` module with the three static
prompt definitions, wire two handlers into `server.py` using the SDK decorators, and
test via direct handler calls — the same pattern used for resources and tools.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp[cli] | 1.9.4 (installed) | Prompt types + handler decorators | Already used; provides `Prompt`, `PromptArgument`, `PromptMessage`, `GetPromptResult` |

No new dependencies. Everything needed is already in the installed `mcp` package.

**Installation:** No new packages required.

## Architecture Patterns

### Recommended Project Structure

The pattern mirrors how resources are organized: a thin registry module consumed by
`server.py`.

```
src/homelab_mcp/
├── server.py                  # Add @server.list_prompts() and @server.get_prompt() handlers
├── prompt_registry.py         # NEW: HOMELAB_PROMPTS dict + build_prompt_messages() helpers
└── ...

tests/
├── test_mcp_prompts.py        # NEW: Wave 0 → implementation tests for PRMT-01..04
└── ...
```

### Pattern 1: Static Prompt Registry Module

**What:** A dict mapping prompt name → `Prompt` metadata, plus a function that returns
`GetPromptResult` for each name (dispatching on the name string).
**When to use:** When prompts are static templates that never change at runtime.

```python
# Source: mcp.types introspection — verified 2026-03-13
import mcp.types as types

HOMELAB_PROMPTS: dict[str, types.Prompt] = {
    "decommission_device_workflow": types.Prompt(
        name="decommission_device_workflow",
        description="Safe guided workflow for decommissioning a device",
        arguments=[
            types.PromptArgument(name="hostname", description="Hostname or IP of device to decommission", required=True),
        ],
    ),
    "deploy_service_workflow": types.Prompt(
        name="deploy_service_workflow",
        description="Pre-flight checked service deployment workflow",
        arguments=[
            types.PromptArgument(name="service_name", description="Name of the service to deploy", required=True),
            types.PromptArgument(name="target_host", description="Target host for deployment", required=True),
        ],
    ),
    "homelab_health_check": types.Prompt(
        name="homelab_health_check",
        description="Read all infrastructure resources and summarize homelab state",
        arguments=[],
    ),
}


def get_prompt_result(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    args = arguments or {}
    if name == "decommission_device_workflow":
        return _build_decommission_result(args)
    elif name == "deploy_service_workflow":
        return _build_deploy_service_result(args)
    elif name == "homelab_health_check":
        return _build_health_check_result(args)
    else:
        raise KeyError(f"Unknown prompt: {name}")
```

### Pattern 2: Handler Registration in server.py

**What:** Two decorators added to `server.py`, following the exact same pattern as
`list_resources` and `call_tool`.
**When to use:** Every time a new MCP capability is added to the server.

```python
# Source: mcp.server.lowlevel.Server.list_prompts / get_prompt — verified 2026-03-13
from .prompt_registry import HOMELAB_PROMPTS, get_prompt_result

@server.list_prompts()  # type: ignore[misc]
async def handle_list_prompts() -> list[types.Prompt]:
    """Return all homelab prompt templates."""
    return list(HOMELAB_PROMPTS.values())


@server.get_prompt()  # type: ignore[misc]
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    """Return the rendered messages for a named prompt."""
    from mcp.shared.exceptions import McpError
    try:
        return get_prompt_result(name, arguments)
    except KeyError:
        raise McpError(
            types.ErrorData(
                code=RESOURCE_NOT_FOUND,
                message=f"Prompt not found: {name}",
                data={"name": name},
            )
        )
```

### Pattern 3: PromptMessage Construction

**What:** A `PromptMessage` wraps a `TextContent` (or other content type) with a `role`
(`"user"` or `"assistant"`). The MCP spec uses `"user"` role for instructions to the AI
and `"assistant"` for pre-filled assistant turns.
**When to use:** Always — this is the only way to build `GetPromptResult.messages`.

```python
# Source: mcp.types — verified 2026-03-13
def _make_user_message(text: str) -> types.PromptMessage:
    return types.PromptMessage(
        role="user",
        content=types.TextContent(type="text", text=text),
    )

def _build_health_check_result(args: dict[str, str]) -> types.GetPromptResult:
    text = (
        "Read the following resources and summarize the homelab infrastructure state:\n"
        "1. Read homelab://vms — list all VMs and containers\n"
        "2. Read homelab://devices — list all network devices\n"
        "3. Read homelab://drift/latest — check for infrastructure drift\n\n"
        "Summarize: total VM count, device count, any drift detected, "
        "and flag any items that need attention."
    )
    return types.GetPromptResult(
        description="Homelab infrastructure health check",
        messages=[_make_user_message(text)],
    )
```

### Capability Advertisement (Automatic)

**Critical finding:** No manual capability wiring needed. The SDK's `get_capabilities()`
method already handles this:

```python
# Source: mcp.server.lowlevel.Server.get_capabilities — verified 2026-03-13
if types.ListPromptsRequest in self.request_handlers:
    prompts_capability = types.PromptsCapability(
        listChanged=notification_options.prompts_changed
    )
```

Registering `@server.list_prompts()` is sufficient. The `initialize` response will
include `"prompts": {...}` automatically. PRMT-01 is satisfied by the decorator alone.

### Anti-Patterns to Avoid

- **Hardcoding prompt text in server.py:** Put prompt text in `prompt_registry.py` —
  keeps `server.py` as a thin registration hub (established pattern from Phase 13).
- **Module-level import of prompt_registry in server.py:** If `prompt_registry` imports
  from `server`, a circular import occurs. Use local imports in handler bodies, or
  ensure `prompt_registry.py` has no imports from `server.py` (preferred — it should
  only import `mcp.types`).
- **Raising ValueError for unknown prompts:** Raise `McpError` with
  `RESOURCE_NOT_FOUND` (-32002) instead — consistent with the resource reader pattern
  already established.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Capability advertisement | Manually set `prompts` in InitializationOptions | Register `@server.list_prompts()` | SDK auto-detects; manual wiring risks mismatch |
| Argument validation | Custom required-arg checker | Return a clear error message in the prompt text when arg is missing | Prompts are advisory — the AI reads the message and decides what to call |
| Prompt serialization | Custom JSON encoding | `types.GetPromptResult` is a Pydantic model — SDK serializes it | Already handled by the SDK server loop |

**Key insight:** Prompts are text templates, not executable code. The AI client reads
the message text and decides which tools to call. There is no server-side enforcement
of "call tool X before tool Y" — the prompt text instructs the AI to do this.

## Common Pitfalls

### Pitfall 1: Circular Import via prompt_registry

**What goes wrong:** If `prompt_registry.py` imports anything from `server.py`
(e.g., `get_resource_manager`), a circular import will crash on startup.
**Why it happens:** `server.py` imports `prompt_registry`, which imports `server`.
**How to avoid:** `prompt_registry.py` must only import from `mcp.types` and the
standard library — no homelab_mcp imports. Arguments are passed in as plain dicts.
**Warning signs:** `ImportError: cannot import name X` or `circular import` traceback
at server startup.

### Pitfall 2: get_prompt Signature Mismatch

**What goes wrong:** The `@server.get_prompt()` decorated function must accept
`(name: str, arguments: dict[str, str] | None)` — exactly two parameters.
**Why it happens:** The SDK's internal handler wraps your function and calls it as
`func(req.params.name, req.params.arguments)`.
**How to avoid:** Use the exact signature from `Server.get_prompt` source:
```python
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
```
**Warning signs:** `TypeError: takes N positional arguments but M were given` at
runtime.

### Pitfall 3: Missing McpError for Unknown Prompt Name

**What goes wrong:** If `prompts/get` is called with an unknown name and the handler
raises `KeyError` or `ValueError`, the SDK may return an unformatted error.
**Why it happens:** The SDK `get_prompt` decorator does not catch non-McpError exceptions
and reformat them (unlike `call_tool` which uses `ToolError`).
**How to avoid:** Catch `KeyError` from the registry dispatch and raise `McpError`
with `RESOURCE_NOT_FOUND` (-32002).

### Pitfall 4: Prompt Text That Refers to Nonexistent Tools

**What goes wrong:** `decommission_device_workflow` must reference
`decommission_device_preview` — but PREV-01 (Phase 15) has not been implemented yet.
**Why it happens:** The prompt text can reference a tool that does not exist yet.
**How to avoid:** The prompt text is just a string. Write it to reference
`decommission_device_preview` as the intended tool. At Phase 14 time, the preview tool
does not exist, but the prompt text is still correct. The AI will call the tool when
it exists. This is acceptable — PRMT-02 only requires the prompt text instructs the AI
correctly, not that the tool exists.

## Code Examples

Verified patterns from official sources (mcp 1.9.4 introspection):

### list_prompts Handler
```python
# Source: mcp.server.lowlevel.Server.list_prompts — verified 2026-03-13
@server.list_prompts()  # type: ignore[misc]
async def handle_list_prompts() -> list[types.Prompt]:
    return list(HOMELAB_PROMPTS.values())
```

### get_prompt Handler
```python
# Source: mcp.server.lowlevel.Server.get_prompt — verified 2026-03-13
@server.get_prompt()  # type: ignore[misc]
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    ...
```

### decommission_device_workflow Prompt Text
The PRMT-02 requirement is: "guides the AI to call `decommission_device_preview` first,
confirm with the user, then execute." The message text should follow this structure:

```
1. Call decommission_device_preview with hostname="{hostname}" to preview the operation.
2. Present the preview result to the user and ask for explicit confirmation.
3. Only if the user confirms: call decommission_device with hostname="{hostname}".
4. Report the result to the user.
```

### homelab_health_check Prompt Text
The PRMT-04 requirement is: reads `homelab://vms`, `homelab://devices`, and
`homelab://drift/latest` and summarizes infra state:

```
Read the following MCP resources and summarize homelab infrastructure state:
1. Read homelab://vms
2. Read homelab://devices
3. Read homelab://drift/latest
Summarize total counts, any errors, and flag drift if detected.
```

### Capability Verification Pattern (for tests)
```python
# Source: server.get_capabilities — verified 2026-03-13
caps = server.get_capabilities(NotificationOptions(), {})
assert caps.prompts is not None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled JSON-RPC prompts handling | `@server.list_prompts()` / `@server.get_prompt()` SDK decorators | MCP SDK ≥1.0 | No manual request routing needed |

## Open Questions

1. **Argument interpolation in prompt text**
   - What we know: The prompt text is a plain string; the SDK passes arguments as a
     `dict[str, str]` to the `get_prompt` handler.
   - What's unclear: Should argument values be interpolated into the prompt text
     (e.g., `f"hostname={args.get('hostname', '<required>') }"`) or left as
     placeholder instructions?
   - Recommendation: Interpolate when the argument is provided; use a clear placeholder
     (`<hostname>`) when not provided. This makes the prompt more actionable.

2. **deploy_service_workflow pre-flight check content**
   - What we know: PRMT-03 says "guides the AI through pre-flight checks before service
     installation." No specific tool names are mandated.
   - What's unclear: Which tools constitute "pre-flight checks" for service deployment?
   - Recommendation: Reference `ssh_discover` (verify connectivity) and
     `list_installed_services` (check for conflicts) as pre-flight tools. The planner
     should decide exact tool names.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (installed) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_mcp_prompts.py -x` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRMT-01 | `initialize` response includes `prompts` capability | unit | `uv run pytest tests/test_mcp_prompts.py::test_prompts_capability_advertised -x` | Wave 0 |
| PRMT-01 | `prompts/list` returns list of `Prompt` objects | unit | `uv run pytest tests/test_mcp_prompts.py::test_list_prompts_returns_prompts -x` | Wave 0 |
| PRMT-02 | `decommission_device_workflow` prompt exists and contains preview instruction | unit | `uv run pytest tests/test_mcp_prompts.py::test_decommission_workflow_prompt -x` | Wave 0 |
| PRMT-03 | `deploy_service_workflow` prompt exists and mentions pre-flight checks | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_prompt -x` | Wave 0 |
| PRMT-04 | `homelab_health_check` prompt exists and references all three resources | unit | `uv run pytest tests/test_mcp_prompts.py::test_health_check_prompt_resources -x` | Wave 0 |
| PRMT-01 | `prompts/get` with unknown name raises McpError(-32002) | unit | `uv run pytest tests/test_mcp_prompts.py::test_get_unknown_prompt_raises_mcp_error -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_mcp_prompts.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mcp_prompts.py` — covers PRMT-01, PRMT-02, PRMT-03, PRMT-04
- [ ] `src/homelab_mcp/prompt_registry.py` — does not exist yet (Wave 0 tests import it)

## Sources

### Primary (HIGH confidence)
- mcp 1.9.4 installed package — introspected `Server.list_prompts`, `Server.get_prompt`,
  `Server.get_capabilities` source directly
- mcp.types — introspected `Prompt`, `PromptArgument`, `PromptMessage`,
  `GetPromptResult`, `PromptsCapability` field signatures directly
- `src/homelab_mcp/server.py` — existing handler patterns for `list_resources`,
  `read_resource`, `call_tool` (direct file read)
- `src/homelab_mcp/resource_readers.py` — module isolation pattern (direct file read)
- `.planning/REQUIREMENTS.md` — exact PRMT-01..04 requirement text

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — accumulated architectural decisions (thin modules, local
  imports, circular import avoidance)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — SDK introspected directly on installed version
- Architecture: HIGH — decorator pattern verified from SDK source; mirrors existing patterns in codebase
- Pitfalls: HIGH — circular import pitfall directly observed from Phase 13 STATE.md notes; signature mismatch verified from SDK source

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable SDK)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PRMT-01 | Server declares `prompts` capability in `initialize` and responds to `prompts/list` and `prompts/get` | SDK auto-advertises when `@server.list_prompts()` handler is registered; `@server.get_prompt()` handles `prompts/get` |
| PRMT-02 | `decommission_device_workflow` prompt guides the AI to call `decommission_device_preview` first, confirm with the user, then execute | Static `GetPromptResult` with user-role message containing step-by-step instruction text |
| PRMT-03 | `deploy_service_workflow` prompt guides the AI through pre-flight checks before service installation | Static `GetPromptResult` with user-role message referencing SSH connectivity check and service conflict check tools |
| PRMT-04 | `homelab_health_check` prompt guides the AI to read `homelab://vms`, `homelab://devices`, and `homelab://drift/latest` and summarize infra state | Static `GetPromptResult` with user-role message listing all three resource URIs explicitly |
</phase_requirements>
