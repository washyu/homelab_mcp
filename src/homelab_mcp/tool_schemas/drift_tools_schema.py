"""Tool schemas for drift detection tools."""

DRIFT_TOOLS: dict[str, dict] = {
    "scan_infrastructure_drift": {
        "description": (
            "Scan for infrastructure drift: config drift (CPU/memory/network changed outside MCP) "
            "and state drift (VMs offline that should be running). "
            "Returns structured report with drift_type, expected, actual, and scan_timestamp per finding."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Proxmox node name to scan (optional; scans all nodes if omitted)",
                },
                "vm_type": {
                    "type": "string",
                    "enum": ["qemu", "lxc", "all"],
                    "description": "VM type to scan (default: 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
    }
}
