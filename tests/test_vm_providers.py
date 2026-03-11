"""Tests for VM providers."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.homelab_mcp.vm_providers import get_vm_provider
from src.homelab_mcp.vm_providers.docker_provider import DockerProvider
from src.homelab_mcp.vm_providers.lxd_provider import LXDProvider


def test_get_vm_provider():
    """Test VM provider factory function."""
    # Test Docker provider
    docker_provider = get_vm_provider("docker")
    assert isinstance(docker_provider, DockerProvider)

    # Test LXD provider
    lxd_provider = get_vm_provider("lxd")
    assert isinstance(lxd_provider, LXDProvider)

    # Test case insensitive
    docker_provider2 = get_vm_provider("DOCKER")
    assert isinstance(docker_provider2, DockerProvider)

    # Test unsupported platform
    with pytest.raises(ValueError, match="Unsupported platform"):
        get_vm_provider("unsupported")


class TestDockerProvider:
    """Test Docker provider implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = DockerProvider()
        self.mock_conn = AsyncMock()

    @pytest.mark.asyncio
    async def test_deploy_vm_success(self):
        """Test successful VM deployment."""
        # Mock successful deployment
        self.mock_conn.run = AsyncMock()
        self.mock_conn.run.side_effect = [
            # Check if container exists (should fail)
            MagicMock(exit_status=1, stderr="No such container"),
            # Deploy container
            MagicMock(exit_status=0, stdout="abc123def456", stderr=""),
            # Inspect container
            MagicMock(
                exit_status=0,
                stdout=json.dumps(
                    [
                        {
                            "State": {"Status": "running"},
                            "NetworkSettings": {"Ports": {"80/tcp": [{"HostPort": "8080"}]}},
                            "Config": {"Image": "nginx:latest"},
                        }
                    ]
                ),
                stderr="",
            ),
        ]

        vm_config = {
            "image": "nginx:latest",
            "ports": ["8080:80"],
            "environment": {"ENV": "test"},
        }

        result = await self.provider.deploy_vm(self.mock_conn, "test-nginx", vm_config)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-nginx"
        assert result["container_id"] == "abc123def456"
        assert result["image"] == "nginx:latest"

    @pytest.mark.asyncio
    async def test_deploy_vm_already_exists(self):
        """Test deployment when container already exists."""
        # Mock container already exists
        self.mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="container exists", stderr=""))

        result = await self.provider.deploy_vm(self.mock_conn, "existing-container", {})

        assert result["status"] == "error"
        assert "already exists" in result["error"]

    @pytest.mark.asyncio
    async def test_start_vm_success(self):
        """Test successful VM start."""
        self.mock_conn.run = AsyncMock()
        self.mock_conn.run.side_effect = [
            # Start command
            MagicMock(exit_status=0, stdout="test-container", stderr=""),
            # Status check (via get_vm_status)
            MagicMock(
                exit_status=0,
                stdout=json.dumps([{"State": {"Status": "running", "Running": True, "Pid": 1234}}]),
                stderr="",
            ),
        ]

        result = await self.provider.start_vm(self.mock_conn, "test-container")

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert "started successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_vm_success(self):
        """Test successful VM stop."""
        self.mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="test-container", stderr=""))

        result = await self.provider.stop_vm(self.mock_conn, "test-container")

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert "stopped successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_list_vms_success(self):
        """Test successful VM listing."""
        self.mock_conn.run = AsyncMock(
            return_value=MagicMock(
                exit_status=0,
                stdout="nginx\\tnginx:latest\\tUp 2 hours\\t8080->80/tcp\\nredis\\tredis:6\\tExited (0) 1 hour ago\\t",
                stderr="",
            )
        )

        result = await self.provider.list_vms(self.mock_conn)

        assert result["status"] == "success"
        assert result["platform"] == "docker"
        assert result["total_containers"] == 2
        assert len(result["containers"]) == 2
        assert result["containers"][0]["name"] == "nginx"
        assert result["containers"][0]["image"] == "nginx:latest"

    @pytest.mark.asyncio
    async def test_get_vm_logs_success(self):
        """Test successful log retrieval."""
        self.mock_conn.run = AsyncMock(
            return_value=MagicMock(
                exit_status=0,
                stdout="2024-01-01 12:00:00 Starting nginx\\n2024-01-01 12:00:01 Ready to accept connections",
                stderr="",
            )
        )

        result = await self.provider.get_vm_logs(self.mock_conn, "test-container", 50)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert result["lines_requested"] == 50
        assert "Starting nginx" in result["logs"]

    @pytest.mark.asyncio
    async def test_remove_vm_success(self):
        """Test successful VM removal."""
        self.mock_conn.run = AsyncMock()
        self.mock_conn.run.side_effect = [
            # Stop container
            MagicMock(exit_status=0, stdout="", stderr=""),
            # Remove container
            MagicMock(exit_status=0, stdout="test-container", stderr=""),
        ]

        result = await self.provider.remove_vm(self.mock_conn, "test-container", force=False)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert "removed successfully" in result["message"]
        assert not result["forced"]


class TestLXDProvider:
    """Test LXD provider implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = LXDProvider()
        self.mock_conn = AsyncMock()

    @pytest.mark.asyncio
    async def test_deploy_vm_success(self):
        """Test successful LXD container deployment."""
        self.mock_conn.run = AsyncMock()
        self.mock_conn.run.side_effect = [
            # Check if container exists (should fail)
            MagicMock(exit_status=1, stderr="not found"),
            # Deploy container
            MagicMock(
                exit_status=0,
                stdout="Creating test-ubuntu\\nStarting test-ubuntu",
                stderr="",
            ),
            # Get container info
            MagicMock(
                exit_status=0,
                stdout="Name: test-ubuntu\\nStatus: Running\\nType: container\\nArchitecture: x86_64",
                stderr="",
            ),
        ]

        vm_config = {
            "image": "ubuntu:22.04",
            "type": "container",
            "profiles": ["default"],
        }

        result = await self.provider.deploy_vm(self.mock_conn, "test-ubuntu", vm_config)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-ubuntu"
        assert result["image"] == "ubuntu:22.04"
        assert result["type"] == "container"

    @pytest.mark.asyncio
    async def test_start_vm_success(self):
        """Test successful LXD container start."""
        self.mock_conn.run = AsyncMock()
        self.mock_conn.run.side_effect = [
            # Start command
            MagicMock(exit_status=0, stdout="", stderr=""),
            # Status check
            MagicMock(
                exit_status=0,
                stdout="Name: test-container\\nStatus: Running\\nType: container",
                stderr="",
            ),
        ]

        result = await self.provider.start_vm(self.mock_conn, "test-container")

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert "started successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_list_vms_success(self):
        """Test successful LXD container listing."""
        self.mock_conn.run = AsyncMock(
            return_value=MagicMock(
                exit_status=0,
                stdout="web-server,RUNNING,192.168.1.100,container,0\\ndb-server,STOPPED,,container,1",
                stderr="",
            )
        )

        result = await self.provider.list_vms(self.mock_conn)

        assert result["status"] == "success"
        assert result["platform"] == "lxd"
        assert result["total_containers"] == 2
        assert len(result["containers"]) == 2
        assert result["containers"][0]["name"] == "web-server"
        assert result["containers"][0]["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_get_vm_logs_success(self):
        """Test successful LXD log retrieval."""
        self.mock_conn.run = AsyncMock(
            return_value=MagicMock(
                exit_status=0,
                stdout="Jan 01 12:00:00 container systemd[1]: Started nginx.service\\nJan 01 12:00:01 container nginx[100]: ready",
                stderr="",
            )
        )

        result = await self.provider.get_vm_logs(self.mock_conn, "test-container", 25)

        assert result["status"] == "success"
        assert result["vm_name"] == "test-container"
        assert result["lines_requested"] == 25
        assert result["log_type"] == "journalctl"
        assert "Started nginx.service" in result["logs"]

    @pytest.mark.asyncio
    async def test_control_vm_actions(self):
        """Test VM control actions."""
        # Test restart
        self.mock_conn.run = AsyncMock()
        self.mock_conn.run.side_effect = [
            # Restart command
            MagicMock(exit_status=0, stdout="", stderr=""),
            # Status check
            MagicMock(exit_status=0, stdout="Name: test\\nStatus: Running", stderr=""),
        ]

        result = await self.provider.restart_vm(self.mock_conn, "test")

        assert result["status"] == "success"
        assert result["operation"] == "restart"
        assert result["vm_name"] == "test"


class TestVMProviderBase:
    """Test VM provider base class functionality."""

    @pytest.mark.asyncio
    async def test_control_vm_dispatcher(self):
        """Test the control_vm method dispatcher."""
        provider = DockerProvider()
        mock_conn = AsyncMock()

        # Mock successful start
        mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="container", stderr=""))

        # Test start action
        with patch.object(provider, "get_vm_status") as mock_status:
            mock_status.return_value = {"status": "running"}
            result = await provider.control_vm(mock_conn, "test", "start")
            assert result["status"] == "success"
            assert result["operation"] == "start"

        # Test invalid action
        result = await provider.control_vm(mock_conn, "test", "invalid")
        assert result["status"] == "error"
        assert "Unknown action" in result["message"]

    def test_format_error_with_exception_has_required_fields(self):
        """Test _format_error with an Exception returns error, error_type, and detail fields."""
        provider = DockerProvider()
        exc = ValueError("test error")
        result = provider._format_error("deploy", "my-vm", exc)

        assert result["status"] == "error"
        assert result["operation"] == "deploy"
        assert result["vm_name"] == "my-vm"
        assert "error" in result
        assert "error_type" in result
        assert "detail" in result

    def test_format_error_exception_type_name(self):
        """Test _format_error uses the actual exception class name for error_type."""
        provider = DockerProvider()
        exc = TimeoutError("connection timed out")
        result = provider._format_error("list", "my-vm", exc)

        assert result["error_type"] == "TimeoutError"

    def test_format_error_with_string_has_required_fields(self):
        """Test _format_error with string input returns error, error_type, and detail fields (backward compat)."""
        provider = DockerProvider()
        result = provider._format_error("deploy", "my-vm", "Container already exists")

        assert result["status"] == "error"
        assert "error" in result
        assert "error_type" in result
        assert "detail" in result
        assert result["error_type"] == "Error"

    def test_format_error_detail_uses_sanitize_error(self):
        """Test _format_error detail field uses sanitize_error not raw repr."""
        provider = DockerProvider()
        exc = ValueError("connection failed password=secret123")
        result = provider._format_error("connect", "my-vm", exc)

        # detail should have credentials redacted
        assert "secret123" not in result["detail"]
        assert "[REDACTED]" in result["detail"]

    def test_error_result_has_required_fields(self):
        """Test that all error results from _format_error have the 3 required fields."""
        provider = DockerProvider()

        # With exception
        exc_result = provider._format_error("op", "vm", RuntimeError("oops"))
        assert all(k in exc_result for k in ("error", "error_type", "detail"))

        # With string
        str_result = provider._format_error("op", "vm", "plain string error")
        assert all(k in str_result for k in ("error", "error_type", "detail"))


class TestDockerProviderErrorPaths:
    """Test DockerProvider exception handling in list_vms and other paths."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = DockerProvider()
        self.mock_conn = AsyncMock()

    @pytest.mark.asyncio
    async def test_list_vms_exception_has_error_type_and_detail(self):
        """Test DockerProvider.list_vms exception path includes error_type and detail fields.

        Mocks _run_command directly because _run_command catches conn.run exceptions
        internally, so the outer except in list_vms is only reachable if _run_command
        itself raises (e.g. from json.JSONDecodeError or similar non-connection errors).
        """
        with patch.object(self.provider, "_run_command", new_callable=AsyncMock) as mock_run_cmd:
            mock_run_cmd.side_effect = RuntimeError("Docker daemon not running")
            result = await self.provider.list_vms(self.mock_conn)

        assert result["status"] == "error"
        assert result["platform"] == "docker"
        assert "error" in result
        assert "error_type" in result
        assert "detail" in result
        assert result["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_deploy_vm_exception_has_error_type_and_detail(self):
        """Test DockerProvider.deploy_vm exception path includes error_type and detail fields."""
        with patch.object(self.provider, "_run_command", new_callable=AsyncMock) as mock_run_cmd:
            mock_run_cmd.side_effect = ConnectionError("SSH connection lost")
            result = await self.provider.deploy_vm(self.mock_conn, "my-container", {})

        assert result["status"] == "error"
        assert "error_type" in result
        assert "detail" in result
        assert result["error_type"] == "ConnectionError"


class TestLXDProviderErrorPaths:
    """Test LXDProvider exception handling in list_vms and other paths."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = LXDProvider()
        self.mock_conn = AsyncMock()

    @pytest.mark.asyncio
    async def test_list_vms_exception_has_error_type_and_detail(self):
        """Test LXDProvider.list_vms exception path includes error_type and detail fields.

        Mocks _run_command directly because _run_command catches conn.run exceptions
        internally, so the outer except in list_vms is only reachable if _run_command
        itself raises (e.g. from parsing errors or other non-connection errors).
        """
        with patch.object(self.provider, "_run_command", new_callable=AsyncMock) as mock_run_cmd:
            mock_run_cmd.side_effect = RuntimeError("LXD socket not available")
            result = await self.provider.list_vms(self.mock_conn)

        assert result["status"] == "error"
        assert result["platform"] == "lxd"
        assert "error" in result
        assert "error_type" in result
        assert "detail" in result
        assert result["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_deploy_vm_exception_has_error_type_and_detail(self):
        """Test LXDProvider.deploy_vm exception path includes error_type and detail fields."""
        with patch.object(self.provider, "_run_command", new_callable=AsyncMock) as mock_run_cmd:
            mock_run_cmd.side_effect = OSError("Permission denied")
            result = await self.provider.deploy_vm(self.mock_conn, "my-container", {})

        assert result["status"] == "error"
        assert "error_type" in result
        assert "detail" in result
        assert result["error_type"] == "OSError"
