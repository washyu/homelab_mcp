"""Tests for DRFT-05: baseline hooks in proxmox create/clone handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCreateProxmoxVmBaselineHook:
    """handle_create_proxmox_vm calls update_baseline_after_mutation on success."""

    @pytest.mark.asyncio
    async def test_baseline_updated_on_success(self):
        """When create_proxmox_vm returns status=success, baseline hook is called."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_vm

        mock_rm = MagicMock()
        mock_rm.proxmox_session = AsyncMock()
        mock_rm.db_adapter = MagicMock()

        with (
            patch("homelab_mcp.tool_handlers.proxmox_handlers.create_proxmox_vm") as mock_create,
            patch("homelab_mcp.drift_detection.update_baseline_after_mutation") as mock_baseline,
            patch("homelab_mcp.server.get_resource_manager", return_value=mock_rm),
        ):
            mock_create.return_value = {"status": "success", "vmid": 100}
            mock_baseline.return_value = None

            result = await handle_create_proxmox_vm(
                {
                    "node": "pve",
                    "vmid": 100,
                    "name": "test-vm",
                }
            )

        assert "content" in result
        mock_baseline.assert_called_once()
        call_kwargs = mock_baseline.call_args[1]
        assert call_kwargs.get("node") == "pve"
        assert call_kwargs.get("vmid") == 100
        assert call_kwargs.get("vm_type") == "qemu"
        assert call_kwargs.get("tool_name") == "create_proxmox_vm"

    @pytest.mark.asyncio
    async def test_baseline_not_called_on_failure(self):
        """When create_proxmox_vm returns status=error, baseline hook is NOT called."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_vm

        mock_rm = MagicMock()
        mock_rm.proxmox_session = AsyncMock()
        mock_rm.db_adapter = MagicMock()

        with (
            patch("homelab_mcp.tool_handlers.proxmox_handlers.create_proxmox_vm") as mock_create,
            patch("homelab_mcp.drift_detection.update_baseline_after_mutation") as mock_baseline,
            patch("homelab_mcp.server.get_resource_manager", return_value=mock_rm),
        ):
            mock_create.return_value = {"status": "error", "message": "VM creation failed"}

            result = await handle_create_proxmox_vm(
                {
                    "node": "pve",
                    "vmid": 100,
                    "name": "test-vm",
                }
            )

        assert "content" in result
        mock_baseline.assert_not_called()


class TestCreateProxmoxLxcBaselineHook:
    """handle_create_proxmox_lxc calls update_baseline_after_mutation on success."""

    @pytest.mark.asyncio
    async def test_baseline_updated_with_lxc_type(self):
        """When create_proxmox_lxc returns status=success, baseline uses vm_type=lxc."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_lxc

        mock_rm = MagicMock()
        mock_rm.proxmox_session = AsyncMock()
        mock_rm.db_adapter = MagicMock()

        with (
            patch("homelab_mcp.tool_handlers.proxmox_handlers.create_proxmox_lxc") as mock_create,
            patch("homelab_mcp.drift_detection.update_baseline_after_mutation") as mock_baseline,
            patch("homelab_mcp.server.get_resource_manager", return_value=mock_rm),
        ):
            mock_create.return_value = {"status": "success", "vmid": 200}
            mock_baseline.return_value = None

            result = await handle_create_proxmox_lxc(
                {
                    "node": "pve",
                    "vmid": 200,
                    "hostname": "test-lxc",
                }
            )

        assert "content" in result
        mock_baseline.assert_called_once()
        call_kwargs = mock_baseline.call_args[1]
        assert call_kwargs.get("vm_type") == "lxc"
        assert call_kwargs.get("tool_name") == "create_proxmox_lxc"
        assert call_kwargs.get("vmid") == 200


class TestCloneProxmoxVmBaselineHook:
    """handle_clone_proxmox_vm calls update_baseline_after_mutation on success using new_vmid."""

    @pytest.mark.asyncio
    async def test_baseline_uses_new_vmid(self):
        """When clone_proxmox_vm returns status=success, baseline uses new_vmid not source vmid."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_clone_proxmox_vm

        mock_rm = MagicMock()
        mock_rm.proxmox_session = AsyncMock()
        mock_rm.db_adapter = MagicMock()

        with (
            patch("homelab_mcp.tool_handlers.proxmox_handlers.clone_proxmox_vm") as mock_clone,
            patch("homelab_mcp.drift_detection.update_baseline_after_mutation") as mock_baseline,
            patch("homelab_mcp.server.get_resource_manager", return_value=mock_rm),
        ):
            mock_clone.return_value = {"status": "success", "new_vmid": 300}
            mock_baseline.return_value = None

            result = await handle_clone_proxmox_vm(
                {
                    "node": "pve",
                    "vmid": 100,
                    "new_vmid": 300,
                }
            )

        assert "content" in result
        mock_baseline.assert_called_once()
        call_kwargs = mock_baseline.call_args[1]
        assert call_kwargs.get("vmid") == 300  # new_vmid, NOT source 100
        assert call_kwargs.get("tool_name") == "clone_proxmox_vm"

    @pytest.mark.asyncio
    async def test_result_returned_even_if_baseline_fails(self):
        """Original result is returned even when baseline update raises an exception."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_clone_proxmox_vm

        mock_rm = MagicMock()
        mock_rm.proxmox_session = AsyncMock()
        mock_rm.db_adapter = MagicMock()

        with (
            patch("homelab_mcp.tool_handlers.proxmox_handlers.clone_proxmox_vm") as mock_clone,
            patch("homelab_mcp.drift_detection.update_baseline_after_mutation") as mock_baseline,
            patch("homelab_mcp.server.get_resource_manager", return_value=mock_rm),
        ):
            mock_clone.return_value = {"status": "success", "new_vmid": 300}
            # update_baseline_after_mutation internally handles errors per plan spec
            # but test that handler still returns content if it raises unexpectedly
            mock_baseline.side_effect = Exception("Unexpected DB error")

            # Should not raise - handler must return result regardless
            result = await handle_clone_proxmox_vm(
                {
                    "node": "pve",
                    "vmid": 100,
                    "new_vmid": 300,
                }
            )

        assert "content" in result
