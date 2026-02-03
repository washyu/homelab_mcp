# 🏠 Homelab MCP Server

[![CI](https://github.com/washyu/homelab_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/ci.yml)
[![Test Coverage](https://github.com/washyu/homelab_mcp/actions/workflows/test-coverage.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/test-coverage.yml)
[![codecov](https://codecov.io/gh/washyu/homelab_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/washyu/homelab_mcp)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-Powered VM Infrastructure Management with Advanced Service Installation Framework**

A comprehensive Model Context Protocol (MCP) server that enables AI assistants to manage, deploy, and monitor homelab infrastructure through automated service installation, Terraform state management, and VM operations.

## 🚀 Quick Start

```bash
# Install uv (ultra-fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and run (takes 3 seconds!)
git clone https://github.com/washyu/homelab_mcp.git
cd homelab_mcp
uv sync && uv run python run_server.py
```

## ✨ Key Features

### 🤖 **AI-Driven Service Installation**
- **49 MCP Tools** for complete infrastructure lifecycle management
- **Service Templates** for Jellyfin, Pi-hole, Ollama, Home Assistant, and more
- **Proxmox Integration** with full API access and 400+ community scripts for discovery
- **Terraform Support** with state management and clean resource tracking
- **Automated Deployment** with requirement validation and health checking
- **One-Command Installation**: *"Install Pi-hole on my homelab server"*

### 🔧 **VM Infrastructure Management**
- **SSH-based Discovery**: Gather comprehensive hardware/software information from any system
- **Automated User Setup**: Configure `mcp_admin` with passwordless access and selective permissions
- **Container Operations**: Deploy, manage, and remove Docker/LXD containers with state tracking
- **Network Mapping**: Intelligent device discovery, topology analysis, and change tracking

### 🏗️ **Enterprise-Grade Infrastructure as Code**
- **Terraform Integration**: Full state management with local/S3 backends
- **Idempotent Deployments**: Safe to run multiple times with automatic drift detection
- **Clean Resource Management**: Proper destroy workflows that remove only what was created
- **Multi-Backend Support**: Local files, S3-compatible storage, Consul/etcd for HA

### ⚡ **Ultra-Fast Development**
- **uv Package Manager**: 600x faster dependency installation (0.07s vs 45s with pip)
- **Reproducible Builds**: Lock files ensure consistent deployments across environments
- **Zero Configuration**: Dependencies and virtual environments handled automatically

## 🛠 Available Tools (41 Total)

### 🛠️ **Service Management Tools (4)**

#### `list_available_services`
List all available service templates for homelab deployment.

#### `install_service`
Deploy services with automated configuration and validation.

#### `plan_terraform_service`
Generate Terraform execution plans to preview infrastructure changes without applying them.

#### `destroy_terraform_service`
Cleanly destroy Terraform-managed services and remove all associated resources.

### 📦 **Featured Services Available**

#### **Ollama** - Local LLM Server
- **Self-hosted LLM deployment** for privacy-focused AI applications
- **Model support** for tinyllama, phi, mistral, and other open-source models
- **API integration** for chat interfaces and custom applications
- **Resource-efficient** operation suitable for homelab environments

#### **Home Assistant** - Smart Home Automation
- **GPIO integration** for Raspberry Pi sensors and control
- **Zigbee/Z-Wave hub** capabilities with USB dongles
- **Energy monitoring** and automation rules
- **Mobile app integration** for remote access

### SSH & Admin Tools (5)

#### `start_interactive_shell`
Start an interactive web-based shell session on a remote system:
- **Full TTY support** with xterm.js browser-based terminal
- **Perfect for interactive scripts** like Proxmox community scripts that require user input
- **Persistent sessions** with automatic cleanup after 30 minutes of inactivity
- **Secure access** through API key authentication
- Returns a URL to open the shell in your browser

Example use case: Run Proxmox community scripts interactively, navigate the filesystem, edit files, or debug issues with a full terminal experience.

**Note**: Uses registered SSH credentials or accepts username/password. Sessions are isolated and automatically cleaned up.

#### `ssh_discover`
SSH into a remote system and gather comprehensive system information including:
- **CPU details** (model, cores, architecture)
- **Memory usage** (total, available, used)
- **Storage information** (disk usage, mount points)
- **Network interfaces** (IPs, MAC addresses, link status)
- **Hardware discovery**: USB devices, PCI devices (network cards, GPUs), block devices (drives, partitions)
- **Operating system** information and uptime

**Note**: When using username `mcp_admin`, the tool automatically uses the MCP's SSH key if available. No password is required after running `setup_mcp_admin` on the target system.

#### `setup_mcp_admin`
SSH into a remote system using admin credentials and set up the `mcp_admin` user with:
- **User creation** (if not exists)
- **Sudo group membership** with passwordless access
- **SSH key authentication** (using MCP's auto-generated key)
- **Selective group permissions** (only adds groups for installed services like docker, lxd)

Parameters:
- `hostname`: Target system IP or hostname
- `username`: Admin username with sudo access
- `password`: Admin password
- `force_update_key` (optional, default: true): Force update SSH key even if mcp_admin already has other keys

#### `verify_mcp_admin`
Verify SSH key access to the `mcp_admin` account on a remote system:
- Tests SSH key authentication
- Verifies sudo privileges
- Returns connection status

### Network Discovery Tools (6)

#### `discover_and_map`
Discover a device via SSH and store it in the network site map database.

#### `bulk_discover_and_map`
Discover multiple devices via SSH and store them in the network site map database.

#### `get_network_sitemap`
Get all discovered devices from the network site map database.

#### `analyze_network_topology`
Analyze the network topology and provide insights about the discovered devices.

#### `suggest_deployments`
Suggest optimal deployment locations based on current network topology and device capabilities.

#### `get_device_changes`
Get change history for a specific device.

### Infrastructure CRUD Tools (7)

#### `deploy_infrastructure`
Deploy new infrastructure based on AI recommendations or user specifications:
- Deploy Docker containers, LXD containers, or systemd services
- Configure networking, storage, and environment variables
- Validate deployment plans before execution

#### `update_device_config`
Update configuration of an existing device:
- Modify service configurations
- Update network settings
- Change security configurations
- Adjust resource allocations

#### `decommission_device`
Safely remove a device from the network infrastructure:
- Analyze dependencies and critical services
- Execute migration plans to move services
- Graceful shutdown and removal

#### `scale_services`
Scale services up or down based on resource analysis:
- Horizontal scaling of containers/VMs
- Resource allocation adjustments
- Load balancing configuration

#### `validate_infrastructure_changes`
Validate infrastructure changes before applying them:
- Basic, comprehensive, and simulation validation levels
- Dependency checking
- Risk assessment

#### `create_infrastructure_backup`
Create a backup of current infrastructure state:
- Full or partial backups
- Device-specific backups
- Configuration and data backup options

#### `rollback_infrastructure_changes`
Rollback recent infrastructure changes:
- Restore from backups
- Selective rollback capabilities
- Validation before rollback

### VM Management Tools (6)

#### `deploy_vm`
Deploy a new VM/container on a specific device:
- Support for Docker containers and LXD VMs
- Configurable images, ports, volumes, environment variables
- Platform-agnostic deployment

#### `control_vm`
Control VM state (start, stop, restart):
- Manage VM lifecycle
- Support for both Docker and LXD platforms
- Real-time status updates

#### `get_vm_status`
Get detailed status of a specific VM:
- Container/VM health information
- Resource usage statistics
- Network and storage details

#### `list_vms`
List all VMs/containers on a device:
- Cross-platform inventory
- Status and configuration overview
- Multi-device support

#### `get_vm_logs`
Get logs from a specific VM/container:
- Configurable log line limits
- Support for Docker and LXD logs
- Real-time log streaming

#### `remove_vm`
Remove a VM/container from a device:
- Graceful or forced removal
- Data preservation options
- Cleanup of associated resources

### Proxmox Community Scripts Integration (2)

Discover and get information about 400+ community-maintained Proxmox installation scripts:

#### `search_proxmox_scripts`
Search the Proxmox community scripts repository:
- Search by keyword (docker, homeassistant, pihole, etc.)
- Filter by category (containers, VMs, installers)
- Optional metadata fetching for resource requirements
- Access to 400+ community-maintained installation scripts

#### `get_proxmox_script_info`
Get detailed information about a specific script:
- CPU, RAM, and disk requirements
- OS and version specifications
- Tags and categorization
- Script preview and download URL with command to run

**Note:** Script execution is not automated because these scripts are interactive and require user input during installation. The AI can help you find the right script and show its requirements, then you run it manually from the Proxmox web shell where you can respond to prompts.

**Scripts provided by:** [community-scripts/ProxmoxVE](https://github.com/community-scripts/ProxmoxVE) (MIT License)

### Proxmox API Integration (8)

Direct Proxmox API access for comprehensive cluster management:

#### `list_proxmox_resources`
List all cluster resources:
- VMs, LXC containers, nodes, storage, pools
- Filter by resource type
- Real-time status and metrics
- Uses PROXMOX_HOST from environment

#### `get_proxmox_node_status`
Get detailed node information:
- CPU usage and specifications
- Memory usage and capacity
- Uptime and load averages
- Disk and network statistics

#### `get_proxmox_vm_status`
Get specific VM/container status:
- Resource usage (CPU, memory, disk, network)
- Configuration details
- Current state (running, stopped, suspended)
- Supports both QEMU VMs and LXC containers

#### `manage_proxmox_vm`
Control VM/container lifecycle:
- Actions: start, stop, shutdown, restart, suspend, resume
- Graceful shutdowns vs forced stops
- Real-time operation status

#### `create_proxmox_lxc`
Create new LXC containers:
- Choose from available OS templates
- Configure CPU cores, RAM, and disk
- Network configuration
- Storage selection

#### `create_proxmox_vm`
Create new QEMU VMs:
- ISO or template-based deployment
- Hardware configuration (CPU, RAM, disk, network)
- Boot order and BIOS settings
- SCSI/VirtIO storage options

#### `clone_proxmox_vm`
Clone existing VMs or containers:
- Full or linked clones
- New VMID assignment
- Name and description customization
- Fast template-based deployments

#### `delete_proxmox_vm`
Remove VMs or containers:
- Clean resource deallocation
- Confirmation safeguards
- Disk cleanup options

**Authentication:** Supports both API tokens (no expiration) and username/password (2-hour sessions). Configure via environment variables or pass credentials per-call.

## 🏗️ Terraform vs SSH Commands

### **Why Terraform Integration Matters**
| Aspect | SSH Commands | Terraform | Benefit |
|--------|--------------|-----------|---------|
| **State Tracking** | ❌ Manual | ✅ Automatic | Know exactly what was created |
| **Idempotency** | ❌ Can break | ✅ Safe reruns | Run deployments multiple times |
| **Clean Removal** | ❌ Orphaned resources | ✅ Complete cleanup | Remove only what Terraform created |
| **Drift Detection** | ❌ Manual checks | ✅ Automatic | Detect manual changes |
| **Rollback** | ❌ Manual process | ✅ State-based | Revert to previous configurations |

### **Deployment Methods Available**
```bash
# Docker Compose (fast, simple)
"Install Pi-hole using Docker Compose"

# Terraform (enterprise-grade, state-managed)
"Install Pi-hole using Terraform with state management"

# Both methods support the same services
```

## 🎭 Ansible Configuration Management

### **Why Ansible for Multi-Service Deployments**
Perfect for deploying multi-service homelab stacks with complex dependencies:

| Capability | Docker Compose | Terraform | Ansible | Best For |
|------------|----------------|-----------|---------|----------|
| **Single Host Services** | ✅ Excellent | ✅ Good | ✅ Good | Simple deployments |
| **Multi-Host Orchestration** | ❌ Limited | ✅ Infrastructure | ✅ Configuration | Complex setups |
| **System Configuration** | ❌ Container only | ❌ Limited | ✅ Full control | OS-level setup |
| **Service Dependencies** | ✅ Basic | ✅ Resource deps | ✅ Cross-service config | Interconnected services |
| **Idempotent Operations** | ✅ Yes | ✅ Yes | ✅ Yes | Safe re-runs |

### **Available Ansible Services**
```bash
# Full AI homelab stack (MCP + Ollama + Web UI + Nginx)
"Install ai_homelab_stack_ansible on my Pi for complete AI setup"

# Individual service with system integration
"Install ollama_ansible on my server for system-level LLM hosting"
```

### **Ansible Tools**
- `check_ansible_service` - Verify Ansible deployment status
- `run_ansible_playbook` - Execute playbooks with tags/variables

### **Example: Complete AI Stack Deployment**
```bash
# One command deploys entire stack:
# ✅ MCP Server as systemd service
# ✅ Ollama LLM server
# ✅ Web UI with pre-configured API endpoints
# ✅ Nginx reverse proxy with SSL ready
# ✅ Firewall configuration
# ✅ Health checks and monitoring

"Install ai_homelab_stack_ansible on my homelab server"
```

## Installation

### **Quick Start (Recommended)**
```bash
# Install uv (ultra-fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and run (takes 3 seconds!)
git clone https://github.com/washyu/homelab_mcp.git
cd homelab_mcp
uv sync && uv run python run_server.py
```

### **Traditional pip Installation**
```bash
# Clone the repository
git clone https://github.com/washyu/homelab_mcp.git
cd homelab_mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (much slower than uv)
pip install -e .
```

### **For Development**
```bash
# Install with development dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/homelab_mcp
```

## Usage

### Running the Server

```bash
python run_server.py
```

The server communicates via stdio (stdin/stdout) using the MCP protocol.

### SSH Key Management

The MCP server automatically generates an SSH key pair on first initialization:
- Private key: `~/.ssh/mcp_admin_rsa`
- Public key: `~/.ssh/mcp_admin_rsa.pub`

This key is used for:
1. Authenticating as `mcp_admin` on remote systems after setup
2. Enabling passwordless SSH access for system management
3. Automatic authentication when using `ssh_discover` with username `mcp_admin`

### Testing with JSON-RPC

You can test the server by sending JSON-RPC requests:

```bash
# List available tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python run_server.py

# Discover a system via SSH (with password)
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ssh_discover","arguments":{"hostname":"192.168.1.100","username":"user","password":"pass"}}}' | python run_server.py

# Discover using mcp_admin (no password needed after setup)
echo '{"jsonrpc":"2.0","id":3b,"method":"tools/call","params":{"name":"ssh_discover","arguments":{"hostname":"192.168.1.100","username":"mcp_admin"}}}' | python run_server.py

# Setup mcp_admin on a remote system
echo '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"setup_mcp_admin","arguments":{"hostname":"192.168.1.100","username":"admin","password":"adminpass"}}}' | python run_server.py

# Verify mcp_admin access
echo '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"verify_mcp_admin","arguments":{"hostname":"192.168.1.100"}}}' | python run_server.py

# Use ssh_discover with mcp_admin (no password needed after setup)
echo '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"ssh_discover","arguments":{"hostname":"192.168.1.100","username":"mcp_admin"}}}' | python run_server.py
```

### Integration with AI Assistants

This server is designed to work with AI assistants that support the Model Context Protocol.

**🚀 For detailed Claude setup instructions, see [CLAUDE_SETUP.md](docs/CLAUDE_SETUP.md)**

**Recommended configuration for Claude Desktop (using uv):**

```json
{
  "mcpServers": {
    "homelab": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "python", "/Users/your-username/workspace/homelab_mcp/run_server.py"],
      "cwd": "/Users/your-username/workspace/homelab_mcp"
    }
  }
}
```

**Alternative configuration (traditional Python):**

```json
{
  "mcpServers": {
    "homelab": {
      "command": "python3",
      "args": ["/path/to/your/homelab_mcp/run_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/your/homelab_mcp/src"
      }
    }
  }
}
```

Place this in:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

### Typical Workflow

1. **Initial Setup**: The MCP automatically generates its SSH key on first run
2. **Configure Remote System**: Use `setup_mcp_admin` with admin credentials to:
   - Create the `mcp_admin` user on the target system
   - Install the MCP's public key for authentication
   - Grant sudo privileges
3. **Verify Access**: Use `verify_mcp_admin` to confirm setup was successful
4. **Manage Systems**: Use `ssh_discover` with username `mcp_admin` for passwordless access

Example workflow:
```bash
# 1. Setup mcp_admin on a new system
{"method":"tools/call","params":{"name":"setup_mcp_admin","arguments":{"hostname":"192.168.1.50","username":"pi","password":"raspberry"}}}

# 2. Verify the setup worked
{"method":"tools/call","params":{"name":"verify_mcp_admin","arguments":{"hostname":"192.168.1.50"}}}

# 3. Now discover system info without needing passwords
{"method":"tools/call","params":{"name":"ssh_discover","arguments":{"hostname":"192.168.1.50","username":"mcp_admin"}}}
```

### Handling Key Updates

If the `mcp_admin` user already exists but has a different SSH key, the `setup_mcp_admin` tool will automatically update it by default. You can control this behavior:

```bash
# Force update the SSH key (default behavior)
{"method":"tools/call","params":{"name":"setup_mcp_admin","arguments":{"hostname":"192.168.1.50","username":"pi","password":"raspberry","force_update_key":true}}}

# Keep existing keys (only add if no MCP key exists)
{"method":"tools/call","params":{"name":"setup_mcp_admin","arguments":{"hostname":"192.168.1.50","username":"pi","password":"raspberry","force_update_key":false}}}
```

When `force_update_key` is true (default), the tool will:
1. Remove any existing MCP keys (identified by the `mcp_admin@` comment)
2. Add the current MCP's public key
3. Preserve any other SSH keys the user might have

## 🎯 Example Use Cases

### **Homelab Service Deployment**
```bash
# 1. Deploy local LLM server
"Install Ollama on my server for hosting Mistral 7B locally"

# 2. Set up smart home automation
"Install Home Assistant on my Pi for smart home control"

# 3. Create network-wide ad blocking
"Install Pi-hole on my Pi for ad blocking with DNS configuration"

# 4. Deploy media server
"Install Jellyfin on my server for media streaming"
```

### **Enterprise Infrastructure Management**
```bash
# 1. Discover and map network infrastructure
"Discover all devices on my network and create a topology map"

# 2. Deploy enterprise storage
"Install TrueNAS on my storage server with ZFS optimization"

# 3. Set up Kubernetes cluster
"Deploy K3s on my cluster nodes for container orchestration"

# 4. Use Terraform for state management
"Install Pi-hole using Terraform with state tracking and backup"
```

### **Hardware Discovery and Optimization**
```bash
# 1. Comprehensive hardware audit
"Discover my server's hardware including USB devices and network cards"

# 2. Storage analysis
"Analyze disk usage and performance across my homelab servers"

# 3. Network device identification
"Show me all network adapters and their capabilities on my devices"
```

### **Development and Testing**
```bash
# 1. Container development platform
"Deploy development containers with persistent storage"

# 2. Service monitoring and debugging
"Check service status and show logs for troubleshooting"

# 3. Infrastructure as code testing
"Plan Terraform changes before applying to production"
```

## Development

### Project Structure

```
homelab_mcp/
├── src/
│   └── homelab_mcp/
│       ├── __init__.py
│       ├── server.py           # Main MCP server with JSON-RPC protocol
│       ├── tools.py            # Tool registry and execution (49 tools)
│       ├── ssh_tools.py        # SSH discovery with hardware detection
│       ├── service_installer.py # Service installation framework
│       ├── infrastructure_crud.py # Infrastructure lifecycle management
│       ├── vm_operations.py    # VM/container operations
│       ├── sitemap.py          # Network topology mapping
│       ├── database.py         # SQLite database for device tracking
│       └── service_templates/  # YAML service definitions
│           ├── ollama.yaml         # Local LLM server
│           ├── homeassistant.yaml  # Smart home automation
│           ├── pihole.yaml         # Network-wide ad blocking
│           ├── pihole_terraform.yaml # Terraform-managed Pi-hole
│           ├── jellyfin.yaml       # Media server
│           ├── k3s.yaml           # Lightweight Kubernetes
│           └── truenas.yaml       # Network-attached storage
├── tests/
│   ├── integration/       # Integration tests with Docker
│   ├── test_*.py         # Unit tests for all components
│   └── conftest.py       # Test fixtures and setup
├── scripts/
│   └── run-integration-tests.sh  # Test automation
├── docs/
│   ├── CLAUDE_SETUP.md       # Claude Desktop integration guide
│   ├── DEPLOYMENT.md         # uv deployment guide
│   ├── QUALITY_ASSURANCE.md  # Quality assurance documentation
│   └── WORKFLOWS.md          # Development workflows
├── pyproject.toml        # uv project configuration
├── uv.lock              # Dependency lock file
└── run_server.py        # Entry point with debug diagnostics
```

### Running Tests

#### Unit Tests
```bash
# Run all unit tests (fast, no Docker required)
pytest tests/ -m "not integration"

# Run with coverage
pytest tests/ -m "not integration" --cov=src/homelab_mcp

# Run specific test file
pytest tests/test_server.py
```

#### Integration Tests
```bash
# Prerequisites: Docker and docker-compose must be installed and running

# Run integration tests (requires Docker)
./scripts/run-integration-tests.sh

# Or run manually
pytest tests/integration/ -m integration -v

# Run specific integration test
pytest tests/integration/test_ssh_integration.py::TestSSHIntegration::test_full_mcp_admin_setup_workflow -v
```

#### All Tests
```bash
# Run all tests (unit + integration)
pytest

# Note: Integration tests will be skipped if Docker is not available
```

### Adding New Tools

1. Define the tool schema in `src/homelab_mcp/tools.py`:
```python
TOOLS["new_tool"] = {
    "description": "Tool description",
    "inputSchema": {
        "type": "object",
        "properties": {
            # Define parameters
        },
        "required": []
    }
}
```

2. Implement the tool logic in the appropriate module

3. Add the execution case in `execute_tool()` function

4. Write tests for the new tool

## Acknowledgments

### Proxmox Community Scripts

This project integrates with the excellent [community-scripts/ProxmoxVE](https://github.com/community-scripts/ProxmoxVE) repository to help users discover installation scripts for Proxmox VE containers and virtual machines.

**Attribution:**
- **Project**: Proxmox VE Helper-Scripts
- **Repository**: https://github.com/community-scripts/ProxmoxVE
- **Author**: tteck (tteckster) and community contributors
- **License**: MIT License
- **Website**: https://helper-scripts.com

The Proxmox script integration tools (`search_proxmox_scripts`, `get_proxmox_script_info`) provide discovery and information about scripts from their repository. All scripts are copyright of their respective authors and distributed under the MIT License.

**What we provide:**
- Script discovery and search functionality
- Metadata parsing (CPU, RAM, disk requirements)
- Download URLs and installation commands

**We do not:**
- Host or redistribute their scripts
- Modify their script content
- Claim authorship of their work
- Automate script execution (scripts are interactive and require user input)

All script information is fetched directly from their GitHub repository at runtime, ensuring you always get the latest versions with all community updates and security fixes.

Thank you to tteck and all contributors for maintaining this invaluable resource for the Proxmox community!

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request
