"""Live data fetchers for MCP Resource URIs.

Three async reader functions that fetch live data for each MCP resource:
- read_vms_resource: Proxmox VMs and containers via proxmox_api
- read_devices_resource: DB-tracked devices with last discovery data enrichment
- read_service_resource: Service status via ServiceInstaller SSH check

These functions are intentionally isolated from server.py so they are
independently testable. server.py dispatches to these in Plan 02.

get_resource_manager is imported locally inside each function to avoid the
circular import that arises when server.py also imports from resource_readers.
Tests patch at 'homelab_mcp.server.get_resource_manager'.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from .proxmox_api import list_proxmox_resources
from .service_installer import ServiceInstaller

logger = logging.getLogger(__name__)


async def read_vms_resource() -> dict[str, Any]:
    """Fetch live VM/container data from Proxmox.

    Returns:
        On success: {"vms": [...], "total": N, "scanned_at": "...", "providers": ["proxmox"]}
        On ValueError (no PROXMOX_HOST): {"vms": [], "scanned_at": "...", "config_error": "..."}
        On RuntimeError (no ResourceManager): {"vms": [], "scanned_at": "...", "error": "..."}
        On other exceptions: {"vms": [], "scanned_at": "...", "error": "..."}
    """
    from .server import get_resource_manager  # deferred to avoid circular import

    scanned_at = datetime.now(UTC).isoformat()

    try:
        rm = get_resource_manager()
        result = await list_proxmox_resources(session=rm.proxmox_session)
        vms: list[dict[str, Any]] = result.get("resources", [])
        return {
            "vms": vms,
            "total": len(vms),
            "scanned_at": scanned_at,
            "providers": ["proxmox"],
        }
    except RuntimeError as e:
        logger.warning("ResourceManager not available for read_vms_resource: %s", e)
        return {
            "vms": [],
            "scanned_at": scanned_at,
            "error": str(e),
        }
    except ValueError as e:
        logger.warning("Proxmox not configured for read_vms_resource: %s", e)
        return {
            "vms": [],
            "scanned_at": scanned_at,
            "config_error": str(e),
        }
    except Exception as e:
        logger.exception("Unexpected error in read_vms_resource")
        return {
            "vms": [],
            "scanned_at": scanned_at,
            "error": str(e),
        }


async def read_devices_resource() -> dict[str, Any]:
    """Fetch all tracked devices from the database, enriched with last discovery data.

    Each device dict is the raw DB row plus a "last_discovery_data" key containing
    the most recent discovery blob from get_device_changes(), or None if no history.

    Returns:
        On success: {"devices": [...], "total": N, "scanned_at": "..."}
        On RuntimeError (no ResourceManager): {"devices": [], "scanned_at": "...", "error": "..."}
        On other exceptions: {"devices": [], "scanned_at": "...", "error": "..."}
    """
    from .server import get_resource_manager  # deferred to avoid circular import

    scanned_at = datetime.now(UTC).isoformat()

    try:
        rm = get_resource_manager()
        db = rm.db_adapter
        raw_devices = db.get_all_devices()

        devices: list[dict[str, Any]] = []
        for device in raw_devices:
            enriched = dict(device)
            device_id: int = device.get("id", -1)
            if device_id >= 0:
                changes = db.get_device_changes(device_id, limit=1)
                enriched["last_discovery_data"] = changes[0]["data"] if changes else None
            else:
                enriched["last_discovery_data"] = None
            devices.append(enriched)

        return {
            "devices": devices,
            "total": len(devices),
            "scanned_at": scanned_at,
        }
    except RuntimeError as e:
        logger.warning("ResourceManager not available for read_devices_resource: %s", e)
        return {
            "devices": [],
            "scanned_at": scanned_at,
            "error": str(e),
        }
    except Exception as e:
        logger.exception("Unexpected error in read_devices_resource")
        return {
            "devices": [],
            "scanned_at": scanned_at,
            "error": str(e),
        }


async def read_service_resource(service_name: str) -> dict[str, Any]:
    """Fetch live service status via SSH.

    Hostname resolution order:
    1. MCP_DEFAULT_SERVICE_HOST environment variable
    2. First device from DB with connection_ip or hostname field

    Returns:
        On success: service status dict with "scanned_at" injected
        If no hostname resolvable: {"service": name, "status": "unconfigured", "reason": "...", "scanned_at": "..."}
        On SSH/other error: {"service": name, "status": "error", "hostname": h, "error": "...", "scanned_at": "..."}
        On RuntimeError (no ResourceManager): {"service": name, "status": "error", "error": "...", "scanned_at": "..."}
    """
    scanned_at = datetime.now(UTC).isoformat()

    from .server import get_resource_manager  # deferred to avoid circular import

    # Resolve hostname
    hostname: str | None = os.environ.get("MCP_DEFAULT_SERVICE_HOST")

    if not hostname:
        try:
            rm = get_resource_manager()
            devices = rm.db_adapter.get_all_devices()
            for dev in devices:
                candidate = dev.get("connection_ip") or dev.get("hostname")
                if candidate:
                    hostname = candidate
                    break
        except RuntimeError as e:
            logger.warning("ResourceManager not available for read_service_resource: %s", e)
            return {
                "service": service_name,
                "status": "error",
                "error": str(e),
                "scanned_at": scanned_at,
            }

    if not hostname:
        return {
            "service": service_name,
            "status": "unconfigured",
            "reason": "No hostname available: set MCP_DEFAULT_SERVICE_HOST or add devices via SSH discovery",
            "scanned_at": scanned_at,
        }

    try:
        installer = ServiceInstaller()
        status = await installer.get_service_status(service_name, hostname)
        status["scanned_at"] = scanned_at
        return status
    except Exception as e:
        logger.warning("SSH error checking service %s on %s: %s", service_name, hostname, e)
        return {
            "service": service_name,
            "status": "error",
            "hostname": hostname,
            "error": str(e),
            "scanned_at": scanned_at,
        }
