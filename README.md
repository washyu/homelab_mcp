# Homelab MCP Server

[![CI](https://github.com/washyu/homelab_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/ci.yml)
[![Test Coverage](https://github.com/washyu/homelab_mcp/actions/workflows/test-coverage.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/test-coverage.yml)
[![codecov](https://codecov.io/gh/washyu/homelab_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/washyu/homelab_mcp)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-Powered Homelab Infrastructure Management via the Model Context Protocol**

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
# Install uv (ultra-fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and run
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

## MCP Client Configuration

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
  tool_schemas/          # Tool definitions (7 schema files)
  tool_annotations.py    # MCP annotation hints per tool
  ssh_tools.py           # SSH discovery and hardware detection
  service_installer.py   # Service installation framework
  infrastructure_crud.py # Infrastructure lifecycle management
  vm_operations.py       # VM/container operations
  sitemap.py             # Network topology mapping
  database.py            # SQLite device tracking
  service_templates/     # YAML service definitions
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
