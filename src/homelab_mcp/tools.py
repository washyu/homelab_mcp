"""Tool definitions and execution for the Homelab MCP server.

This module provides a clean interface for tool registration and execution.
Tool schemas are defined in tool_schemas/, and handlers in tool_handlers/.
"""

import logging
from typing import Any

from .error_handling import timeout_wrapper
from .tool_handlers import get_tool_handler
from .tool_schemas import get_all_tool_schemas

# Configure logging
logger = logging.getLogger(__name__)


def get_available_tools() -> dict[str, dict[str, Any]]:
    """Return all available tools with their schemas."""
    return get_all_tool_schemas()


@timeout_wrapper(timeout_seconds=120.0)
async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name with the given arguments, with timeout protection.

    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments for the tool

    Returns:
        Dictionary containing the tool execution result

    Raises:
        ValueError: If the tool name is unknown
    """
    logger.info(f"Executing tool: {tool_name}")

    # Get and execute the handler for this tool
    handler = get_tool_handler(tool_name)
    return await handler(arguments)
