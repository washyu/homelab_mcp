# Product Requirements Document (PRD)

## Homelab MCP Server

**Version:** 1.3.2
**Date:** 2026-04-11
**Status:** Active Development

---

## 1. Product Objective

Homelab MCP Server is a Python-based Model Context Protocol (MCP) server that enables AI assistants (primarily Claude) to discover, provision, configure, and manage homelab infrastructure through natural language. It bridges the gap between conversational AI interfaces and complex infrastructure operations — allowing users to manage their entire homelab without memorizing CLI commands, SSH credentials, or API documentation.

**Primary Goal:** Provide a single, unified MCP interface that gives AI assistants full operational control over heterogeneous homelab environments — from bare-metal discovery through service deployment, monitoring, and lifecycle management.

---

## 2. Target Users

### 2.1 Primary User — Homelab Enthusiast

A technically capable individual who runs self-hosted infrastructure at home (Proxmox clusters, Docker hosts, NAS appliances, Kubernetes clusters) and wants to manage it conversationally through an AI assistant rather than through SSH sessions, web UIs, and scripts.

### 2.2 Secondary User — AI Assistant (Claude)

The MCP server's direct consumer is an AI assistant that translates user intent into tool calls. The server must expose tools with clear schemas, descriptive documentation, and predictable error handling so the AI can operate infrastructure reliably.

---

## 3. User Needs

| # | Need | Priority |
|---|------|----------|
| N1 | Discover and inventory all devices on my home network without manual data entry | High |
| N2 | Install and manage self-hosted services (media servers, ad blockers, home automation) without writing Docker Compose files or Ansible playbooks | High |
| N3 | Manage Proxmox VMs and containers through natural language | High |
| N4 | Store SSH credentials securely so I don't re-enter passwords for every operation | High |
| N5 | Get deployment recommendations based on my infrastructure's actual resource availability | Medium |
| N6 | Detect configuration drift and state drift across my infrastructure | Medium |
| N7 | Back up and roll back infrastructure changes safely | Medium |
| N8 | Run Proxmox community scripts interactively on my nodes | Medium |
| N9 | Scale services up or down based on resource utilization | Low |
| N10 | Migrate from SQLite to PostgreSQL as my infrastructure tracking grows | Low |

---

## 4. User Stories

### 4.1 Device Discovery & Onboarding

**US-1: First-time device discovery**
> As a homelab user, I want to point the AI at an IP address and have it discover all hardware details (CPU, RAM, disk, network interfaces, OS) so that I have an accurate inventory without manual data entry.

**Acceptance Criteria:**
- Given a hostname/IP and SSH credentials, the system connects and returns CPU model/cores, total/used/free memory, disk usage, network interfaces with IPs, OS info, and uptime
- Discovery results are persisted to the sitemap database
- Discovery works with password auth, SSH key auth, or auto-injected keyring credentials
- Errors (unreachable host, auth failure) return clear, actionable messages

**US-2: Bulk device discovery**
> As a homelab user, I want to discover multiple devices in one operation so I can onboard my entire network quickly.

**Acceptance Criteria:**
- Accepts an array of target configurations (hostname, username, optional password/key)
- Discovers devices concurrently up to the configured batch size
- Returns per-device success/failure results
- All successful discoveries are stored in the sitemap

**US-3: Secure admin bootstrapping**
> As a homelab user, I want to set up a dedicated `mcp_admin` user on my servers with SSH key access so that future operations don't require passwords.

**Acceptance Criteria:**
- Creates the `mcp_admin` user on the target system
- Generates and deploys an SSH key pair
- Configures passwordless sudo
- Verifiable through a separate verification tool
- Works on Debian/Ubuntu and RHEL-family Linux distributions

### 4.2 Credential Management

**US-4: Register server credentials**
> As a homelab user, I want to store my SSH credentials once so the AI auto-injects them on every future connection.

**Acceptance Criteria:**
- Credentials are stored in the OS keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- Metadata is tracked in a local registry file
- Tools automatically resolve credentials by hostname without explicit parameters
- CLI subcommands (`credentials add`, `credentials list`, `credentials remove`) manage the credential store
- Graceful fallback when the OS keyring is unavailable (headless Linux)

**US-5: Proxmox API credentials**
> As a homelab user, I want to store my Proxmox API token or password so the AI can manage my Proxmox cluster without re-authentication.

**Acceptance Criteria:**
- Supports both API token and username/password authentication
- Credentials sourced from environment variables or keyring with automatic fallback
- SSL verification configurable (including custom CA certificates)

### 4.3 Network Topology & Planning

**US-6: View network topology**
> As a homelab user, I want to see my full network map — all discovered devices with their specs and status — so I can plan deployments.

**Acceptance Criteria:**
- Returns all devices with hardware specs, IP addresses, OS info, and online/offline status
- Data is current as of the last discovery scan

**US-7: Topology analysis**
> As a homelab user, I want the AI to analyze my network and tell me about OS distribution, resource utilization hot spots, and network segmentation.

**Acceptance Criteria:**
- Reports online/offline device counts
- Breaks down OS distribution across the fleet
- Identifies CPU architecture inventory
- Maps network segments by IP prefix
- Flags devices with high memory or disk utilization

**US-8: Deployment recommendations**
> As a homelab user, I want the AI to suggest where to deploy services based on available resources.

**Acceptance Criteria:**
- Recommends load balancer candidates (4+ cores, 4+ GB RAM)
- Suggests database hosts (low disk usage, 8+ GB RAM)
- Identifies monitoring targets
- Flags devices needing hardware upgrades

### 4.4 Service Installation

**US-9: Browse available services**
> As a homelab user, I want to see what services I can install and their requirements before committing.

**Acceptance Criteria:**
- Lists all available service templates with names and descriptions
- Shows per-service resource requirements (CPU, RAM, disk, ports)
- Indicates supported installation methods (Docker Compose, Terraform, Ansible, shell script)

**US-10: Install a service**
> As a homelab user, I want to install a self-hosted service (e.g., Jellyfin, Pi-hole, Home Assistant) on a target device by name.

**Acceptance Criteria:**
- Pre-flight requirement check validates the target device meets CPU, RAM, disk, and port requirements
- Installs via the appropriate method (Docker Compose, Ansible, Terraform, or shell script)
- Supports configuration overrides for non-default settings
- Returns installation status with access URLs and default credentials where applicable

**US-11: Check service status**
> As a homelab user, I want to check if an installed service is running and healthy.

**Acceptance Criteria:**
- Returns service running state, health status, and resource usage
- Works for Docker Compose, Ansible-managed, and Terraform-managed services

**Currently supported services:**
- Home Assistant (home automation)
- Pi-hole (network ad blocking)
- Jellyfin (media streaming)
- Ollama (local LLM inference)
- K3s (lightweight Kubernetes)
- TrueNAS (network-attached storage)
- AI Homelab Stack (Ollama + Text Generation UI via Ansible)
- Docker/Pi-hole via Terraform

### 4.5 Proxmox Management

**US-12: List Proxmox cluster resources**
> As a homelab user, I want to see all VMs, containers, nodes, and storage in my Proxmox cluster.

**Acceptance Criteria:**
- Lists all resources filterable by type (VM, LXC, node, storage, pool)
- Shows resource status (running, stopped), CPU/memory allocation
- Works with both API token and password authentication

**US-13: Create and manage Proxmox VMs/containers**
> As a homelab user, I want to create, start, stop, clone, and delete Proxmox VMs and LXC containers through conversation.

**Acceptance Criteria:**
- Create QEMU VMs with configurable cores, memory, disk, ISO, and storage
- Create LXC containers with configurable template, memory, cores, and root filesystem
- Clone existing VMs/containers (full or linked clone)
- Manage state: start, stop, shutdown, reboot, reset, suspend, resume
- Delete with optional purge and dry-run preview
- Get detailed per-VM/container status (CPU, memory, uptime)

**US-14: Search and run Proxmox community scripts**
> As a homelab user, I want to find and run community Proxmox installation scripts without leaving my AI conversation.

**Acceptance Criteria:**
- Search the community-scripts/ProxmoxVE GitHub repository by keyword
- Filter by category (containers, VMs, utilities, misc)
- View script metadata (resource requirements, description, tags)
- Launch an interactive web terminal to run scripts on a target node

### 4.6 VM/Container Operations (Docker & LXD)

**US-15: Deploy and manage Docker/LXD containers**
> As a homelab user, I want to deploy, control, and monitor Docker and LXD containers on any discovered device.

**Acceptance Criteria:**
- Deploy containers with configurable image, ports, volumes, environment variables
- Control container state (start, stop, restart)
- Get container status and retrieve logs
- List all containers across Docker and LXD on a device
- Remove containers with optional force mode and dry-run preview

### 4.7 Infrastructure Lifecycle

**US-16: Deploy infrastructure from a plan**
> As a homelab user, I want the AI to deploy services and network configurations across multiple devices based on a deployment plan.

**Acceptance Criteria:**
- Accepts a structured deployment plan (services + network changes)
- Validates the plan before execution (or validate-only mode)
- Deploys services to specified target devices
- Applies network and security configurations

**US-17: Decommission a device safely**
> As a homelab user, I want to remove a device from my infrastructure with dependency analysis and optional service migration.

**Acceptance Criteria:**
- Analyzes device dependencies before removal
- Accepts a migration plan to move services to other devices
- Supports dry-run preview to see impact before executing
- Force removal option for emergencies (with data loss warning)

**US-18: Back up and restore infrastructure state**
> As a homelab user, I want to snapshot my infrastructure state and roll back if something goes wrong.

**Acceptance Criteria:**
- Create backups (full, partial, or device-specific)
- Rollback to a previous backup with dry-run preview
- Validate rollback plans before execution

### 4.8 Drift Detection

**US-19: Detect infrastructure drift**
> As a homelab user, I want to know when my VMs or containers have drifted from their expected configuration.

**Acceptance Criteria:**
- Scans for config drift (CPU, memory, network changed outside MCP)
- Scans for state drift (VMs offline that should be running)
- Returns structured report with drift type, expected vs. actual values, and timestamps
- Filterable by Proxmox node and VM type (QEMU, LXC, or all)
- Drift baselines stored in database for comparison

### 4.9 Infrastructure as Code Integration

**US-20: Terraform service management**
> As a homelab user, I want to manage services through Terraform — plan, apply, refresh state, and destroy.

**Acceptance Criteria:**
- Generate a Terraform plan before applying changes
- Refresh Terraform state to detect drift
- Destroy Terraform-managed services with dry-run preview

**US-21: Ansible playbook execution**
> As a homelab user, I want to run Ansible playbooks for service deployment and configuration management.

**Acceptance Criteria:**
- Execute Ansible playbooks for defined services
- Support tags for selective task execution
- Support extra variables for parameterized runs
- Check mode (dry-run) for safe previewing

---

## 5. Functional Requirements

### 5.1 MCP Protocol Compliance

| ID | Requirement |
|----|-------------|
| FR-1 | Implement the MCP SDK `lowlevel.Server` protocol with stdio and HTTP transports |
| FR-2 | Expose all tools via `tools/list` with JSON Schema input definitions and tool annotations |
| FR-3 | Execute tools via `tools/call` and return structured MCP content (text, JSON) |
| FR-4 | Expose MCP resources (`homelab://vms`, `homelab://devices`, `homelab://services/{name}`, `homelab://drift/latest`) with live data |
| FR-5 | Support resource subscriptions with push notifications on mutation |
| FR-6 | Emit `resources/list_changed` notifications when discovery tools modify the device list |

### 5.2 Transport & Connectivity

| ID | Requirement |
|----|-------------|
| FR-7 | Default to stdio transport for Claude Desktop integration |
| FR-8 | Support HTTP transport (Starlette/Uvicorn) with optional API key authentication |
| FR-9 | Support HTTPS with user-provided SSL certificates |
| FR-10 | Support async SSH connections via asyncssh with configurable timeout and retry |
| FR-11 | Support Proxmox REST API with token and password authentication |

### 5.3 Data Persistence

| ID | Requirement |
|----|-------------|
| FR-12 | Store discovered device data in SQLite (default) or PostgreSQL |
| FR-13 | Track device discovery history with SHA-256 deduplication |
| FR-14 | Store SSH credentials in OS keyring with local metadata registry |
| FR-15 | Maintain drift baselines in the database for comparison scans |
| FR-16 | Support database migration from SQLite to PostgreSQL |

### 5.4 Error Handling & Resilience

| ID | Requirement |
|----|-------------|
| FR-17 | Apply configurable timeouts to all SSH and network operations |
| FR-18 | Retry failed SSH connections with exponential backoff |
| FR-19 | Return structured error responses with actionable messages (not stack traces) |
| FR-20 | Provide health monitoring with request counts, error rates, and uptime tracking |

### 5.5 Safety & Dry-Run Support

| ID | Requirement |
|----|-------------|
| FR-21 | All destructive tools (delete VM, decommission device, destroy Terraform service, remove server, remove VM, rollback) must support a dry-run/preview mode |
| FR-22 | Preview tools return a structured report of what would be affected without executing |
| FR-23 | Decommission operations must analyze dependencies before execution |

### 5.6 Configuration

| ID | Requirement |
|----|-------------|
| FR-24 | All configuration via environment variables (no config files required) |
| FR-25 | Validate configuration at startup with detailed error messages |
| FR-26 | Support feature flags for optional capabilities (PostgreSQL, resource pools) |

---

## 6. Current Scope

### 6.1 In Scope (Implemented)

- 55+ MCP tools across 8 categories (SSH, Network, Proxmox, VM, Service, Credential, Infrastructure, Drift)
- SSH device discovery with hardware profiling
- Secure admin user bootstrapping (`mcp_admin` with SSH key access)
- OS keyring credential management with CLI interface
- Network topology mapping, analysis, and deployment suggestions
- 10 service templates (Home Assistant, Pi-hole, Jellyfin, Ollama, K3s, TrueNAS, AI stack)
- Proxmox VE integration (VMs, LXC, nodes, storage, community scripts)
- Docker and LXD container lifecycle management
- Infrastructure deployment, scaling, decommissioning, backup, and rollback
- Terraform and Ansible integration for IaC workflows
- Configuration drift detection with baseline tracking
- Dual-database support (SQLite default, PostgreSQL optional)
- Dual-transport support (stdio for Claude Desktop, HTTP for OpenWebUI)
- Interactive web terminal for running scripts on remote systems
- Cross-platform support (Windows, macOS, Linux)
- CI/CD with GitHub Actions (tests, linting, type checking, security scans, PyPI publishing)
- 43 unit test files + 7 integration test files

### 6.2 Out of Scope (Not Currently Planned)

- GUI or web dashboard (the AI assistant is the UI)
- Multi-user or team access control
- Cloud provider integration (AWS, Azure, GCP)
- Automated scheduling of discovery scans or drift checks
- Real-time monitoring dashboards or alerting
- Windows Server or non-Linux target management
- Proprietary hypervisor support beyond Proxmox (VMware, Hyper-V)

---

## 7. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Python 3.12+ with strict type annotations (mypy enforced) |
| NFR-2 | Async-first architecture for all I/O operations |
| NFR-3 | Minimum 40% unit test code coverage (CI-enforced) |
| NFR-4 | Security scanning with Bandit and Safety on every release |
| NFR-5 | Installable via `pip install homelab-mcp` or `uvx homelab-mcp` |
| NFR-6 | MIT License |
| NFR-7 | SSH operations timeout within 10 seconds by default |
| NFR-8 | Discovery batch operations timeout within 300 seconds |

---

## 8. Success Metrics

| Metric | Target |
|--------|--------|
| Tool count | 55+ tools covering all homelab management needs |
| Service templates | 10+ self-hosted services installable by name |
| Platform support | Linux targets, with server running on Windows/macOS/Linux |
| Test coverage | 40%+ unit test coverage, integration tests for critical paths |
| Installation | Single command install from PyPI |
| Time to first device | Under 2 minutes from install to first device discovered |
