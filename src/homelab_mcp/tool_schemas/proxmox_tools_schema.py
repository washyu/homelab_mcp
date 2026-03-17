"""Schema definitions for Proxmox API and community scripts tools."""

from typing import Any

PROXMOX_TOOLS: dict[str, dict[str, Any]] = {
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
    "list_proxmox_resources": {
        "description": "List all Proxmox cluster resources (VMs, containers, nodes, storage). Uses PROXMOX_HOST from environment if host not provided.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional, uses PROXMOX_HOST env var if not provided)",
                },
                "resource_type": {
                    "type": "string",
                    "description": "Filter by resource type",
                    "enum": ["vm", "lxc", "node", "storage", "pool"],
                },
            },
            "required": [],
        },
    },
    "get_proxmox_node_status": {
        "description": "Get detailed status of a Proxmox node (CPU, memory, uptime, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node name (e.g., 'pve', 'proxmox')",
                },
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional, uses PROXMOX_HOST env var)",
                },
            },
            "required": ["node"],
        },
    },
    "get_proxmox_vm_status": {
        "description": "Get status of a specific VM or container",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node name",
                },
                "vmid": {
                    "type": "integer",
                    "description": "VM or Container ID",
                },
                "vm_type": {
                    "type": "string",
                    "description": "Type: 'qemu' for VM or 'lxc' for container",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                },
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional)",
                },
            },
            "required": ["node", "vmid"],
        },
    },
    "manage_proxmox_vm": {
        "description": "Manage a VM or container (start, stop, shutdown, reboot, reset, suspend, resume)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node name",
                },
                "vmid": {
                    "type": "integer",
                    "description": "VM or Container ID",
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": [
                        "start",
                        "stop",
                        "shutdown",
                        "reboot",
                        "reset",
                        "suspend",
                        "resume",
                    ],
                },
                "vm_type": {
                    "type": "string",
                    "description": "Type: 'qemu' for VM or 'lxc' for container",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                },
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional)",
                },
            },
            "required": ["node", "vmid", "action"],
        },
    },
    "create_proxmox_lxc": {
        "description": "Create a new LXC container on Proxmox",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node name",
                },
                "vmid": {
                    "type": "integer",
                    "description": "Container ID (must be unique)",
                },
                "hostname": {
                    "type": "string",
                    "description": "Container hostname",
                },
                "ostemplate": {
                    "type": "string",
                    "description": "Template (e.g., 'local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst')",
                    "default": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                },
                "storage": {
                    "type": "string",
                    "description": "Storage for rootfs",
                    "default": "local-lvm",
                },
                "memory": {
                    "type": "integer",
                    "description": "RAM in MB",
                    "default": 512,
                },
                "swap": {
                    "type": "integer",
                    "description": "Swap size in MB",
                    "default": 512,
                },
                "cores": {
                    "type": "integer",
                    "description": "Number of CPU cores",
                    "default": 1,
                },
                "rootfs_size": {
                    "type": "integer",
                    "description": "Root filesystem size in GB",
                    "default": 8,
                },
                "password": {
                    "type": "string",
                    "description": "Root password",
                },
                "ssh_public_keys": {
                    "type": "string",
                    "description": "SSH public keys to add to the container (one per line)",
                },
                "unprivileged": {
                    "type": "boolean",
                    "description": "Create as unprivileged container (default: true, recommended for security)",
                    "default": True,
                },
                "start": {
                    "type": "boolean",
                    "description": "Start container after creation",
                    "default": False,
                },
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional)",
                },
            },
            "required": ["node", "vmid", "hostname"],
        },
    },
    "create_proxmox_vm": {
        "description": "Create a new VM (QEMU) on Proxmox",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node name",
                },
                "vmid": {
                    "type": "integer",
                    "description": "VM ID (must be unique)",
                },
                "name": {
                    "type": "string",
                    "description": "VM name",
                },
                "memory": {
                    "type": "integer",
                    "description": "RAM in MB",
                    "default": 2048,
                },
                "cores": {
                    "type": "integer",
                    "description": "Number of CPU cores",
                    "default": 2,
                },
                "disk_size": {
                    "type": "integer",
                    "description": "Disk size in GB",
                    "default": 32,
                },
                "storage": {
                    "type": "string",
                    "description": "Storage for disks",
                    "default": "local-lvm",
                },
                "sockets": {
                    "type": "integer",
                    "description": "Number of CPU sockets",
                    "default": 1,
                },
                "iso": {
                    "type": "string",
                    "description": "ISO image to attach (e.g., 'local:iso/debian-12.iso')",
                },
                "cdrom": {
                    "type": "string",
                    "description": "CD-ROM device (e.g., 'local:iso/debian-12.iso'). Alternative to iso — use one or the other.",
                },
                "net0": {
                    "type": "string",
                    "description": "Network device configuration (default: 'virtio,bridge=vmbr0')",
                    "default": "virtio,bridge=vmbr0",
                },
                "ostype": {
                    "type": "string",
                    "description": "OS type for optimization (default: 'l26' for Linux 2.6+)",
                    "default": "l26",
                },
                "start": {
                    "type": "boolean",
                    "description": "Start VM after creation",
                    "default": False,
                },
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional)",
                },
            },
            "required": ["node", "vmid", "name"],
        },
    },
    "clone_proxmox_vm": {
        "description": "Clone a VM or container to create a new one",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node name",
                },
                "vmid": {
                    "type": "integer",
                    "description": "Source VM/Container ID",
                },
                "new_vmid": {
                    "type": "integer",
                    "description": "New VM/Container ID",
                },
                "name": {
                    "type": "string",
                    "description": "New VM name (optional)",
                },
                "full": {
                    "type": "boolean",
                    "description": "Full clone (true) or linked clone (false)",
                    "default": True,
                },
                "vm_type": {
                    "type": "string",
                    "description": "Type: 'qemu' for VM or 'lxc' for container",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                },
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional)",
                },
            },
            "required": ["node", "vmid", "new_vmid"],
        },
    },
    "delete_proxmox_vm": {
        "description": "Delete a VM or container from Proxmox",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node name",
                },
                "vmid": {
                    "type": "integer",
                    "description": "VM/Container ID to delete",
                },
                "vm_type": {
                    "type": "string",
                    "description": "Type: 'qemu' for VM or 'lxc' for container",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                },
                "purge": {
                    "type": "boolean",
                    "description": "Remove from all related configurations",
                    "default": False,
                },
                "host": {
                    "type": "string",
                    "description": "Proxmox host (optional)",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, return a preview of what would be affected without executing any changes.",
                },
            },
            "required": ["node", "vmid"],
        },
    },
}

PROXMOX_TOOLS["delete_proxmox_vm_preview"] = {
    "description": (
        "Preview what delete_proxmox_vm would affect without executing. "
        "Returns a structured dry-run report. No VM is deleted."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "node": {
                "type": "string",
                "description": "Node name",
            },
            "vmid": {
                "type": "integer",
                "description": "VM/Container ID to delete",
            },
            "vm_type": {
                "type": "string",
                "description": "Type: 'qemu' for VM or 'lxc' for container",
                "enum": ["qemu", "lxc"],
                "default": "qemu",
            },
            "purge": {
                "type": "boolean",
                "description": "Remove from all related configurations",
                "default": False,
            },
            "host": {
                "type": "string",
                "description": "Proxmox host (optional)",
            },
        },
        "required": ["node", "vmid"],
    },
}
