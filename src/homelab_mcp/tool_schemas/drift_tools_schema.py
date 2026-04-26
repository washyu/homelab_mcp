"""Tool schemas for drift detection tools."""

DRIFT_TOOLS: dict[str, dict] = {
    "scan_infrastructure_drift": {
        "description": (
            "Scan for infrastructure drift against the sitemap. Returns a four-bucket "
            "coverage report — probed_ok (sitemap host probed successfully), unreachable "
            "(sitemap host that did not respond), unknown (reserved for Phase 39 — "
            "infrastructure present on a Proxmox hypervisor but absent from sitemap), "
            "and changed (reserved for Phase 39 — fingerprint differs from stored). "
            "All four buckets are always present in the response (empty arrays for "
            "Phase-39-reserved buckets) so client code can iterate without defensive "
            "checks. Each scan also returns a counts sub-dict mirroring bucket sizes "
            "and, when zero hosts were scanned (empty sitemap or filter narrowed to "
            "zero), a top-level guidance field pointing to the sitemap CRUD tools "
            "(discover_and_map, get_network_sitemap, purge_failed_discoveries, "
            "decommission_device). Recovery from credential-resolution failure is "
            "handled via 'homelab-mcp credentials add --type proxmox'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": (
                        "Optional sitemap hostname filter. Exact-match only — no "
                        "wildcards, no case folding. When omitted, all sitemap rows "
                        "are scanned. When set to a hostname that does not match any "
                        "sitemap row, the scan returns status='success' with all four "
                        "buckets empty and a guidance field — never an error."
                    ),
                },
                "vm_type": {
                    "type": "string",
                    "enum": ["qemu", "lxc", "all"],
                    "description": (
                        "Reserved for Phase 39 per-VM detection; currently filters at "
                        "host level only (no-op until per-VM enumeration ships). Accepts "
                        "qemu, lxc, or all — all three values produce identical scan "
                        "results in this release."
                    ),
                    "default": "all",
                },
            },
            "required": [],
        },
    }
}
