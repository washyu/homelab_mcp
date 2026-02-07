"""Handler functions for server credential management tools."""

from typing import Any

from ..ssh_tools import (
    list_registered_servers,
    register_server,
    remove_server,
    update_server_credentials,
)


async def handle_register_server(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle register_server tool."""
    result = await register_server(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_list_registered_servers(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_registered_servers tool."""
    result = list_registered_servers(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_update_server_credentials(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update_server_credentials tool."""
    result = update_server_credentials(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_remove_server(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle remove_server tool."""
    result = remove_server(**arguments)
    return {"content": [{"type": "text", "text": result}]}
