"""Schema definitions for service installation and management tools."""

from typing import Any

SERVICE_TOOLS: dict[str, dict[str, Any]] = {
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
}
