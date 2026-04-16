# Homelab MCP Server

[![CI](https://github.com/washyu/homelab_mcp/actions/workflows/main.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/main.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-Powered Homelab Infrastructure Management via the Model Context Protocol**

---

## 🏆 TestSprite Season 2 Hackathon Submission

**Branch:** `TestSprite_Hackathon` | **Final Pass Rate: 10/10 (100%)**

### What I Built

homelab_mcp is an MCP (Model Context Protocol) server — it doesn't speak REST. TestSprite tests REST APIs. The core challenge of this submission was bridging that protocol gap.

**The solution:** A FastAPI wrapper that exposes all 56 MCP tools as proper REST endpoints, complete with a documented HTTP error contract, so TestSprite can exercise the full tool surface without any MCP protocol knowledge.

```
TestSprite Agent → FastAPI wrapper (port 8080) → homelab_mcp tools → Infrastructure
```

### Error Contract Design

Rather than returning generic 500s, the wrapper implements a three-tier HTTP error contract:

| Status | Meaning | Example |
|--------|---------|---------|
| 422 | Missing or malformed request fields | Required `hostname` not provided |
| 412 | Infrastructure precondition not met | Device ID not registered in sitemap |
| 424 | External dependency unreachable | SSH target / Proxmox host down |

The **424 Failed Dependency** design is the most interesting piece. Tools that talk to real infrastructure (SSH hosts, Proxmox API, TrueNAS) run a TCP preflight probe before invoking the handler. If the target is unreachable, the wrapper returns 424 with a structured payload — `status`, `host`, `port`, `protocol`, and a `requires` remediation hint — without ever touching the handler. No partial execution, no credential leakage to unreachable hosts.

Once this contract was documented in the Swagger spec, TestSprite automatically generated negative-path test cases for all three error types.

### Test Results — Five Run Arc

| Run | Pass Rate | Key Change |
|-----|-----------|------------|
| Pre-hackathon baseline | ~40% | MCP protocol mismatch — all test harness failures, zero server bugs |
| Run 1 | 7/10 (70%) | FastAPI wrapper + 424 spec — real bugs surfaced |
| Run 2 | 9/10 (90%) | Per-route jsonschema validation — 422 contract fixed for all 56 tools |
| Run 3 | 7/10 (70%) | Regenerated test plan after fixing code_summary.yaml — stricter tests exposed new gaps |
| Run 4 | 8/10 (80%) | ResourceManager lifespan wiring + 412 classifier patterns |
| Run 5 | **10/10 (100%)** | minItems schema fix + consistent error message wording |

### Fixes Delivered by TestSprite

| File | Change |
|------|--------|
| `openapi_app.py` | Per-route jsonschema validator; 422 with field path; FastAPI lifespan for ResourceManager; extended error classifier |
| `drift_handlers.py` | Short-circuit to 412 when no drift baselines registered |
| `network_tools_schema.py` | `minItems: 1` on `bulk_discover_and_map.targets` |
| `vm_operations.py` | Consistent "Device not found" error wording for classifier matching |
| `code_summary.yaml` | Corrected field names; documented 412/422/424 contracts per tool |

### Running the TestSprite Test Suite

```bash
# Clone the hackathon branch
git clone -b TestSprite_Hackathon https://github.com/washyu/homelab_mcp.git
cd homelab_mcp

# Install dependencies
uv sync

# Start the FastAPI wrapper (no auth mode for testing)
uv run python run_server.py --openapi --port 8080 --no-auth

# TestSprite test cases are in testsprite_tests/
# Run via the TestSprite agent pointed at http://localhost:8080
```

### Lessons Learned

1. **MCP servers need a REST facade** for conventional API testing tools
2. **Your Swagger spec is your test plan** — document error contracts and TestSprite generates tests for them
3. **`code_summary.yaml` accuracy matters** — wrong field names produce wrong tests
4. **Add CLAUDE.md guardrails** before letting Claude Code near TestSprite — without them it will autonomously loop fix→rerun and burn through credits
5. **Exclude `testsprite_tests/` from your linter and formatter** — treat it like `vendor/`
6. **Commit or copy reports after every run** — the summary is overwritten each time
7. **Auth and no-auth modes require separate runs** — can't cover both in one TestSprite session

Full writeup: [shaunjackson.space](https://www.shaunjackson.space)

---

A Python MCP server that enables AI assistants to manage, deploy, and monitor homelab infrastructure. Tools span SSH discovery, VM management, service installation, network topology mapping, Proxmox operations, and credential management.

## Key Features

- **SSH Discovery** -- Gather comprehensive hardware and software information from any system
- **Service Installation** -- Deploy Jellyfin, Pi-hole, Ollama, Home Assistant, and more from templates
- **Proxmox Integration** -- Full API access plus community script discovery
- **VM/Container Lifecycle** -- Deploy, control, and remove Docker and LXD workloads
- **Network Mapping** -- Discover devices, analyze topology, and track changes
- **Terraform and Ansible** -- State-managed deployments with drift detection and playbooks
- **Credential Management** -- Register servers once, connect without re-entering credentials

## Quick Start

```bash
# Install from PyPI (recommended — no clone needed)
uvx homelab-mcp

# Or clone and run from source
git clone https://github.com/washyu/homelab_mcp.git
cd homelab_mcp
uv sync && uv run python run_server.py
```

For the full walkthrough (environment variables, MCP client configuration, first tool call), see the [Setup Guide](docs/setup-guide.md).

## Documentation

| Guide | Description |
|-------|-------------|
| [Setup Guide](docs/setup-guide.md) | From zero to first tool call |
| [Tool Reference](docs/tool-reference.md) | All tools with arguments and examples |
| [Configuration](docs/configuration.md) | Environment variables and CLI options |
| [Claude Desktop Setup](docs/CLAUDE_SETUP.md) | Claude Desktop integration guide |

## How It Works

1. **Setup** -- The server generates an SSH key pair on first run (`~/.ssh/mcp_admin_rsa`)
2. **Onboard a host** -- Use `setup_mcp_admin` to create a managed user on the target system
3. **Verify** -- Use `verify_mcp_admin` to confirm passwordless SSH access
4. **Manage** -- Discover hardware, install services, control VMs, and map your network

The server communicates over stdio using the MCP protocol. Connect it to any MCP-compatible client (Claude Desktop, etc.) and interact through natural language.

## Credential Management

Store SSH and Proxmox credentials once so the server auto-injects them on every connection:

```bash
# Store an SSH credential
homelab-mcp credentials add 192.168.1.10 admin

# Store a Proxmox API credential
homelab-mcp credentials add 192.168.1.200 root@pam --type proxmox

# List stored credentials
homelab-mcp credentials list
homelab-mcp credentials list --type proxmox

# Remove a credential
homelab-mcp credentials remove 192.168.1.10
```

Credentials are stored in the OS keyring (libsecret on Linux, Keychain on macOS). When the OS keyring is unavailable (headless servers), credentials fall back to environment variables.

See [Credentials CLI reference](docs/configuration.md#credentials-cli) for full documentation.

## MCP Client Configuration

**From PyPI (uvx) — recommended:**

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uvx",
      "args": ["homelab-mcp"]
    }
  }
}
```

**From source clone:**

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uv",
      "args": ["run", "python", "run_server.py"],
      "cwd": "/path/to/homelab_mcp"
    }
  }
}
```

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests (unit only, no Docker required)
uv run pytest tests/ -m "not integration"

# Code quality
uv run ruff check src/ tests/
uv run mypy src/
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment details.

## Project Structure

```
src/homelab_mcp/
  server.py              # MCP server with JSON-RPC protocol
  tool_schemas/          # Tool definitions (8 schema files)
  tool_annotations.py    # MCP annotation hints per tool
  ssh_tools.py           # SSH discovery and hardware detection
  service_installer.py   # Service installation framework
  infrastructure_crud.py # Infrastructure lifecycle management
  vm_operations.py       # VM/container operations
  sitemap.py             # Network topology mapping
  database.py            # SQLite device tracking
  error_handling.py      # Centralized error handling
  credential_store.py    # OS keyring credential storage
  log_filter.py          # Credential redaction for log output
  prompt_registry.py     # MCP prompts registry
  resource_readers.py    # MCP resource read handlers
  service_templates/     # YAML service definitions
testsprite_tests/        # TestSprite generated test suite (hackathon)
tests/                   # Unit and integration tests
docs/                    # Full documentation
```

## Acknowledgments

Proxmox community script integration powered by [community-scripts/ProxmoxVE](https://github.com/community-scripts/ProxmoxVE) (MIT License).

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License -- see LICENSE file for details.
