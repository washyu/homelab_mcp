# Homelab MCP Server

[![CI](https://github.com/washyu/homelab_mcp/actions/workflows/main.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/main.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
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
| [HTTP Service](docs/HTTP_SERVICE.md) | REST/OpenAPI mode, endpoints, and error contract |

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

# Store an SSH key-based credential (stores the key file path in the keyring, not the key)
homelab-mcp credentials add 192.168.1.10 admin --key-path ~/.ssh/id_ed25519

# Store a Proxmox API credential
homelab-mcp credentials add 192.168.1.200 root@pam --type proxmox

# Update an existing credential — `add` is upsert; re-running replaces the stored entry
homelab-mcp credentials add 192.168.1.10 admin

# List stored credentials
homelab-mcp credentials list
homelab-mcp credentials list --type proxmox

# Remove a credential
homelab-mcp credentials remove 192.168.1.10
```

The CLI provides full CRUD over credentials: `add` (create/update — upsert), `list` (read), `remove` (delete). There is no separate `update` subcommand — re-running `add` replaces both the keyring secret and the registry entry's auth type.

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
