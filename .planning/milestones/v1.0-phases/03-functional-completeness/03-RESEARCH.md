# Phase 3: Functional Completeness - Research

**Researched:** 2026-03-09
**Domain:** MCP protocol compliance, infrastructure lifecycle hooks, service installation, error observability
**Confidence:** HIGH

## Summary

Phase 3 addresses six requirements across two domains: functional completeness (FUNC-01 through FUNC-04) and MCP protocol compliance (MCP-01, MCP-02). The codebase has clear, well-defined gaps for each requirement -- no ambiguity about what needs to change.

The MCP SDK (`mcp` package) already provides `ToolAnnotations` and `CallToolResult` types with the exact fields needed (readOnlyHint, destructiveHint, idempotentHint, isError). The current `handle_call_tool` handler swallows errors into text content, preventing the SDK from setting `isError: true`. The `_update_sitemap_after_deployment` and `_rediscover_device_after_changes` functions are stub `pass` bodies. The `_install_script_service` method returns a TODO error. There are ~6 genuine silent `except: pass` patterns in non-abstract code.

**Primary recommendation:** Work bottom-up: (1) implement the stub functions, (2) replace silent exception handlers with logging, (3) add tool annotations to the schema/list_tools layer, (4) restructure error flow so errors raise exceptions that the SDK catches and marks with isError.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FUNC-01 | Sitemap updates automatically after infrastructure deployment | `_update_sitemap_after_deployment()` at infrastructure_crud.py:752 is a stub `pass` -- needs to call `discover_and_store()` for each deployed device |
| FUNC-02 | Device info refreshes after configuration changes | `_rediscover_device_after_changes()` at infrastructure_crud.py:945 is a stub `pass` -- needs to SSH-discover the device and update sitemap |
| FUNC-03 | Script-based service installation works end-to-end | `_install_script_service()` at service_installer.py:455 returns TODO error -- needs to read `installation_script` from template YAML and execute via SSH |
| FUNC-04 | Silent exception handlers replaced with debug/warning logging | ~6 silent `except: pass` patterns in sitemap.py, ssh_tools.py, service_installer.py, database.py need logger.debug/warning calls |
| MCP-01 | All tools annotated with readOnlyHint, destructiveHint, idempotentHint | `handle_list_tools()` in server.py creates `types.Tool()` without `annotations` parameter -- needs `ToolAnnotations` per tool |
| MCP-02 | All error responses include isError: true | SDK auto-sets `isError=True` on exception, but handlers return error dicts as text content (never raise) -- need to detect error results and either raise or return `CallToolResult` directly |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp | installed | ToolAnnotations, CallToolResult, types.Tool | Already in project; provides exact types needed |
| logging (stdlib) | N/A | Replace silent passes with debug/warning logs | Already used throughout the project |
| asyncssh | installed | SSH execution for script-based install | Already used for all SSH operations |

### Supporting
No new dependencies needed. All requirements are implementable with existing libraries.

## Architecture Patterns

### Pattern 1: Tool Annotations Registry
**What:** A data dict mapping each tool name to its `ToolAnnotations`, co-located with the schema definitions.
**When to use:** MCP-01 -- annotating all 49 tools.
**Example:**
```python
# Source: MCP SDK types.Tool and types.ToolAnnotations
from mcp.types import ToolAnnotations

# Add to each schema file alongside the tool dict
TOOL_ANNOTATIONS: dict[str, ToolAnnotations] = {
    "ssh_discover": ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "deploy_vm": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "remove_vm": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
    ),
}
```

### Pattern 2: Error-as-Exception for isError Compliance
**What:** The SDK `call_tool` decorator catches exceptions and auto-sets `isError=True`. Currently, handlers return error dicts as content text, which the SDK treats as success.
**When to use:** MCP-02 -- every tool error response.
**Approach options:**

Option A (Preferred): Modify `handle_call_tool` in server.py to inspect the handler result for error status and raise a custom exception:
```python
@server.call_tool()
async def handle_call_tool(name, arguments):
    handler = get_tool_handler(name)
    result = await handler(arguments or {})

    # Detect error results and raise so SDK sets isError=True
    if _is_error_result(result):
        raise ToolError(_extract_error_text(result))

    return _convert_result(result)
```

Option B: Return `types.CallToolResult` directly instead of `list[Content]`. However, the SDK decorator expects `Iterable[Content]` as the return type (see lowlevel/server.py:387), so this would require modifying the decorator usage. Not recommended.

**Recommendation:** Option A. The SDK already wraps exceptions into `CallToolResult(isError=True)`. Create a `ToolError` exception class that carries the formatted error text.

### Pattern 3: Sitemap Auto-Refresh via discover_and_store
**What:** After deployment or config change, SSH-discover the affected device(s) and upsert into sitemap.
**When to use:** FUNC-01, FUNC-02.
**Example:**
```python
async def _update_sitemap_after_deployment(manager, results):
    for result in results:
        if result.get("status") == "success" and result.get("device_id"):
            conn_info = await manager.get_device_connection_info(result["device_id"])
            if conn_info:
                await discover_and_store(
                    manager.sitemap,
                    conn_info["hostname"],
                    conn_info["username"],
                )
```

### Pattern 4: Script-Based Installation via SSH
**What:** Read `installation_script` from the YAML template, substitute variables, upload to target host, execute via SSH.
**When to use:** FUNC-03 -- `_install_script_service`.
**Example:**
```python
async def _install_script_service(self, service_name, service, hostname, username, password, config_override):
    installation = service.get("installation", {})
    script_content = installation.get("installation_script", "")
    if not script_content:
        return {"status": "error", "error": f"No installation script in template for {service_name}"}

    # Substitute config variables
    if config_override:
        for key, value in config_override.items():
            script_content = script_content.replace(f"${{{key}}}", str(value))

    # Upload and execute via SSH
    result = await ssh_execute_command(
        hostname=hostname, username=username, password=password,
        command=f"cat << 'SCRIPT_EOF' | sudo bash\n{script_content}\nSCRIPT_EOF"
    )
    return json.loads(result)
```

### Anti-Patterns to Avoid
- **Swallowing exceptions silently:** `except (ValueError, AttributeError): pass` -- always log at minimum `logger.debug()`
- **Error-as-content:** Returning `{"status": "error", ...}` as text content with `isError=False` -- MCP clients cannot distinguish errors from success
- **Stub functions:** `async def func(): pass` -- always at minimum raise `NotImplementedError` or implement

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Error detection in results | Custom error parsing per handler | Centralized `_is_error_result()` that checks JSON for `"status": "error"` | 49 tools, consistent pattern needed |
| Tool annotation data | Inline annotations in server.py | Per-schema-file annotation dicts merged like tool schemas | Keeps annotations co-located with schemas for maintainability |
| Script execution | Custom SSH upload+execute | Existing `ssh_execute_command()` with heredoc | Already handles SSH connection, auth, timeouts |

## Common Pitfalls

### Pitfall 1: isError Detection False Positives
**What goes wrong:** Some handlers return JSON strings, some return dicts. Error detection must handle both formats consistently.
**Why it happens:** Legacy handlers return varied formats -- some `{"content": [{"type": "text", "text": "{\"status\":\"error\",...}"}]}`, some return flat dicts.
**How to avoid:** Parse the text content as JSON and check for `"status": "error"` key. Handle `json.JSONDecodeError` gracefully.
**Warning signs:** Tests pass but MCP clients still see `isError: false` on errors.

### Pitfall 2: ToolAnnotations Must Match Tool Behavior
**What goes wrong:** Marking a tool as `readOnlyHint=True` when it actually modifies state.
**Why it happens:** 49 tools is a lot; easy to misclassify.
**How to avoid:** Categorize systematically by handler module (ssh_handlers = mostly read-only except setup/execute, infrastructure_handlers = mostly destructive, etc.).
**Warning signs:** MCP client auto-approves a destructive operation because it was marked read-only.

### Pitfall 3: Script Installation Security
**What goes wrong:** Script injection via config_override values or template variable substitution.
**Why it happens:** Naive string replacement in shell scripts.
**How to avoid:** Use environment variables instead of string substitution for config values. Pass config via `env` parameter to SSH, not inline in the script.
**Warning signs:** Config values containing backticks, semicolons, or `$(...)` get executed.

### Pitfall 4: Rediscovery Failures Masking Success
**What goes wrong:** Infrastructure deploys successfully but the post-deployment rediscovery fails (SSH timeout, etc.), and the whole operation appears to fail.
**Why it happens:** `_update_sitemap_after_deployment` could raise an exception that propagates up.
**How to avoid:** Wrap rediscovery in try/except, log failures as warnings, don't fail the overall operation.
**Warning signs:** Deployment returns error even though VMs were created successfully.

### Pitfall 5: Silent Exception Categories
**What goes wrong:** Confusing abstract method `pass` bodies, import fallback `except ImportError`, and genuine silent error swallowing.
**Why it happens:** Grepping for `except.*pass` returns all three categories.
**How to avoid:** Only change genuine silent exception handlers. Leave abstract methods and import fallbacks alone. The specific targets are:
- `sitemap.py:190` -- `except (ValueError, AttributeError): pass` in topology analysis
- `sitemap.py:277` -- `except (ValueError, AttributeError): pass` in suggest_deployments
- `ssh_tools.py:482` -- `except json.JSONDecodeError: pass` in network discovery fallback
- `ssh_tools.py:576` -- `except json.JSONDecodeError: pass` in block device parsing
- `service_installer.py:720` -- `except json.JSONDecodeError: pass` in terraform output parsing
- `database.py:403` -- `except json.JSONDecodeError: pass` in discovery history parsing

## Code Examples

### Tool Annotations Classification (all 49 tools)

Based on codebase analysis, here is the complete classification:

**Read-Only Tools (readOnlyHint=True, destructiveHint=False):**
- ssh_discover, get_network_sitemap, analyze_network_topology, suggest_deployments, get_device_changes
- list_available_services, get_service_info, check_service_requirements, get_service_status
- list_vms, get_vm_status, get_vm_logs
- list_registered_servers
- search_proxmox_scripts, get_proxmox_script_info, list_proxmox_resources, get_proxmox_node_status, get_proxmox_vm_status
- verify_mcp_admin, check_ansible_service
- validate_infrastructure_changes (validate_only is default)

**Mutating Non-Destructive Tools (readOnlyHint=False, destructiveHint=False):**
- discover_and_map, bulk_discover_and_map (creates/updates records)
- setup_mcp_admin, update_mcp_admin_groups (creates user)
- ssh_execute_command, start_interactive_shell (executes arbitrary commands -- special case)
- deploy_infrastructure, deploy_vm, install_service
- update_device_config, update_server_credentials, scale_services
- register_server
- create_proxmox_vm, create_proxmox_lxc, clone_proxmox_vm
- create_infrastructure_backup
- plan_terraform_service, refresh_terraform_service, run_ansible_playbook

**Destructive Tools (readOnlyHint=False, destructiveHint=True):**
- decommission_device, remove_vm, remove_server
- delete_proxmox_vm, destroy_terraform_service
- rollback_infrastructure_changes

**Idempotent Tools (idempotentHint=True):**
- All read-only tools
- discover_and_map, bulk_discover_and_map (upsert)
- setup_mcp_admin (checks if exists first)
- register_server (upsert)
- plan_terraform_service, refresh_terraform_service

**Special Case -- manage_proxmox_vm:**
- readOnlyHint=False, destructiveHint=False (start/stop/restart are not data-destructive), idempotentHint=True
- Note: `control_vm` similarly -- start/stop/restart

### Error Detection Helper
```python
def _is_error_result(result: dict[str, Any]) -> bool:
    """Check if a handler result represents an error."""
    # Check direct status field
    if result.get("status") == "error":
        return True
    # Check nested content for error JSON
    content = result.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    parsed = json.loads(item.get("text", ""))
                    if isinstance(parsed, dict) and parsed.get("status") == "error":
                        return True
                except (json.JSONDecodeError, TypeError):
                    pass
    return False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No tool annotations | ToolAnnotations in types.Tool | MCP spec 2024-11-05 | Clients can show safety warnings |
| isError optional | isError on all CallToolResult | MCP spec 2024-11-05 | Clients distinguish errors from success |

**Key SDK detail:** The `lowlevel.Server.call_tool()` decorator (lowlevel/server.py:383-405) automatically wraps the handler:
- Success path: `CallToolResult(content=list(results), isError=False)`
- Exception path: `CallToolResult(content=[TextContent(text=str(e))], isError=True)`

This means the simplest path to MCP-02 compliance is to raise exceptions for errors rather than returning error dicts.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `uv run pytest tests/ -m "not integration" -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUNC-01 | Sitemap auto-updates after deployment | unit | `uv run pytest tests/test_infrastructure_crud.py -k "sitemap_after_deploy" -x` | No -- Wave 0 |
| FUNC-02 | Device info refreshes after config change | unit | `uv run pytest tests/test_infrastructure_crud.py -k "rediscover_after_change" -x` | No -- Wave 0 |
| FUNC-03 | Script-based install works end-to-end | unit | `uv run pytest tests/test_service_installer.py -k "install_script" -x` | No -- Wave 0 |
| FUNC-04 | No silent except:pass remains | unit | `uv run pytest tests/test_silent_exceptions.py -x` | No -- Wave 0 |
| MCP-01 | All tools have annotations | unit | `uv run pytest tests/test_server.py -k "annotations" -x` | No -- Wave 0 |
| MCP-02 | Error responses include isError | unit | `uv run pytest tests/test_server.py -k "is_error" -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -m "not integration" -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] `tests/test_infrastructure_crud.py` -- add tests for `_update_sitemap_after_deployment` and `_rediscover_device_after_changes`
- [ ] `tests/test_service_installer.py` -- add test for `_install_script_service` with mocked SSH
- [ ] `tests/test_silent_exceptions.py` -- AST-based test scanning for bare `except: pass` patterns
- [ ] `tests/test_server.py` -- add tests for ToolAnnotations presence and isError on error results

## Open Questions

1. **ssh_execute_command and start_interactive_shell classification**
   - What we know: These tools execute arbitrary commands on remote hosts, which could be read-only or destructive depending on the command.
   - What's unclear: Should they be marked `destructiveHint=True` (conservative) or `destructiveHint=False` (reflects typical use)?
   - Recommendation: Mark as `destructiveHint=False` but `readOnlyHint=False` -- they are conduits, not inherently destructive. Add `openWorldHint=True` since they interact with external systems.

2. **Script injection in config_override**
   - What we know: YAML templates contain shell scripts with variable placeholders.
   - What's unclear: Whether to sanitize config_override values or use env vars.
   - Recommendation: Use environment variables exported before script execution, not string substitution. This is the standard secure pattern for shell script parameterization.

## Sources

### Primary (HIGH confidence)
- MCP SDK source: `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` -- call_tool decorator, isError handling
- MCP SDK types: `mcp.types.ToolAnnotations` -- readOnlyHint, destructiveHint, idempotentHint, openWorldHint fields verified via runtime introspection
- MCP SDK types: `mcp.types.CallToolResult` -- isError field verified via runtime introspection
- Project source: Direct analysis of all files in `src/homelab_mcp/`

### Secondary (MEDIUM confidence)
- Tool classification (49 tools) -- based on reading handler implementations and schema descriptions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all types verified in installed SDK
- Architecture: HIGH -- SDK behavior verified by reading source code directly
- Pitfalls: HIGH -- identified from actual code patterns
- Tool classifications: MEDIUM -- 49 tools classified by reading code, but edge cases exist

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable -- no fast-moving dependencies)
