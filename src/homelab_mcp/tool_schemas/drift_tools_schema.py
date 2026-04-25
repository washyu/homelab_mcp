"""Tool schemas for drift detection tools."""

DRIFT_TOOLS: dict[str, dict] = {
    "scan_infrastructure_drift": {
        "description": (
            "Scan for infrastructure drift against the sitemap. Returns 2-bucket coverage report "
            "(probed_ok, unreachable) per resolved Proxmox host. "
            "Filter semantics under Phase 37 redesign — node/vm_type currently inert."
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
