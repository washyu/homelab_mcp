# Tool Reference

Homelab MCP Server provides tools organized into seven categories: SSH, Network, Infrastructure, VM, Service, Credential, and Proxmox. See individual categories below for the complete list.

Each tool is documented with its description, annotations, arguments, a usage example, and return information.

## Table of Contents

- [Annotation Legend](#annotation-legend)
- [SSH Tools](#ssh-tools)
- [Network Tools](#network-tools)
- [Infrastructure Tools](#infrastructure-tools)
- [VM Tools](#vm-tools)
- [Service Tools](#service-tools)
- [Credential Tools](#credential-tools)
- [Proxmox Tools](#proxmox-tools)

## Annotation Legend

MCP tool annotations provide hints to clients about tool behavior:

| Badge | Meaning |
|-------|---------|
| `[Read-Only]` | Only queries state; never modifies anything (`readOnlyHint=True`) |
| `[Destructive]` | Deletes or destroys resources (`destructiveHint=True`) |
| `[Idempotent]` | Safe to call multiple times with the same result (`idempotentHint=True`) |
| `[Open-World]` | May interact with external systems in unpredictable ways (`openWorldHint=True`) |

---

## SSH Tools

Tools for SSH-based system discovery, administration, and remote command execution.

### ssh_discover

**Description:** SSH into a system and gather hardware/system information.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address |
| username | string | Yes | -- | SSH username (use 'mcp_admin' for passwordless access after setup) |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| key_path | string | No | -- | Path to SSH private key |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "username": "mcp_admin"
}
```

**Returns:** A dict with comprehensive system information including CPU, memory, storage, network interfaces, and hardware details.

---

### setup_mcp_admin

**Description:** SSH into a remote system and setup mcp_admin user with admin permissions and SSH key access.

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address of the target system |
| username | string | Yes | -- | Admin username to connect with (must have sudo access) |
| password | string | Yes | -- | Password for the admin user |
| force_update_key | boolean | No | true | Force update SSH key even if mcp_admin already has keys |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "username": "admin",
  "password": "adminpass",
  "force_update_key": true
}
```

**Returns:** A dict with the setup result including user creation status and key installation details.

---

### verify_mcp_admin

**Description:** Verify SSH key access to mcp_admin account on a remote system.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address of the target system |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "hostname": "192.168.1.50"
}
```

**Returns:** A dict with verification status including SSH key authentication and sudo privilege checks.

---

### ssh_execute_command

**Description:** Execute a command on a remote system via SSH.

**Annotations:** `[Open-World]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address |
| username | string | Yes | -- | SSH username (use 'mcp_admin' for passwordless access after setup) |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| command | string | Yes | -- | Command to execute on the remote system |
| sudo | boolean | No | false | Execute command with sudo privileges |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "username": "mcp_admin",
  "command": "df -h",
  "sudo": false
}
```

**Returns:** A dict with command output including stdout, stderr, and exit code.

---

### start_interactive_shell

**Description:** Start an interactive web-based shell session on a remote system. Opens a browser-based terminal with full TTY support for running interactive commands and scripts. Perfect for Proxmox community scripts or any interactive command-line tools.

**Annotations:** `[Open-World]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address of the target system |
| username | string | No | -- | SSH username (optional, uses registered credentials if available) |
| password | string | No | -- | SSH password (optional, uses SSH keys if available) |
| port | integer | No | 22 | SSH port |
| initial_command | string | No | -- | Optional command to run automatically when shell starts |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "initial_command": "bash -c \"$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/docker.sh)\""
}
```

**Returns:** A dict with the shell session URL and connection details.

---

### update_mcp_admin_groups

**Description:** Update mcp_admin group memberships to include groups for installed services (docker, lxd, libvirt, kvm).

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address of the target system |
| username | string | Yes | -- | Admin username to connect with (must have sudo access) |
| password | string | Yes | -- | Password for the admin user |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "username": "admin",
  "password": "adminpass"
}
```

**Returns:** A dict with the updated group memberships for the mcp_admin user.

---

## Network Tools

Tools for network device discovery, topology mapping, and change tracking.

### discover_and_map

**Description:** Discover a device via SSH and store it in the network site map database.

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address |
| username | string | Yes | -- | SSH username (use 'mcp_admin' for passwordless access after setup) |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| key_path | string | No | -- | Path to SSH private key |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "username": "mcp_admin"
}
```

**Returns:** A dict with the discovered device information and its database record.

---

### bulk_discover_and_map

**Description:** Discover multiple devices via SSH and store them in the network site map database.

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| targets | array | Yes | -- | Array of target device configurations. Each item has: hostname (string, required), username (string, required), password (string), key_path (string), port (integer, default 22) |

**Example:**

```json
{
  "targets": [
    {"hostname": "192.168.1.50", "username": "mcp_admin"},
    {"hostname": "192.168.1.51", "username": "mcp_admin"},
    {"hostname": "192.168.1.52", "username": "mcp_admin"}
  ]
}
```

**Returns:** A dict with discovery results for each target device.

---

### get_network_sitemap

**Description:** Get all discovered devices from the network site map database.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

None.

**Example:**

```json
{}
```

**Returns:** A dict with all discovered devices and their details from the site map database.

---

### analyze_network_topology

**Description:** Analyze the network topology and provide insights about the discovered devices.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

None.

**Example:**

```json
{}
```

**Returns:** A dict with topology analysis including network segments, device relationships, and insights.

---

### suggest_deployments

**Description:** Suggest optimal deployment locations based on current network topology and device capabilities.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

None.

**Example:**

```json
{}
```

**Returns:** A dict with deployment suggestions based on available device resources and network topology.

---

### get_device_changes

**Description:** Get change history for a specific device.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the device |
| limit | integer | No | 10 | Maximum number of changes to return |

**Example:**

```json
{
  "device_id": 1,
  "limit": 5
}
```

**Returns:** A dict with the change history records for the specified device.

---

## Infrastructure Tools

Tools for infrastructure deployment, configuration, scaling, backup, and rollback.

### deploy_infrastructure

**Description:** Deploy new infrastructure based on AI recommendations or user specifications.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| deployment_plan | object | Yes | -- | Infrastructure deployment plan containing: services (array of {name, type, target_device_id, config}), network_changes (array of {action, target_device_id, config}) |
| validate_only | boolean | No | false | Only validate the plan without executing |

**Example:**

```json
{
  "deployment_plan": {
    "services": [
      {
        "name": "nginx",
        "type": "docker",
        "target_device_id": 1,
        "config": {"ports": ["80:80", "443:443"]}
      }
    ]
  },
  "validate_only": false
}
```

**Returns:** A dict with deployment results including service statuses and any errors.

---

### update_device_config

**Description:** Update configuration of an existing device.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the device to update |
| config_changes | object | Yes | -- | Configuration changes to apply containing: services (object), network (object), security (object), resources (object) |
| backup_before_change | boolean | No | true | Create backup before applying changes |
| validate_only | boolean | No | false | Only validate changes without applying |

**Example:**

```json
{
  "device_id": 1,
  "config_changes": {
    "resources": {"memory_limit": "4GB"},
    "network": {"vlan": 10}
  },
  "backup_before_change": true
}
```

**Returns:** A dict with the configuration update results.

---

### decommission_device

**Description:** Safely remove a device from the network infrastructure.

**Annotations:** `[Destructive]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the device to decommission |
| migration_plan | object | No | -- | Plan for migrating services to other devices containing: target_devices (array of integers), service_mapping (object) |
| force_removal | boolean | No | false | Force removal without migration (data loss possible) |
| validate_only | boolean | No | false | Only validate decommission plan without executing |

**Example:**

```json
{
  "device_id": 3,
  "migration_plan": {
    "target_devices": [1, 2],
    "service_mapping": {"nginx": 1, "postgres": 2}
  },
  "validate_only": true
}
```

**Returns:** A dict with the decommission operation results or validation report.

---

### scale_services

**Description:** Scale services up or down based on resource analysis.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| scaling_plan | object | Yes | -- | Service scaling plan containing: scale_up (array of {device_id, service_name, target_replicas, resource_allocation}), scale_down (array of {device_id, service_name, target_replicas}) |
| validate_only | boolean | No | false | Only validate scaling plan without executing |

**Example:**

```json
{
  "scaling_plan": {
    "scale_up": [
      {"device_id": 1, "service_name": "nginx", "target_replicas": 3}
    ]
  },
  "validate_only": false
}
```

**Returns:** A dict with scaling operation results.

---

### validate_infrastructure_changes

**Description:** Validate infrastructure changes before applying them.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| change_plan | object | Yes | -- | Infrastructure change plan to validate |
| validation_level | string | No | "comprehensive" | Level of validation to perform. One of: "basic", "comprehensive", "simulation" |

**Example:**

```json
{
  "change_plan": {
    "services": [{"name": "redis", "type": "docker", "target_device_id": 1}]
  },
  "validation_level": "comprehensive"
}
```

**Returns:** A dict with validation results including any warnings or errors found.

---

### create_infrastructure_backup

**Description:** Create a backup of current infrastructure state.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| backup_scope | string | No | "full" | Scope of the backup. One of: "full", "partial", "device_specific" |
| device_ids | array | No | -- | Specific device IDs to backup (for partial/device_specific) |
| include_data | boolean | No | false | Include application data in backup |
| backup_name | string | No | -- | Name for the backup (auto-generated if not provided) |

**Example:**

```json
{
  "backup_scope": "device_specific",
  "device_ids": [1, 2],
  "backup_name": "pre-migration-backup"
}
```

**Returns:** A dict with backup details including backup ID and location.

---

### rollback_infrastructure_changes

**Description:** Rollback recent infrastructure changes.

**Annotations:** `[Destructive]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| backup_id | string | Yes | -- | Backup ID to rollback to |
| rollback_scope | string | No | "full" | Scope of the rollback. One of: "full", "partial", "device_specific" |
| device_ids | array | No | -- | Specific device IDs to rollback (for partial/device_specific) |
| validate_only | boolean | No | false | Only validate rollback plan without executing |

**Example:**

```json
{
  "backup_id": "backup-2024-01-15-001",
  "rollback_scope": "full",
  "validate_only": true
}
```

**Returns:** A dict with rollback operation results or validation report.

---

### scan_infrastructure_drift

**Description:** Scan for infrastructure drift against the sitemap. Iterates registered devices in the network sitemap, resolves Proxmox credentials per row through the keyring (per-node -> cluster -> error), and probes each resolved host's `/cluster/status` endpoint. Returns a 2-bucket coverage report (`probed_ok`, `unreachable`) per host. Filter semantics for `node` and `vm_type` are under Phase 37 redesign and are currently inert -- both arguments are accepted for back-compat but not yet acted upon.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | No | (none) | Filter scope (Phase 37 will activate; currently inert) |
| vm_type | string | No | "all" | Filter scope: "qemu", "lxc", or "all" (Phase 37 will activate; currently inert) |

**Example:**

```json
{}
```

**Returns:**

```json
{
  "status": "success",
  "scan_timestamp": "2026-04-25T12:34:56+00:00",
  "scanned": 2,
  "probed_ok": [
    {
      "hostname": "pve1",
      "connection_ip": "10.0.0.10",
      "scope": "node",
      "cluster_name": null,
      "status": "probed-ok",
      "error": null,
      "scan_timestamp": "2026-04-25T12:34:56+00:00"
    }
  ],
  "unreachable": [
    {
      "hostname": "pi-lab",
      "connection_ip": "10.0.0.12",
      "scope": "cluster",
      "cluster_name": "homelab-prod",
      "status": "unreachable",
      "error": "Cannot connect to host pi-lab",
      "scan_timestamp": "2026-04-25T12:34:56+00:00"
    }
  ]
}
```

**Notes:**
- Baselines are not registered separately. The sitemap (populated by `discover_and_map`) serves as the baseline for drift detection. To add a host to drift coverage, register it via `discover_and_map`.
- Hosts without Proxmox credentials in the keyring are silently excluded (they are not Proxmox hosts).
- Empty sitemap returns a successful empty result (`scanned: 0`), not an error.
- Phase 37 will expand the response to a 4-bucket shape (probed-OK / unreachable / unknown / changed).

---

## VM Tools

Tools for deploying, controlling, monitoring, and removing virtual machines and containers.

### deploy_vm

**Description:** Deploy a new VM/container on a specific device.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the target device |
| platform | string | Yes | -- | VM platform to use. One of: "docker", "lxd" |
| vm_name | string | Yes | -- | Name for the new VM/container |
| vm_config | object | No | -- | VM configuration containing: image (string), ports (array of strings), volumes (array of strings), environment (object), command (string) |

**Example:**

```json
{
  "device_id": 1,
  "platform": "docker",
  "vm_name": "web-server",
  "vm_config": {
    "image": "nginx:latest",
    "ports": ["80:80", "443:443"],
    "environment": {"NGINX_HOST": "example.com"}
  }
}
```

**Returns:** A dict with deployment results including container ID and status.

---

### control_vm

**Description:** Control VM state (start, stop, restart).

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the target device |
| platform | string | Yes | -- | VM platform. One of: "docker", "lxd" |
| vm_name | string | Yes | -- | Name of the VM/container |
| action | string | Yes | -- | Action to perform. One of: "start", "stop", "restart" |

**Example:**

```json
{
  "device_id": 1,
  "platform": "docker",
  "vm_name": "web-server",
  "action": "restart"
}
```

**Returns:** A dict with the operation result and current VM state.

---

### get_vm_status

**Description:** Get detailed status of a specific VM.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the target device |
| platform | string | Yes | -- | VM platform. One of: "docker", "lxd" |
| vm_name | string | Yes | -- | Name of the VM/container |

**Example:**

```json
{
  "device_id": 1,
  "platform": "docker",
  "vm_name": "web-server"
}
```

**Returns:** A dict with detailed VM status including resource usage, network, and health.

---

### list_vms

**Description:** List all VMs/containers on a device.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the target device |
| platforms | array | No | -- | Platforms to check (default: ['docker', 'lxd']). Items: "docker", "lxd" |

**Example:**

```json
{
  "device_id": 1,
  "platforms": ["docker"]
}
```

**Returns:** A dict with a list of all VMs/containers and their statuses on the device.

---

### get_vm_logs

**Description:** Get logs from a specific VM/container.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the target device |
| platform | string | Yes | -- | VM platform. One of: "docker", "lxd" |
| vm_name | string | Yes | -- | Name of the VM/container |
| lines | integer | No | 100 | Number of log lines to retrieve |

**Example:**

```json
{
  "device_id": 1,
  "platform": "docker",
  "vm_name": "web-server",
  "lines": 50
}
```

**Returns:** A dict with the log output from the specified VM/container.

---

### remove_vm

**Description:** Remove a VM/container from a device.

**Annotations:** `[Destructive]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the target device |
| platform | string | Yes | -- | VM platform. One of: "docker", "lxd" |
| vm_name | string | Yes | -- | Name of the VM/container |
| force | boolean | No | false | Force removal without graceful shutdown |

**Example:**

```json
{
  "device_id": 1,
  "platform": "docker",
  "vm_name": "old-container",
  "force": false
}
```

**Returns:** A dict with the removal operation result.

---

## Service Tools

Tools for managing homelab service installations, Terraform deployments, and Ansible playbooks.

### list_available_services

**Description:** List all available homelab services that can be installed.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

None.

**Example:**

```json
{}
```

**Returns:** A dict with all available service templates and their descriptions.

---

### get_service_info

**Description:** Get detailed information about a specific service.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to get information about |

**Example:**

```json
{
  "service_name": "jellyfin"
}
```

**Returns:** A dict with detailed service information including requirements, configuration options, and dependencies.

---

### check_service_requirements

**Description:** Check if a device meets the requirements for a service installation.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to check requirements for |
| hostname | string | Yes | -- | Hostname or IP address of the target device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "ollama",
  "hostname": "192.168.1.50",
  "username": "mcp_admin"
}
```

**Returns:** A dict with requirement check results including pass/fail status and details.

---

### install_service

**Description:** Install a homelab service on a target device.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to install (e.g., 'jellyfin', 'nextcloud') |
| hostname | string | Yes | -- | Hostname or IP address of the target device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| config_override | object | No | -- | Optional configuration overrides for the service |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "pihole",
  "hostname": "192.168.1.50",
  "config_override": {"dns_port": 5353}
}
```

**Returns:** A dict with installation results including service status and access details.

---

### get_service_status

**Description:** Get the current status of an installed service.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to check status for |
| hostname | string | Yes | -- | Hostname or IP address of the device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "pihole",
  "hostname": "192.168.1.50"
}
```

**Returns:** A dict with the service's current status, health, and resource usage.

---

### plan_terraform_service

**Description:** Generate a Terraform plan to preview changes without applying them.

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to plan |
| hostname | string | Yes | -- | Hostname or IP address of the device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| config_override | object | No | -- | Optional configuration overrides for the service |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "pihole",
  "hostname": "192.168.1.50",
  "config_override": {"web_port": 8080}
}
```

**Returns:** A dict with the Terraform execution plan showing proposed changes.

---

### destroy_terraform_service

**Description:** Destroy a Terraform-managed service and clean up all resources.

**Annotations:** `[Destructive]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to destroy |
| hostname | string | Yes | -- | Hostname or IP address of the device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "pihole",
  "hostname": "192.168.1.50"
}
```

**Returns:** A dict with the destruction results and resource cleanup details.

---

### refresh_terraform_service

**Description:** Refresh Terraform state and detect configuration drift.

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to refresh |
| hostname | string | Yes | -- | Hostname or IP address of the device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "pihole",
  "hostname": "192.168.1.50"
}
```

**Returns:** A dict with the refreshed state and any detected drift.

---

### check_ansible_service

**Description:** Check the status of an Ansible-managed service deployment.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service to check |
| hostname | string | Yes | -- | Hostname or IP address of the device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "ai_homelab_stack_ansible",
  "hostname": "192.168.1.50"
}
```

**Returns:** A dict with the Ansible service deployment status.

---

### run_ansible_playbook

**Description:** Run an existing Ansible playbook for a service.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| service_name | string | Yes | -- | Name of the service playbook to run |
| hostname | string | Yes | -- | Hostname or IP address of the device |
| username | string | No | "mcp_admin" | SSH username |
| password | string | No | -- | SSH password (not needed for mcp_admin after setup) |
| tags | array | No | -- | Ansible tags to run specific tasks |
| extra_vars | object | No | -- | Extra variables to pass to the playbook |
| check_mode | boolean | No | false | Run in check mode (dry run) |
| port | integer | No | 22 | SSH port |

**Example:**

```json
{
  "service_name": "ai_homelab_stack_ansible",
  "hostname": "192.168.1.50",
  "tags": ["ollama", "webui"],
  "check_mode": true
}
```

**Returns:** A dict with playbook execution results including task statuses.

---

## Credential Tools

Tools for registering and managing persistent server SSH credentials.

### register_server

**Description:** Register a server with SSH credentials for persistent access without repeatedly providing credentials.

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| hostname | string | Yes | -- | Hostname or IP address of the server |
| username | string | No | "mcp_admin" | SSH username |
| key_path | string | No | -- | Path to SSH private key (optional, uses default MCP key if not provided) |
| port | integer | No | 22 | SSH port |
| display_name | string | No | -- | Friendly name for the server |
| verify_connection | boolean | No | true | Whether to verify SSH connection before saving |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "display_name": "Main Server",
  "verify_connection": true
}
```

**Returns:** A dict with the registration result and credential ID.

---

### list_registered_servers

**Description:** List all registered servers with their SSH credentials and connection status.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| active_only | boolean | No | true | Only show active servers |

**Example:**

```json
{
  "active_only": true
}
```

**Returns:** A dict with all registered servers and their credential details.

---

### update_server_credentials

**Description:** Update SSH credentials for an existing registered server.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| credential_id | integer | No | -- | ID of the credential to update (optional if hostname provided) |
| hostname | string | No | -- | Hostname to look up (optional if credential_id provided) |
| username | string | No | -- | New SSH username |
| key_path | string | No | -- | New path to SSH private key |
| port | integer | No | -- | New SSH port |
| display_name | string | No | -- | New friendly name for the server |
| is_active | boolean | No | -- | Set server active/inactive status |

**Example:**

```json
{
  "hostname": "192.168.1.50",
  "username": "new_admin",
  "display_name": "Renamed Server"
}
```

**Returns:** A dict with the updated credential details.

---

### remove_server

**Description:** Remove a server from the registered servers list.

**Annotations:** `[Destructive]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| credential_id | integer | No | -- | ID of the credential to remove (optional if hostname provided) |
| hostname | string | No | -- | Hostname to look up (optional if credential_id provided) |

**Example:**

```json
{
  "hostname": "192.168.1.50"
}
```

**Returns:** A dict with the removal confirmation.

---

## Proxmox Tools

Tools for Proxmox API integration, community script discovery, and VM/container lifecycle management.

### search_proxmox_scripts

**Description:** Search Proxmox community installation scripts from the community-scripts/ProxmoxVE repository.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| query | string | Yes | -- | Search query (matches script name, e.g. 'home assistant', 'docker', 'pihole') |
| category | string | No | -- | Optional category filter. One of: "ct", "vm", "install", "misc" |
| include_metadata | boolean | No | false | If true, fetch and parse script metadata (CPU, RAM, disk requirements). Slower but more detailed. |

**Example:**

```json
{
  "query": "docker",
  "category": "ct",
  "include_metadata": true
}
```

**Returns:** A dict with matching scripts and their details.

---

### get_proxmox_script_info

**Description:** Get detailed information about a specific Proxmox community script.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| script_name | string | Yes | -- | Name of the script file (e.g. 'homeassistant.sh', 'docker.sh') |
| category | string | No | -- | Optional category hint to speed up search. One of: "ct", "vm", "install", "misc" |

**Example:**

```json
{
  "script_name": "homeassistant.sh",
  "category": "ct"
}
```

**Returns:** A dict with detailed script information including requirements, tags, and download URL.

---

### list_proxmox_resources

**Description:** List all Proxmox cluster resources (VMs, containers, nodes, storage). Uses PROXMOX_HOST from environment if host not provided.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| host | string | No | -- | Proxmox host (optional, uses PROXMOX_HOST env var if not provided) |
| resource_type | string | No | -- | Filter by resource type. One of: "vm", "lxc", "node", "storage", "pool" |

**Example:**

```json
{
  "resource_type": "vm"
}
```

**Returns:** A dict with all matching Proxmox cluster resources and their statuses.

---

### get_proxmox_node_status

**Description:** Get detailed status of a Proxmox node (CPU, memory, uptime, etc.).

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | Yes | -- | Node name (e.g., 'pve', 'proxmox') |
| host | string | No | -- | Proxmox host (optional, uses PROXMOX_HOST env var) |

**Example:**

```json
{
  "node": "pve"
}
```

**Returns:** A dict with detailed node status including CPU, memory, uptime, and disk statistics.

---

### get_proxmox_vm_status

**Description:** Get status of a specific VM or container.

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | Yes | -- | Node name |
| vmid | integer | Yes | -- | VM or Container ID |
| vm_type | string | No | "qemu" | Type: 'qemu' for VM or 'lxc' for container. One of: "qemu", "lxc" |
| host | string | No | -- | Proxmox host (optional) |

**Example:**

```json
{
  "node": "pve",
  "vmid": 100,
  "vm_type": "qemu"
}
```

**Returns:** A dict with detailed VM/container status including resource usage and configuration.

---

### manage_proxmox_vm

**Description:** Manage a VM or container (start, stop, shutdown, reboot, reset, suspend, resume).

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | Yes | -- | Node name |
| vmid | integer | Yes | -- | VM or Container ID |
| action | string | Yes | -- | Action to perform. One of: "start", "stop", "shutdown", "reboot", "reset", "suspend", "resume" |
| vm_type | string | No | "qemu" | Type: 'qemu' for VM or 'lxc' for container. One of: "qemu", "lxc" |
| host | string | No | -- | Proxmox host (optional) |

**Example:**

```json
{
  "node": "pve",
  "vmid": 100,
  "action": "shutdown",
  "vm_type": "qemu"
}
```

**Returns:** A dict with the operation result and task ID.

---

### create_proxmox_lxc

**Description:** Create a new LXC container on Proxmox.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | Yes | -- | Node name |
| vmid | integer | Yes | -- | Container ID (must be unique) |
| hostname | string | Yes | -- | Container hostname |
| ostemplate | string | No | "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst" | Template to use |
| storage | string | No | "local-lvm" | Storage for rootfs |
| memory | integer | No | 512 | RAM in MB |
| cores | integer | No | 1 | Number of CPU cores |
| rootfs_size | integer | No | 8 | Root filesystem size in GB |
| password | string | No | -- | Root password |
| start | boolean | No | false | Start container after creation |
| host | string | No | -- | Proxmox host (optional) |

**Example:**

```json
{
  "node": "pve",
  "vmid": 200,
  "hostname": "docker-host",
  "memory": 2048,
  "cores": 2,
  "rootfs_size": 16,
  "start": true
}
```

**Returns:** A dict with the container creation result and task ID.

---

### create_proxmox_vm

**Description:** Create a new VM (QEMU) on Proxmox.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | Yes | -- | Node name |
| vmid | integer | Yes | -- | VM ID (must be unique) |
| name | string | Yes | -- | VM name |
| memory | integer | No | 2048 | RAM in MB |
| cores | integer | No | 2 | Number of CPU cores |
| disk_size | integer | No | 32 | Disk size in GB |
| storage | string | No | "local-lvm" | Storage for disks |
| iso | string | No | -- | ISO image to attach (e.g., 'local:iso/debian-12.iso') |
| start | boolean | No | false | Start VM after creation |
| host | string | No | -- | Proxmox host (optional) |

**Example:**

```json
{
  "node": "pve",
  "vmid": 300,
  "name": "ubuntu-server",
  "memory": 4096,
  "cores": 4,
  "disk_size": 64,
  "iso": "local:iso/ubuntu-24.04-server.iso",
  "start": false
}
```

**Returns:** A dict with the VM creation result and task ID.

---

### clone_proxmox_vm

**Description:** Clone a VM or container to create a new one.

**Annotations:** (none -- mutating, non-idempotent)

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | Yes | -- | Node name |
| vmid | integer | Yes | -- | Source VM/Container ID |
| new_vmid | integer | Yes | -- | New VM/Container ID |
| name | string | No | -- | New VM name (optional) |
| full | boolean | No | true | Full clone (true) or linked clone (false) |
| vm_type | string | No | "qemu" | Type: 'qemu' for VM or 'lxc' for container. One of: "qemu", "lxc" |
| host | string | No | -- | Proxmox host (optional) |

**Example:**

```json
{
  "node": "pve",
  "vmid": 100,
  "new_vmid": 101,
  "name": "ubuntu-clone",
  "full": true
}
```

**Returns:** A dict with the clone operation result and task ID.

---

### delete_proxmox_vm

**Description:** Delete a VM or container from Proxmox.

**Annotations:** `[Destructive]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| node | string | Yes | -- | Node name |
| vmid | integer | Yes | -- | VM/Container ID to delete |
| vm_type | string | No | "qemu" | Type: 'qemu' for VM or 'lxc' for container. One of: "qemu", "lxc" |
| purge | boolean | No | false | Remove from all related configurations |
| host | string | No | -- | Proxmox host (optional) |

**Example:**

```json
{
  "node": "pve",
  "vmid": 100,
  "vm_type": "qemu",
  "purge": true
}
```

**Returns:** A dict with the deletion result and task ID.
