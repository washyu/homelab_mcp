"""Tool annotations for MCP spec compliance.

Maps all 58 tool names to ToolAnnotations instances with readOnlyHint,
destructiveHint, and idempotentHint set. MCP clients use these hints
to distinguish read-only from destructive tools and provide safety warnings.
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Read-Only tools: read_only_hint=True, destructive_hint=False, idempotent_hint=True
# These tools only query state and never modify anything.
# ---------------------------------------------------------------------------

_READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
)

_READ_ONLY_TOOLS = [
    "ssh_discover",
    "get_background_job",
    "get_network_sitemap",
    "analyze_network_topology",
    "suggest_deployments",
    "get_device_changes",
    "list_available_services",
    "get_service_info",
    "check_service_requirements",
    "get_service_status",
    "list_vms",
    "get_vm_status",
    "get_vm_logs",
    "list_registered_servers",
    "list_keyring_credentials",
    "scan_infrastructure_drift",
    "search_proxmox_scripts",
    "get_proxmox_script_info",
    "list_proxmox_resources",
    "get_proxmox_node_status",
    "get_proxmox_vm_status",
    "check_ansible_service",
    "validate_infrastructure_changes",
    "decommission_device_preview",
    "delete_proxmox_vm_preview",
    "remove_vm_preview",
    "destroy_terraform_service_preview",
    "rollback_infrastructure_changes_preview",
    "update_device_fingerprint_preview",  # Phase 38 D-05c (Plan 05)
    "remove_device_preview",  # Phase 44 D-11
    "purge_devices_preview",  # Phase 44 D-11
]

# ---------------------------------------------------------------------------
# Destructive tools: read_only_hint=False, destructive_hint=True, idempotent_hint=True
# These tools delete or destroy resources.
# ---------------------------------------------------------------------------

_DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=True,
)

_DESTRUCTIVE_TOOLS = [
    "decommission_device",
    "remove_vm",
    "delete_proxmox_vm",
    "destroy_terraform_service",
    "rollback_infrastructure_changes",
    "purge_failed_discoveries",
    "remove_device",  # Phase 44 D-06
    "purge_devices",  # Phase 44 D-01
]

# ---------------------------------------------------------------------------
# Mutating Non-Destructive tools: read_only_hint=False, destructive_hint=False
# Each has its own idempotentHint and openWorldHint settings.
# ---------------------------------------------------------------------------

_MUTATING_ANNOTATIONS: dict[str, ToolAnnotations] = {
    "discover_and_map": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "bulk_discover_and_map": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "update_device_fingerprint": ToolAnnotations(
        # Phase 38: idempotent because identical (hostname, fingerprint) input
        # produces identical merged output.
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "ssh_execute_command": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=True,
    ),
    "cancel_background_job": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "start_interactive_shell": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=True,
    ),
    "deploy_infrastructure": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "deploy_vm": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "install_service": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "update_device_config": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "scale_services": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "register_server": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "create_proxmox_vm": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "create_proxmox_lxc": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "clone_proxmox_vm": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "create_infrastructure_backup": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "plan_terraform_service": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "refresh_terraform_service": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "run_ansible_playbook": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
    "manage_proxmox_vm": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
    "control_vm": ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
}

# ---------------------------------------------------------------------------
# Combined TOOL_ANNOTATIONS dict
# ---------------------------------------------------------------------------

TOOL_ANNOTATIONS: dict[str, ToolAnnotations] = {}

for _name in _READ_ONLY_TOOLS:
    TOOL_ANNOTATIONS[_name] = _READ_ONLY

for _name in _DESTRUCTIVE_TOOLS:
    TOOL_ANNOTATIONS[_name] = _DESTRUCTIVE

TOOL_ANNOTATIONS.update(_MUTATING_ANNOTATIONS)


def get_tool_annotations(name: str) -> ToolAnnotations | None:
    """Return the ToolAnnotations for a given tool name, or None if not found."""
    return TOOL_ANNOTATIONS.get(name)
