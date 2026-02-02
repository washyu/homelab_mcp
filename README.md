# 🏠 Homelab MCP Server

[![CI](https://github.com/washyu/homelab_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/ci.yml)
[![Test Coverage](https://github.com/washyu/homelab_mcp/actions/workflows/test-coverage.yml/badge.svg)](https://github.com/washyu/homelab_mcp/actions/workflows/test-coverage.yml)
[![codecov](https://codecov.io/gh/washyu/homelab_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/washyu/homelab_mcp)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-Powered VM Infrastructure Management with Advanced Service Installation Framework**

A comprehensive Model Context Protocol (MCP) server that enables AI assistants to manage, deploy, and monitor homelab infrastructure through automated service installation, Terraform state management, AI accelerator support, and VM operations.

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
- **34 MCP Tools** for complete infrastructure lifecycle management
- **Service Templates** for Jellyfin, Pi-hole, Ollama, Home Assistant, Frigate NVR, and more
- **Terraform Support** with state management and clean resource tracking
- **Automated Deployment** with requirement validation and health checking
- **One-Command Installation**: *"Install Pi-hole on my homelab server with AI acceleration"*

### 🧠 **AI Accelerator Support**
- **Auto-Detection** of MemryX MX3, Coral Edge TPU, Hailo-8, Intel Neural Compute Stick
- **Hardware Discovery** with USB/PCI device enumeration and classification
- **Performance Optimization** for Pi 4/5 with memory and thermal management
- **Real-time AI Applications** like Frigate NVR object detection and local LLM hosting

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

## 🛠 Available Tools (34 Total)

### 🤖 **AI & Machine Learning Tools (4)**

#### `list_available_services`
List all available service templates including AI accelerator-optimized services.

#### `install_service`
Deploy services with automatic AI accelerator detection and optimization.

#### `plan_terraform_service`
Generate Terraform execution plans to preview infrastructure changes without applying them.

#### `destroy_terraform_service`
Cleanly destroy Terraform-managed services and remove all associated resources.

### 🧠 **AI Accelerator Services Available**

#### **Frigate NVR** - AI-Powered Security Camera System
- **Auto-detects** MemryX MX3, Coral TPU, Hailo-8, Intel NCS accelerators
- **Real-time object detection** at 80+ FPS vs 4 FPS CPU-only
- **Home Assistant integration** for smart home automation
- **Perfect for Pi Camera modules and USB cameras**

#### **AI Inference Server** - Custom AI Applications
- **Multi-accelerator support** with automatic detection and fallback
- **REST API** for image inference and performance benchmarking
- **ONNX, TensorFlow Lite, OpenVINO** model format support
- **Performance testing tools** to validate accelerator speedup

#### **Ollama** - Local LLM Server
- **Pi-optimized** for 4GB/8GB RAM configurations
- **Model recommendations** (tinyllama, phi, mistral:7b based on available RAM)
- **API integration ready** for future UI development
- **Thermal and performance tuning** for sustained Pi workloads

#### **Home Assistant** - Smart Home Automation
- **Pi GPIO integration** for sensors, relays, and hardware control
- **Pi Camera module support** with motion detection
- **Zigbee/Z-Wave hub capabilities** with USB dongles
- **Energy monitoring** and mobile app integration

### SSH & Admin Tools (4)

#### `ssh_discover`
SSH into a remote system and gather comprehensive system information including:
- **CPU details** (model, cores, architecture)
- **Memory usage** (total, available, used)
- **Storage information** (disk usage, mount points)
- **Network interfaces** (IPs, MAC addresses, link status)
- **Hardware discovery**: USB devices (cameras, AI accelerators), PCI devices (network cards, GPUs), block devices (drives, partitions)
- **Operating system** information and uptime
- **AI accelerator detection**: MemryX MX3, Coral TPU, Hailo-8, Intel NCS

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

## 🧠 AI Accelerator Performance

### **Supported AI Hardware**
| Accelerator | Performance | Power | Model Formats | Pi Compatibility |
|-------------|-------------|-------|---------------|------------------|
| **MemryX MX3** | 20+ TOPS | 3W | ONNX, Quantized ONNX | ✅ USB/PCIe |
| **Coral Edge TPU** | 13 TOPS | 2W | TensorFlow Lite | ✅ USB/M.2 |
| **Hailo-8** | 26 TOPS | 2.5W | ONNX, TensorFlow, PyTorch | ✅ USB/PCIe |
| **Intel NCS2** | 1 TOPS | 1W | OpenVINO, ONNX | ✅ USB |

### **Real-World Performance Benchmarks**
*Tested on Raspberry Pi 4/5 with actual AI accelerators*

| Task | MemryX MX3 | Coral TPU | Pi 4 CPU | Speedup |
|------|------------|-----------|----------|---------|
| **Object Detection (YOLOv5)** | 83 FPS | 45 FPS | 4 FPS | **20x faster** |
| **Image Classification** | 250 FPS | 200 FPS | 5.5 FPS | **45x faster** |
| **Face Detection** | 120 FPS | 80 FPS | 3 FPS | **40x faster** |
| **Power Consumption** | 3W | 2W | 8W | **62% less** |

### **Example AI Applications**
```bash
# Deploy Frigate NVR with automatic AI accelerator detection
"Install Frigate NVR on my Pi to use the MemryX accelerator"

# Set up custom AI inference server with benchmarking
"Install AI inference server and test accelerator performance"

# Deploy Ollama for local LLM hosting (7B models on Pi 5)
"Install Ollama on my Pi 5 for local AI chat"

# Set up Home Assistant with Pi GPIO and camera integration
"Install Home Assistant for smart home automation with Pi camera"
```

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

# Both methods support the same services with automatic accelerator detection
```

## 🎭 Ansible Configuration Management

### **Why Ansible for Multi-Service Deployments**
Perfect for deploying complete AI homelab stacks like MCP + Ollama + Web UI:

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
# ✅ Ollama with GPU/AI accelerator support
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

### **AI-Powered Homelab Setup**
```bash
# 1. Set up Pi with AI accelerator for object detection
"Install Frigate NVR on my Raspberry Pi at 192.168.1.100 to use the MemryX accelerator"

# 2. Deploy local AI chat server
"Install Ollama on my Pi 5 for hosting Mistral 7B locally"

# 3. Set up smart home automation with GPIO
"Install Home Assistant on my Pi for smart home control with camera integration"

# 4. Create network-wide ad blocking with travel hotspot support
"Install Pi-hole on my Pi for ad blocking with hotspot configuration for travel"
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
"Discover my Pi's hardware including USB devices, PCI cards, and AI accelerators"

# 2. AI accelerator performance testing
"Install AI inference server and benchmark my MemryX accelerator performance"

# 3. Storage analysis
"Analyze disk usage and performance across my homelab servers"

# 4. Network device identification
"Show me all network adapters and their capabilities on my devices"
```

### **Development and Testing**
```bash
# 1. Local AI development environment
"Set up AI inference server for testing custom ONNX models"

# 2. Container development platform
"Deploy development containers with persistent storage"

# 3. Service monitoring and debugging
"Check service status and show logs for troubleshooting"

# 4. Infrastructure as code testing
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
│       ├── tools.py            # Tool registry and execution (34 tools)
│       ├── ssh_tools.py        # SSH discovery with hardware detection
│       ├── service_installer.py # Service installation framework
│       ├── infrastructure_crud.py # Infrastructure lifecycle management
│       ├── vm_operations.py    # VM/container operations
│       ├── sitemap.py          # Network topology mapping
│       ├── database.py         # SQLite database for device tracking
│       └── service_templates/  # YAML service definitions
│           ├── ollama.yaml         # Local LLM server (Pi-optimized)
│           ├── frigate_nvr.yaml    # AI-powered security cameras
│           ├── ai_inference.yaml   # Custom AI applications
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

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request
