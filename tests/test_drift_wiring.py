"""Tests for drift detection wiring: schema registry, handler registry, annotations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDriftSchemaRegistration:
    """scan_infrastructure_drift appears in tool schemas."""

    def test_scan_infrastructure_drift_in_schemas(self):
        """get_all_tool_schemas returns dict containing scan_infrastructure_drift."""
        from homelab_mcp.tool_schemas import get_all_tool_schemas

        tools = get_all_tool_schemas()
        assert "scan_infrastructure_drift" in tools

    def test_drift_tool_schema_has_required_keys(self):
        """scan_infrastructure_drift schema has description and inputSchema."""
        from homelab_mcp.tool_schemas import get_all_tool_schemas

        tools = get_all_tool_schemas()
        schema = tools["scan_infrastructure_drift"]
        assert "description" in schema
        assert "inputSchema" in schema

    def test_drift_tool_schema_properties(self):
        """scan_infrastructure_drift inputSchema has node and vm_type properties."""
        from homelab_mcp.tool_schemas import get_all_tool_schemas

        tools = get_all_tool_schemas()
        props = tools["scan_infrastructure_drift"]["inputSchema"]["properties"]
        assert "node" in props
        assert "vm_type" in props


class TestDriftHandlerRegistration:
    """scan_infrastructure_drift handler is callable and in TOOL_HANDLERS."""

    def test_scan_infrastructure_drift_in_handlers(self):
        """TOOL_HANDLERS contains scan_infrastructure_drift key."""
        from homelab_mcp.tool_handlers import TOOL_HANDLERS

        assert "scan_infrastructure_drift" in TOOL_HANDLERS

    def test_handler_is_callable(self):
        """TOOL_HANDLERS['scan_infrastructure_drift'] is callable."""
        from homelab_mcp.tool_handlers import TOOL_HANDLERS

        assert callable(TOOL_HANDLERS["scan_infrastructure_drift"])

    @pytest.mark.asyncio
    async def test_handler_returns_content_wrapped_dict(self):
        """handle_scan_infrastructure_drift returns dict with 'content' key."""
        from homelab_mcp.tool_handlers import TOOL_HANDLERS

        handler = TOOL_HANDLERS["scan_infrastructure_drift"]

        mock_rm = MagicMock()
        mock_rm.proxmox_session = AsyncMock()
        mock_rm.db_adapter = MagicMock()
        mock_rm.db_adapter.get_all_devices.return_value = []

        with patch("homelab_mcp.server.get_resource_manager", return_value=mock_rm):
            result = await handler({})

        assert "content" in result
        assert isinstance(result["content"], list)
        assert len(result["content"]) > 0
        assert result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_handler_passes_node_and_vm_type(self):
        """handle_scan_infrastructure_drift passes node and vm_type to scan_drift."""
        from homelab_mcp.tool_handlers.drift_handlers import handle_scan_infrastructure_drift

        mock_rm = MagicMock()
        mock_rm.proxmox_session = AsyncMock()
        mock_rm.db_adapter = MagicMock()

        with (
            patch("homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch("homelab_mcp.tool_handlers.drift_handlers.scan_drift") as mock_scan,
        ):
            mock_scan.return_value = {
                "status": "success",
                "scan_timestamp": "2026-01-01T00:00:00Z",
                "scanned": 0,
                "probed_ok": [],
                "unreachable": [],
            }

            await handle_scan_infrastructure_drift({"node": "pve", "vm_type": "qemu"})

            mock_scan.assert_called_once()
            call_kwargs = mock_scan.call_args[1]
            assert call_kwargs.get("node") == "pve"
            assert call_kwargs.get("vm_type") == "qemu"


class TestDriftAnnotations:
    """scan_infrastructure_drift is marked as read-only in TOOL_ANNOTATIONS."""

    def test_scan_infrastructure_drift_in_annotations(self):
        """TOOL_ANNOTATIONS contains scan_infrastructure_drift."""
        from homelab_mcp.tool_annotations import TOOL_ANNOTATIONS

        assert "scan_infrastructure_drift" in TOOL_ANNOTATIONS

    def test_scan_infrastructure_drift_is_read_only(self):
        """scan_infrastructure_drift annotation has readOnlyHint=True."""
        from homelab_mcp.tool_annotations import TOOL_ANNOTATIONS

        annotation = TOOL_ANNOTATIONS["scan_infrastructure_drift"]
        assert annotation.read_only_hint is True

    def test_scan_infrastructure_drift_not_destructive(self):
        """scan_infrastructure_drift annotation has destructiveHint=False."""
        from homelab_mcp.tool_annotations import TOOL_ANNOTATIONS

        annotation = TOOL_ANNOTATIONS["scan_infrastructure_drift"]
        assert annotation.destructive_hint is False
