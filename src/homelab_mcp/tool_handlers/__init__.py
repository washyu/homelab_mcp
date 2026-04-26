"""Tool handler registry - maps tool names to handler functions."""

from collections.abc import Awaitable, Callable
from typing import Any

from .credential_handlers import (
    handle_list_keyring_credentials,
    handle_list_registered_servers,
    handle_register_server,
)
from .drift_handlers import handle_scan_infrastructure_drift
from .infrastructure_handlers import (
    handle_create_infrastructure_backup,
    handle_decommission_device,
    handle_decommission_device_preview,
    handle_deploy_infrastructure,
    handle_rollback_infrastructure_changes,
    handle_rollback_infrastructure_changes_preview,
    handle_scale_services,
    handle_update_device_config,
    handle_validate_infrastructure_changes,
)
from .network_handlers import (
    handle_analyze_network_topology,
    handle_bulk_discover_and_map,
    handle_discover_and_map,
    handle_get_device_changes,
    handle_get_network_sitemap,
    handle_purge_failed_discoveries,
    handle_suggest_deployments,
    handle_update_device_fingerprint,
    handle_update_device_fingerprint_preview,  # Phase 38 D-05c (Plan 05)
)
from .proxmox_handlers import (
    handle_clone_proxmox_vm,
    handle_create_proxmox_lxc,
    handle_create_proxmox_vm,
    handle_delete_proxmox_vm,
    handle_delete_proxmox_vm_preview,
    handle_get_proxmox_node_status,
    handle_get_proxmox_script_info,
    handle_get_proxmox_vm_status,
    handle_list_proxmox_resources,
    handle_manage_proxmox_vm,
    handle_search_proxmox_scripts,
)
from .service_handlers import (
    handle_check_ansible_service,
    handle_check_service_requirements,
    handle_destroy_terraform_service,
    handle_destroy_terraform_service_preview,
    handle_get_service_info,
    handle_get_service_status,
    handle_install_service,
    handle_list_available_services,
    handle_plan_terraform_service,
    handle_refresh_terraform_service,
    handle_run_ansible_playbook,
)
from .ssh_handlers import (
    handle_ssh_discover,
    handle_ssh_execute_command,
    handle_start_interactive_shell,
)
from .vm_handlers import (
    handle_control_vm,
    handle_deploy_vm,
    handle_get_vm_logs,
    handle_get_vm_status,
    handle_list_vms,
    handle_remove_vm,
    handle_remove_vm_preview,
)

# Type alias for handler functions
ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

# Tool handler registry mapping tool names to their handler functions
TOOL_HANDLERS: dict[str, ToolHandler] = {
    # SSH tools
    "ssh_discover": handle_ssh_discover,
    "ssh_execute_command": handle_ssh_execute_command,
    "start_interactive_shell": handle_start_interactive_shell,
    # Network tools
    "discover_and_map": handle_discover_and_map,
    "bulk_discover_and_map": handle_bulk_discover_and_map,
    "get_network_sitemap": handle_get_network_sitemap,
    "analyze_network_topology": handle_analyze_network_topology,
    "suggest_deployments": handle_suggest_deployments,
    "get_device_changes": handle_get_device_changes,
    "purge_failed_discoveries": handle_purge_failed_discoveries,
    "update_device_fingerprint": handle_update_device_fingerprint,  # Phase 38
    "update_device_fingerprint_preview": handle_update_device_fingerprint_preview,  # Phase 38 D-05c (Plan 05)
    # Infrastructure tools
    "deploy_infrastructure": handle_deploy_infrastructure,
    "update_device_config": handle_update_device_config,
    "decommission_device": handle_decommission_device,
    "decommission_device_preview": handle_decommission_device_preview,
    "scale_services": handle_scale_services,
    "validate_infrastructure_changes": handle_validate_infrastructure_changes,
    "create_infrastructure_backup": handle_create_infrastructure_backup,
    "rollback_infrastructure_changes": handle_rollback_infrastructure_changes,
    "rollback_infrastructure_changes_preview": handle_rollback_infrastructure_changes_preview,
    # VM tools
    "deploy_vm": handle_deploy_vm,
    "control_vm": handle_control_vm,
    "get_vm_status": handle_get_vm_status,
    "list_vms": handle_list_vms,
    "get_vm_logs": handle_get_vm_logs,
    "remove_vm": handle_remove_vm,
    "remove_vm_preview": handle_remove_vm_preview,
    # Service tools
    "list_available_services": handle_list_available_services,
    "get_service_info": handle_get_service_info,
    "check_service_requirements": handle_check_service_requirements,
    "install_service": handle_install_service,
    "get_service_status": handle_get_service_status,
    "plan_terraform_service": handle_plan_terraform_service,
    "destroy_terraform_service": handle_destroy_terraform_service,
    "destroy_terraform_service_preview": handle_destroy_terraform_service_preview,
    "refresh_terraform_service": handle_refresh_terraform_service,
    "check_ansible_service": handle_check_ansible_service,
    "run_ansible_playbook": handle_run_ansible_playbook,
    # Credential tools
    "register_server": handle_register_server,
    "list_registered_servers": handle_list_registered_servers,
    "list_keyring_credentials": handle_list_keyring_credentials,
    # Drift tools
    "scan_infrastructure_drift": handle_scan_infrastructure_drift,
    # Proxmox tools
    "search_proxmox_scripts": handle_search_proxmox_scripts,
    "get_proxmox_script_info": handle_get_proxmox_script_info,
    "list_proxmox_resources": handle_list_proxmox_resources,
    "get_proxmox_node_status": handle_get_proxmox_node_status,
    "get_proxmox_vm_status": handle_get_proxmox_vm_status,
    "manage_proxmox_vm": handle_manage_proxmox_vm,
    "create_proxmox_lxc": handle_create_proxmox_lxc,
    "create_proxmox_vm": handle_create_proxmox_vm,
    "clone_proxmox_vm": handle_clone_proxmox_vm,
    "delete_proxmox_vm": handle_delete_proxmox_vm,
    "delete_proxmox_vm_preview": handle_delete_proxmox_vm_preview,
}


def get_tool_handler(tool_name: str) -> ToolHandler:
    """Get the handler function for a given tool name."""
    if tool_name not in TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOL_HANDLERS[tool_name]


__all__ = ["TOOL_HANDLERS", "get_tool_handler", "ToolHandler", "handle_scan_infrastructure_drift"]
