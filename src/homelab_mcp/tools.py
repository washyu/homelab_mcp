"""Tool definitions and execution for the Homelab MCP server."""

import json
import logging
from typing import Any

from .error_handling import timeout_wrapper
from .proxmox_scripts import (
    execute_proxmox_script,
    get_script_details,
    search_scripts,
)
from .sitemap import NetworkSiteMap, bulk_discover_and_store, discover_and_store
from .ssh_tools import (
    list_registered_servers,
    register_server,
    remove_server,
    setup_remote_mcp_admin,
    ssh_discover_system,
    update_server_credentials,
    verify_mcp_admin_access,
)

# Configure logging
logger = logging.getLogger(__name__)


# Tool registry
TOOLS = {
    "ssh_discover": {
        "description": "SSH into a system and gather hardware/system information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "key_path": {
                    "type": "string",
                    "description": "Path to SSH private key",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "username"],
        },
    },
    "setup_mcp_admin": {
        "description": "SSH into a remote system and setup mcp_admin user with admin permissions and SSH key access",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target system",
                },
                "username": {
                    "type": "string",
                    "description": "Admin username to connect with (must have sudo access)",
                },
                "password": {
                    "type": "string",
                    "description": "Password for the admin user",
                },
                "force_update_key": {
                    "type": "boolean",
                    "description": "Force update SSH key even if mcp_admin already has keys (default: true)",
                    "default": True,
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "username", "password"],
        },
    },
    "verify_mcp_admin": {
        "description": "Verify SSH key access to mcp_admin account on a remote system",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target system",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname"],
        },
    },
    "discover_and_map": {
        "description": "Discover a device via SSH and store it in the network site map database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "key_path": {
                    "type": "string",
                    "description": "Path to SSH private key",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "username"],
        },
    },
    "bulk_discover_and_map": {
        "description": "Discover multiple devices via SSH and store them in the network site map database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "description": "Array of target device configurations",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hostname": {"type": "string"},
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                            "key_path": {"type": "string"},
                            "port": {"type": "integer", "default": 22},
                        },
                        "required": ["hostname", "username"],
                    },
                }
            },
            "required": ["targets"],
        },
    },
    "get_network_sitemap": {
        "description": "Get all discovered devices from the network site map database",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "analyze_network_topology": {
        "description": "Analyze the network topology and provide insights about the discovered devices",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "suggest_deployments": {
        "description": "Suggest optimal deployment locations based on current network topology and device capabilities",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "get_device_changes": {
        "description": "Get change history for a specific device",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the device",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of changes to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["device_id"],
        },
    },
    "deploy_infrastructure": {
        "description": "Deploy new infrastructure based on AI recommendations or user specifications",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deployment_plan": {
                    "type": "object",
                    "description": "Infrastructure deployment plan",
                    "properties": {
                        "services": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {
                                        "type": "string",
                                        "enum": ["docker", "lxd", "service"],
                                    },
                                    "target_device_id": {"type": "integer"},
                                    "config": {"type": "object"},
                                },
                                "required": ["name", "type", "target_device_id"],
                            },
                        },
                        "network_changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "enum": [
                                            "create_vlan",
                                            "configure_firewall",
                                            "setup_routing",
                                        ],
                                    },
                                    "target_device_id": {"type": "integer"},
                                    "config": {"type": "object"},
                                },
                            },
                        },
                    },
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate the plan without executing",
                },
            },
            "required": ["deployment_plan"],
        },
    },
    "update_device_config": {
        "description": "Update configuration of an existing device",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the device to update",
                },
                "config_changes": {
                    "type": "object",
                    "description": "Configuration changes to apply",
                    "properties": {
                        "services": {
                            "type": "object",
                            "description": "Service configuration changes",
                        },
                        "network": {
                            "type": "object",
                            "description": "Network configuration changes",
                        },
                        "security": {
                            "type": "object",
                            "description": "Security configuration changes",
                        },
                        "resources": {
                            "type": "object",
                            "description": "Resource allocation changes",
                        },
                    },
                },
                "backup_before_change": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create backup before applying changes",
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate changes without applying",
                },
            },
            "required": ["device_id", "config_changes"],
        },
    },
    "decommission_device": {
        "description": "Safely remove a device from the network infrastructure",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the device to decommission",
                },
                "migration_plan": {
                    "type": "object",
                    "description": "Plan for migrating services to other devices",
                    "properties": {
                        "target_devices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Device IDs to migrate services to",
                        },
                        "service_mapping": {
                            "type": "object",
                            "description": "Mapping of services to target devices",
                        },
                    },
                },
                "force_removal": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force removal without migration (data loss possible)",
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate decommission plan without executing",
                },
            },
            "required": ["device_id"],
        },
    },
    "scale_services": {
        "description": "Scale services up or down based on resource analysis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scaling_plan": {
                    "type": "object",
                    "description": "Service scaling plan",
                    "properties": {
                        "scale_up": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "device_id": {"type": "integer"},
                                    "service_name": {"type": "string"},
                                    "target_replicas": {"type": "integer"},
                                    "resource_allocation": {"type": "object"},
                                },
                            },
                        },
                        "scale_down": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "device_id": {"type": "integer"},
                                    "service_name": {"type": "string"},
                                    "target_replicas": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate scaling plan without executing",
                },
            },
            "required": ["scaling_plan"],
        },
    },
    "validate_infrastructure_changes": {
        "description": "Validate infrastructure changes before applying them",
        "inputSchema": {
            "type": "object",
            "properties": {
                "change_plan": {
                    "type": "object",
                    "description": "Infrastructure change plan to validate",
                },
                "validation_level": {
                    "type": "string",
                    "enum": ["basic", "comprehensive", "simulation"],
                    "default": "comprehensive",
                    "description": "Level of validation to perform",
                },
            },
            "required": ["change_plan"],
        },
    },
    "create_infrastructure_backup": {
        "description": "Create a backup of current infrastructure state",
        "inputSchema": {
            "type": "object",
            "properties": {
                "backup_scope": {
                    "type": "string",
                    "enum": ["full", "partial", "device_specific"],
                    "default": "full",
                    "description": "Scope of the backup",
                },
                "device_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Specific device IDs to backup (for partial/device_specific)",
                },
                "include_data": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include application data in backup",
                },
                "backup_name": {
                    "type": "string",
                    "description": "Name for the backup (auto-generated if not provided)",
                },
            },
            "required": [],
        },
    },
    "rollback_infrastructure_changes": {
        "description": "Rollback recent infrastructure changes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "backup_id": {
                    "type": "string",
                    "description": "Backup ID to rollback to",
                },
                "rollback_scope": {
                    "type": "string",
                    "enum": ["full", "partial", "device_specific"],
                    "default": "full",
                    "description": "Scope of the rollback",
                },
                "device_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Specific device IDs to rollback (for partial/device_specific)",
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate rollback plan without executing",
                },
            },
            "required": ["backup_id"],
        },
    },
    "deploy_vm": {
        "description": "Deploy a new VM/container on a specific device",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the target device",
                },
                "platform": {
                    "type": "string",
                    "enum": ["docker", "lxd"],
                    "description": "VM platform to use (docker or lxd)",
                },
                "vm_name": {
                    "type": "string",
                    "description": "Name for the new VM/container",
                },
                "vm_config": {
                    "type": "object",
                    "description": "VM configuration",
                    "properties": {
                        "image": {
                            "type": "string",
                            "description": "Container/VM image to use",
                        },
                        "ports": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Port mappings (e.g., '80:80')",
                        },
                        "volumes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Volume mounts (e.g., '/host/path:/container/path')",
                        },
                        "environment": {
                            "type": "object",
                            "description": "Environment variables",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command to run in container",
                        },
                    },
                },
            },
            "required": ["device_id", "platform", "vm_name"],
        },
    },
    "control_vm": {
        "description": "Control VM state (start, stop, restart)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the target device",
                },
                "platform": {
                    "type": "string",
                    "enum": ["docker", "lxd"],
                    "description": "VM platform",
                },
                "vm_name": {
                    "type": "string",
                    "description": "Name of the VM/container",
                },
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "restart"],
                    "description": "Action to perform",
                },
            },
            "required": ["device_id", "platform", "vm_name", "action"],
        },
    },
    "get_vm_status": {
        "description": "Get detailed status of a specific VM",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the target device",
                },
                "platform": {
                    "type": "string",
                    "enum": ["docker", "lxd"],
                    "description": "VM platform",
                },
                "vm_name": {
                    "type": "string",
                    "description": "Name of the VM/container",
                },
            },
            "required": ["device_id", "platform", "vm_name"],
        },
    },
    "list_vms": {
        "description": "List all VMs/containers on a device",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the target device",
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["docker", "lxd"]},
                    "description": "Platforms to check (default: ['docker', 'lxd'])",
                },
            },
            "required": ["device_id"],
        },
    },
    "get_vm_logs": {
        "description": "Get logs from a specific VM/container",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the target device",
                },
                "platform": {
                    "type": "string",
                    "enum": ["docker", "lxd"],
                    "description": "VM platform",
                },
                "vm_name": {
                    "type": "string",
                    "description": "Name of the VM/container",
                },
                "lines": {
                    "type": "integer",
                    "default": 100,
                    "description": "Number of log lines to retrieve",
                },
            },
            "required": ["device_id", "platform", "vm_name"],
        },
    },
    "remove_vm": {
        "description": "Remove a VM/container from a device",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the target device",
                },
                "platform": {
                    "type": "string",
                    "enum": ["docker", "lxd"],
                    "description": "VM platform",
                },
                "vm_name": {
                    "type": "string",
                    "description": "Name of the VM/container",
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force removal without graceful shutdown",
                },
            },
            "required": ["device_id", "platform", "vm_name"],
        },
    },
    "ssh_execute_command": {
        "description": "Execute a command on a remote system via SSH",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute on the remote system",
                },
                "sudo": {
                    "type": "boolean",
                    "default": False,
                    "description": "Execute command with sudo privileges",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "username", "command"],
        },
    },
    "update_mcp_admin_groups": {
        "description": "Update mcp_admin group memberships to include groups for installed services (docker, lxd, libvirt, kvm)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target system",
                },
                "username": {
                    "type": "string",
                    "description": "Admin username to connect with (must have sudo access)",
                },
                "password": {
                    "type": "string",
                    "description": "Password for the admin user",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "username", "password"],
        },
    },
    "list_available_services": {
        "description": "List all available homelab services that can be installed",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "get_service_info": {
        "description": "Get detailed information about a specific service",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to get information about",
                }
            },
            "required": ["service_name"],
        },
    },
    "check_service_requirements": {
        "description": "Check if a device meets the requirements for a service installation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to check requirements for",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "install_service": {
        "description": "Install a homelab service on a target device",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to install (e.g., 'jellyfin', 'nextcloud')",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "config_override": {
                    "type": "object",
                    "description": "Optional configuration overrides for the service",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "get_service_status": {
        "description": "Get the current status of an installed service",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to check status for",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "plan_terraform_service": {
        "description": "Generate a Terraform plan to preview changes without applying them",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to plan",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "config_override": {
                    "type": "object",
                    "description": "Optional configuration overrides for the service",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "destroy_terraform_service": {
        "description": "Destroy a Terraform-managed service and clean up all resources",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to destroy",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "refresh_terraform_service": {
        "description": "Refresh Terraform state and detect configuration drift",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to refresh",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "check_ansible_service": {
        "description": "Check the status of an Ansible-managed service deployment",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to check",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "run_ansible_playbook": {
        "description": "Run an existing Ansible playbook for a service",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service playbook to run",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the device",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (use 'mcp_admin' for passwordless access after setup)",
                    "default": "mcp_admin",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (not needed for mcp_admin after setup)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ansible tags to run specific tasks",
                },
                "extra_vars": {
                    "type": "object",
                    "description": "Extra variables to pass to the playbook",
                },
                "check_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "Run in check mode (dry run)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["service_name", "hostname"],
        },
    },
    "register_server": {
        "description": "Register a server with SSH credentials for persistent access without repeatedly providing credentials",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the server",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (default: mcp_admin)",
                    "default": "mcp_admin",
                },
                "key_path": {
                    "type": "string",
                    "description": "Path to SSH private key (optional, uses default MCP key if not provided)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
                "display_name": {
                    "type": "string",
                    "description": "Friendly name for the server (optional)",
                },
                "verify_connection": {
                    "type": "boolean",
                    "description": "Whether to verify SSH connection before saving (default: true)",
                    "default": True,
                },
            },
            "required": ["hostname"],
        },
    },
    "list_registered_servers": {
        "description": "List all registered servers with their SSH credentials and connection status",
        "inputSchema": {
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "Only show active servers (default: true)",
                    "default": True,
                },
            },
            "required": [],
        },
    },
    "update_server_credentials": {
        "description": "Update SSH credentials for an existing registered server",
        "inputSchema": {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "integer",
                    "description": "ID of the credential to update (optional if hostname provided)",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname to look up (optional if credential_id provided)",
                },
                "username": {
                    "type": "string",
                    "description": "New SSH username",
                },
                "key_path": {
                    "type": "string",
                    "description": "New path to SSH private key",
                },
                "port": {
                    "type": "integer",
                    "description": "New SSH port",
                },
                "display_name": {
                    "type": "string",
                    "description": "New friendly name for the server",
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Set server active/inactive status",
                },
            },
            "required": [],
        },
    },
    "remove_server": {
        "description": "Remove a server from the registered servers list",
        "inputSchema": {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "integer",
                    "description": "ID of the credential to remove (optional if hostname provided)",
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname to look up (optional if credential_id provided)",
                },
            },
            "required": [],
        },
    },
    "search_proxmox_scripts": {
        "description": "Search Proxmox community installation scripts from the community-scripts/ProxmoxVE repository",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (matches script name, e.g. 'home assistant', 'docker', 'pihole')",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter: 'ct' (containers), 'vm' (virtual machines), 'install' (utilities), 'misc'",
                    "enum": ["ct", "vm", "install", "misc"],
                },
                "include_metadata": {
                    "type": "boolean",
                    "description": "If true, fetch and parse script metadata (CPU, RAM, disk requirements, tags). Slower but more detailed.",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    },
    "get_proxmox_script_info": {
        "description": "Get detailed information about a specific Proxmox community script",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_name": {
                    "type": "string",
                    "description": "Name of the script file (e.g. 'homeassistant.sh', 'docker.sh')",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category hint to speed up search: 'ct', 'vm', 'install', 'misc'",
                    "enum": ["ct", "vm", "install", "misc"],
                },
            },
            "required": ["script_name"],
        },
    },
    "execute_proxmox_script": {
        "description": "Execute a Proxmox community script on a Proxmox host via SSH. Installs containers, VMs, or services.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Proxmox host IP address or hostname",
                },
                "script_name": {
                    "type": "string",
                    "description": "Name of the script to execute (e.g. 'podman.sh', 'homeassistant.sh')",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (default: root)",
                    "default": "root",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (if not using key authentication)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
                "category": {
                    "type": "string",
                    "description": "Optional category hint: 'ct', 'vm', 'install', 'misc'",
                    "enum": ["ct", "vm", "install", "misc"],
                },
                "config": {
                    "type": "object",
                    "description": "Configuration overrides (e.g. {\"cpu\": 4, \"ram\": 4096, \"disk\": 32})",
                    "properties": {
                        "cpu": {"type": "integer", "description": "Number of CPU cores"},
                        "ram": {"type": "integer", "description": "RAM in MB"},
                        "disk": {"type": "integer", "description": "Disk size in GB"},
                        "os": {"type": "string", "description": "Operating system"},
                        "version": {"type": "string", "description": "OS version"},
                    },
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, show what would be executed without actually running it",
                    "default": False,
                },
            },
            "required": ["hostname", "script_name"],
        },
    },
}


def get_available_tools() -> dict[str, dict[str, Any]]:
    """Return all available tools with their schemas."""
    return TOOLS.copy()


@timeout_wrapper(timeout_seconds=45.0)
async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name with the given arguments, with timeout protection."""
    logger.info(f"Executing tool: {tool_name}")

    # Initialize sitemap instance
    sitemap = NetworkSiteMap()

    if tool_name == "ssh_discover":
        result = await ssh_discover_system(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "setup_mcp_admin":
        result = await setup_remote_mcp_admin(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "verify_mcp_admin":
        result = await verify_mcp_admin_access(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "discover_and_map":
        result = await discover_and_store(sitemap, **arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "bulk_discover_and_map":
        result = await bulk_discover_and_store(sitemap, arguments["targets"])
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "get_network_sitemap":
        devices = sitemap.get_all_devices()
        result = json.dumps(
            {"status": "success", "total_devices": len(devices), "devices": devices},
            indent=2,
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "analyze_network_topology":
        analysis = sitemap.analyze_network_topology()
        result = json.dumps({"status": "success", "analysis": analysis}, indent=2)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "suggest_deployments":
        suggestions = sitemap.suggest_deployments()
        result = json.dumps({"status": "success", "suggestions": suggestions}, indent=2)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "get_device_changes":
        changes = sitemap.get_device_changes(
            arguments["device_id"], arguments.get("limit", 10)
        )
        result = json.dumps(
            {
                "status": "success",
                "device_id": arguments["device_id"],
                "changes": changes,
            },
            indent=2,
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "deploy_infrastructure":
        from .infrastructure_crud import deploy_infrastructure_plan

        result = await deploy_infrastructure_plan(
            deployment_plan=arguments["deployment_plan"],
            validate_only=arguments.get("validate_only", False),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "update_device_config":
        from .infrastructure_crud import update_device_configuration

        result = await update_device_configuration(
            device_id=arguments["device_id"],
            config_changes=arguments["config_changes"],
            backup_before_change=arguments.get("backup_before_change", True),
            validate_only=arguments.get("validate_only", False),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "decommission_device":
        from .infrastructure_crud import decommission_network_device

        result = await decommission_network_device(
            device_id=arguments["device_id"],
            migration_plan=arguments.get("migration_plan"),
            force_removal=arguments.get("force_removal", False),
            validate_only=arguments.get("validate_only", False),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "scale_services":
        from .infrastructure_crud import scale_infrastructure_services

        result = await scale_infrastructure_services(
            scaling_plan=arguments["scaling_plan"],
            validate_only=arguments.get("validate_only", False),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "validate_infrastructure_changes":
        from .infrastructure_crud import validate_infrastructure_plan

        result = await validate_infrastructure_plan(
            change_plan=arguments["change_plan"],
            validation_level=arguments.get("validation_level", "comprehensive"),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "create_infrastructure_backup":
        from .infrastructure_crud import create_infrastructure_backup

        result = await create_infrastructure_backup(
            backup_scope=arguments.get("backup_scope", "full"),
            device_ids=arguments.get("device_ids"),
            include_data=arguments.get("include_data", False),
            backup_name=arguments.get("backup_name"),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "rollback_infrastructure_changes":
        from .infrastructure_crud import rollback_infrastructure_to_backup

        result = await rollback_infrastructure_to_backup(
            backup_id=arguments["backup_id"],
            rollback_scope=arguments.get("rollback_scope", "full"),
            device_ids=arguments.get("device_ids"),
            validate_only=arguments.get("validate_only", False),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "deploy_vm":
        from .vm_operations import deploy_vm

        result = await deploy_vm(
            device_id=arguments["device_id"],
            platform=arguments["platform"],
            vm_name=arguments["vm_name"],
            vm_config=arguments.get("vm_config", {}),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "control_vm":
        from .vm_operations import control_vm_state

        result = await control_vm_state(
            device_id=arguments["device_id"],
            platform=arguments["platform"],
            vm_name=arguments["vm_name"],
            action=arguments["action"],
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "get_vm_status":
        from .vm_operations import get_vm_status

        result = await get_vm_status(
            device_id=arguments["device_id"],
            platform=arguments["platform"],
            vm_name=arguments["vm_name"],
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "list_vms":
        from .vm_operations import list_vms_on_device

        result = await list_vms_on_device(
            device_id=arguments["device_id"], platforms=arguments.get("platforms")
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "get_vm_logs":
        from .vm_operations import get_vm_logs

        result = await get_vm_logs(
            device_id=arguments["device_id"],
            platform=arguments["platform"],
            vm_name=arguments["vm_name"],
            lines=arguments.get("lines", 100),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "remove_vm":
        from .vm_operations import remove_vm

        result = await remove_vm(
            device_id=arguments["device_id"],
            platform=arguments["platform"],
            vm_name=arguments["vm_name"],
            force=arguments.get("force", False),
        )
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "ssh_execute_command":
        from .ssh_tools import ssh_execute_command

        result = await ssh_execute_command(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "update_mcp_admin_groups":
        from .ssh_tools import update_mcp_admin_groups

        result = await update_mcp_admin_groups(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "list_available_services":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        services = installer.get_available_services()
        result_dict = {"available_services": services, "count": len(services)}
        return {
            "content": [{"type": "text", "text": json.dumps(result_dict, indent=2)}]
        }

    elif tool_name == "get_service_info":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        service_info = installer.get_service_info(arguments["service_name"])
        if service_info:
            return {
                "content": [
                    {"type": "text", "text": json.dumps(service_info, indent=2)}
                ]
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Service '{arguments['service_name']}' not found",
                    }
                ]
            }

    elif tool_name == "check_service_requirements":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        requirements_result = await installer.check_service_requirements(**arguments)
        return {
            "content": [
                {"type": "text", "text": json.dumps(requirements_result, indent=2)}
            ]
        }

    elif tool_name == "install_service":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        install_result = await installer.install_service(**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(install_result, indent=2)}]
        }

    elif tool_name == "get_service_status":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        status_result = await installer.get_service_status(**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(status_result, indent=2)}]
        }

    elif tool_name == "plan_terraform_service":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        plan_result = await installer.plan_terraform_service(**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(plan_result, indent=2)}]
        }

    elif tool_name == "destroy_terraform_service":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        destroy_result = await installer.destroy_terraform_service(**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(destroy_result, indent=2)}]
        }

    elif tool_name == "refresh_terraform_service":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        refresh_result = await installer.refresh_terraform_service(**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(refresh_result, indent=2)}]
        }

    elif tool_name == "check_ansible_service":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        ansible_result = await installer.check_ansible_service(**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(ansible_result, indent=2)}]
        }

    elif tool_name == "run_ansible_playbook":
        from .service_installer import ServiceInstaller

        installer = ServiceInstaller()
        playbook_result = await installer.run_ansible_playbook(**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(playbook_result, indent=2)}]
        }

    elif tool_name == "register_server":
        result = await register_server(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "list_registered_servers":
        result = list_registered_servers(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "update_server_credentials":
        result = update_server_credentials(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "remove_server":
        result = remove_server(**arguments)
        return {"content": [{"type": "text", "text": result}]}

    elif tool_name == "search_proxmox_scripts":
        results = await search_scripts(
            query=arguments["query"],
            category=arguments.get("category"),
            include_metadata=arguments.get("include_metadata", False),
        )
        # Format the results nicely
        result = {
            "status": "success",
            "query": arguments["query"],
            "total_found": len(results),
            "scripts": results,
        }
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    elif tool_name == "get_proxmox_script_info":
        details = await get_script_details(
            script_name=arguments["script_name"],
            category=arguments.get("category"),
        )
        if details:
            result = {"status": "success", "script": details}
        else:
            result = {
                "status": "error",
                "message": f"Script '{arguments['script_name']}' not found",
            }
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    elif tool_name == "execute_proxmox_script":
        exec_result = await execute_proxmox_script(
            hostname=arguments["hostname"],
            script_name=arguments["script_name"],
            username=arguments.get("username", "root"),
            password=arguments.get("password"),
            port=arguments.get("port", 22),
            category=arguments.get("category"),
            config=arguments.get("config"),
            dry_run=arguments.get("dry_run", False),
        )
        return {"content": [{"type": "text", "text": json.dumps(exec_result, indent=2)}]}

    else:
        raise ValueError(f"Unknown tool: {tool_name}")
