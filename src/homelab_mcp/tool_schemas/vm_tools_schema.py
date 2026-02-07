"""Schema definitions for VM/container operations."""

from typing import Any

VM_TOOLS: dict[str, dict[str, Any]] = {
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
}
