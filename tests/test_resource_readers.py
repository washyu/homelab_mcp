"""Tests for resource_readers module — live data fetchers for MCP resources.

Covers:
- read_vms_resource: success, no proxmox config, no resource manager
- read_devices_resource: success, last_discovery_data enrichment, no history
- read_service_resource: unconfigured, success, SSH error
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# read_vms_resource tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_vms_resource_returns_scanned_at() -> None:
    """read_vms_resource returns dict with 'scanned_at' and 'vms' from list_proxmox_resources."""
    mock_rm = MagicMock()
    mock_rm.proxmox_session = MagicMock()

    mock_proxmox_result: dict[str, Any] = {
        "status": "success",
        "total": 2,
        "resources": [
            {"vmid": 100, "name": "vm1", "type": "qemu"},
            {"vmid": 101, "name": "vm2", "type": "lxc"},
        ],
    }

    with (
        patch(
            "homelab_mcp.resource_readers.get_resource_manager",
            return_value=mock_rm,
        ),
        patch(
            "homelab_mcp.resource_readers.list_proxmox_resources",
            new=AsyncMock(return_value=mock_proxmox_result),
        ),
    ):
        from homelab_mcp.resource_readers import read_vms_resource

        result = await read_vms_resource()

    assert "scanned_at" in result
    assert result["vms"] == mock_proxmox_result["resources"]
    assert result["total"] == 2
    assert result.get("providers") == ["proxmox"]


@pytest.mark.asyncio
async def test_read_vms_resource_no_proxmox_config() -> None:
    """read_vms_resource returns graceful error payload (not exception) when PROXMOX_HOST not set."""
    mock_rm = MagicMock()
    mock_rm.proxmox_session = MagicMock()

    with (
        patch(
            "homelab_mcp.resource_readers.get_resource_manager",
            return_value=mock_rm,
        ),
        patch(
            "homelab_mcp.resource_readers.list_proxmox_resources",
            new=AsyncMock(side_effect=ValueError("PROXMOX_HOST environment variable is not set")),
        ),
    ):
        from homelab_mcp.resource_readers import read_vms_resource

        result = await read_vms_resource()

    assert result["vms"] == []
    assert "config_error" in result
    assert "scanned_at" in result


@pytest.mark.asyncio
async def test_read_vms_resource_no_resource_manager() -> None:
    """read_vms_resource returns graceful error payload when ResourceManager unavailable."""
    with patch(
        "homelab_mcp.resource_readers.get_resource_manager",
        side_effect=RuntimeError("ResourceManager not available -- server lifespan not started"),
    ):
        from homelab_mcp.resource_readers import read_vms_resource

        result = await read_vms_resource()

    assert result["vms"] == []
    assert "error" in result
    assert "scanned_at" in result


# ---------------------------------------------------------------------------
# read_devices_resource tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_devices_resource_returns_scanned_at() -> None:
    """read_devices_resource returns dict with 'scanned_at' and 'total'."""
    mock_device: dict[str, Any] = {
        "id": 1,
        "hostname": "device1",
        "connection_ip": "192.168.1.10",
    }
    mock_rm = MagicMock()
    mock_rm.db_adapter.get_all_devices.return_value = [mock_device]
    mock_rm.db_adapter.get_device_changes.return_value = []

    with patch(
        "homelab_mcp.resource_readers.get_resource_manager",
        return_value=mock_rm,
    ):
        from homelab_mcp.resource_readers import read_devices_resource

        result = await read_devices_resource()

    assert "scanned_at" in result
    assert result["total"] == 1
    assert len(result["devices"]) == 1


@pytest.mark.asyncio
async def test_read_devices_resource_includes_last_discovery_data() -> None:
    """Each device dict includes 'last_discovery_data' from get_device_changes."""
    discovery_blob: dict[str, Any] = {"key": "val", "cpu": "x86_64"}
    mock_device: dict[str, Any] = {
        "id": 1,
        "hostname": "device1",
        "connection_ip": "192.168.1.10",
    }
    mock_rm = MagicMock()
    mock_rm.db_adapter.get_all_devices.return_value = [mock_device]
    mock_rm.db_adapter.get_device_changes.return_value = [
        {"data": discovery_blob, "discovered_at": "2026-01-01T00:00:00"}
    ]

    with patch(
        "homelab_mcp.resource_readers.get_resource_manager",
        return_value=mock_rm,
    ):
        from homelab_mcp.resource_readers import read_devices_resource

        result = await read_devices_resource()

    device = result["devices"][0]
    assert device["last_discovery_data"] == discovery_blob


@pytest.mark.asyncio
async def test_read_devices_resource_no_history() -> None:
    """Device with no change history has last_discovery_data == None."""
    mock_device: dict[str, Any] = {
        "id": 2,
        "hostname": "device2",
        "connection_ip": "192.168.1.20",
    }
    mock_rm = MagicMock()
    mock_rm.db_adapter.get_all_devices.return_value = [mock_device]
    mock_rm.db_adapter.get_device_changes.return_value = []

    with patch(
        "homelab_mcp.resource_readers.get_resource_manager",
        return_value=mock_rm,
    ):
        from homelab_mcp.resource_readers import read_devices_resource

        result = await read_devices_resource()

    device = result["devices"][0]
    assert device["last_discovery_data"] is None


# ---------------------------------------------------------------------------
# read_service_resource tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_service_resource_unconfigured() -> None:
    """read_service_resource returns unconfigured status when no hostname resolvable."""
    mock_rm = MagicMock()
    mock_rm.db_adapter.get_all_devices.return_value = []

    with (
        patch(
            "homelab_mcp.resource_readers.get_resource_manager",
            return_value=mock_rm,
        ),
        patch.dict(os.environ, {}, clear=False),
    ):
        # Ensure MCP_DEFAULT_SERVICE_HOST is not set
        os.environ.pop("MCP_DEFAULT_SERVICE_HOST", None)

        from homelab_mcp.resource_readers import read_service_resource

        result = await read_service_resource("nginx")

    assert result["status"] == "unconfigured"
    assert "scanned_at" in result
    assert result["service"] == "nginx"


@pytest.mark.asyncio
async def test_read_service_resource_returns_status() -> None:
    """read_service_resource injects scanned_at into the service status dict."""
    mock_status: dict[str, Any] = {
        "service": "nginx",
        "status": "running",
        "hostname": "myhost.local",
    }
    mock_installer = AsyncMock()
    mock_installer.get_service_status = AsyncMock(return_value=mock_status)

    mock_rm = MagicMock()

    with (
        patch(
            "homelab_mcp.resource_readers.get_resource_manager",
            return_value=mock_rm,
        ),
        patch(
            "homelab_mcp.resource_readers.ServiceInstaller",
            return_value=mock_installer,
        ),
        patch.dict(os.environ, {"MCP_DEFAULT_SERVICE_HOST": "myhost.local"}),
    ):
        from homelab_mcp.resource_readers import read_service_resource

        result = await read_service_resource("nginx")

    assert "scanned_at" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_read_service_resource_ssh_error() -> None:
    """read_service_resource returns error payload when get_service_status raises."""
    mock_installer = AsyncMock()
    mock_installer.get_service_status = AsyncMock(side_effect=Exception("Connection refused"))

    mock_rm = MagicMock()

    with (
        patch(
            "homelab_mcp.resource_readers.get_resource_manager",
            return_value=mock_rm,
        ),
        patch(
            "homelab_mcp.resource_readers.ServiceInstaller",
            return_value=mock_installer,
        ),
        patch.dict(os.environ, {"MCP_DEFAULT_SERVICE_HOST": "badhost.local"}),
    ):
        from homelab_mcp.resource_readers import read_service_resource

        result = await read_service_resource("nginx")

    assert result["status"] == "error"
    assert "error" in result
    assert "scanned_at" in result
    assert result["service"] == "nginx"
