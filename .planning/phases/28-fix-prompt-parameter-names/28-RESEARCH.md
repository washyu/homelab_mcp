# Phase 28: Fix Prompt Parameter Names - Research

**Researched:** 2026-03-19
**Domain:** MCP Prompt text content — parameter name accuracy in prompt_registry.py
**Confidence:** HIGH

## Summary

Phase 28 is a single-file, surgical text fix. The prompt text strings in
`src/homelab_mcp/prompt_registry.py` instruct agents to call tools using
`host=` as the parameter name. All four affected tools (`setup_mcp_admin`,
`ssh_discover`, `discover_and_map`, `verify_mcp_admin`) declare `hostname` as
the required parameter in their JSON schemas. A fifth case is the
`deploy_service_workflow` prompt, which also uses `host=` for its `ssh_discover`
and `list_installed_services` step. When an agent follows the prompt literally,
every tool call is rejected by MCP schema validation before the handler is
reached.

The fix is pure text: change `host=` to `hostname=` (and `host=` used as a
keyword argument in `install_service` instruction as well) in two prompt builder
functions. No schema changes, no handler changes, no new files. The existing
test suite already passes but does NOT assert parameter name accuracy — a new
regression test is needed to catch future regressions of this kind.

The audit document (`v1.4-MILESTONE-AUDIT.md`) identifies all four affected
lines precisely: prompt_registry.py lines 130, 136, 138, 140 for
`connect_to_device` and line 113 for `deploy_service_workflow`. The fix strategy
is completely unambiguous.

**Primary recommendation:** Fix the four `host=` occurrences in
`_build_connect_to_device_result` and the one `host=` occurrence in
`_build_deploy_service_result`, then add a test that asserts every parameter
name mentioned in each prompt matches the corresponding tool schema's declared
parameter names.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TOFU-03 | `connect_to_device` MCP prompt sequences full device onboarding workflow | Prompt exists and dispatches correctly; only the parameter name strings are wrong. Fix the text, add a regression test, and the requirement is fully satisfied. |
</phase_requirements>

## Standard Stack

No new dependencies. This phase uses only what is already installed.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp[cli] | already installed | Prompt types (`GetPromptResult`, `PromptMessage`) | Project-wide MCP framework |
| pytest | already installed | Unit tests | Project test framework |
| pytest-asyncio | already installed | Async test support | Already in use across test suite |

**Installation:** none required

## Architecture Patterns

### File to Modify
```
src/homelab_mcp/
└── prompt_registry.py   # Only file that needs changes
```

### Tests to Modify/Add
```
tests/
└── test_mcp_prompts.py  # Add parameter name accuracy assertions
```

### Pattern: Prompt Text as Agent Contract

Prompt text in `_build_connect_to_device_result` and `_build_deploy_service_result`
uses Python f-strings. The instructions include inline keyword argument syntax
(`tool_name with param="{value}"`). These strings are the contract between the
server and any MCP agent that invokes the prompt — they must use exact parameter
names from the tool schemas.

The pattern to follow for correct text:

```python
# Source: prompt_registry.py _build_connect_to_device_result (corrected)
text = f"""...
1. Call setup_mcp_admin with hostname="{hostname}" ...
4. Call ssh_discover with hostname="{hostname}" ...
5. Call discover_and_map with hostname="{hostname}" ...
6. Call verify_mcp_admin with hostname="{hostname}" ...
"""
```

```python
# Source: prompt_registry.py _build_deploy_service_result (corrected)
text = f"""...
1. Call ssh_discover with hostname="{target_host}" ...
2. Call list_installed_services with hostname="{target_host}" ...
3. Call install_service with service_name="{service_name}" and hostname="{target_host}".
"""
```

### Pattern: Parameter Name Regression Test

The existing `test_connect_to_device_prompt` test checks that tool names appear
in the prompt text, but never checks that parameter names are correct. The
regression guard must verify:

1. For each tool mentioned in a prompt, the parameter keyword in the prompt text
   matches the `required` list (or declared properties) in that tool's
   `inputSchema`.
2. Specifically: `hostname=` (not `host=`) appears in the prompt text for each
   tool call.

Concrete test approach — assert that the string `"host="` does NOT appear in
the combined prompt text for both prompts (since all tools use `hostname=`, not
`host=`), and assert that `hostname=` DOES appear for each tool call step.

```python
# Source: project test pattern from test_mcp_prompts.py
def test_connect_to_device_prompt_parameter_names() -> None:
    """TOFU-03: connect_to_device prompt uses hostname= not host= for all tool calls."""
    from homelab_mcp.prompt_registry import get_prompt_result

    result = get_prompt_result("connect_to_device", {"hostname": "myhost"})
    combined = " ".join(
        msg.content.text for msg in result.messages if hasattr(msg.content, "text")
    )
    assert "host=" not in combined, "All tools use hostname=, not host="
    # Four tool steps that require hostname=
    for tool in ("setup_mcp_admin", "ssh_discover", "discover_and_map", "verify_mcp_admin"):
        assert f'hostname="myhost"' in combined or "hostname=" in combined, (
            f"{tool} step must use hostname= parameter"
        )


def test_deploy_service_workflow_prompt_parameter_names() -> None:
    """PRMT-03: deploy_service_workflow prompt uses hostname= not host= for all tool calls."""
    from homelab_mcp.prompt_registry import get_prompt_result

    result = get_prompt_result(
        "deploy_service_workflow",
        {"service_name": "nginx", "target_host": "myhost"},
    )
    combined = " ".join(
        msg.content.text for msg in result.messages if hasattr(msg.content, "text")
    )
    assert "host=" not in combined, "All tools use hostname=, not host="
    assert "hostname=" in combined
```

### Anti-Patterns to Avoid

- **Fixing only `connect_to_device` and ignoring `deploy_service_workflow`:** The audit
  confirmed both prompts are affected. Fix both in the same commit.
- **Changing tool schemas to accept `host` as an alias:** Tool schemas are correct.
  The prompt text is wrong. Fix the prompt text, not the schemas.
- **Testing only for tool name presence:** The existing test already does that and
  still passes despite the bug. The new test must assert on the parameter keyword string.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema lookup in test | Custom schema loader | `SSH_TOOLS`, `NETWORK_TOOLS` from tool_schemas modules | Already importable; importing confirms schemas match at test time |

## Common Pitfalls

### Pitfall 1: `host=` appears in non-tool-call sentences

**What goes wrong:** The regex or substring check for `host=` might find false
positives if the prompt text contains other sentences using the word "host" as
part of a URL or description.

**How to avoid:** Inspect the full corrected prompt text before writing the assertion.
In the current prompt text, `host=` only appears in the four `with host=` tool call
instructions. After the fix, it will not appear at all. The assertion `"host=" not in
combined` is safe.

### Pitfall 2: `list_installed_services` schema uses a different parameter name

**What goes wrong:** The `deploy_service_workflow` prompt step 2 calls
`list_installed_services with host=`. If `list_installed_services` also uses
`hostname=`, fixing the text is straightforward. If it uses a different name
(e.g., `target`), the fix differs.

**Current state (verified):** `list_installed_services` is not in the SSH or
network schema files read above. Check `tools.py` or `infrastructure_tools_schema.py`
before writing the fix. Based on Phase 26 schema alignment work and the service
schema file (`service_tools_schema.py`), service tools consistently use `hostname`.
Confirm by searching for `list_installed_services` in the schema files.

**Warning signs:** If the plan writer finds `list_installed_services` uses `host`
and not `hostname`, that is a pre-existing schema issue outside Phase 28 scope —
leave it and fix only the line that references `ssh_discover`.

### Pitfall 3: Test asserts the wrong substituted value

**What goes wrong:** The prompt builder substitutes the `hostname` argument into
the f-string. If the test passes `{"hostname": "myhost"}`, the rendered text
contains `hostname="myhost"`, which includes the value `"myhost"`. Assertions
must account for the quotes in the rendered string.

**How to avoid:** Assert on `hostname=` (the keyword and equals sign) rather than
the full `hostname="myhost"` substring, since the core invariant is the keyword
name, not the specific test value.

## Code Examples

### Current Bug (confirmed at prompt_registry.py lines 130, 136, 138, 140)

```python
# Source: src/homelab_mcp/prompt_registry.py (current — BROKEN)
# Line 130
text = f"""...
1. Call setup_mcp_admin with host="{hostname}" to create the mcp_admin user ...
...
4. Call ssh_discover with host="{hostname}" to collect hardware ...
5. Call discover_and_map with host="{hostname}" to add the device ...
6. Call verify_mcp_admin with host="{hostname}" to confirm ...
"""
```

```python
# Source: src/homelab_mcp/prompt_registry.py (current — BROKEN)
# Line 113
text = f"""...
1. Call ssh_discover with host="{target_host}" to verify SSH connectivity.
2. Call list_installed_services with host="{target_host}" ...
...
3. Call install_service with service_name="{service_name}" and host="{target_host}".
"""
```

### Tool Schema Reference (all four tools require `hostname`)

```python
# Source: src/homelab_mcp/tool_schemas/ssh_tools_schema.py
"setup_mcp_admin": { "inputSchema": { "required": ["hostname"] } }
"ssh_discover":    { "inputSchema": { "required": ["hostname"] } }
"verify_mcp_admin": { "inputSchema": { "required": ["hostname"] } }
# Source: src/homelab_mcp/tool_schemas/network_tools_schema.py
"discover_and_map": { "inputSchema": { "required": ["hostname"] } }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prompt text used `host=` | Prompt text must use `hostname=` | Phase 28 (this phase) | E2E onboarding flow works end-to-end |

## Open Questions

1. **Does `list_installed_services` use `hostname` or `host`?**
   - What we know: All service tools in `service_tools_schema.py` use `hostname`
     consistently in their property definitions, but `list_installed_services` is
     not present in that file. It may be in `tools.py` (legacy location) or
     elsewhere.
   - What's unclear: The exact parameter name used by `list_installed_services`.
   - Recommendation: The planner should include a task that searches for
     `list_installed_services` in all schema files and `tools.py`, confirms the
     parameter name, then writes the fix accordingly.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_mcp_prompts.py -v` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOFU-03 | `connect_to_device` prompt uses `hostname=` in all tool call steps | unit | `uv run pytest tests/test_mcp_prompts.py::test_connect_to_device_prompt_parameter_names -x` | ❌ Wave 0 |
| TOFU-03 | `deploy_service_workflow` prompt uses `hostname=` in all tool call steps | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_prompt_parameter_names -x` | ❌ Wave 0 |
| TOFU-03 | No prompt text contains `host=` substring | unit | `uv run pytest tests/test_mcp_prompts.py -k "parameter_names" -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_mcp_prompts.py -v`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full unit suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mcp_prompts.py` — add `test_connect_to_device_prompt_parameter_names` (new function in existing file)
- [ ] `tests/test_mcp_prompts.py` — add `test_deploy_service_workflow_prompt_parameter_names` (new function in existing file)

*(Framework install: not needed — pytest already installed and configured)*

## Sources

### Primary (HIGH confidence)
- `src/homelab_mcp/prompt_registry.py` — read in full; lines 130, 136, 138, 140 confirmed as `host=`; line 113 confirmed as `host=` in deploy workflow
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — read in full; `setup_mcp_admin`, `ssh_discover`, `verify_mcp_admin` all declare `"required": ["hostname"]`
- `src/homelab_mcp/tool_schemas/network_tools_schema.py` — read in full; `discover_and_map` declares `"required": ["hostname"]`
- `.planning/v1.4-MILESTONE-AUDIT.md` — read in full; lines 130, 136, 138, 140 and 113 identified as root cause; fix strategy stated explicitly
- `tests/test_mcp_prompts.py` — read in full; 7 existing tests all pass; no test currently checks parameter keyword names

### Secondary (MEDIUM confidence)
- `src/homelab_mcp/tool_schemas/service_tools_schema.py` — read in full; `install_service` and `list_installed_services` absent (not in this file); consistent `hostname` usage in all service tools that are present

## Metadata

**Confidence breakdown:**
- Bug location: HIGH — audit document and direct file read agree on exact lines
- Fix content: HIGH — all four affected schemas confirmed to use `hostname`
- Test strategy: HIGH — existing test file structure is clear; new tests follow established pattern
- `list_installed_services` parameter name: MEDIUM — schema file does not contain it; needs one search before writing the fix

**Research date:** 2026-03-19
**Valid until:** Stable (prompt text and schemas do not change between phases unless explicitly modified)
