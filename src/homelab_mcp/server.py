"""MCP server for homelab system management using MCP SDK lowlevel.Server.

Replaces the hand-rolled JSON-RPC HomelabMCPServer with the official MCP SDK.
Uses lowlevel.Server with lifespan, list_tools, and call_tool decorators.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl

from .config import MCPConfig, get_config
from .log_filter import CredentialFilter, sanitize_error
from .progress import (
    LOG_LEVEL_ORDER,
    emit_progress,
    set_min_log_level,
    should_emit,
)
from .resource_manager import ResourceManager
from .resource_readers import read_devices_resource, read_service_resource, read_vms_resource
from .tool_annotations import get_tool_annotations
from .tool_handlers import get_tool_handler
from .tool_schemas import get_all_tool_schemas

# Re-export progress symbols for backward compatibility and plan contract
__all__ = ["LOG_LEVEL_ORDER", "emit_progress", "should_emit"]

# Error code constant — SDK has no named constant for resource-not-found
RESOURCE_NOT_FOUND = -32002

logger = logging.getLogger(__name__)

# Attach credential redaction filter to root logger so all log output is scrubbed.
logging.getLogger().addFilter(CredentialFilter())

# Module-level ResourceManager reference for handlers that need direct access.
# Set during lifespan, cleared on shutdown.
_resource_manager: ResourceManager | None = None


def get_resource_manager() -> ResourceManager:
    """Get the active ResourceManager instance.

    Raises:
        RuntimeError: If the server lifespan has not started.
    """
    if _resource_manager is None:
        raise RuntimeError("ResourceManager not available -- server lifespan not started")
    return _resource_manager


@asynccontextmanager
async def app_lifespan(server: Server[dict[str, Any], Any]) -> AsyncIterator[dict[str, Any]]:
    """Server lifespan: initialize and shut down ResourceManager.

    Yields a context dict with the ResourceManager instance, accessible via
    ``server.request_context.lifespan_context["resource_manager"]``.
    """
    global _resource_manager  # noqa: PLW0603

    config: MCPConfig = get_config()
    resource_manager = ResourceManager(config)

    try:
        await resource_manager.initialize()
        _resource_manager = resource_manager
        logger.info("Server lifespan started -- ResourceManager ready")
        yield {"resource_manager": resource_manager}
    finally:
        logger.info("Shutting down ResourceManager...")
        _resource_manager = None
        await resource_manager.shutdown()
        logger.info("ResourceManager shutdown complete")


# ---------------------------------------------------------------------------
# Create the SDK server instance
# ---------------------------------------------------------------------------

server = Server("homelab-mcp", version="0.2.0", lifespan=app_lifespan)

# ---------------------------------------------------------------------------
# MCP Resources registry
# ---------------------------------------------------------------------------

#: Registry of homelab:// resources exposed via resources/list and resources/read.
#: Keys must match str(AnyUrl("homelab://...")) output exactly.
#: Values are dicts with: name, description (used by handle_list_resources for metadata).
#: Live data dispatch is handled by handle_read_resource via resource_readers module.
HOMELAB_RESOURCES: dict[str, dict[str, object]] = {
    "homelab://vms": {
        "name": "Virtual Machines",
        "description": "Proxmox, Docker, and LXD VM/container inventory from all managed hosts",
    },
    "homelab://devices": {
        "name": "Device Inventory",
        "description": "All devices discovered on the homelab network via SSH and mDNS scanning",
    },
    "homelab://services": {
        "name": "Services",
        "description": "Status of installed services (Docker, Proxmox, custom stacks) across all hosts",
    },
}

#: Set of URI strings currently subscribed by MCP clients.
#: Populated by handle_subscribe_resource, cleared by handle_unsubscribe_resource.
_subscriptions: set[str] = set()

#: Tools that write new device rows to the database.
#: A successful (non-error, non-dry-run) call to any of these tools triggers
#: a notifications/resources/list_changed push to subscribed clients.
MUTATING_TOOLS: frozenset[str] = frozenset(
    {
        "discover_and_map",
        "bulk_discover_and_map",
    }
)


# ---------------------------------------------------------------------------
# Handler: list_resources
# ---------------------------------------------------------------------------


@server.list_resources()  # type: ignore[misc]
async def handle_list_resources() -> list[types.Resource]:
    """Return all homelab:// resources with metadata.

    Returns a types.Resource for each entry in HOMELAB_RESOURCES with
    mimeType application/json so clients know the payload format.
    """
    resources: list[types.Resource] = []
    for uri_str, meta in HOMELAB_RESOURCES.items():
        resources.append(
            types.Resource(
                uri=AnyUrl(uri_str),
                name=str(meta["name"]),
                description=str(meta["description"]),
                mimeType="application/json",
            )
        )
    return resources


# ---------------------------------------------------------------------------
# Handler: read_resource
# ---------------------------------------------------------------------------


@server.read_resource()  # type: ignore[misc]
async def handle_read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
    """Return live JSON content for a known homelab:// resource URI.

    Dispatches to the appropriate reader function from resource_readers module.
    Non-McpError exceptions are caught and returned as error payloads (not raised).

    Raises:
        McpError: With code -32002 if the URI is not recognized, or if
            homelab://services/ is requested without a service name.
    """
    uri_str = str(uri)

    try:
        if uri_str == "homelab://vms":
            payload = await read_vms_resource()
        elif uri_str == "homelab://devices":
            payload = await read_devices_resource()
        elif uri_str.startswith("homelab://services/"):
            service_name = uri_str.removeprefix("homelab://services/")
            if not service_name:
                raise McpError(
                    types.ErrorData(
                        code=RESOURCE_NOT_FOUND,
                        message="Service name required",
                        data={"uri": uri_str},
                    )
                )
            payload = await read_service_resource(service_name)
        elif uri_str in HOMELAB_RESOURCES:
            # Bare homelab://services or other registered URIs without a live reader
            payload = {
                "_note": "Use homelab://services/{name} for specific service status",
                "scanned_at": datetime.now(UTC).isoformat(),
            }
        else:
            raise McpError(
                types.ErrorData(
                    code=RESOURCE_NOT_FOUND,
                    message="Resource not found",
                    data={"uri": uri_str},
                )
            )
    except McpError:
        raise
    except Exception as e:
        logger.exception("Error reading resource %s", uri_str)
        payload = {
            "error": sanitize_error(e),
            "scanned_at": datetime.now(UTC).isoformat(),
        }

    return [ReadResourceContents(content=json.dumps(payload), mime_type="application/json")]


# ---------------------------------------------------------------------------
# Handler: subscribe_resource
# ---------------------------------------------------------------------------


@server.subscribe_resource()  # type: ignore[misc]
async def handle_subscribe_resource(uri: AnyUrl) -> None:
    """Add URI to subscription tracker so future updates can be pushed."""
    _subscriptions.add(str(uri))


# ---------------------------------------------------------------------------
# Handler: unsubscribe_resource
# ---------------------------------------------------------------------------


@server.unsubscribe_resource()  # type: ignore[misc]
async def handle_unsubscribe_resource(uri: AnyUrl) -> None:
    """Remove URI from subscription tracker (no-op if not present)."""
    _subscriptions.discard(str(uri))


# ---------------------------------------------------------------------------
# Handler: set_logging_level
# ---------------------------------------------------------------------------


@server.set_logging_level()  # type: ignore[misc]
async def handle_set_logging_level(level: types.LoggingLevel) -> None:
    """Store the client-requested minimum log level for notification filtering."""
    set_min_log_level(level)
    logger.info("Client set minimum log level to %s", level)


# ---------------------------------------------------------------------------
# Handler: list_tools
# ---------------------------------------------------------------------------


@server.list_tools()  # type: ignore[misc]
async def handle_list_tools() -> list[types.Tool]:
    """Return all available tools as MCP Tool objects."""
    schemas = get_all_tool_schemas()
    tools: list[types.Tool] = []
    for name, schema in schemas.items():
        tools.append(
            types.Tool(
                name=name,
                description=schema.get("description", ""),
                inputSchema=schema.get("inputSchema", {"type": "object", "properties": {}}),
                annotations=get_tool_annotations(name),
            )
        )
    return tools


# ---------------------------------------------------------------------------
# Error detection for tool results
# ---------------------------------------------------------------------------


class ToolError(Exception):
    """Raised when a tool handler returns an error result.

    The SDK call_tool decorator catches exceptions and auto-sets isError=True
    in the CallToolResult, so raising this converts handler error dicts into
    proper MCP error signals.
    """


def _is_error_result(result: dict[str, Any]) -> bool:
    """Detect whether a handler result dict represents an error.

    Checks two patterns:
    1. Direct: ``{"status": "error", ...}``
    2. Nested: ``{"content": [{"type": "text", "text": '{"status": "error", ...}'}]}``
    """
    # Pattern 1: direct error status
    if result.get("status") == "error":
        return True

    # Pattern 2: nested JSON in content
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and parsed.get("status") == "error":
                        return True
                except (json.JSONDecodeError, TypeError):
                    logger.debug("Failed to parse content text as JSON when checking for error status")

    return False


def _extract_error_text(result: dict[str, Any]) -> str:
    """Extract a human-readable error message from an error result dict."""
    # Direct error fields
    if "error" in result:
        return str(result["error"])
    if "message" in result:
        return str(result["message"])

    # Try nested content
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        if "error" in parsed:
                            return str(parsed["error"])
                        if "message" in parsed:
                            return str(parsed["message"])
                except (json.JSONDecodeError, TypeError):
                    logger.debug("Failed to parse content text as JSON when extracting error message")

    return str(result)


# ---------------------------------------------------------------------------
# Handler: call_tool
# ---------------------------------------------------------------------------


@server.call_tool()  # type: ignore[misc]
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Dispatch a tool call to the appropriate handler.

    Converts the handler's legacy dict result format into MCP SDK content types.
    Detects error results and raises ToolError so the SDK sets isError=True.
    After a successful call to a device-writing tool, emits
    notifications/resources/list_changed to subscribed clients.

    Raises:
        ValueError: If the tool name is not recognized.
        ToolError: If the handler returns an error result dict.
    """
    handler = get_tool_handler(name)  # raises ValueError for unknown tools
    result = await handler(arguments or {})
    if _is_error_result(result):
        raise ToolError(_extract_error_text(result))
    content = _convert_result(result)

    # Notify subscribed clients when a device-writing tool succeeds.
    # Dry-run calls are excluded — they do not mutate the database.
    is_dry_run = bool((arguments or {}).get("dry_run", False))
    if name in MUTATING_TOOLS and not is_dry_run:
        try:
            session = server.request_context.session
            await session.send_resource_list_changed()
        except LookupError:
            # No active request context — handler called outside MCP lifecycle (e.g. tests).
            logger.debug("No request context available for resource notification")

    return content


def _convert_result(
    result: dict[str, Any],
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Convert a legacy handler result dict to MCP content objects.

    Handlers return ``{"content": [{"type": "text", "text": "..."}, ...]}``
    or sometimes a flat dict. This normalizes to SDK content types.
    """
    content_items: list[dict[str, Any]] = []

    if "content" in result and isinstance(result["content"], list):
        content_items = result["content"]
    else:
        # Fallback: wrap the whole result as a single text item
        content_items = [{"type": "text", "text": json.dumps(result)}]

    converted: list[types.TextContent | types.ImageContent | types.EmbeddedResource] = []
    for item in content_items:
        item_type = item.get("type", "text")
        if item_type == "image":
            converted.append(
                types.ImageContent(
                    type="image",
                    data=item.get("data", ""),
                    mimeType=item.get("mimeType", "image/png"),
                )
            )
        else:
            converted.append(
                types.TextContent(
                    type="text",
                    text=item.get("text", ""),
                )
            )
    return converted
