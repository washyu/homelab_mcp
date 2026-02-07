"""Handler functions for SSH-related tools."""

import json
import os
from typing import Any

from ..ssh_tools import (
    setup_remote_mcp_admin,
    ssh_discover_system,
    ssh_execute_command,
    update_mcp_admin_groups,
    verify_mcp_admin_access,
)
from ..shell_session import session_manager


async def handle_ssh_discover(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle ssh_discover tool."""
    result = await ssh_discover_system(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_setup_mcp_admin(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle setup_mcp_admin tool."""
    result = await setup_remote_mcp_admin(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_verify_mcp_admin(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle verify_mcp_admin tool."""
    result = await verify_mcp_admin_access(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_ssh_execute_command(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle ssh_execute_command tool."""
    result = await ssh_execute_command(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_start_interactive_shell(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle start_interactive_shell tool."""
    # Get initial command if provided
    initial_command = arguments.get("initial_command")

    # Create shell session
    session_id, session = await session_manager.create_session(
        hostname=arguments["hostname"],
        username=arguments.get("username"),
        password=arguments.get("password"),
        port=arguments.get("port", 22),
        initial_command=initial_command,
    )

    # Get the MCP HTTP server host/port from environment or defaults
    mcp_host = os.getenv("MCP_HTTP_HOST", "localhost")
    mcp_port = os.getenv("MCP_HTTP_PORT", "8080")

    # Build the shell URL
    shell_url = f"http://{mcp_host}:{mcp_port}/shell/{session_id}"

    message = f"Interactive shell started. Open this URL in your browser:\n{shell_url}\n\nSession will expire after 30 minutes of inactivity."
    if initial_command:
        message += f"\n\nInitial command executed:\n{initial_command}"

    result = {
        "status": "success",
        "session_id": session_id,
        "shell_url": shell_url,
        "hostname": session.hostname,
        "username": session.username,
        "message": message,
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_update_mcp_admin_groups(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update_mcp_admin_groups tool."""
    result = await update_mcp_admin_groups(**arguments)
    return {"content": [{"type": "text", "text": result}]}
