# Product Requirements Document (PRD)

## Homelab MCP Server — REST API

**Version:** 1.3.2
**Date:** 2026-04-13
**Status:** Active Development
**Transport:** FastAPI OpenAPI/REST on port 8080

---

## 1. Product Objective

Homelab MCP Server exposes 56 infrastructure management tools as a REST API built with FastAPI. Each tool is available as a POST endpoint under `/api/tools/{tool_name}`. The API includes auto-generated OpenAPI documentation (Swagger UI at `/docs`) and consistent JSON response formatting.

---

## 2. API Overview

- **Base URL:** `http://localhost:8080`
- **Authentication:** Optional (disabled by default for local development)
- **Content-Type:** `application/json`
- **Swagger UI:** `GET /docs`
- **ReDoc:** `GET /redoc`
- **OpenAPI Spec:** `GET /openapi.json`

### Response Format

**Success (200):**
```json
{"status": "success", "tool": "tool_name", "result": <dict|string|number>}
```

**Client Error (400):**
```json
{"status": "error", "tool": "tool_name", "error": "validation message"}
```

**Server Error (500):**
```json
{"status": "error", "tool": "tool_name", "error": "error message"}
```

**Failed Dependency (424):**
```json
{
  "status": "failed_dependency",
  "tool": "tool_name",
  "error": "TCP connect to host:port timed out after 1.0s",
  "host": "target.example.com",
  "port": 22,
  "protocol": "SSH",
  "requires": "an SSH target host. Register credentials first: POST /api/tools/register_server"
}
```

**Not Found (404):**
```json
{"status": "error", "error": "Not Found"}
```

---

## 3. System Endpoints

### 3.1 Health Check
- **Endpoint:** `GET /health`
- **Description:** Returns server health status and metrics
- **Response:** `{"status": "success", "result": {"server_status": "healthy", "uptime_seconds": N, "total_requests": N, "total_errors": N, "error_rate": N, "transport": "openapi"}}`

### 3.2 List All Tools
- **Endpoint:** `GET /api/tools`
- **Description:** Returns the full registry of 56 tools with their input schemas
- **Response:** `{"tools": [{"name": "ssh_discover", "description": "...", "category": "SSH", "input_schema": {...}}, ...], "count": 56}`

---

## 4. Tool Endpoints

All tool endpoints follow the pattern `POST /api/tools/{tool_name}` with a JSON request body containing the tool's input parameters.

### 4.1 SSH Tools (6 tools)

#### POST /api/tools/ssh_discover
- **Description:** SSH into a system and gather hardware/OS information (CPU, RAM, disks, network interfaces, OS version)
- **Required fields:** `hostname`
- **Optional fields:** `username`, `password`, `key_path`, `port`
- **Request:** `{"hostname": "192.168.1.10", "username": "root", "password": "pass"}`
- **Success result:** Dict with discovered system info (CPU, memory, disks, interfaces, OS)
- **Error result (unreachable host):** 500 with `{"status": "error", "tool": "ssh_discover", "error": "Operation failed..."}`

#### POST /api/tools/setup_mcp_admin
- **Description:** Create mcp_admin user with SSH key access on remote system
- **Required fields:** `hostname`, `username`, `password`
- **Optional fields:** `force_update_key`, `port`
- **Request:** `{"hostname": "192.168.1.10", "username": "root", "password": "pass"}`
- **Success result:** String with setup report

#### POST /api/tools/verify_mcp_admin
- **Description:** Verify passwordless SSH access to mcp_admin account
- **Required fields:** `hostname`
- **Optional fields:** `port`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** String with verification status

#### POST /api/tools/ssh_execute_command
- **Description:** Execute a command on a remote system via SSH
- **Required fields:** `hostname`, `command`
- **Optional fields:** `username`, `password`, `sudo`, `port`
- **Request:** `{"hostname": "192.168.1.10", "command": "uname -a"}`
- **Success result:** String with command output

#### POST /api/tools/start_interactive_shell
- **Description:** Start a browser-based interactive TTY terminal session
- **Required fields:** `hostname`
- **Optional fields:** `username`, `password`, `port`, `initial_command`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** Dict with session URL and connection info

#### POST /api/tools/update_mcp_admin_groups
- **Description:** Update mcp_admin group memberships for docker/lxd/libvirt/kvm
- **Required fields:** `hostname`, `username`, `password`
- **Optional fields:** `port`
- **Request:** `{"hostname": "192.168.1.10", "username": "root", "password": "pass"}`
- **Success result:** String with group update report

### 4.2 Network Discovery Tools (6 tools)

#### POST /api/tools/discover_and_map
- **Description:** SSH discover a single device and store it in the sitemap database
- **Required fields:** `hostname`
- **Optional fields:** `username`, `password`, `key_path`, `port`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** Dict with device info and database record

#### POST /api/tools/bulk_discover_and_map
- **Description:** Batch discover multiple devices concurrently
- **Required fields:** `hosts`
- **Optional fields:** `batch_size`
- **Request:** `{"hosts": [{"hostname": "192.168.1.10"}, {"hostname": "192.168.1.11"}]}`
- **Success result:** Dict with per-host results (successes and failures)

#### POST /api/tools/get_network_sitemap
- **Description:** Retrieve all discovered devices and their details from the database
- **Required fields:** none
- **Request:** `{}`
- **Success result:** Dict with devices list and metadata

#### POST /api/tools/analyze_network_topology
- **Description:** Analyze network structure, OS distribution, and resource utilization
- **Required fields:** none
- **Request:** `{}`
- **Success result:** Dict with network analysis (device counts, OS breakdown, segments)

#### POST /api/tools/suggest_deployments
- **Description:** AI-powered deployment recommendations based on available resources
- **Required fields:** none
- **Request:** `{}`
- **Success result:** Dict with deployment suggestions per device

#### POST /api/tools/get_device_changes
- **Description:** Track device changes and discovery history
- **Required fields:** none
- **Optional fields:** `hostname`, `limit`
- **Request:** `{}`
- **Success result:** Dict with change history records

### 4.3 VM & Container Tools (7 tools)

#### POST /api/tools/deploy_vm
- **Description:** Deploy a new VM or container on Docker or LXD
- **Required fields:** `hostname`, `platform`, `image`
- **Optional fields:** `name`, `ports`, `volumes`, `environment`, `cpu_limit`, `memory_limit`
- **Request:** `{"hostname": "192.168.1.10", "platform": "docker", "image": "nginx"}`
- **Success result:** Dict with container ID and access info

#### POST /api/tools/control_vm
- **Description:** Start, stop, or restart a container/VM
- **Required fields:** `hostname`, `platform`, `container_name`, `action`
- **Request:** `{"hostname": "192.168.1.10", "platform": "docker", "container_name": "nginx", "action": "restart"}`
- **Success result:** String with action confirmation

#### POST /api/tools/get_vm_status
- **Description:** Get detailed VM/container status
- **Required fields:** `hostname`, `platform`, `container_name`
- **Request:** `{"hostname": "192.168.1.10", "platform": "docker", "container_name": "nginx"}`
- **Success result:** Dict with container status details

#### POST /api/tools/list_vms
- **Description:** List all VMs/containers on a device by platform
- **Required fields:** `hostname`, `platform`
- **Request:** `{"hostname": "192.168.1.10", "platform": "docker"}`
- **Success result:** Dict with containers list

#### POST /api/tools/get_vm_logs
- **Description:** Retrieve container/VM logs
- **Required fields:** `hostname`, `platform`, `container_name`
- **Optional fields:** `tail`
- **Request:** `{"hostname": "192.168.1.10", "platform": "docker", "container_name": "nginx"}`
- **Success result:** String with log output

#### POST /api/tools/remove_vm
- **Description:** Delete a VM/container
- **Required fields:** `hostname`, `platform`, `container_name`
- **Optional fields:** `force`
- **Request:** `{"hostname": "192.168.1.10", "platform": "docker", "container_name": "nginx"}`
- **Success result:** String with removal confirmation

#### POST /api/tools/remove_vm_preview
- **Description:** Dry-run preview of VM removal (shows what would be affected)
- **Required fields:** `hostname`, `platform`, `container_name`
- **Request:** `{"hostname": "192.168.1.10", "platform": "docker", "container_name": "nginx"}`
- **Success result:** Dict with preview of affected resources

### 4.4 Service Installation Tools (11 tools)

#### POST /api/tools/list_available_services
- **Description:** List all available service templates
- **Required fields:** none
- **Request:** `{}`
- **Success result:** `{"available_services": ["jellyfin", "pihole", "ollama", ...], "count": 10}`

#### POST /api/tools/get_service_info
- **Description:** Get detailed metadata for a service template
- **Required fields:** `service_name`
- **Request:** `{"service_name": "jellyfin"}`
- **Success result:** Dict with service description, requirements, and configuration

#### POST /api/tools/check_service_requirements
- **Description:** Verify a target device meets service prerequisites
- **Required fields:** `service_name`, `hostname`
- **Request:** `{"service_name": "jellyfin", "hostname": "192.168.1.10"}`
- **Success result:** Dict with requirement check results

#### POST /api/tools/install_service
- **Description:** Deploy a service from a YAML template
- **Required fields:** `service_name`, `hostname`
- **Optional fields:** `overrides`
- **Request:** `{"service_name": "jellyfin", "hostname": "192.168.1.10"}`
- **Success result:** Dict with installation status and access URLs

#### POST /api/tools/get_service_status
- **Description:** Check running service health
- **Required fields:** `service_name`, `hostname`
- **Request:** `{"service_name": "jellyfin", "hostname": "192.168.1.10"}`
- **Success result:** Dict with service status and health

#### POST /api/tools/plan_terraform_service
- **Description:** Preview Terraform changes before applying
- **Required fields:** `service_name`, `hostname`
- **Request:** `{"service_name": "docker_terraform", "hostname": "192.168.1.10"}`
- **Success result:** String with Terraform plan output

#### POST /api/tools/destroy_terraform_service
- **Description:** Remove a Terraform-managed service
- **Required fields:** `service_name`, `hostname`
- **Request:** `{"service_name": "docker_terraform", "hostname": "192.168.1.10"}`
- **Success result:** String with destruction results

#### POST /api/tools/destroy_terraform_service_preview
- **Description:** Dry-run preview of Terraform service destruction
- **Required fields:** `service_name`, `hostname`
- **Request:** `{"service_name": "docker_terraform", "hostname": "192.168.1.10"}`
- **Success result:** Dict with preview of what would be destroyed

#### POST /api/tools/refresh_terraform_service
- **Description:** Refresh Terraform state to detect drift
- **Required fields:** `service_name`, `hostname`
- **Request:** `{"service_name": "docker_terraform", "hostname": "192.168.1.10"}`
- **Success result:** String with refresh output

#### POST /api/tools/check_ansible_service
- **Description:** Validate an Ansible playbook (check mode)
- **Required fields:** `service_name`, `hostname`
- **Request:** `{"service_name": "ollama_ansible", "hostname": "192.168.1.10"}`
- **Success result:** String with check mode output

#### POST /api/tools/run_ansible_playbook
- **Description:** Execute an Ansible playbook for service deployment
- **Required fields:** `service_name`, `hostname`
- **Optional fields:** `tags`, `extra_vars`
- **Request:** `{"service_name": "ollama_ansible", "hostname": "192.168.1.10"}`
- **Success result:** String with playbook execution output

### 4.5 Credential Management Tools (5 tools)

#### POST /api/tools/register_server
- **Description:** Register a host with SSH or Proxmox credentials in the OS keyring
- **Required fields:** `hostname`, `username`, `password`
- **Optional fields:** `credential_type`, `port`
- **Request:** `{"hostname": "192.168.1.10", "username": "root", "password": "pass", "credential_type": "ssh"}`
- **Success result:** String with registration confirmation

#### POST /api/tools/list_registered_servers
- **Description:** List all stored server credentials
- **Required fields:** none
- **Optional fields:** `credential_type`
- **Request:** `{}`
- **Success result:** `{"status": "success", "total_servers": N, "servers": [{"hostname": "...", "username": "...", "type": "ssh"}, ...]}`

#### POST /api/tools/update_server_credentials
- **Description:** Update stored credentials for a server
- **Required fields:** `hostname`
- **Optional fields:** `username`, `password`, `credential_type`
- **Request:** `{"hostname": "192.168.1.10", "username": "root", "password": "newpass"}`
- **Success result:** String with update confirmation

#### POST /api/tools/remove_server
- **Description:** Remove server credentials from the keyring
- **Required fields:** `hostname`
- **Optional fields:** `credential_type`, `dry_run`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** String with removal confirmation

#### POST /api/tools/remove_server_preview
- **Description:** Dry-run preview of credential removal
- **Required fields:** `hostname`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** Dict with preview of what would be removed

### 4.6 Infrastructure Lifecycle Tools (9 tools)

#### POST /api/tools/deploy_infrastructure
- **Description:** Execute a multi-device deployment plan
- **Required fields:** `plan`
- **Request:** `{"plan": {"services": [...], "network": {...}}}`
- **Success result:** Dict with deployment results

#### POST /api/tools/update_device_config
- **Description:** Modify device settings in the database
- **Required fields:** `hostname`
- **Optional fields:** various device config fields
- **Request:** `{"hostname": "192.168.1.10", "tags": ["webserver"]}`
- **Success result:** String with update confirmation

#### POST /api/tools/decommission_device
- **Description:** Safely remove a device with dependency analysis
- **Required fields:** `hostname`
- **Optional fields:** `migration_plan`, `force`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** Dict with decommission results

#### POST /api/tools/decommission_device_preview
- **Description:** Dry-run preview of device decommissioning
- **Required fields:** `hostname`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** Dict with dependency analysis and impact report

#### POST /api/tools/scale_services
- **Description:** Scale service replicas up or down
- **Required fields:** `hostname`, `service_name`, `replicas`
- **Request:** `{"hostname": "192.168.1.10", "service_name": "nginx", "replicas": 3}`
- **Success result:** String with scaling results

#### POST /api/tools/validate_infrastructure_changes
- **Description:** Pre-flight validation of infrastructure changes
- **Required fields:** `plan`
- **Request:** `{"plan": {"services": [...]}}`
- **Success result:** Dict with validation results

#### POST /api/tools/create_infrastructure_backup
- **Description:** Create a backup of infrastructure state
- **Required fields:** `hostname`
- **Optional fields:** `backup_type`
- **Request:** `{"hostname": "192.168.1.10"}`
- **Success result:** Dict with backup ID and metadata

#### POST /api/tools/rollback_infrastructure_changes
- **Description:** Rollback to a previous infrastructure state
- **Required fields:** `backup_id`
- **Request:** `{"backup_id": "backup-123"}`
- **Success result:** Dict with rollback results

#### POST /api/tools/rollback_infrastructure_changes_preview
- **Description:** Dry-run preview of infrastructure rollback
- **Required fields:** `backup_id`
- **Request:** `{"backup_id": "backup-123"}`
- **Success result:** Dict with preview of changes

### 4.7 Proxmox Tools (11 tools)

#### POST /api/tools/search_proxmox_scripts
- **Description:** Search the community-scripts/ProxmoxVE GitHub repository
- **Required fields:** `query`
- **Optional fields:** `category`
- **Request:** `{"query": "docker"}`
- **Success result:** `{"status": "success", "query": "docker", "total_found": N, "scripts": [{"name": "...", "path": "...", "download_url": "...", "category": "ct"}, ...]}`

#### POST /api/tools/get_proxmox_script_info
- **Description:** Get detailed metadata for a community script
- **Required fields:** `script_name`
- **Request:** `{"script_name": "docker"}`
- **Success result:** Dict with script description, requirements, and install info

#### POST /api/tools/list_proxmox_resources
- **Description:** List all VMs, containers, nodes, and storage in a Proxmox cluster
- **Required fields:** `hostname`
- **Optional fields:** `resource_type`
- **Request:** `{"hostname": "192.168.1.100"}`
- **Success result:** Dict with resources grouped by type

#### POST /api/tools/get_proxmox_node_status
- **Description:** Get CPU, memory, uptime, and storage stats for a node
- **Required fields:** `hostname`, `node`
- **Request:** `{"hostname": "192.168.1.100", "node": "pve"}`
- **Success result:** Dict with node metrics

#### POST /api/tools/get_proxmox_vm_status
- **Description:** Get detailed status for a specific VM or container
- **Required fields:** `hostname`, `vmid`
- **Optional fields:** `node`
- **Request:** `{"hostname": "192.168.1.100", "vmid": 100}`
- **Success result:** Dict with VM status details

#### POST /api/tools/manage_proxmox_vm
- **Description:** Perform state operations on a VM (start, stop, shutdown, reboot, reset, suspend, resume)
- **Required fields:** `hostname`, `vmid`, `action`
- **Optional fields:** `node`
- **Request:** `{"hostname": "192.168.1.100", "vmid": 100, "action": "start"}`
- **Success result:** String with action confirmation

#### POST /api/tools/create_proxmox_lxc
- **Description:** Create a new LXC container in Proxmox
- **Required fields:** `hostname`, `node`, `ostemplate`
- **Optional fields:** `vmid`, `memory`, `cores`, `rootfs_size`, `hostname_lxc`, `password`, `storage`
- **Request:** `{"hostname": "192.168.1.100", "node": "pve", "ostemplate": "local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"}`
- **Success result:** Dict with new container ID and status

#### POST /api/tools/create_proxmox_vm
- **Description:** Create a new QEMU virtual machine in Proxmox
- **Required fields:** `hostname`, `node`, `name`
- **Optional fields:** `vmid`, `memory`, `cores`, `disk_size`, `iso`, `storage`
- **Request:** `{"hostname": "192.168.1.100", "node": "pve", "name": "testvm"}`
- **Success result:** Dict with new VM ID and status

#### POST /api/tools/clone_proxmox_vm
- **Description:** Clone an existing VM or container
- **Required fields:** `hostname`, `vmid`, `newid`
- **Optional fields:** `node`, `name`, `full`
- **Request:** `{"hostname": "192.168.1.100", "vmid": 100, "newid": 200}`
- **Success result:** Dict with cloned VM details

#### POST /api/tools/delete_proxmox_vm
- **Description:** Delete a VM or container from Proxmox
- **Required fields:** `hostname`, `vmid`
- **Optional fields:** `node`, `purge`
- **Request:** `{"hostname": "192.168.1.100", "vmid": 200}`
- **Success result:** String with deletion confirmation

#### POST /api/tools/delete_proxmox_vm_preview
- **Description:** Dry-run preview of VM/container deletion
- **Required fields:** `hostname`, `vmid`
- **Optional fields:** `node`
- **Request:** `{"hostname": "192.168.1.100", "vmid": 200}`
- **Success result:** Dict with preview of what would be deleted

### 4.8 Drift Detection Tools (1 tool)

#### POST /api/tools/scan_infrastructure_drift
- **Description:** Scan for configuration and state drift from stored baselines
- **Required fields:** `hostname`
- **Optional fields:** `node`, `scan_type`, `vmid`
- **Request:** `{"hostname": "192.168.1.100"}`
- **Success result:** Dict with drift report (expected vs actual values, drift type, timestamps)

---

## 5. Error Handling

All endpoints return consistent error responses:

- **400 Bad Request:** Invalid input parameters (validation errors from tool schemas)
- **404 Not Found:** Tool name does not exist in the registry — `{"status": "error", "error": "Not Found"}`
- **412 Precondition Failed:** Infrastructure precondition not met post-handler (missing credentials, unclassified connection failure) — `{"status": "precondition_failed", "tool": "tool_name", "error": "...", "requires": "..."}`
- **422 Unprocessable Entity:** Request body validation failure — `{"status": "error", "error": "Validation error", "details": [...]}`
- **424 Failed Dependency:** External target host is unreachable per the pre-handler TCP probe — `{"status": "failed_dependency", "tool": "tool_name", "host": "...", "port": N, "protocol": "...", "error": "...", "requires": "..."}`
- **500 Internal Server Error:** Unexpected tool execution failure — `{"status": "error", "tool": "tool_name", "error": "descriptive message"}`

### External Dependency Preflight

Tools that connect to an external host (SSH targets on port 22, Proxmox API on port 8006) undergo a TCP-connect reachability probe (1s timeout) before the handler runs. On failure the endpoint returns **424 Failed Dependency** and does not execute the tool. The target host is resolved from the request body field (`hostname` for SSH-class tools, `host` for Proxmox tools) or from an environment variable where applicable. Tools without a resolvable target skip the preflight and proceed normally — downstream handler errors still surface as 412/500.

Each route that performs preflight advertises it in the `/docs` description under **External dependency**.

---

## 6. Test Expectations

### Tools that work without infrastructure (testable without SSH/Proxmox targets):
- `GET /health` — always returns healthy status
- `GET /api/tools` — always returns 56 tools
- `POST /api/tools/list_available_services` — returns service template list
- `POST /api/tools/get_service_info` — returns metadata for known services
- `POST /api/tools/list_registered_servers` — returns credential list (empty on fresh install)
- `POST /api/tools/get_network_sitemap` — returns device list (empty on fresh install)
- `POST /api/tools/analyze_network_topology` — returns analysis (empty data on fresh install)
- `POST /api/tools/suggest_deployments` — returns suggestions (empty data on fresh install)
- `POST /api/tools/get_device_changes` — returns change history (empty on fresh install)
- `POST /api/tools/search_proxmox_scripts` — searches GitHub, returns matching scripts

### Tools that require SSH targets (will return errors without infrastructure):
- All SSH tools (ssh_discover, setup_mcp_admin, verify_mcp_admin, ssh_execute_command, etc.)
- All VM tools (deploy_vm, control_vm, list_vms, etc.)
- Service installation tools (install_service, check_service_requirements, get_service_status)
- Infrastructure lifecycle tools

### Tools that require Proxmox targets:
- list_proxmox_resources, get_proxmox_node_status, get_proxmox_vm_status
- create_proxmox_lxc, create_proxmox_vm, clone_proxmox_vm
- manage_proxmox_vm, delete_proxmox_vm

### Error handling tests:
- Non-existent tool returns 404 with `{"status": "error", "error": "Not Found"}`
- SSH to unreachable host returns **424 Failed Dependency** from the preflight probe (not 500), with `host`, `port`, `protocol`, and `requires` fields in the body
- Proxmox tool against an unreachable host returns **424 Failed Dependency** for port 8006
- Tools with missing required fields return 400 or 422 with error details
- Preflight is bypassed when the host field is absent from the body — downstream validation/handler errors apply
