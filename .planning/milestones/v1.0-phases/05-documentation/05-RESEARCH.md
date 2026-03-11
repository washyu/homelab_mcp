# Phase 5: Documentation - Research

**Researched:** 2026-03-11
**Domain:** Technical documentation for a Python MCP server
**Confidence:** HIGH

## Summary

Phase 5 is a documentation-only phase with no code changes. The project already has significant documentation scattered across README.md, docs/, .env.example, and CLAUDE.md, but it is outdated (tool counts vary: "34+", "41", "49" across files), inconsistent, and missing a structured tool reference. The actual tool count is 49 tools across 7 schema categories.

The primary work is: (1) a clean setup guide that takes a user from zero to first tool call, (2) a comprehensive tool reference auto-derivable from the tool_schemas/ directory, and (3) a configuration reference extractable from config.py and run_server.py.

**Primary recommendation:** Write three focused markdown documents. Extract tool reference data programmatically from tool_schemas/*.py files to ensure accuracy. Extract configuration data from config.py (MCPConfig, HTTPConfig, DatabaseConfig classes) and run_server.py (CLI args).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-01 | Setup guide covers clone, install, configure, connect, and verify | Existing README.md and docs/DEPLOYMENT.md provide partial content but need consolidation into a single authoritative guide with verification steps |
| DOCS-02 | Tool reference documents all tools with arguments, returns, and examples | 49 tools defined in src/homelab_mcp/tool_schemas/ with JSON Schema definitions; tool_handlers/ contains return value patterns |
| DOCS-03 | Configuration reference lists all environment variables with defaults | config.py has 3 config classes (MCPConfig, HTTPConfig, DatabaseConfig) with ~20 env vars; run_server.py adds CLI args; .env.example exists but is outdated |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Markdown | N/A | Documentation format | Universal, renders on GitHub, readable as plain text |

### Supporting
No additional libraries needed. This phase produces only .md files.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plain markdown | MkDocs/Sphinx | Overkill for a single-server project; markdown renders natively on GitHub |
| Manual tool reference | Auto-generated from schemas | Manual risks drift; but auto-gen adds build complexity -- recommend manual with schemas as source of truth |

## Architecture Patterns

### Recommended Documentation Structure
```
docs/
  setup-guide.md          # DOCS-01: Clone to first tool call
  tool-reference.md       # DOCS-02: All 49 tools documented
  configuration.md        # DOCS-03: All env vars and CLI args
```

### Pattern 1: Single Source of Truth for Tool Reference
**What:** Write tool documentation by reading each tool schema from `src/homelab_mcp/tool_schemas/*_schema.py` and documenting arguments, types, required/optional, defaults, and descriptions already present in JSON Schema.
**When to use:** For DOCS-02.
**Details:** Each schema file has a dict literal with keys being tool names, containing `description` and `inputSchema` with `properties` and `required`. The tool_annotations.py file adds `readOnlyHint`, `destructiveHint`, and `idempotentHint` metadata.

Tool categories (from schema files):
- SSH Tools (6): ssh_discover, setup_mcp_admin, verify_mcp_admin, ssh_execute_command, start_interactive_shell, update_mcp_admin_groups
- Network Tools (6): discover_and_map, bulk_discover_and_map, get_network_sitemap, analyze_network_topology, suggest_deployments, get_device_changes
- Infrastructure Tools (7): deploy_infrastructure, update_device_config, decommission_device, scale_services, validate_infrastructure_changes, create_infrastructure_backup, rollback_infrastructure_changes
- VM Tools (6): deploy_vm, control_vm, get_vm_status, list_vms, get_vm_logs, remove_vm
- Service Tools (10): list_available_services, get_service_info, check_service_requirements, install_service, get_service_status, plan_terraform_service, destroy_terraform_service, refresh_terraform_service, check_ansible_service, run_ansible_playbook
- Credential Tools (4): register_server, list_registered_servers, update_server_credentials, remove_server
- Proxmox Tools (10): search_proxmox_scripts, get_proxmox_script_info, list_proxmox_resources, get_proxmox_node_status, get_proxmox_vm_status, manage_proxmox_vm, create_proxmox_lxc, create_proxmox_vm, clone_proxmox_vm, delete_proxmox_vm

### Pattern 2: Configuration Reference from Source Code
**What:** Extract all environment variables from config.py classes and run_server.py CLI arguments. Document variable name, default value, description, and which feature it controls.
**When to use:** For DOCS-03.
**Details:** Key env vars found in source:

From MCPConfig (config.py):
- MCP_DEBUG (default: false)
- MCP_LOG_LEVEL (default: INFO)
- SSH_TIMEOUT (default: 10)
- SSH_RETRIES (default: 3)
- DISCOVERY_BATCH_SIZE (default: 10)
- DISCOVERY_TIMEOUT (default: 300)
- PROXMOX_VERIFY_SSL (default: true)
- PROXMOX_CA_CERT (default: none)
- ENABLE_POSTGRESQL (default: false)
- ENABLE_RESOURCE_POOLS (default: false)

From HTTPConfig (config.py):
- MCP_HTTP_ENABLED (default: false)
- MCP_HTTP_HOST (default: 0.0.0.0)
- MCP_HTTP_PORT (default: 8080)
- MCP_API_KEY (default: none)
- MCP_AUTH_ENABLED (default: true)

From DatabaseConfig (config.py):
- DATABASE_TYPE (default: sqlite)
- SQLITE_PATH (default: ~/.mcp/sitemap.db)
- POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

From run_server.py CLI / .env.example:
- MCP_SSL_CERT, MCP_SSL_KEY
- PROXMOX_HOST, PROXMOX_USER, PROXMOX_PASSWORD, PROXMOX_API_TOKEN

### Pattern 3: Setup Guide as Narrative Walkthrough
**What:** Linear guide: prerequisites -> clone -> install -> configure env -> choose transport -> connect MCP client -> verify with a tool call.
**When to use:** For DOCS-01.
**Details:** The existing README has a quick start but lacks the configure and verify steps. The setup guide must cover:
1. Prerequisites (Python 3.12+, uv, a Proxmox server or SSH-accessible Linux host)
2. Clone and install (`git clone`, `uv sync`)
3. Configure (copy .env.example, set PROXMOX_HOST at minimum)
4. Choose transport mode (stdio for Claude Desktop, HTTP for OpenWebUI)
5. Connect to MCP client (Claude Desktop config, Claude Code config)
6. Verify with a test tool call (e.g., `list_available_services` or `get_network_sitemap`)

### Anti-Patterns to Avoid
- **Documenting tool counts as magic numbers:** The README says "34+", "41", "49" in different places. Use "see Tool Reference" instead of hardcoding counts.
- **Duplicating content across files:** The README, CLAUDE_SETUP.md, and DEPLOYMENT.md all have overlapping setup instructions. The new setup guide should be authoritative; README should link to it.
- **Documenting return formats from memory:** Return formats should be verified by checking handler implementations or test assertions.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool reference accuracy | Writing tool args from memory | Read tool_schemas/*.py as source of truth | Schemas are the canonical definition; manual docs will drift |
| Config var inventory | Listing env vars from memory | Read config.py classes systematically | All env vars are in os.getenv() calls in config.py |

## Common Pitfalls

### Pitfall 1: Outdated Tool Counts
**What goes wrong:** README says different numbers in different places (34+, 41, 49)
**Why it happens:** Tools were added over time, documentation wasn't updated
**How to avoid:** Don't hardcode tool counts; reference the tool reference doc instead
**Warning signs:** Any number next to "tools" in documentation

### Pitfall 2: Inconsistent .env.example
**What goes wrong:** .env.example references "Ansible MCP Server" and has vars like OLLAMA_HOST that aren't used by the MCP server
**Why it happens:** The .env.example is from an older project iteration
**How to avoid:** The config reference should list only vars actually read by config.py and run_server.py
**Warning signs:** Env vars in .env.example not found in config.py

### Pitfall 3: Missing Verification Step
**What goes wrong:** User follows setup but has no way to confirm it works
**Why it happens:** Setup guides often end at "run the server" without showing how to test
**How to avoid:** Include a concrete verification: send a JSON-RPC request or use Claude to call a simple tool
**Warning signs:** Setup guide ending with "start the server" as the last step

### Pitfall 4: Platform-Specific Path Assumptions
**What goes wrong:** Config file paths shown only for macOS
**Why it happens:** Developer uses macOS
**How to avoid:** Show paths for macOS, Linux, and Windows for Claude Desktop config
**Warning signs:** Only one OS mentioned in path examples

## Code Examples

### Tool Schema Structure (source of truth for DOCS-02)
```python
# Source: src/homelab_mcp/tool_schemas/ssh_tools_schema.py
SSH_TOOLS: dict[str, dict[str, Any]] = {
    "ssh_discover": {
        "description": "SSH into a system and gather hardware/system information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {"type": "string", "description": "SSH username"},
                "password": {"type": "string", "description": "SSH password"},
                "key_path": {"type": "string", "description": "Path to SSH private key"},
                "port": {"type": "integer", "description": "SSH port (default: 22)", "default": 22},
            },
            "required": ["hostname", "username"],
        },
    },
}
```

### Config Class Structure (source of truth for DOCS-03)
```python
# Source: src/homelab_mcp/config.py
class MCPConfig:
    def __init__(self) -> None:
        self.debug = os.getenv("MCP_DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
        self.ssh_timeout = int(os.getenv("SSH_TIMEOUT", "10"))
        # ... pattern repeats for all config vars
```

### MCP Client Configuration (for setup guide)
```json
// Source: docs/DEPLOYMENT.md - Claude Desktop with uv
{
  "mcpServers": {
    "homelab": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/homelab_mcp", "python", "run_server.py"],
      "cwd": "/path/to/homelab_mcp"
    }
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| README as sole docs | docs/ directory with focused guides | Already exists | Reduces README bloat |
| Listing tools in README | Schema-driven tool definitions in tool_schemas/ | Phase 1 refactor | Tool reference can be derived from schemas |
| .env.example as config reference | MCPConfig class with defaults | Already exists | Code is the source of truth for defaults |

**Deprecated/outdated in current docs:**
- README tool count numbers (34+, 41, 49 -- actual is 49)
- .env.example header says "Ansible MCP Server" and includes unused vars (OLLAMA_HOST, ANSIBLE_* vars)
- docs/CLAUDE_SETUP.md lists only 23 tools (very outdated)
- README references `hello_world` tool which may not exist in current schemas

## Existing Documentation Inventory

| File | Status | Relevance |
|------|--------|-----------|
| README.md | Outdated tool counts, overlapping content | Needs updating to link to new docs |
| docs/CLAUDE_SETUP.md | Very outdated (23 tools) | Should be superseded by setup guide |
| docs/DEPLOYMENT.md | Partially current | Good content for setup guide |
| docs/HTTP_SERVICE.md | Unknown currency | May inform HTTP transport section |
| docs/WORKFLOWS.md | Dev-focused | Out of scope for DOCS-01/02/03 |
| docs/QUALITY_ASSURANCE.md | Dev-focused | Out of scope |
| .env.example | Outdated header and vars | Needs updating as part of DOCS-03 |
| CLAUDE.md | Current project guidelines | Internal, not user-facing |
| CONTRIBUTING.md | Contributor guide | Out of scope |

## Open Questions

1. **Return format documentation for DOCS-02**
   - What we know: Tool schemas define inputs but not outputs
   - What's unclear: Return formats are only visible in handler implementations and tests
   - Recommendation: Document return format per-tool by examining handler code; at minimum document that all tools return dict with standard MCP content blocks

2. **Should .env.example be updated as part of this phase?**
   - What we know: Current .env.example is outdated and misleading
   - What's unclear: Whether updating it is in scope for DOCS-03 (which says "lists all environment variables")
   - Recommendation: Yes, update .env.example to match config.py -- it's a documentation artifact

3. **Should README.md be updated to remove redundant content?**
   - What we know: README has extensive tool docs that will be superseded by tool-reference.md
   - What's unclear: How much to trim vs. keep for GitHub landing page
   - Recommendation: Slim README to overview + quick start + links to docs/; remove detailed tool listings

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5+ with pytest-asyncio |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_tools.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-01 | Setup guide exists and covers required sections | manual-only | N/A - documentation content review | N/A |
| DOCS-02 | Tool reference covers all 49 tools | smoke | `uv run python -c "from src.homelab_mcp.tool_schemas import get_all_tool_schemas; assert len(get_all_tool_schemas()) == 49"` | No dedicated test |
| DOCS-03 | Config reference covers all env vars | manual-only | N/A - documentation content review | N/A |

**Manual-only justification:** Documentation phases are inherently about prose quality and completeness. Automated tests can verify that documented tool names match actual tools, but cannot verify that descriptions, examples, and setup steps are correct and followable.

### Sampling Rate
- **Per task commit:** Verify markdown renders (no broken links, proper formatting)
- **Per wave merge:** Cross-check tool names in docs against tool_schemas
- **Phase gate:** Manual review of all three documents against success criteria

### Wave 0 Gaps
None -- no test infrastructure needed for documentation. Existing test suite validates the code being documented.

## Sources

### Primary (HIGH confidence)
- src/homelab_mcp/tool_schemas/*.py - 49 tool definitions with JSON Schema
- src/homelab_mcp/config.py - MCPConfig, HTTPConfig, DatabaseConfig classes
- run_server.py - CLI argument definitions
- .env.example - existing environment variable template

### Secondary (MEDIUM confidence)
- README.md - existing documentation (partially outdated)
- docs/DEPLOYMENT.md - existing deployment guide
- docs/CLAUDE_SETUP.md - existing Claude setup guide (outdated)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - documentation is plain markdown, no library choices needed
- Architecture: HIGH - documentation structure derived from requirements and existing code analysis
- Pitfalls: HIGH - identified by direct comparison of existing docs against source code

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- documentation phase, no external dependencies)
