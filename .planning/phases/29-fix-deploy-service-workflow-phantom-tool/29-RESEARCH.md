# Phase 29: Fix deploy_service_workflow Phantom Tool - Research

**Researched:** 2026-03-19
**Domain:** MCP Prompt Registry — service workflow prompt text correction
**Confidence:** HIGH

## Summary

The `deploy_service_workflow` prompt in `src/homelab_mcp/prompt_registry.py` (line 114) instructs agents to call `list_installed_services` as step 2 of the deployment pre-flight check. This tool does not exist: it has no schema in any `tool_schemas/*.py` file, no handler in `tool_handlers/`, and no entry in `TOOL_HANDLERS`. Any agent executing this prompt will fail at step 2 with `ValueError: Unknown tool: list_installed_services`.

The fix is a targeted text substitution in `_build_deploy_service_result()` replacing the phantom tool reference with a valid registered tool. The audit report (v1.4-MILESTONE-AUDIT.md) identifies two candidates: `get_service_status` (checks running state of a named service) or `list_available_services` (lists installable services). The conflict-detection intent of step 2 — "check for conflicts with service_name" — is best served by `get_service_status`, which actually inspects whether the named service is already running on the target host.

An existing test (`test_deploy_service_workflow_prompt`) at line 76–78 of `tests/test_mcp_prompts.py` checks for `list_installed_services` in the combined text as an OR condition alongside `ssh_discover`. This test must be updated to reflect the replacement tool. A new regression test must assert that `list_installed_services` never appears in the prompt body.

**Primary recommendation:** Replace `list_installed_services` with `get_service_status` in `_build_deploy_service_result()` and update/add tests in `tests/test_mcp_prompts.py`.

## Standard Stack

### Core (all pre-existing, no new dependencies)

| Module | Version | Purpose | Note |
|--------|---------|---------|------|
| `src/homelab_mcp/prompt_registry.py` | current | Static prompt text builders | Single file to edit |
| `tests/test_mcp_prompts.py` | current | Prompt content regression tests | Contains conflicting assertion on line 77–78 |
| `src/homelab_mcp/tool_schemas/service_tools_schema.py` | current | Source of truth for registered tools | Confirms `get_service_status` schema exists |
| `src/homelab_mcp/tool_handlers/__init__.py` | current | Source of truth for TOOL_HANDLERS | Confirms `get_service_status` handler exists |

**No new packages required.** This is a prompt-text and test edit only.

## Architecture Patterns

### How the Prompt System Works

```
prompt_registry.py
├── HOMELAB_PROMPTS: dict[str, types.Prompt]   # metadata (name, description, args)
└── get_prompt_result(name, args)               # dispatcher → builder functions
    ├── _build_decommission_result(args)
    ├── _build_deploy_service_result(args)      # ← EDIT HERE
    ├── _build_connect_to_device_result(args)
    └── _build_health_check_result(args)
```

The prompt builders produce a plain f-string body. No tool invocation happens inside `prompt_registry.py` — the string is handed to the MCP client which then calls tools as instructed. The fix is therefore purely textual: change the tool name in the instruction string.

### Pattern: Prompt Tool Reference Convention

All other prompts in the file use this pattern for tool calls in prompt text:

```python
# Source: src/homelab_mcp/prompt_registry.py (lines 89-99, 130-143)
f'Call {tool_name} with hostname="{hostname}"'
f'Call {tool_name} with service_name="{service_name}" and hostname="{target_host}"'
```

The replacement must follow the same pattern and use parameter names that exactly match the target tool's schema.

### `get_service_status` Schema (valid replacement)

From `tool_schemas/service_tools_schema.py` lines 79–104:
- Required parameters: `service_name` (string), `hostname` (string)
- Optional: `username` (string), `password` (string)
- Call syntax: `get_service_status with service_name="{service_name}" and hostname="{target_host}"`

### `list_available_services` Schema (alternative)

From `tool_schemas/service_tools_schema.py` lines 5–9:
- No parameters — returns the catalog of installable services
- Does NOT check whether a specific service is already running on the target
- Less appropriate for conflict detection

### Anti-Patterns to Avoid

- **Don't create a new `list_installed_services` tool:** The audit report explicitly states the fix is to update the prompt text. Implementing the phantom tool would require a new schema, handler, and SSH implementation — far more scope than needed.
- **Don't use `list_available_services` for conflict detection:** It lists the service catalog, not what's running on the host. A conflict check needs per-host state.
- **Don't modify the existing `test_deploy_service_workflow_prompt` in-place and leave a passing-but-wrong assertion:** The OR condition on line 77–78 currently accepts `list_installed_services` as a valid keyword. After the fix it must not.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Conflict detection | Custom `list_installed_services` tool | `get_service_status` | Already registered, already implemented, checks per-host per-service running state |
| Test pattern | Novel assertion framework | Follow existing `test_mcp_prompts.py` patterns | All other prompt tests use `combined_text` assertion style |

## Common Pitfalls

### Pitfall 1: Leaving the OR Test Assertion Unchanged
**What goes wrong:** The existing test at line 76–78 uses `any(keyword in combined_text for keyword in ("pre-flight", "preflight", "ssh_discover", "list_installed_services"))`. After the fix this still passes because `ssh_discover` is present — the phantom tool is no longer guarded against.
**How to avoid:** Add a separate negative assertion: `assert "list_installed_services" not in combined_text`.
**Warning signs:** Test passes but the original phantom name could silently re-enter the prompt.

### Pitfall 2: Wrong Parameter Name for `get_service_status`
**What goes wrong:** The deploy workflow uses `target_host` as the prompt argument name (not `hostname`). The interpolation must map `target_host` → `hostname=` for the tool call.
**Root cause:** `deploy_service_workflow` uses `target_host` in its argument schema and in `_build_deploy_service_result`. The tool schema uses `hostname`. The current `ssh_discover` call on line 113 already correctly does `hostname="{target_host}"` — the same pattern must be followed for `get_service_status`.
**How to avoid:** Copy the pattern from line 113 exactly: `hostname="{target_host}"`.

### Pitfall 3: Forgetting `service_name` in `get_service_status` Call
**What goes wrong:** `get_service_status` requires both `service_name` and `hostname`. If only `hostname` is passed the agent call will fail schema validation.
**How to avoid:** The prompt text must include both: `get_service_status with service_name="{service_name}" and hostname="{target_host}"`.

### Pitfall 4: Updating Test Without Verifying Test Still Passes
**What goes wrong:** Changing the existing assertion to remove `list_installed_services` and add `get_service_status` without running the suite — the test could still fail if `get_service_status` isn't present in the prompt text.
**How to avoid:** Assert positively that `get_service_status` appears in `combined_text`.

## Code Examples

### Current Broken Prompt Text (line 113–118)
```python
# Source: src/homelab_mcp/prompt_registry.py lines 110–118
text = f"""Follow these steps to deploy {service_name} on {target_host}:

Pre-flight checks:
1. Call ssh_discover with hostname="{target_host}" to verify SSH connectivity.
2. Call list_installed_services with hostname="{target_host}" to check for conflicts with {service_name}.

If pre-flight checks pass:
3. Call install_service with service_name="{service_name}" and hostname="{target_host}".
4. Report the installation result to the user."""
```

### Required Fix (step 2 replacement)
```python
# Replace line 114 only
2. Call get_service_status with service_name="{service_name}" and hostname="{target_host}" to check whether {service_name} is already installed.
```

### Existing Test That Needs Updating (test_mcp_prompts.py lines 76–78)
```python
# Source: tests/test_mcp_prompts.py lines 75–78
assert any(
    keyword in combined_text for keyword in ("pre-flight", "preflight", "ssh_discover", "list_installed_services")
)
```

After fix: the `list_installed_services` keyword must be removed from the OR list and a negative assertion added.

### Regression Test Pattern to Add
```python
# New test — follow existing pattern in test_mcp_prompts.py
def test_deploy_service_workflow_no_phantom_tool() -> None:
    """Phase 29: deploy_service_workflow must not reference unregistered list_installed_services."""
    from homelab_mcp.prompt_registry import get_prompt_result

    result = get_prompt_result(
        "deploy_service_workflow",
        {"service_name": "nginx", "target_host": "myhost"},
    )
    combined = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text"))
    assert "list_installed_services" not in combined, (
        "deploy_service_workflow must not reference phantom tool list_installed_services"
    )
    assert "get_service_status" in combined, (
        "deploy_service_workflow step 2 must use registered get_service_status tool"
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phantom `list_installed_services` in step 2 | Valid `get_service_status` reference | Phase 29 | E2E deploy workflow becomes functional; agent no longer fails at step 2 |

**Deprecated:**
- `list_installed_services` reference: never implemented, must be removed permanently

## Open Questions

1. **Is `get_service_status` the right semantic fit?**
   - What we know: It checks the status of a named service on a named host. The audit report lists it as one of the two candidates.
   - What's unclear: Whether "checking for conflicts" means "is it already running" or "would installing conflict with another service." `get_service_status` covers the former.
   - Recommendation: Use `get_service_status` — it's the closest semantic match and requires both `service_name` and `hostname`, making it directly actionable in context.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_mcp_prompts.py -v` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

This phase has no formal requirement IDs. The behavioral requirements are:

| Behavior | Test Type | Automated Command |
|----------|-----------|-------------------|
| `deploy_service_workflow` prompt does not reference `list_installed_services` | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_no_phantom_tool -x` |
| `deploy_service_workflow` step 2 references `get_service_status` | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_no_phantom_tool -x` |
| Updated PRMT-03 test still passes (no regression) | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_prompt -x` |
| Parameter name test still passes (no regression) | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_prompt_parameter_names -x` |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_mcp_prompts.py -v`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_mcp_prompts.py` — add `test_deploy_service_workflow_no_phantom_tool` (new test for phantom tool regression guard)

## Sources

### Primary (HIGH confidence)
- `src/homelab_mcp/prompt_registry.py` — direct inspection of `_build_deploy_service_result()` confirms phantom reference on line 114
- `src/homelab_mcp/tool_handlers/__init__.py` — `TOOL_HANDLERS` dict confirms `list_installed_services` is absent, `get_service_status` is present
- `src/homelab_mcp/tool_schemas/service_tools_schema.py` — `SERVICE_TOOLS` dict confirms `get_service_status` schema with `service_name` + `hostname` required
- `tests/test_mcp_prompts.py` — existing OR assertion on line 77–78 confirmed; must be updated
- `.planning/v1.4-MILESTONE-AUDIT.md` — audit report confirms gap origin, root cause, and two fix candidates

### Secondary (MEDIUM confidence)
- None needed — all findings verified from direct source inspection.

## Metadata

**Confidence breakdown:**
- The bug: HIGH — directly confirmed in source, audit report, and TOOL_HANDLERS inspection
- The fix (use `get_service_status`): HIGH — both candidates confirmed registered; semantic fit confirmed by schema inspection
- Test changes needed: HIGH — existing test logic directly read and analyzed
- No new dependencies: HIGH — pure text and test change

**Research date:** 2026-03-19
**Valid until:** Until `prompt_registry.py` or `SERVICE_TOOLS` keys change (stable, 30+ days)

<phase_requirements>
## Phase Requirements

No formal requirement IDs are assigned to this phase. The phase closes an integration gap identified in the v1.4 milestone audit.

| Behavior | Research Support |
|----------|-----------------|
| `deploy_service_workflow` step 2 calls a registered tool | `get_service_status` confirmed in TOOL_HANDLERS and SERVICE_TOOLS |
| Phantom `list_installed_services` reference removed | Direct line 114 inspection confirms the exact text to replace |
| Regression test guards against re-introduction | Existing test pattern in test_mcp_prompts.py supports new negative assertion |
</phase_requirements>
