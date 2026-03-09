"""Tests for VM operations module."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.homelab_mcp.vm_operations import (
    VMManager,
    control_vm_state,
    deploy_vm,
    get_vm_logs,
    get_vm_status,
    list_vms_on_device,
    remove_vm,
)


class TestVMManager:
    """Test VMManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VMManager()

    @patch("src.homelab_mcp.vm_operations.NetworkSiteMap")
    def test_get_device_connection_info_found(self, mock_sitemap_class):
        """Test getting connection info for existing device."""
        mock_sitemap = MagicMock()
        mock_sitemap.get_all_devices.return_value = [
            {"id": 1, "hostname": "pi-server", "connection_ip": "192.168.1.100"},
            {"id": 2, "hostname": "mini-pc", "connection_ip": "192.168.1.101"},
        ]
        mock_sitemap_class.return_value = mock_sitemap
        self.manager.sitemap = mock_sitemap

        result = asyncio.run(self.manager.get_device_connection_info(1))

        assert result is not None
        assert result["hostname"] == "192.168.1.100"
        assert result["username"] == "mcp_admin"
        assert result["port"] == 22

    @patch("src.homelab_mcp.vm_operations.NetworkSiteMap")
    def test_get_device_connection_info_not_found(self, mock_sitemap_class):
        """Test getting connection info for non-existent device."""
        mock_sitemap = MagicMock()
        mock_sitemap.get_all_devices.return_value = [{"id": 1, "hostname": "pi-server"}]
        mock_sitemap_class.return_value = mock_sitemap
        self.manager.sitemap = mock_sitemap

        result = asyncio.run(self.manager.get_device_connection_info(999))

        assert result is None


@pytest.mark.asyncio
class TestVMOperations:
    """Test VM operation functions."""

    @patch("src.homelab_mcp.vm_operations.VMManager")
    @patch("src.homelab_mcp.vm_operations.get_vm_provider")
    @patch("src.homelab_mcp.vm_operations.ssh_connect", new_callable=AsyncMock)
    async def test_deploy_vm_success(self, mock_connect, mock_get_provider, mock_manager_class):
        """Test successful VM deployment."""
        # Setup mocks
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(
            return_value={
                "hostname": "192.168.1.100",
                "username": "mcp_admin",
                "port": 22,
            }
        )
        mock_manager_class.return_value = mock_manager

        mock_provider = MagicMock()
        mock_provider.deploy_vm = AsyncMock(
            return_value={
                "status": "success",
                "vm_name": "test-nginx",
                "container_id": "abc123",
            }
        )
        mock_get_provider.return_value = mock_provider

        mock_conn = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn

        # Test deployment
        vm_config = {"image": "nginx:latest", "ports": ["80:80"]}
        result_json = await deploy_vm(1, "docker", "test-nginx", vm_config)
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-nginx"
        assert result["device_id"] == 1
        assert result["platform"] == "docker"

        # Verify calls
        mock_provider.deploy_vm.assert_called_once_with(mock_conn, "test-nginx", vm_config)

    @patch("src.homelab_mcp.vm_operations.VMManager")
    async def test_deploy_vm_device_not_found(self, mock_manager_class):
        """Test VM deployment when device not found."""
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(return_value=None)
        mock_manager_class.return_value = mock_manager

        result_json = await deploy_vm(999, "docker", "test", {})
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert "not found in sitemap" in result["message"]

    @patch("src.homelab_mcp.vm_operations.VMManager")
    @patch("src.homelab_mcp.vm_operations.get_vm_provider")
    @patch("src.homelab_mcp.vm_operations.ssh_connect", new_callable=AsyncMock)
    async def test_control_vm_state_success(self, mock_connect, mock_get_provider, mock_manager_class):
        """Test successful VM state control."""
        # Setup mocks
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(
            return_value={
                "hostname": "192.168.1.100",
                "username": "mcp_admin",
                "port": 22,
            }
        )
        mock_manager_class.return_value = mock_manager

        mock_provider = MagicMock()
        mock_provider.control_vm = AsyncMock(
            return_value={
                "status": "success",
                "operation": "start",
                "vm_name": "test-container",
            }
        )
        mock_get_provider.return_value = mock_provider

        mock_conn = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn

        # Test start action
        result_json = await control_vm_state(1, "docker", "test-container", "start")
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["operation"] == "start"
        assert result["vm_name"] == "test-container"
        assert result["device_id"] == 1
        assert result["platform"] == "docker"

        mock_provider.control_vm.assert_called_once_with(mock_conn, "test-container", "start")

    @patch("src.homelab_mcp.vm_operations.VMManager")
    @patch("src.homelab_mcp.vm_operations.get_vm_provider")
    @patch("src.homelab_mcp.vm_operations.ssh_connect", new_callable=AsyncMock)
    async def test_get_vm_status_success(self, mock_connect, mock_get_provider, mock_manager_class):
        """Test successful VM status retrieval."""
        # Setup mocks
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(
            return_value={
                "hostname": "192.168.1.100",
                "username": "mcp_admin",
                "port": 22,
            }
        )
        mock_manager_class.return_value = mock_manager

        mock_provider = MagicMock()
        mock_provider.get_vm_status = AsyncMock(
            return_value={
                "status": "success",
                "vm_name": "test-container",
                "container_status": "running",
                "pid": 1234,
            }
        )
        mock_get_provider.return_value = mock_provider

        mock_conn = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn

        # Test status retrieval
        result_json = await get_vm_status(1, "docker", "test-container")
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert result["container_status"] == "running"
        assert result["device_id"] == 1
        assert result["platform"] == "docker"

    @patch("src.homelab_mcp.vm_operations.VMManager")
    @patch("src.homelab_mcp.vm_operations.get_vm_provider")
    @patch("src.homelab_mcp.vm_operations.ssh_connect", new_callable=AsyncMock)
    async def test_list_vms_on_device_success(self, mock_connect, mock_get_provider, mock_manager_class):
        """Test successful VM listing on device."""
        # Setup mocks
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(
            return_value={
                "hostname": "192.168.1.100",
                "username": "mcp_admin",
                "port": 22,
            }
        )
        mock_manager_class.return_value = mock_manager

        mock_provider = MagicMock()
        mock_provider.list_vms = AsyncMock(
            return_value={
                "status": "success",
                "containers": [
                    {"name": "nginx", "status": "running"},
                    {"name": "redis", "status": "stopped"},
                ],
            }
        )
        mock_get_provider.return_value = mock_provider

        mock_conn = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn

        # Test VM listing
        result_json = await list_vms_on_device(1, ["docker"])
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["device_id"] == 1
        assert result["total_vms"] == 2
        assert len(result["vms"]) == 2
        assert result["vms"][0]["name"] == "nginx"
        assert result["vms"][0]["platform"] == "docker"

    @patch("src.homelab_mcp.vm_operations.VMManager")
    @patch("src.homelab_mcp.vm_operations.get_vm_provider")
    @patch("src.homelab_mcp.vm_operations.ssh_connect", new_callable=AsyncMock)
    async def test_get_vm_logs_success(self, mock_connect, mock_get_provider, mock_manager_class):
        """Test successful VM log retrieval."""
        # Setup mocks
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(
            return_value={
                "hostname": "192.168.1.100",
                "username": "mcp_admin",
                "port": 22,
            }
        )
        mock_manager_class.return_value = mock_manager

        mock_provider = MagicMock()
        mock_provider.get_vm_logs = AsyncMock(
            return_value={
                "status": "success",
                "vm_name": "test-container",
                "logs": "Starting nginx\\nReady to accept connections",
                "lines_requested": 50,
            }
        )
        mock_get_provider.return_value = mock_provider

        mock_conn = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn

        # Test log retrieval
        result_json = await get_vm_logs(1, "docker", "test-container", 50)
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert result["lines_requested"] == 50
        assert "Starting nginx" in result["logs"]
        assert result["device_id"] == 1
        assert result["platform"] == "docker"

    @patch("src.homelab_mcp.vm_operations.VMManager")
    @patch("src.homelab_mcp.vm_operations.get_vm_provider")
    @patch("src.homelab_mcp.vm_operations.ssh_connect", new_callable=AsyncMock)
    async def test_remove_vm_success(self, mock_connect, mock_get_provider, mock_manager_class):
        """Test successful VM removal."""
        # Setup mocks
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(
            return_value={
                "hostname": "192.168.1.100",
                "username": "mcp_admin",
                "port": 22,
            }
        )
        mock_manager_class.return_value = mock_manager

        mock_provider = MagicMock()
        mock_provider.remove_vm = AsyncMock(
            return_value={
                "status": "success",
                "operation": "remove",
                "vm_name": "test-container",
                "forced": False,
            }
        )
        mock_get_provider.return_value = mock_provider

        mock_conn = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn

        # Test VM removal
        result_json = await remove_vm(1, "docker", "test-container", force=False)
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["operation"] == "remove"
        assert result["vm_name"] == "test-container"
        assert not result["forced"]
        assert result["device_id"] == 1
        assert result["platform"] == "docker"

        mock_provider.remove_vm.assert_called_once_with(mock_conn, "test-container", False)

    @patch("src.homelab_mcp.vm_operations.VMManager")
    @patch("src.homelab_mcp.vm_operations.get_vm_provider")
    async def test_unsupported_platform(self, mock_get_provider, mock_manager_class):
        """Test handling of unsupported platform."""
        # Mock device lookup to succeed
        mock_manager = MagicMock()
        mock_manager.get_device_connection_info = AsyncMock(
            return_value={
                "hostname": "192.168.1.100",
                "username": "mcp_admin",
                "port": 22,
            }
        )
        mock_manager_class.return_value = mock_manager

        # Mock platform provider to fail with unsupported platform
        mock_get_provider.side_effect = ValueError("Unsupported platform: unsupported")

        result_json = await deploy_vm(1, "unsupported", "test", {})
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert "Unsupported platform" in result["message"]
