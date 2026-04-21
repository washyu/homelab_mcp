"""Schema definitions for server credential management tools."""

from typing import Any

CREDENTIAL_TOOLS: dict[str, dict[str, Any]] = {
    "register_server": {
        "description": (
            "Verify SSH connectivity to a registered server using keyring credentials. "
            "Does not write any credentials — credentials must already be stored via "
            "`homelab-mcp credentials add <hostname> <username>` in the CLI. "
            "Returns a status object with verified=true on successful handshake."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target server",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username to verify; must match a keyring entry",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default 22)",
                    "default": 22,
                },
                "display_name": {
                    "type": "string",
                    "description": "Optional human-readable label",
                },
            },
            "required": ["hostname", "username"],
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

