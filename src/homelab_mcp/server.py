"""MCP server for homelab system management using MCP SDK lowlevel.Server.

Replaces the hand-rolled JSON-RPC HomelabMCPServer with the official MCP SDK.
Uses lowlevel.Server with lifespan, list_tools, and call_tool decorators.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl

from .config import MCPConfig, get_config
from .credential_store import (
    delete_credential,
    list_credentials,
    register_credential,
    store_credential,
    unregister_cluster_credential,
    unregister_credential,
)
from .log_filter import CredentialFilter, sanitize_error
from .progress import (
    LOG_LEVEL_ORDER,
    emit_progress,
    set_min_log_level,
    should_emit,
)
from .prompt_registry import HOMELAB_PROMPTS, get_prompt_result
from .resource_manager import ResourceManager
from .resource_readers import read_devices_resource, read_drift_resource, read_service_resource, read_vms_resource
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


#: Latest drift scan result. None until scan_infrastructure_drift has run.
_latest_drift_report: dict[str, Any] | None = None


def get_latest_drift_report() -> dict[str, Any] | None:
    """Return the latest drift scan result, or None if no scan has run."""
    return _latest_drift_report


def set_latest_drift_report(report: dict[str, Any] | None) -> None:
    """Store a completed drift scan result for homelab://drift/latest."""
    global _latest_drift_report  # noqa: PLW0603
    _latest_drift_report = report


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


def _get_version() -> str:
    """Return package version from installed dist-info."""
    try:
        return version("homelab-mcp")
    except PackageNotFoundError:
        return "unknown"


server = Server("homelab-mcp", version=_get_version(), lifespan=app_lifespan)

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
    "homelab://drift/latest": {
        "name": "Drift Report",
        "description": (
            "Latest infrastructure drift scan result. Four-bucket coverage report "
            "(probed_ok, unreachable, unknown, changed) with per-bucket counts and a "
            "conditional guidance field when no hosts were scanned. Populated by "
            "scan_infrastructure_drift; recovery via discover_and_map / "
            "get_network_sitemap / purge_failed_discoveries."
        ),
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

#: Tools that update the drift report resource.
#: A successful call triggers notifications/resources/updated for homelab://drift/latest.
DRIFT_SCAN_TOOLS: frozenset[str] = frozenset({"scan_infrastructure_drift"})


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
        elif uri_str == "homelab://drift/latest":
            payload = await read_drift_resource()
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
# Handler: list_prompts
# ---------------------------------------------------------------------------


@server.list_prompts()  # type: ignore[misc]
async def handle_list_prompts() -> list[types.Prompt]:
    """Return all homelab prompt templates."""
    return list(HOMELAB_PROMPTS.values())


# ---------------------------------------------------------------------------
# Handler: get_prompt
# ---------------------------------------------------------------------------


@server.get_prompt()  # type: ignore[misc]
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    """Return the rendered messages for a named prompt."""
    return get_prompt_result(name, arguments)


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

    # Notify subscribed clients when the drift scan completes (resource content changed).
    if name in DRIFT_SCAN_TOOLS:
        try:
            session = server.request_context.session
            await session.send_resource_updated(AnyUrl("homelab://drift/latest"))
        except LookupError:
            logger.debug("No request context available for drift resource notification")

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


def _parse_scope_arg(scope_arg: str | None) -> tuple[str, str]:
    """Return (scope, cluster_name). scope_arg of None or empty → ("node", "").

    scope_arg of "cluster:<name>" → ("cluster", "<name>"). "<name>" must be non-empty.
    Any other value raises ValueError for the caller to translate into stderr + exit.
    """
    if not scope_arg:
        return ("node", "")
    if scope_arg == "node":
        return ("node", "")
    if scope_arg.startswith("cluster:"):
        cluster_name = scope_arg[len("cluster:") :]
        if not cluster_name:
            raise ValueError(
                "--scope cluster: requires a cluster_name after the colon (e.g. --scope cluster:homelab-prod)"
            )
        return ("cluster", cluster_name)
    raise ValueError(f"Unknown --scope value {scope_arg!r} — expected 'node' (default) or 'cluster:<name>'")


def _cmd_credentials_add(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials add ...`.

    Supports two credential shapes:
      1. Per-node SSH/Proxmox: ``add <hostname> <username> [--type ssh|proxmox] [--key-path PATH]``
      2. Cluster-scoped Proxmox: ``add --type proxmox --scope cluster:<name> <username>`` (no hostname)

    When ``--key-path`` is given (per-node SSH only), the key file path (resolved absolute)
    is stored as the "secret" in the OS keyring and the registry entry gets ``auth_type="key"``.
    When absent, the user is prompted for a password via ``getpass`` (TTY echo suppressed)
    and the registry entry gets ``auth_type="password"``.
    """
    import getpass  # noqa: PLC0415
    import pathlib  # noqa: PLC0415
    import sys  # noqa: PLC0415

    credential_type: str = args.credential_type
    key_path: str | None = getattr(args, "key_path", None)
    scope_arg: str | None = getattr(args, "scope", None)
    hostname: str | None = args.hostname

    # Parse --scope.
    try:
        scope, cluster_name = _parse_scope_arg(scope_arg)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Cluster-scope branch (D-06).
    if scope == "cluster":
        if credential_type != "proxmox":
            print(
                f"Error: --scope cluster:<name> requires --type proxmox (got {credential_type!r})",
                file=sys.stderr,
            )
            sys.exit(1)
        if hostname is not None:
            print(
                "Error: <hostname> positional must not be provided when --scope cluster:<name> is used",
                file=sys.stderr,
            )
            sys.exit(1)
        if key_path is not None:
            print(
                "Error: --key-path is not valid with --scope cluster:<name>",
                file=sys.stderr,
            )
            sys.exit(1)
        auth_type = "password"
        prompt = "Token/Password: "
        secret = getpass.getpass(prompt)
        if not secret:
            print("Error: empty password rejected", file=sys.stderr)
            sys.exit(1)
        ok = store_credential(
            "",
            args.username,
            secret,
            credential_type=credential_type,
            scope="cluster",
            cluster_name=cluster_name,
        )
        if ok:
            register_credential(
                "",
                args.username,
                credential_type=credential_type,
                auth_type=auth_type,
                scope="cluster",
                cluster_name=cluster_name,
            )
            print(f"Stored {credential_type} credential for {args.username}@cluster:{cluster_name}")
        else:
            print(
                f"Warning: OS keyring unavailable — credential not persisted for cluster:{cluster_name}",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    # Per-node path — hostname is required.
    if hostname is None:
        print(
            "Error: <hostname> is required for per-node credentials (use --scope cluster:<name> for cluster-scoped)",
            file=sys.stderr,
        )
        sys.exit(1)

    if key_path is not None:
        # Key-path auth branch (D-09). Strict validation (Claude's Discretion).
        if credential_type != "ssh":
            print(
                f"Error: --key-path is only valid with --type ssh (got {credential_type!r})",
                file=sys.stderr,
            )
            sys.exit(1)
        key_file = pathlib.Path(key_path).expanduser()
        if not key_file.exists():
            print(f"Error: key file not found: {key_path}", file=sys.stderr)
            sys.exit(1)
        if not key_file.is_file():
            print(f"Error: key path is not a file: {key_path}", file=sys.stderr)
            sys.exit(1)
        secret = str(key_file.resolve())
        auth_type = "key"
    else:
        prompt = "Token/Password: " if credential_type == "proxmox" else "Password: "
        secret = getpass.getpass(prompt)
        if not secret:
            print("Error: empty password rejected", file=sys.stderr)
            sys.exit(1)
        auth_type = "password"

    ok = store_credential(hostname, args.username, secret, credential_type=credential_type)
    if ok:
        register_credential(
            hostname,
            args.username,
            credential_type=credential_type,
            auth_type=auth_type,
        )
        if auth_type == "key":
            print(f"Stored {credential_type} credential (key-path) for {args.username}@{hostname}")
        else:
            print(f"Stored {credential_type} credential for {args.username}@{hostname}")
    else:
        print(
            f"Warning: OS keyring unavailable — credential not persisted for {hostname}",
            file=sys.stderr,
        )
        sys.exit(1)


def _cmd_credentials_list(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials list [--type ssh|proxmox]`. Groups output by scope (D-08)."""
    credential_type: str = args.credential_type
    entries = list_credentials(credential_type=credential_type)
    if not entries:
        print(f"No stored {credential_type} credentials.")
        return
    node_entries = [e for e in entries if e.get("scope", "node") == "node"]
    cluster_entries = [e for e in entries if e.get("scope") == "cluster"]
    print(f"Stored {credential_type} credentials:")
    if node_entries:
        print("  Per-node:")
        for e in node_entries:
            print(f"    {e['username']}@{e['hostname']}")
    if cluster_entries:
        print("  Cluster-scoped:")
        for e in cluster_entries:
            print(f"    {e['username']}@cluster:{e.get('cluster_name', '')}")


def _cmd_credentials_remove(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials remove ...`.

    Supports per-node and cluster-scoped removal. See --scope help for details.
    """
    import sys  # noqa: PLC0415

    credential_type: str = args.credential_type
    scope_arg: str | None = getattr(args, "scope", None)
    hostname: str | None = args.hostname

    try:
        scope, cluster_name = _parse_scope_arg(scope_arg)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if scope == "cluster":
        if credential_type != "proxmox":
            print(
                f"Error: --scope cluster:<name> requires --type proxmox (got {credential_type!r})",
                file=sys.stderr,
            )
            sys.exit(1)
        if hostname is not None:
            print(
                "Error: <hostname> positional must not be provided when --scope cluster:<name> is used",
                file=sys.stderr,
            )
            sys.exit(1)
        all_entries = list_credentials(credential_type=credential_type)
        cluster_entries = [
            e for e in all_entries if e.get("scope") == "cluster" and e.get("cluster_name", "") == cluster_name
        ]
        if not cluster_entries:
            print(
                f"No {credential_type} credential found for cluster:{cluster_name}",
                file=sys.stderr,
            )
            sys.exit(1)
        for entry in cluster_entries:
            delete_credential(
                "",
                entry["username"],
                credential_type=credential_type,
                scope="cluster",
                cluster_name=cluster_name,
            )
        unregister_cluster_credential(cluster_name, credential_type=credential_type)
        print(f"Removed {credential_type} credential for cluster:{cluster_name}")
        return

    # Per-node path — hostname is required.
    if hostname is None:
        print(
            "Error: <hostname> is required for per-node credentials (use --scope cluster:<name> for cluster-scoped)",
            file=sys.stderr,
        )
        sys.exit(1)

    entries = [e for e in list_credentials(credential_type=credential_type) if e["hostname"] == hostname]
    if not entries:
        print(
            f"No {credential_type} credential found for {hostname}",
            file=sys.stderr,
        )
        sys.exit(1)

    for entry in entries:
        delete_credential(entry["hostname"], entry["username"], credential_type=credential_type)
    unregister_credential(hostname, credential_type=credential_type)
    print(f"Removed {credential_type} credential for {hostname}")


def _run_stdio_wrapper(args: argparse.Namespace) -> None:
    """Dispatch to stdio or HTTP server. Called when no credentials subcommand is given."""
    import asyncio  # noqa: PLC0415
    import sys  # noqa: PLC0415

    if getattr(args, "http", False):
        import uvicorn  # noqa: PLC0415

        from homelab_mcp.http_app import create_http_app  # noqa: PLC0415

        protocol = "HTTPS" if getattr(args, "ssl_cert", None) else "HTTP"
        print(
            f"MCP Server starting in {protocol} mode on "
            f"{getattr(args, 'host', '127.0.0.1')}:{getattr(args, 'port', 8080)}",
            file=sys.stderr,
        )
        app = create_http_app()
        config = uvicorn.Config(
            app=app,
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8080),
            log_level="info",
            ssl_certfile=getattr(args, "ssl_cert", None),
            ssl_keyfile=getattr(args, "ssl_key", None),
        )
        uvi_server = uvicorn.Server(config)
        asyncio.run(uvi_server.serve())
    else:
        print("MCP Server starting in stdio mode...", file=sys.stderr)
        asyncio.run(_run_stdio())


def main() -> None:
    """Console script entry point for `uvx homelab-mcp` and `python -m homelab_mcp`."""
    import os  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        description="Homelab MCP Server - AI-powered homelab infrastructure management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uvx homelab-mcp                        # stdio mode (Claude Desktop)
  uvx homelab-mcp --http --port 8080     # HTTP mode (OpenWebUI)

Credential management (OS keyring):
  uvx homelab-mcp credentials add <hostname> <username>                                     # store SSH credential (prompts for password)
  uvx homelab-mcp credentials add <hostname> <username> --key-path PATH                     # store SSH key-path credential (D-09)
  uvx homelab-mcp credentials add <hostname> <username> --type proxmox                      # store Proxmox credential
  uvx homelab-mcp credentials add --type proxmox --scope cluster:<name> <username>          # store cluster-scoped Proxmox token
  uvx homelab-mcp credentials list                                                          # list stored SSH credentials
  uvx homelab-mcp credentials list --type proxmox                                           # (extended) shows Per-node + Cluster-scoped sections
  uvx homelab-mcp credentials remove <hostname>                                             # remove SSH credential
  uvx homelab-mcp credentials remove <hostname> --type proxmox                              # remove Proxmox credential
  uvx homelab-mcp credentials remove --type proxmox --scope cluster:<name>                  # remove cluster-scoped Proxmox credential

  Note: `add` is upsert — re-running it for the same (hostname, username, type)
  replaces the existing credential (both the keyring secret and the registry
  entry's auth_type). There is no separate `update` subcommand.
""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        default=os.getenv("MCP_HTTP_ENABLED", "false").lower() == "true",
        help="Run in HTTP mode instead of stdio mode",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
        help="HTTP server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_HTTP_PORT", "8080")),
        help="HTTP server port (default: 8080)",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        default=os.getenv("MCP_AUTH_ENABLED", "true").lower() == "false",
        help="Disable API key authentication",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("MCP_API_KEY"),
        help="API key for authentication",
    )
    parser.add_argument(
        "--ssl-cert",
        type=str,
        default=os.getenv("MCP_SSL_CERT"),
        help="Path to SSL certificate file (enables HTTPS)",
    )
    parser.add_argument(
        "--ssl-key",
        type=str,
        default=os.getenv("MCP_SSL_KEY"),
        help="Path to SSL private key file",
    )

    # Ensure bare `homelab-mcp` still starts the server (set_defaults pattern)
    parser.set_defaults(func=_run_stdio_wrapper)

    # credentials subcommand group
    sub = parser.add_subparsers(dest="command")
    cred_p = sub.add_parser("credentials", help="Manage stored credentials")
    cred_sub = cred_p.add_subparsers(dest="cred_action")

    # credentials add [<hostname>] <username> [--type ssh|proxmox] [--key-path PATH] [--scope SCOPE]
    add_p = cred_sub.add_parser(
        "add",
        help="Store a credential (upsert — re-run to replace an existing entry)",
        description=(
            "Store a credential in the OS keyring. This is upsert behavior: re-running "
            "`add` for the same (hostname, username, type) replaces the existing secret "
            "and its auth_type. There is no separate `update` subcommand — `add` is it."
        ),
    )
    add_p.add_argument(
        "hostname",
        nargs="?",
        default=None,
        help=(
            "Target host DNS name (required for per-node credentials; "
            "must be omitted when --scope cluster:<name> is used)"
        ),
    )
    add_p.add_argument(
        "username",
        help="Username on the target host (proxmox: the Proxmox token ID in `user@realm!tokenname` form)",
    )
    add_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh", dest="credential_type")
    add_p.add_argument(
        "--key-path",
        dest="key_path",
        default=None,
        metavar="PATH",
        help=(
            "Path to SSH private key file for key-based auth. "
            "When given, skips the password prompt and stores the path "
            "as the credential instead (D-09). The key file itself is "
            "not copied — only its filesystem path."
        ),
    )
    add_p.add_argument(
        "--scope",
        dest="scope",
        default=None,
        metavar="SCOPE",
        help=(
            "Credential scope. Omit for per-node (default). "
            "Use --scope cluster:<cluster_name> to store a Proxmox cluster-wide token "
            "(requires --type proxmox). When --scope cluster:<name> is used, the positional "
            "<hostname> is not allowed."
        ),
    )
    add_p.set_defaults(func=_cmd_credentials_add)

    # credentials list [--type ssh|proxmox]
    list_p = cred_sub.add_parser("list", help="List stored credential hostnames")
    list_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh", dest="credential_type")
    list_p.set_defaults(func=_cmd_credentials_list)

    # credentials remove [<hostname>] [--type ssh|proxmox] [--scope SCOPE]
    remove_p = cred_sub.add_parser("remove", help="Remove a stored credential")
    remove_p.add_argument(
        "hostname",
        nargs="?",
        default=None,
        help=(
            "Target host DNS name (required for per-node removal; must be omitted when --scope cluster:<name> is used)"
        ),
    )
    remove_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh", dest="credential_type")
    remove_p.add_argument(
        "--scope",
        dest="scope",
        default=None,
        metavar="SCOPE",
        help=(
            "Scope filter. Omit for per-node removal. "
            "Use --scope cluster:<cluster_name> to remove a Proxmox cluster-wide credential."
        ),
    )
    remove_p.set_defaults(func=_cmd_credentials_remove)

    args = parser.parse_args()
    getattr(args, "func", _run_stdio_wrapper)(args)


async def _run_stdio() -> None:
    """Run the MCP server in stdio mode. Internal helper for main()."""
    import signal

    import anyio
    from mcp.server.stdio import stdio_server

    shutdown_event = anyio.Event()

    def _signal_handler(signum: int, frame: object) -> None:
        import sys

        print(f"\nReceived signal {signal.Signals(signum).name}, shutting down...", file=sys.stderr)
        shutdown_event.set()

    previous_sigterm = signal.signal(signal.SIGTERM, _signal_handler)
    previous_sigint = signal.signal(signal.SIGINT, _signal_handler)

    try:
        async with anyio.create_task_group() as tg:

            async def _run_server() -> None:
                async with stdio_server() as (read_stream, write_stream):
                    await server.run(read_stream, write_stream, server.create_initialization_options())

            async def _wait_for_shutdown() -> None:
                await shutdown_event.wait()
                tg.cancel_scope.cancel()

            tg.start_soon(_run_server)
            tg.start_soon(_wait_for_shutdown)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)
