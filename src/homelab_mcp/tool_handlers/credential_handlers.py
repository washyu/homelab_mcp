"""Handler functions for server credential management tools."""

import json
from typing import Any

from ..credential_store import list_credentials
from ..ssh_tools import (
    list_registered_servers,
    register_server,
)


async def handle_register_server(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle register_server tool."""
    result = await register_server(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_list_registered_servers(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_registered_servers tool."""
    result = list_registered_servers(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_list_keyring_credentials(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_keyring_credentials tool."""
    credential_type = arguments.get("credential_type", "ssh")
    entries = list_credentials(credential_type=credential_type)
    result = {
        "status": "success",
        "credential_type": credential_type,
        "count": len(entries),
        "credentials": [
            {
                "hostname": (f"cluster:{e.get('cluster_name', '')}" if e.get("scope") == "cluster" else e["hostname"]),
                "username": e["username"],
            }
            for e in entries
        ],
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
