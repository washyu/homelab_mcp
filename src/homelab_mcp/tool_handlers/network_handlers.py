"""Handler functions for network topology and sitemap tools."""

import json
from typing import Any

from ..sitemap import NetworkSiteMap, bulk_discover_and_store, discover_and_store
from ..validation import validate_hostname


async def handle_discover_and_map(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle discover_and_map tool."""
    validate_hostname(arguments["hostname"])
    sitemap = NetworkSiteMap()
    result = await discover_and_store(sitemap, **arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_bulk_discover_and_map(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle bulk_discover_and_map tool."""
    for target in arguments["targets"]:
        validate_hostname(target["hostname"])
    sitemap = NetworkSiteMap()
    result = await bulk_discover_and_store(sitemap, arguments["targets"])
    return {"content": [{"type": "text", "text": result}]}


async def handle_get_network_sitemap(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_network_sitemap tool."""
    sitemap = NetworkSiteMap()
    devices = sitemap.get_all_devices()
    result = json.dumps(
        {"status": "success", "total_devices": len(devices), "devices": devices},
        indent=2,
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_analyze_network_topology(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle analyze_network_topology tool."""
    sitemap = NetworkSiteMap()
    analysis = sitemap.analyze_network_topology()
    result = json.dumps({"status": "success", "analysis": analysis}, indent=2)
    return {"content": [{"type": "text", "text": result}]}


async def handle_suggest_deployments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle suggest_deployments tool."""
    sitemap = NetworkSiteMap()
    suggestions = sitemap.suggest_deployments()
    result = json.dumps({"status": "success", "suggestions": suggestions}, indent=2)
    return {"content": [{"type": "text", "text": result}]}


async def handle_get_device_changes(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_device_changes tool."""
    sitemap = NetworkSiteMap()
    changes = sitemap.get_device_changes(arguments["device_id"], arguments.get("limit", 10))
    result = json.dumps(
        {
            "status": "success",
            "device_id": arguments["device_id"],
            "changes": changes,
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_purge_failed_discoveries(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle purge_failed_discoveries tool."""
    dry_run = bool(arguments.get("dry_run", False))
    sitemap = NetworkSiteMap()
    removed = sitemap.purge_failed_devices(dry_run=dry_run)
    result = json.dumps(
        {
            "status": "success",
            "dry_run": dry_run,
            "purged_count": len(removed),
            "purged_devices": removed,
        },
        indent=2,
        default=str,
    )
    return {"content": [{"type": "text", "text": result}]}
