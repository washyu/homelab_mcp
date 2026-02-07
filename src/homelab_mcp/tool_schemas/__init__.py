"""Tool schema registry - combines all tool schemas."""

from typing import Any

from .credential_tools_schema import CREDENTIAL_TOOLS
from .infrastructure_tools_schema import INFRASTRUCTURE_TOOLS
from .network_tools_schema import NETWORK_TOOLS
from .proxmox_tools_schema import PROXMOX_TOOLS
from .service_tools_schema import SERVICE_TOOLS
from .ssh_tools_schema import SSH_TOOLS
from .vm_tools_schema import VM_TOOLS


def get_all_tool_schemas() -> dict[str, dict[str, Any]]:
    """Combine all tool schemas into a single registry."""
    return {
        **SSH_TOOLS,
        **NETWORK_TOOLS,
        **INFRASTRUCTURE_TOOLS,
        **VM_TOOLS,
        **SERVICE_TOOLS,
        **CREDENTIAL_TOOLS,
        **PROXMOX_TOOLS,
    }


__all__ = ["get_all_tool_schemas"]
