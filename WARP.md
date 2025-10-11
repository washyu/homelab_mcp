# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

The **Homelab MCP Server** is a Model Context Protocol (MCP) server that enables AI assistants to manage homelab infrastructure through 34+ specialized tools. It provides comprehensive VM/container management, network discovery, SSH automation, and service installation capabilities across multiple deployment platforms.

## Key Architecture Components

### Core MCP Server (`src/homelab_mcp/server.py`)
- **JSON-RPC Protocol Handler**: Processes MCP requests over stdio
- **Tool Registry**: Dynamically loads and manages 34+ infrastructure tools
- **SSH Key Management**: Auto-generates and manages SSH keys on initialization
- **Asynchronous Design**: Built with asyncio for concurrent operations

### Tool System (`src/homelab_mcp/tools.py`)
The tool registry is organized into 4 main categories:
- **SSH & Admin Tools (4)**: Device access, user setup, verification
- **Network Discovery (6)**: Device scanning, topology analysis, change tracking
- **Infrastructure CRUD (7)**: Full lifecycle management, backups, rollbacks
- **VM Management (6)**: Container/VM operations across Docker and LXD

### SSH Infrastructure (`src/homelab_mcp/ssh_tools.py`)
- **Automated Key Management**: Generates RSA keys at `~/.ssh/mcp/mcp_admin_key`
- **Remote User Setup**: Creates `mcp_admin` user with passwordless sudo
- **Hardware Discovery**: Detects AI accelerators, USB/PCI devices, system specs
- **Secure Authentication**: Uses SSH keys instead of passwords after setup

### Service Installation Framework (`src/homelab_mcp/service_installer.py`)
- **YAML Template System**: Service definitions in `src/homelab_mcp/service_templates/`
- **Multi-Platform Deployment**: Supports Docker Compose, Terraform, Ansible
- **Requirement Validation**: Checks ports, memory, disk space before installation
- **AI Accelerator Support**: Auto-detects and optimizes for MemryX, Coral TPU, etc.

### Infrastructure Management (`src/homelab_mcp/infrastructure_crud.py`)
- **Device Lifecycle**: Deploy, update, scale, decommission operations
- **Backup & Recovery**: Configuration snapshots and rollback capabilities
- **Validation System**: Pre-deployment checks and risk assessment
- **Network Topology**: Understands device relationships and dependencies

### VM Operations (`src/homelab_mcp/vm_operations.py`)
- **Platform Abstraction**: Unified interface for Docker and LXD
- **Resource Management**: CPU, memory, storage allocation
- **State Control**: Start, stop, restart, remove operations
- **Monitoring**: Status checks, log retrieval, health monitoring

### Network Site Mapping (`src/homelab_mcp/sitemap.py`)
- **Device Discovery**: Automated network scanning and cataloging
- **Change Tracking**: Monitors configuration drift and updates
- **Topology Analysis**: Network relationship mapping
- **SQLite Database**: Persistent device and service state storage

## Common Development Commands

### Quick Start (Recommended - using uv)
```bash
# Install ultra-fast Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and run (takes ~3 seconds!)
git clone <repository-url>
cd mcp_python_server
uv sync && uv run python run_server.py
```

### Testing Commands
```bash
# Run all unit tests (fast, no Docker required)
uv run pytest tests/ -m "not integration"

# Run with coverage
uv run pytest tests/ -m "not integration" --cov=src/homelab_mcp

# Run specific test file
uv run pytest tests/test_server.py

# Run integration tests (requires Docker)
./scripts/run-integration-tests.sh

# Or manually with pytest
uv run pytest tests/integration/ -m integration -v

# Run all tests (unit + integration)
uv run pytest

# Test enhanced error handling
python test_error_handling.py
```

### Development Dependencies
```bash
# Install with development tools
uv sync --group dev

# Add new dependencies
uv add pyyaml asyncssh httpx

# Add optional feature groups
uv add --group monitoring pandas pyarrow
uv add --group automation ansible paramiko
uv add --group ai ollama
uv add --group security keyring cryptography
```

### Service Testing
```bash
# Test service installer
uv run python -c "
from src.homelab_mcp.service_installer import ServiceInstaller
installer = ServiceInstaller()
print('Available services:', installer.get_available_services())
"

# Test service configuration
uv run python -c "
from src.homelab_mcp.service_installer import ServiceInstaller
installer = ServiceInstaller()
import json
print(json.dumps(installer.get_service_info('jellyfin'), indent=2))
"
```

### MCP Connection Testing
```bash
# Test basic MCP protocol
python run_server.py
# Then in another terminal:
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python run_server.py

# Test specific tool
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ssh_discover","arguments":{"hostname":"192.168.1.100","username":"mcp_admin"}}}' | python run_server.py

# Test server health status
echo '{"jsonrpc":"2.0","id":4,"method":"health/status"}' | python run_server.py

# Test timeout handling (should not crash)
echo '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ssh_discover","arguments":{"hostname":"192.0.2.1","username":"test"}}}' | python run_server.py

# Test MCP connection helper
python test_mcp_connection.py
```

### Code Quality
The project uses:
- **pytest**: Testing framework with async support
- **black**: Code formatting (via uv run black src/)
- **flake8**: Linting (via uv run flake8 src/)
- **mypy**: Type checking (via uv run mypy src/)

## Service Templates Architecture

Services are defined in YAML templates at `src/homelab_mcp/service_templates/`:

- **AI Services**: Ollama (local LLM), Frigate NVR (security cameras), AI inference server
- **Media**: Jellyfin media server with GPU acceleration
- **Network**: Pi-hole (ad blocking), TrueNAS (storage)
- **Infrastructure**: K3s (Kubernetes), Docker registry
- **Deployment Methods**: Docker Compose, Terraform (with state), Ansible playbooks

### Template Structure
```yaml
name: "Service Name"
description: "Service description"
category: "ai|media|network|infrastructure"
requirements:
  ports: [80, 443]
  memory_gb: 2
  disk_gb: 10
installation:
  method: "docker-compose|terraform|ansible"
  # Method-specific configuration
```

## AI Accelerator Integration

The system automatically detects and optimizes for:
- **MemryX MX3**: 20+ TOPS, USB/PCIe
- **Coral Edge TPU**: 13 TOPS, TensorFlow Lite
- **Hailo-8**: 26 TOPS, multi-format
- **Intel NCS2**: 1 TOPS, OpenVINO

Hardware detection happens during SSH discovery and influences service deployment recommendations.

## Database Schema

SQLite database stores:
- **Devices**: Hardware specs, network info, connection details
- **Services**: Installed services, configurations, status
- **Changes**: Audit trail of all modifications
- **Backups**: Infrastructure snapshots for recovery

## Integration Patterns

### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "homelab": {
      "command": "uv",
      "args": ["run", "python", "run_server.py"],
      "cwd": "/path/to/mcp_python_server"
    }
  }
}
```

### SSH Key Security
- Keys generated at `~/.ssh/mcp/mcp_admin_key`
- Public key distributed to managed devices
- Passwordless sudo access for infrastructure operations
- Secure credential management (no passwords in code)

## Error Handling Patterns

**🛡️ Enhanced Error Handling (Fixed Timeout Crashes)**
- **Comprehensive Timeout Protection**: All operations wrapped with configurable timeouts
- **Graceful SSH Failures**: Retry logic with exponential backoff (2 retries for setup, 1 for discovery)
- **Server Stability**: Consecutive error limits prevent infinite error loops
- **Health Monitoring**: Built-in health endpoint tracks server status and error rates
- **Structured Error Responses**: Detailed error types with actionable suggestions
- **Connection Resilience**: 15-30s SSH timeouts, 60s tool execution, 120s request handling
- **Service Validation**: Pre-deployment requirement checking
- **Rollback Support**: Automatic backup creation before major changes
- **JSON Response Format**: Consistent error/success structure across all tools

## Performance Considerations

- **uv Package Manager**: 600x faster than pip for dependency resolution
- **Async SSH**: Concurrent operations across multiple devices  
- **SQLite Optimization**: Indexed queries for large device inventories
- **Service Caching**: Template loading and validation caching
- **Network Discovery**: Parallel device scanning with rate limiting

## Testing Strategy

- **Unit Tests**: Mock SSH connections, test tool logic in isolation
- **Integration Tests**: Real Docker containers for SSH server simulation  
- **Service Tests**: Validate YAML templates and installation procedures
- **MCP Protocol Tests**: JSON-RPC request/response validation
- **End-to-End Tests**: Full workflow testing with Claude integration

The test suite is designed to run quickly in CI/CD while providing comprehensive coverage of the complex infrastructure management scenarios.