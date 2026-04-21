"""Schema definitions for server credential management tools."""

from typing import Any

CREDENTIAL_TOOLS: dict[str, dict[str, Any]] = {
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
}

CREDENTIAL_TOOLS["list_keyring_credentials"] = {
    "description": (
        "List hosts that have credentials stored in the OS keyring registry. "
        "Call this before ssh_discover or ssh_execute_command to check whether "
        "a host has stored credentials. Returns hostname and username per entry."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "credential_type": {
                "type": "string",
                "description": "Credential type to list: 'ssh' (default) or 'proxmox'",
                "default": "ssh",
                "enum": ["ssh", "proxmox"],
            }
        },
        "required": [],
    },
}

