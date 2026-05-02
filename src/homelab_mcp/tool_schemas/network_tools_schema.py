"""Schema definitions for network topology and sitemap tools."""

from typing import Any

NETWORK_TOOLS: dict[str, dict[str, Any]] = {
    "discover_and_map": {
        "description": (
            "Discover a device via SSH and store it in the network site map database. "
            "Recommended follow-up: run the configure_host_fingerprint prompt to capture "
            "per-host capability signals for drift detection."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {
                    "type": "string",
                    "description": "SSH username. Omit if credentials were stored with `credentials add` — they are auto-injected.",
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
                            "username": {"type": "string"},
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
    "purge_failed_discoveries": {
        "description": (
            "Remove sitemap rows for devices where discovery failed (status='error' "
            "or empty/null/'unknown' hostname). Pass dry_run=true to preview the "
            "removal candidates without deleting them."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, return removal candidates without deleting (default: false)",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    "update_device_fingerprint": {
        "description": (
            "Merge fingerprint data (kernel, OS, package digest, capabilities) into a "
            "device's sitemap row. Top-level keys overwrite (last-write-wins). The "
            "capabilities sub-dict updates one level deep — incoming top-level capability "
            "keys REPLACE the stored entry entirely (NOT a recursive merge), so callers "
            "updating any field within a capability must pass the full capability dict. "
            "Run discover_and_map first to populate the device. See the "
            "configure_host_fingerprint prompt for the conversational workflow. Persists "
            "to DB and bumps updated_at; last_seen is preserved (Phase 38 REVIEW-FIX WR-03)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname of the device to fingerprint",
                },
                "fingerprint": {
                    "type": "object",
                    "description": (
                        "Fingerprint dict. Recognized top-level keys: kernel_name, kernel_version, "
                        "os_name, os_version, package_fingerprint, capabilities. Unknown top-level "
                        "keys are dropped server-side. capabilities is a freeform sub-dict."
                    ),
                    "properties": {
                        "kernel_name": {"type": "string"},
                        "kernel_version": {"type": "string"},
                        "os_name": {"type": "string"},
                        "os_version": {"type": "string"},
                        "package_fingerprint": {"type": "string"},
                        "capabilities": {"type": "object", "additionalProperties": True},
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["hostname", "fingerprint"],
        },
    },
    "update_device_fingerprint_preview": {
        "description": (
            "Preview the merge result of update_device_fingerprint without persisting. "
            "Returns the would-be merged fingerprint dict using the same merge rules: "
            "top-level overwrite + capabilities one-level overwrite (incoming capability "
            "keys replace stored entries entirely; not recursive). Read-only — no DB "
            "write, no last_seen or updated_at mutation. Phase 38 D-05c."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname of the device to preview-fingerprint",
                },
                "fingerprint": {
                    "type": "object",
                    "description": (
                        "Same shape as update_device_fingerprint.fingerprint. Recognized top-level "
                        "keys: kernel_name, kernel_version, os_name, os_version, package_fingerprint, "
                        "capabilities."
                    ),
                    "properties": {
                        "kernel_name": {"type": "string"},
                        "kernel_version": {"type": "string"},
                        "os_name": {"type": "string"},
                        "os_version": {"type": "string"},
                        "package_fingerprint": {"type": "string"},
                        "capabilities": {"type": "object", "additionalProperties": True},
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["hostname", "fingerprint"],
        },
    },
}
