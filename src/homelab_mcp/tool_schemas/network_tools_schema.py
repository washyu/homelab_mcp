"""Schema definitions for network topology and sitemap tools."""

from typing import Any

NETWORK_TOOLS: dict[str, dict[str, Any]] = {
    "discover_and_map": {
        "description": "Discover a device via SSH and store it in the network site map database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {
                    "type": "string",
                    "description": "SSH username. Defaults to 'mcp_admin' if omitted. Omit if credentials were stored with `credentials add` — they are auto-injected.",
                    "default": "mcp_admin",
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
            "required": ["hostname"],
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
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "hostname": {"type": "string"},
                            "username": {"type": "string", "default": "mcp_admin"},
                            "password": {"type": "string"},
                            "key_path": {"type": "string"},
                            "port": {"type": "integer", "default": 22},
                        },
                        "required": ["hostname"],
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
}
