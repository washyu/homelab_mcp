"""Tool annotations for MCP spec compliance.

Maps all 57 tool names to ToolAnnotations instances with readOnlyHint,
destructiveHint, and idempotentHint set. MCP clients use these hints
to distinguish read-only from destructive tools and provide safety warnings.
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Read-Only tools: readOnlyHint=True, destructiveHint=False, idempotentHint=True
# These tools only query state and never modify anything.
# ---------------------------------------------------------------------------

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
)

_READ_ONLY_TOOLS = [
    "ssh_discover",
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
    "list_keyring_credentials",
    "decommission_device_preview",
    "delete_proxmox_vm_preview",
    "remove_vm_preview",
    "destroy_terraform_service_preview",
    "rollback_infrastructure_changes_preview",
]

# ---------------------------------------------------------------------------
# Destructive tools: readOnlyHint=False, destructiveHint=True, idempotentHint=True
# These tools delete or destroy resources.
# ---------------------------------------------------------------------------

_DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
)

_DESTRUCTIVE_TOOLS = [
    "decommission_device",
    "remove_vm",
    "delete_proxmox_vm",
    "destroy_terraform_service",
    "rollback_infrastructure_changes",
    "purge_failed_discoveries",
]

# ---------------------------------------------------------------------------
# Mutating Non-Destructive tools: readOnlyHint=False, destructiveHint=False
# Each has its own idempotentHint and openWorldHint settings.
# ---------------------------------------------------------------------------

_MUTATING_ANNOTATIONS: dict[str, ToolAnnotations] = {
    "discover_and_map": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "bulk_discover_and_map": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "update_device_fingerprint": ToolAnnotations(
        # Phase 38: idempotent because identical (hostname, fingerprint) input
        # produces identical merged output.
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "ssh_execute_command": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
    "start_interactive_shell": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
    "deploy_infrastructure": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "deploy_vm": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "install_service": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "update_device_config": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "scale_services": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "register_server": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "create_proxmox_vm": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "create_proxmox_lxc": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "clone_proxmox_vm": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "create_infrastructure_backup": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "plan_terraform_service": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "refresh_terraform_service": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "run_ansible_playbook": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
    "manage_proxmox_vm": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
    "control_vm": ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
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
