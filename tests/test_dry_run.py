"""Tests for dry-run mode: contract builder (DRY-07) and handler stubs (DRY-01..DRY-06).

TestDryRunContract tests the build_dry_run_response() builder — these pass after Task 2.
All TestXxxDryRun handler test classes are RED stubs — they pass only after Wave 2 handlers
are modified to support dry_run=True.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homelab_mcp.dry_run import build_dry_run_response

# ---------------------------------------------------------------------------
# DRY-07: contract builder
# ---------------------------------------------------------------------------


class TestDryRunContract:
    """Tests for the shared dry-run response contract builder (DRY-07)."""

    def test_build_dry_run_response_required_fields(self) -> None:
        """All four required fields must be present in the response."""
        result = build_dry_run_response(
            tool_name="decommission_device",
            would_affect=[{"type": "device", "id": 1}],
            risk_level="high",
            reversible=False,
        )
        assert result["mode"] == "dry_run"
        assert result["tool"] == "decommission_device"
        assert result["would_affect"] == [{"type": "device", "id": 1}]
        assert result["risk_level"] == "high"
        assert result["reversible"] is False

    def test_build_dry_run_response_no_preview(self) -> None:
        """The 'preview' key must be absent when preview_details is None."""
        result = build_dry_run_response(
            tool_name="remove_vm",
            would_affect=[],
            risk_level="medium",
            reversible=True,
        )
        assert "preview" not in result

    def test_build_dry_run_response_with_preview(self) -> None:
        """The 'preview' key must be present when preview_details is given."""
        details = {"vm_name": "test-vm", "platform": "docker"}
        result = build_dry_run_response(
            tool_name="remove_vm",
            would_affect=[{"type": "vm", "id": "test-vm"}],
            risk_level="medium",
            reversible=True,
            preview_details=details,
        )
        assert "preview" in result
        assert result["preview"] == details

    def test_would_affect_is_list(self) -> None:
        """would_affect must be a list, not a plain dict."""
        result = build_dry_run_response(
            tool_name="remove_server",
            would_affect=[{"type": "server", "id": 5}],
            risk_level="low",
            reversible=True,
        )
        assert isinstance(result["would_affect"], list)


# ---------------------------------------------------------------------------
# DRY-01: decommission_device
# ---------------------------------------------------------------------------


class TestDecommissionDeviceDryRun:
    """Dry-run tests for decommission_device handler (DRY-01).

    These tests are RED stubs — handle_decommission_device does not yet
    support dry_run=True. They will go GREEN when Wave 2 adds the logic.
    """

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.infrastructure_handlers.decommission_network_device",
        new_callable=AsyncMock,
    )
    async def test_decommission_device_dry_run_returns_preview(self, mock_decommission: AsyncMock) -> None:
        """handle_decommission_device with dry_run=True must return mode='dry_run'."""
        from homelab_mcp.tool_handlers.infrastructure_handlers import (
            handle_decommission_device,
        )

        arguments = {"device_id": 1, "dry_run": True}
        result = await handle_decommission_device(arguments)
        assert result.get("mode") == "dry_run"

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.infrastructure_handlers.decommission_network_device",
        new_callable=AsyncMock,
    )
    async def test_decommission_device_dry_run_no_mutation(self, mock_decommission: AsyncMock) -> None:
        """decommission_network_device must NOT be called with validate_only=False when dry_run=True."""
        from homelab_mcp.tool_handlers.infrastructure_handlers import (
            handle_decommission_device,
        )

        arguments = {"device_id": 1, "dry_run": True}
        await handle_decommission_device(arguments)
        # Assert not called with validate_only=False (real mutation must not happen)
        for call in mock_decommission.call_args_list:
            kwargs = call.kwargs if call.kwargs else {}
            args = call.args if call.args else ()
            validate_only = kwargs.get("validate_only", args[3] if len(args) > 3 else None)
            assert validate_only is not False, (
                "decommission_network_device called with validate_only=False during dry-run"
            )

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.infrastructure_handlers.decommission_network_device",
        new_callable=AsyncMock,
    )
    async def test_decommission_device_real_execution(self, mock_decommission: AsyncMock) -> None:
        """Without dry_run, real decommission_network_device must be called."""
        from homelab_mcp.tool_handlers.infrastructure_handlers import (
            handle_decommission_device,
        )

        mock_decommission.return_value = "decommissioned"
        arguments = {"device_id": 1}
        await handle_decommission_device(arguments)
        mock_decommission.assert_called_once()


# ---------------------------------------------------------------------------
# DRY-02: remove_vm
# ---------------------------------------------------------------------------


class TestRemoveVmDryRun:
    """Dry-run tests for remove_vm handler (DRY-02).

    These tests are RED stubs — handle_remove_vm does not yet support dry_run=True.
    """

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.vm_handlers.remove_vm",
        new_callable=AsyncMock,
    )
    async def test_remove_vm_dry_run_returns_preview(self, mock_remove_vm: AsyncMock) -> None:
        """handle_remove_vm with dry_run=True must return mode='dry_run'."""
        from homelab_mcp.tool_handlers.vm_handlers import handle_remove_vm

        arguments = {
            "device_id": 1,
            "platform": "docker",
            "vm_name": "test-vm",
            "dry_run": True,
        }
        result = await handle_remove_vm(arguments)
        assert result.get("mode") == "dry_run"

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.vm_handlers.remove_vm",
        new_callable=AsyncMock,
    )
    async def test_remove_vm_dry_run_no_ssh(self, mock_remove_vm: AsyncMock) -> None:
        """remove_vm (SSH) must NOT be called when dry_run=True."""
        from homelab_mcp.tool_handlers.vm_handlers import handle_remove_vm

        arguments = {
            "device_id": 1,
            "platform": "docker",
            "vm_name": "test-vm",
            "dry_run": True,
        }
        await handle_remove_vm(arguments)
        mock_remove_vm.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.vm_handlers.remove_vm",
        new_callable=AsyncMock,
    )
    async def test_remove_vm_real_execution(self, mock_remove_vm: AsyncMock) -> None:
        """Without dry_run, remove_vm must be called."""
        from homelab_mcp.tool_handlers.vm_handlers import handle_remove_vm

        mock_remove_vm.return_value = "removed"
        arguments = {"device_id": 1, "platform": "docker", "vm_name": "test-vm"}
        await handle_remove_vm(arguments)
        mock_remove_vm.assert_called_once()


# ---------------------------------------------------------------------------
# DRY-03: remove_server
# ---------------------------------------------------------------------------


class TestRemoveServerDryRun:
    """Dry-run tests for remove_server handler (DRY-03).

    remove_server is SYNC; handle_remove_server is async but calls sync remove_server.
    These are RED stubs until Wave 2.
    """

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.credential_handlers.remove_server",
        new_callable=MagicMock,
    )
    async def test_remove_server_dry_run_returns_preview(self, mock_remove_server: MagicMock) -> None:
        """handle_remove_server with dry_run=True must return mode='dry_run'."""
        from homelab_mcp.tool_handlers.credential_handlers import handle_remove_server

        arguments = {"credential_id": 5, "dry_run": True}
        result = await handle_remove_server(arguments)
        assert result.get("mode") == "dry_run"

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.credential_handlers.remove_server",
        new_callable=MagicMock,
    )
    async def test_remove_server_dry_run_no_delete(self, mock_remove_server: MagicMock) -> None:
        """remove_server (DB delete) must NOT be called when dry_run=True."""
        from homelab_mcp.tool_handlers.credential_handlers import handle_remove_server

        arguments = {"credential_id": 5, "dry_run": True}
        await handle_remove_server(arguments)
        mock_remove_server.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.credential_handlers.remove_server",
        new_callable=MagicMock,
    )
    async def test_remove_server_real_execution(self, mock_remove_server: MagicMock) -> None:
        """Without dry_run, remove_server must be called."""
        from homelab_mcp.tool_handlers.credential_handlers import handle_remove_server

        mock_remove_server.return_value = "removed"
        arguments = {"credential_id": 5}
        await handle_remove_server(arguments)
        mock_remove_server.assert_called_once()


# ---------------------------------------------------------------------------
# DRY-04: delete_proxmox_vm
# ---------------------------------------------------------------------------


class TestDeleteProxmoxVmDryRun:
    """Dry-run tests for delete_proxmox_vm handler (DRY-04).

    These are RED stubs until Wave 2 modifies handle_delete_proxmox_vm.
    """

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.proxmox_handlers.delete_proxmox_vm",
        new_callable=AsyncMock,
    )
    @patch(
        "homelab_mcp.tool_handlers.proxmox_handlers.get_proxmox_vm_status",
        new_callable=AsyncMock,
    )
    @patch("homelab_mcp.server.get_resource_manager")
    async def test_delete_proxmox_vm_dry_run_returns_preview(
        self,
        mock_get_rm: MagicMock,
        mock_get_status: AsyncMock,
        mock_delete: AsyncMock,
    ) -> None:
        """handle_delete_proxmox_vm with dry_run=True must return mode='dry_run'."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_delete_proxmox_vm

        mock_rm = MagicMock()
        mock_rm.proxmox_session = None
        mock_get_rm.return_value = mock_rm
        mock_get_status.return_value = {"status": "running", "vmid": 100}
        arguments = {"node": "pve", "vmid": 100, "dry_run": True}
        result = await handle_delete_proxmox_vm(arguments)
        assert result.get("mode") == "dry_run"

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.proxmox_handlers.delete_proxmox_vm",
        new_callable=AsyncMock,
    )
    @patch(
        "homelab_mcp.tool_handlers.proxmox_handlers.get_proxmox_vm_status",
        new_callable=AsyncMock,
    )
    @patch("homelab_mcp.server.get_resource_manager")
    async def test_delete_proxmox_vm_dry_run_no_delete(
        self,
        mock_get_rm: MagicMock,
        mock_get_status: AsyncMock,
        mock_delete: AsyncMock,
    ) -> None:
        """delete_proxmox_vm must NOT be called when dry_run=True."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_delete_proxmox_vm

        mock_rm = MagicMock()
        mock_rm.proxmox_session = None
        mock_get_rm.return_value = mock_rm
        mock_get_status.return_value = {"status": "running", "vmid": 100}
        arguments = {"node": "pve", "vmid": 100, "dry_run": True}
        await handle_delete_proxmox_vm(arguments)
        mock_delete.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.proxmox_handlers.delete_proxmox_vm",
        new_callable=AsyncMock,
    )
    @patch("homelab_mcp.server.get_resource_manager")
    async def test_delete_proxmox_vm_real_execution(self, mock_get_rm: MagicMock, mock_delete: AsyncMock) -> None:
        """Without dry_run, delete_proxmox_vm must be called."""
        from homelab_mcp.tool_handlers.proxmox_handlers import handle_delete_proxmox_vm

        mock_rm = MagicMock()
        mock_rm.proxmox_session = None
        mock_get_rm.return_value = mock_rm
        mock_delete.return_value = {"status": "deleted"}
        arguments = {"node": "pve", "vmid": 100}
        await handle_delete_proxmox_vm(arguments)
        mock_delete.assert_called_once()


# ---------------------------------------------------------------------------
# DRY-05: destroy_terraform_service
# ---------------------------------------------------------------------------


class TestDestroyTerraformServiceDryRun:
    """Dry-run tests for destroy_terraform_service handler (DRY-05).

    These are RED stubs until Wave 2 modifies handle_destroy_terraform_service.
    """

    @pytest.mark.asyncio
    async def test_destroy_terraform_dry_run_returns_preview(self) -> None:
        """handle_destroy_terraform_service with dry_run=True must return mode='dry_run'."""
        from homelab_mcp.tool_handlers.service_handlers import (
            handle_destroy_terraform_service,
        )

        with patch("homelab_mcp.tool_handlers.service_handlers.ServiceInstaller") as mock_cls:
            mock_installer = MagicMock()
            mock_cls.return_value = mock_installer
            mock_installer.destroy_terraform_service = AsyncMock(return_value={"status": "destroyed"})
            mock_installer.plan_terraform_service = AsyncMock(
                return_value={"status": "success", "plan_output": "Plan: 0 to add, 0 to change, 1 to destroy."}
            )

            arguments = {"service_name": "my-service", "dry_run": True}
            result = await handle_destroy_terraform_service(arguments)
            assert result.get("mode") == "dry_run"

    @pytest.mark.asyncio
    async def test_destroy_terraform_dry_run_no_destroy(self) -> None:
        """destroy_terraform_service must NOT be called when dry_run=True."""
        from homelab_mcp.tool_handlers.service_handlers import (
            handle_destroy_terraform_service,
        )

        with patch("homelab_mcp.tool_handlers.service_handlers.ServiceInstaller") as mock_cls:
            mock_installer = MagicMock()
            mock_cls.return_value = mock_installer
            mock_installer.destroy_terraform_service = AsyncMock(return_value={"status": "destroyed"})
            mock_installer.plan_terraform_service = AsyncMock(
                return_value={"status": "success", "plan_output": "Plan: 0 to add, 0 to change, 1 to destroy."}
            )

            arguments = {"service_name": "my-service", "dry_run": True}
            await handle_destroy_terraform_service(arguments)
            mock_installer.destroy_terraform_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_destroy_terraform_real_execution(self) -> None:
        """Without dry_run, destroy_terraform_service must be called."""
        from homelab_mcp.tool_handlers.service_handlers import (
            handle_destroy_terraform_service,
        )

        with patch("homelab_mcp.tool_handlers.service_handlers.ServiceInstaller") as mock_cls:
            mock_installer = MagicMock()
            mock_cls.return_value = mock_installer
            mock_installer.destroy_terraform_service = AsyncMock(return_value={"status": "destroyed"})

            arguments = {"service_name": "my-service"}
            await handle_destroy_terraform_service(arguments)
            mock_installer.destroy_terraform_service.assert_called_once()


# ---------------------------------------------------------------------------
# DRY-06: rollback_infrastructure_changes
# ---------------------------------------------------------------------------


class TestRollbackInfrastructureDryRun:
    """Dry-run tests for rollback_infrastructure_changes handler (DRY-06).

    These are RED stubs until Wave 2 modifies handle_rollback_infrastructure_changes.
    """

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.infrastructure_handlers.rollback_infrastructure_to_backup",
        new_callable=AsyncMock,
    )
    async def test_rollback_dry_run_returns_preview(self, mock_rollback: AsyncMock) -> None:
        """handle_rollback_infrastructure_changes with dry_run=True must return mode='dry_run'."""
        from homelab_mcp.tool_handlers.infrastructure_handlers import (
            handle_rollback_infrastructure_changes,
        )

        arguments = {"backup_id": "backup-123", "dry_run": True}
        result = await handle_rollback_infrastructure_changes(arguments)
        assert result.get("mode") == "dry_run"

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.infrastructure_handlers.rollback_infrastructure_to_backup",
        new_callable=AsyncMock,
    )
    async def test_rollback_dry_run_no_mutation(self, mock_rollback: AsyncMock) -> None:
        """rollback_infrastructure_to_backup must NOT be called with validate_only=False when dry_run=True."""
        from homelab_mcp.tool_handlers.infrastructure_handlers import (
            handle_rollback_infrastructure_changes,
        )

        arguments = {"backup_id": "backup-123", "dry_run": True}
        await handle_rollback_infrastructure_changes(arguments)
        for call in mock_rollback.call_args_list:
            kwargs = call.kwargs if call.kwargs else {}
            args = call.args if call.args else ()
            validate_only = kwargs.get("validate_only", args[3] if len(args) > 3 else None)
            assert validate_only is not False, (
                "rollback_infrastructure_to_backup called with validate_only=False during dry-run"
            )

    @pytest.mark.asyncio
    @patch(
        "homelab_mcp.tool_handlers.infrastructure_handlers.rollback_infrastructure_to_backup",
        new_callable=AsyncMock,
    )
    async def test_rollback_real_execution(self, mock_rollback: AsyncMock) -> None:
        """Without dry_run, rollback_infrastructure_to_backup must be called."""
        from homelab_mcp.tool_handlers.infrastructure_handlers import (
            handle_rollback_infrastructure_changes,
        )

        mock_rollback.return_value = "rolled back"
        arguments = {"backup_id": "backup-123"}
        await handle_rollback_infrastructure_changes(arguments)
        mock_rollback.assert_called_once()
