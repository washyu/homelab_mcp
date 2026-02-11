"""
Tests for Proxmox API integration.

Tests the Proxmox VE API client and all Proxmox management tools.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientError
from aioresponses import aioresponses

from src.homelab_mcp.proxmox_api import (
    ProxmoxAPIClient,
    clone_proxmox_vm,
    create_proxmox_lxc,
    create_proxmox_vm,
    delete_proxmox_vm,
    get_proxmox_client,
    get_proxmox_node_status,
    get_proxmox_vm_status,
    list_proxmox_resources,
    manage_proxmox_vm,
)


class TestProxmoxAPIClient:
    """Test the ProxmoxAPIClient class."""

    def test_client_init_with_password(self):
        """Test client initialization with username/password auth."""
        # GIVEN: Valid credentials
        client = ProxmoxAPIClient(
            host="192.168.1.100",
            port=8006,
            username="root@pam",
            password="secret123",
        )

        # THEN: Client should be configured correctly
        assert client.host == "192.168.1.100"
        assert client.port == 8006
        assert client.base_url == "https://192.168.1.100:8006/api2/json"
        assert client.username == "root@pam"
        assert client.password == "secret123"
        assert client.api_token is None
        assert client._auth_cookie is None

    def test_client_init_with_api_token(self):
        """Test client initialization with API token auth."""
        # GIVEN: API token instead of password
        client = ProxmoxAPIClient(
            host="proxmox.local",
            api_token="root@pam!mytoken=abc123-secret-token",
        )

        # THEN: Client should be configured for token auth
        assert client.host == "proxmox.local"
        assert client.api_token == "root@pam!mytoken=abc123-secret-token"
        assert client.username is None
        assert client.password is None

    def test_client_init_custom_port(self):
        """Test client initialization with custom port."""
        # GIVEN: Non-default port
        client = ProxmoxAPIClient(host="192.168.1.100", port=9443)

        # THEN: URL should use custom port
        assert client.base_url == "https://192.168.1.100:9443/api2/json"

    def test_get_headers_with_api_token(self):
        """Test header generation for API token authentication."""
        # GIVEN: Client with API token
        client = ProxmoxAPIClient(
            host="test.local",
            api_token="root@pam!token=secret",
        )

        # WHEN: Getting headers
        headers = client._get_headers()

        # THEN: Should include Authorization header
        assert "Authorization" in headers
        assert headers["Authorization"] == "PVEAPIToken=root@pam!token=secret"

    def test_get_headers_with_csrf_token(self):
        """Test header generation for cookie-based authentication."""
        # GIVEN: Client with CSRF token (after password auth)
        client = ProxmoxAPIClient(host="test.local")
        client._csrf_token = "csrf-token-123"

        # WHEN: Getting headers
        headers = client._get_headers()

        # THEN: Should include CSRF header
        assert "CSRFPreventionToken" in headers
        assert headers["CSRFPreventionToken"] == "csrf-token-123"

    def test_get_cookies_with_auth_cookie(self):
        """Test cookie generation after authentication."""
        # GIVEN: Client with authentication cookie
        client = ProxmoxAPIClient(host="test.local")
        client._auth_cookie = "PVE-ticket-12345"

        # WHEN: Getting cookies
        cookies = client._get_cookies()

        # THEN: Should include auth cookie
        assert "PVEAuthCookie" in cookies
        assert cookies["PVEAuthCookie"] == "PVE-ticket-12345"


class TestProxmoxAuthentication:
    """Test Proxmox authentication flows."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test successful password authentication."""
        # GIVEN: A client with username/password
        client = ProxmoxAPIClient(
            host="192.168.1.100",
            username="root@pam",
            password="test123",
        )

        # AND: Mock HTTP response for authentication
        with aioresponses() as mocked:
            # Mock the /access/ticket endpoint (authentication)
            mocked.post(
                "https://192.168.1.100:8006/api2/json/access/ticket",
                payload={
                    "data": {
                        "ticket": "PVE:root@pam:12345678::ticket",
                        "CSRFPreventionToken": "12345:csrf-token",
                    }
                },
                status=200,
            )

            # WHEN: Making an authenticated request
            # Note: We need to test _authenticate directly since request() calls it
            import aiohttp

            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                await client._authenticate(session)

            # THEN: Auth cookie and CSRF token should be set
            assert client._auth_cookie == "PVE:root@pam:12345678::ticket"
            assert client._csrf_token == "12345:csrf-token"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(self):
        """Test authentication failure with invalid credentials."""
        # GIVEN: Client with wrong credentials
        client = ProxmoxAPIClient(
            host="192.168.1.100",
            username="root@pam",
            password="wrong-password",
        )

        # AND: Mock HTTP 401 Unauthorized response
        with aioresponses() as mocked:
            mocked.post(
                "https://192.168.1.100:8006/api2/json/access/ticket",
                status=401,
                body="Authentication failure",
            )

            # WHEN/THEN: Authentication should raise an error
            import aiohttp

            connector = aiohttp.TCPConnector(ssl=False)
            with pytest.raises(aiohttp.ClientResponseError):
                async with aiohttp.ClientSession(connector=connector) as session:
                    await client._authenticate(session)

    @pytest.mark.asyncio
    async def test_authenticate_missing_credentials(self):
        """Test authentication without credentials."""
        # GIVEN: Client without username/password
        client = ProxmoxAPIClient(host="192.168.1.100")

        # WHEN/THEN: Should raise ValueError
        import aiohttp

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            with pytest.raises(ValueError, match="Username and password required"):
                await client._authenticate(session)


class TestGetProxmoxClient:
    """Test the get_proxmox_client factory function."""

    @patch.dict(
        os.environ,
        {
            "PROXMOX_HOST": "192.168.1.100",
            "PROXMOX_USER": "root@pam",
            "PROXMOX_PASSWORD": "secret",
        },
    )
    def test_client_from_env_vars(self):
        """Test creating client from environment variables."""
        # WHEN: Creating client without parameters
        client = get_proxmox_client()

        # THEN: Should use environment variables
        assert client.host == "192.168.1.100"
        assert client.username == "root@pam"
        assert client.password == "secret"

    @patch.dict(os.environ, {"PROXMOX_HOST": "192.168.1.100"}, clear=True)
    def test_client_missing_credentials(self):
        """Test client creation without credentials."""
        # WHEN/THEN: Should raise ValueError if no credentials
        with pytest.raises(
            ValueError,
            match="Must provide either PROXMOX_API_TOKEN or PROXMOX_USER\\+PROXMOX_PASSWORD",
        ):
            get_proxmox_client()

    @patch.dict(os.environ, {}, clear=True)
    def test_client_missing_host(self):
        """Test client creation without host."""
        # WHEN/THEN: Should raise ValueError if no host
        with pytest.raises(ValueError, match="Proxmox host must be provided or set in PROXMOX_HOST"):
            get_proxmox_client()

    @patch.dict(
        os.environ,
        {
            "PROXMOX_HOST": "proxmox.local",
            "PROXMOX_API_TOKEN": "root@pam!token=secret",
        },
    )
    def test_client_with_api_token_from_env(self):
        """Test creating client with API token from environment."""
        # WHEN: Creating client
        client = get_proxmox_client()

        # THEN: Should use API token
        assert client.api_token == "root@pam!token=secret"
        assert client.username is None
        assert client.password is None

    def test_client_with_explicit_params_override_env(self):
        """Test that explicit parameters override environment variables."""
        # GIVEN: Environment has one host
        with patch.dict(os.environ, {"PROXMOX_HOST": "env-host.local"}):
            # WHEN: Creating client with explicit host
            client = get_proxmox_client(
                host="explicit-host.local",
                username="admin@pam",
                password="test",
            )

            # THEN: Should use explicit parameters
            assert client.host == "explicit-host.local"


class TestListProxmoxResources:
    """Test list_proxmox_resources function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_list_all_resources_success(self, mock_get_client):
        """Test listing all Proxmox resources."""
        # GIVEN: Mock Proxmox client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        # AND: Mock response data
        mock_resources = [
            {"type": "node", "node": "pve", "status": "online"},
            {"type": "qemu", "vmid": 100, "name": "test-vm"},
            {"type": "lxc", "vmid": 101, "name": "test-container"},
            {"type": "storage", "storage": "local-lvm"},
        ]
        mock_client.get.return_value = mock_resources

        # WHEN: Listing all resources
        result = await list_proxmox_resources()

        # THEN: Should return all resources
        assert result["status"] == "success"
        assert result["total"] == 4
        assert len(result["resources"]) == 4
        assert result["resources"] == mock_resources

        # AND: Should have called the correct endpoint
        mock_client.get.assert_called_once_with("/cluster/resources")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_list_resources_filtered_by_type(self, mock_get_client):
        """Test listing resources filtered by type."""
        # GIVEN: Mock client with mixed resources
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        all_resources = [
            {"type": "node", "node": "pve"},
            {"type": "qemu", "vmid": 100},
            {"type": "lxc", "vmid": 101},
            {"type": "qemu", "vmid": 102},
        ]
        mock_client.get.return_value = all_resources

        # WHEN: Filtering by 'qemu' type
        result = await list_proxmox_resources(resource_type="qemu")

        # THEN: Should only return qemu VMs
        assert result["status"] == "success"
        assert result["total"] == 2
        assert all(r["type"] == "qemu" for r in result["resources"])

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_list_resources_api_error(self, mock_get_client):
        """Test handling of API errors when listing resources."""
        # GIVEN: Mock client that raises an exception
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.side_effect = ClientError("Connection timeout")

        # WHEN: Listing resources
        result = await list_proxmox_resources()

        # THEN: Should return error response
        assert result["status"] == "error"
        assert "Connection timeout" in result["message"]


class TestGetProxmoxNodeStatus:
    """Test get_proxmox_node_status function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_get_node_status_success(self, mock_get_client):
        """Test getting status for a node."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = {
            "boot_info": {},
            "cpu": 50,
            "cpuinfo": {},
            "current-kernel": {},
            "loadavg": [1, 1, 1],
            "memory": {},
            "pveversion": "1.2.3.4.5",
            "rootfs": {},
        }

        result = await get_proxmox_node_status(node="pve")

        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert len(result["data"]) > 0

        mock_client.get.assert_called_once_with("/nodes/pve/status")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_get_status_invalid_node(self, mock_get_client):
        """Test error handling with invalid node name."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.side_effect = ClientError(
            "hostname lookup 'bad_node' failed - failed to get address info for: bad_node: Name or service not known\n"
        )

        result = await get_proxmox_node_status(node="bad_node")

        assert result["status"] == "error"
        assert "bad_node" in result["message"] or "failed to get address" in result["message"]

        mock_client.get.assert_called_once_with(
            "/nodes/bad_node/status",
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_get_node_status_api_error(self, mock_get_client):
        """Test API error handling."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.side_effect = ClientError("Connection timeout")

        # WHEN: Listing resources
        result = await get_proxmox_node_status(node="pve")

        # THEN: Should return error response
        assert result["status"] == "error"
        assert "Connection timeout" in result["message"]


class TestGetProxmoxVMStatus:
    """Test get_proxmox_vm_status function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_get_vm_status_qemu_success(self, mock_get_client):
        """Test getting status of a QEMU VM."""
        # GIVEN: Mock client with VM status
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = {
            "status": "running",
            "cpus": 2,
            "mem": 2048,
            "uptime": 12345,
        }

        # WHEN: Getting VM status
        result = await get_proxmox_vm_status(node="pve", vmid=100, vm_type="qemu")

        # THEN: Should return success with VM details
        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 100
        assert result["type"] == "qemu"
        assert result["data"]["status"] == "running"

        # AND: Should call correct endpoint
        mock_client.get.assert_called_once_with("/nodes/pve/qemu/100/status/current")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_get_vm_status_lxc_success(self, mock_get_client):
        """Test getting status of an LXC container."""
        # GIVEN: Mock client with container status
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = {
            "status": "running",
            "cpus": 1,
            "mem": 512,
        }

        # WHEN: Getting LXC status
        result = await get_proxmox_vm_status(node="pve", vmid=101, vm_type="lxc")

        # THEN: Should return success with container details
        assert result["status"] == "success"
        assert result["type"] == "lxc"
        assert result["vmid"] == 101

        # AND: Should call LXC endpoint
        mock_client.get.assert_called_once_with("/nodes/pve/lxc/101/status/current")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_get_vm_status_vm_not_found(self, mock_get_client):
        """Test getting status of non-existent VM."""
        # GIVEN: Mock client that raises exception
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.side_effect = ClientError("VM 999 does not exist")

        # WHEN: Getting status of non-existent VM
        result = await get_proxmox_vm_status(node="pve", vmid=999)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "does not exist" in result["message"]

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_get_vm_status_default_type_is_qemu(self, mock_get_client):
        """Test that default VM type is qemu."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = {"status": "stopped"}

        # WHEN: Getting VM status without specifying type
        result = await get_proxmox_vm_status(node="pve", vmid=100)

        # THEN: Should default to qemu
        assert result["type"] == "qemu"
        mock_client.get.assert_called_once_with("/nodes/pve/qemu/100/status/current")


class TestManageProxmoxVM:
    """Test manage_proxmox_vm function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_start_vm_success(self, mock_get_client):
        """Test starting a VM successfully."""

        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="start")

        assert result["status"] == "success"
        assert result["action"] == "start"
        assert result["node"] == "pve"
        assert result["vmid"] == 100

        mock_client.post.assert_called_once_with("/nodes/pve/qemu/100/status/start", {})

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_stop_vm_success(self, mock_get_client):
        """Test stopping a VM successfully."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="stop")

        assert result["status"] == "success"
        assert result["action"] == "stop"
        assert result["node"] == "pve"
        assert result["vmid"] == 100

        mock_client.post.assert_called_once_with("/nodes/pve/qemu/100/status/stop", {})

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_shutdown_vm_success(self, mock_get_client):
        """Test shutting down a VM successfully."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="shutdown")

        assert result["status"] == "success"
        assert result["action"] == "shutdown"
        assert result["node"] == "pve"
        assert result["vmid"] == 100

        mock_client.post.assert_called_once_with("/nodes/pve/qemu/100/status/shutdown", {})

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_reboot_vm_success(self, mock_get_client):
        """Test rebooting a VM."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="reboot")

        assert result["status"] == "success"
        assert result["action"] == "reboot"
        assert result["node"] == "pve"
        assert result["vmid"] == 100

        mock_client.post.assert_called_once_with("/nodes/pve/qemu/100/status/reboot", {})

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_reset_vm_success(self, mock_get_client):
        """Test resetting a VM."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="reset")

        assert result["status"] == "success"
        assert result["action"] == "reset"
        assert result["node"] == "pve"
        assert result["vmid"] == 100

        mock_client.post.assert_called_once_with("/nodes/pve/qemu/100/status/reset", {})

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_suspend_vm_success(self, mock_get_client):
        """Test suspending a VM."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="suspend")

        assert result["status"] == "success"
        assert result["action"] == "suspend"
        assert result["node"] == "pve"
        assert result["vmid"] == 100

        mock_client.post.assert_called_once_with("/nodes/pve/qemu/100/status/suspend", {})

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_resume_vm_success(self, mock_get_client):
        """Test resuming a VM."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="resume")

        assert result["status"] == "success"
        assert result["action"] == "resume"
        assert result["node"] == "pve"
        assert result["vmid"] == 100

        mock_client.post.assert_called_once_with("/nodes/pve/qemu/100/status/resume", {})

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_invalid_action(self, mock_get_client):
        """Test invalid action is handled properly."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {}

        result = await manage_proxmox_vm(node="pve", vmid=100, action="restart")

        assert result["status"] == "error"
        assert "Invalid action." in result["message"]

        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_manage_lxc_container(self, mock_get_client):
        """Test managing an LXC container."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        result = await manage_proxmox_vm(node="pve", vmid=101, action="start", vm_type="lxc")

        assert result["status"] == "success"
        assert result["action"] == "start"
        assert result["node"] == "pve"
        assert result["vmid"] == 101

        mock_client.post.assert_called_once_with("/nodes/pve/lxc/101/status/start", {})


class TestCreateProxmoxLXC:
    """Test create_proxmox_lxc function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_lxc_minimal_config(self, mock_get_client):
        """Test LXC creation with minimal configuration."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post_return_value = {"data", "OK"}

        result = await create_proxmox_lxc(node="pve", vmid=999, hostname="test_lxc")
        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 999
        assert "LXC container" in result["message"] and "created successfully" in result["message"]

        mock_client.post.assert_called_once_with(
            "/nodes/pve/lxc",
            {
                "vmid": 999,
                "hostname": "test_lxc",
                "ostemplate": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                "storage": "local-lvm",
                "memory": 512,
                "swap": 512,
                "cores": 1,
                "rootfs": "local-lvm:8",
                "unprivileged": 1,
                "start": 0,
            },
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_lxc_with_password(self, mock_get_client):
        """Test LXC creation with password."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post_return_value = {"data", "OK"}

        result = await create_proxmox_lxc(node="pve", vmid=999, hostname="test_lxc", password="test1!")

        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 999
        assert "LXC container" in result["message"] and "created successfully" in result["message"]

        mock_client.post.assert_called_once_with(
            "/nodes/pve/lxc",
            {
                "vmid": 999,
                "hostname": "test_lxc",
                "ostemplate": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                "storage": "local-lvm",
                "memory": 512,
                "swap": 512,
                "cores": 1,
                "rootfs": "local-lvm:8",
                "unprivileged": 1,
                "start": 0,
                "password": "test1!",
            },
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_lxc_with_ssh_keys(self, mock_get_client):
        """Test LXC creation with SSH keys."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post_return_value = {"data", "OK"}

        result = await create_proxmox_lxc(
            node="pve",
            vmid=999,
            hostname="test_lxc",
            ssh_public_keys="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMpj96/+MCP_ADMIN mcp_admin@homelab_mcp",
        )

        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 999
        assert "LXC container" in result["message"] and "created successfully" in result["message"]

        mock_client.post.assert_called_once_with(
            "/nodes/pve/lxc",
            {
                "vmid": 999,
                "hostname": "test_lxc",
                "ostemplate": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                "storage": "local-lvm",
                "memory": 512,
                "swap": 512,
                "cores": 1,
                "rootfs": "local-lvm:8",
                "unprivileged": 1,
                "start": 0,
                "ssh-public-keys": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMpj96/+MCP_ADMIN mcp_admin@homelab_mcp",
            },
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_lxc_and_start(self, mock_get_client):
        """Test LXC creation with auto-start."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post_return_value = {"data", "OK"}

        result = await create_proxmox_lxc(node="pve", vmid=999, hostname="test_lxc", start=1)
        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 999
        assert "LXC container" in result["message"] and "created successfully" in result["message"]

        mock_client.post.assert_called_once_with(
            "/nodes/pve/lxc",
            {
                "vmid": 999,
                "hostname": "test_lxc",
                "ostemplate": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                "storage": "local-lvm",
                "memory": 512,
                "swap": 512,
                "cores": 1,
                "rootfs": "local-lvm:8",
                "unprivileged": 1,
                "start": 1,
            },
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_lxc_custom_resources(self, mock_get_client):
        """Test LXC creation with custom resources."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post_return_value = {"data", "OK"}

        result = await create_proxmox_lxc(
            node="pve",
            vmid=999,
            hostname="test_lxc",
            start=0,
            memory=2048,
            swap=256,
            cores=8,
        )
        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 999
        assert "LXC container" in result["message"] and "created successfully" in result["message"]

        mock_client.post.assert_called_once_with(
            "/nodes/pve/lxc",
            {
                "vmid": 999,
                "hostname": "test_lxc",
                "ostemplate": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                "storage": "local-lvm",
                "memory": 2048,
                "swap": 256,
                "cores": 8,
                "rootfs": "local-lvm:8",
                "unprivileged": 1,
                "start": 0,
            },
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_lxc_privileged(self, mock_get_client):
        """Test privileged LXC creation."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post_return_value = {"data", "OK"}

        result = await create_proxmox_lxc(node="pve", vmid=999, hostname="test_lxc", unprivileged=0)
        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 999
        assert "LXC container" in result["message"] and "created successfully" in result["message"]

        mock_client.post.assert_called_once_with(
            "/nodes/pve/lxc",
            {
                "vmid": 999,
                "hostname": "test_lxc",
                "ostemplate": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                "storage": "local-lvm",
                "memory": 512,
                "swap": 512,
                "cores": 1,
                "rootfs": "local-lvm:8",
                "unprivileged": 0,
                "start": 0,
            },
        )


class TestCreateProxmoxVM:
    """Test create_proxmox_vm function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_vm_minimal_config(self, mock_get_client):
        """Test VM creation with minimal configuration."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post_return_value = {"data", "OK"}

        result = await create_proxmox_vm(node="pve", vmid=999, name="test_vm")

        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 999
        assert "VM" in result["message"] and "created successfully" in result["message"]

        mock_client.post.assert_called_once_with(
            "/nodes/pve/qemu",
            {
                "vmid": 999,
                "name": "test_vm",
                "memory": 2048,
                "cores": 2,
                "sockets": 1,
                "scsi0": "local-lvm:32",
                "net0": "virtio,bridge=vmbr0",
                "ostype": "l26",
            },
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_vm_with_iso(self, mock_get_client):
        """Test creating VM with ISO attached."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        # WHEN: Creating VM with ISO
        result = await create_proxmox_vm(
            node="pve",
            vmid=100,
            name="test-vm",
            iso="local:iso/debian-12.0.0-amd64-netinst.iso",
        )

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["vmid"] == 100
        assert "created successfully" in result["message"]

        # AND: Should include ISO in config
        call_args = mock_client.post.call_args[0]
        config = call_args[1]
        assert "ide2" in config
        assert "debian-12" in config["ide2"]
        assert "media=cdrom" in config["ide2"]

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    @patch("src.homelab_mcp.proxmox_api.manage_proxmox_vm")
    async def test_create_vm_and_start(self, mock_manage_vm, mock_get_client):
        """Test creating VM with auto-start."""
        # GIVEN: Mock client and manage function
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}
        mock_manage_vm.return_value = {"status": "success"}

        # WHEN: Creating VM with start=True
        result = await create_proxmox_vm(
            node="pve",
            vmid=100,
            name="auto-start-vm",
            start=True,
        )

        # THEN: Should create and start VM
        assert result["status"] == "success"
        mock_client.post.assert_called_once()
        mock_manage_vm.assert_called_once_with("pve", 100, "start", None, "qemu")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_vm_custom_resources(self, mock_get_client):
        """Test creating VM with custom resource allocation."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "OK"}

        # WHEN: Creating VM with custom resources
        result = await create_proxmox_vm(
            node="pve",
            vmid=100,
            name="high-spec-vm",
            memory=8192,
            cores=4,
            sockets=2,
            disk_size=128,
        )

        # THEN: Should succeed
        assert result["status"] == "success"

        # AND: Should use custom resources
        call_args = mock_client.post.call_args[0]
        config = call_args[1]
        assert config["memory"] == 8192
        assert config["cores"] == 4
        assert config["sockets"] == 2
        assert "128" in config["scsi0"]

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_create_vm_api_error(self, mock_get_client):
        """Test VM creation API error handling."""
        # GIVEN: Mock client that fails
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.side_effect = ClientError("Storage 'local-lvm' does not exist")

        # WHEN: Creating VM with invalid storage
        result = await create_proxmox_vm(
            node="pve",
            vmid=100,
            name="failing-vm",
            storage="invalid-storage",
        )

        # THEN: Should return error
        assert result["status"] == "error"
        assert "Failed to create VM" in result["message"]


class TestCloneProxmoxVM:
    """Test clone_proxmox_vm function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_clone_vm_full_clone(self, mock_get_client):
        """Test full clone of a VM."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "UPID:pve:00000000"}

        # WHEN: Cloning VM with full=True (default)
        result = await clone_proxmox_vm(
            node="pve",
            vmid=100,
            new_vmid=200,
            full=True,
        )

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["source_vmid"] == 100
        assert result["new_vmid"] == 200
        assert "cloned" in result["message"]

        # AND: Should use full clone
        mock_client.post.assert_called_once_with(
            "/nodes/pve/qemu/100/clone",
            {"newid": 200, "full": 1},
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_clone_vm_linked_clone(self, mock_get_client):
        """Test linked clone of a VM."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "UPID:pve:00000000"}

        # WHEN: Cloning VM with full=False
        result = await clone_proxmox_vm(
            node="pve",
            vmid=100,
            new_vmid=201,
            full=False,
        )

        # THEN: Should succeed
        assert result["status"] == "success"

        # AND: Should use linked clone
        call_args = mock_client.post.call_args[0]
        config = call_args[1]
        assert config["full"] == 0

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_clone_lxc_container(self, mock_get_client):
        """Test cloning an LXC container."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "UPID:pve:00000000"}

        # WHEN: Cloning LXC container
        result = await clone_proxmox_vm(
            node="pve",
            vmid=101,
            new_vmid=102,
            vm_type="lxc",
        )

        # THEN: Should succeed
        assert result["status"] == "success"

        # AND: Should use LXC endpoint
        mock_client.post.assert_called_once_with(
            "/nodes/pve/lxc/101/clone",
            {"newid": 102, "full": 1},
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    async def test_clone_with_new_name(self, mock_get_client):
        """Test cloning VM with a custom name."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.post.return_value = {"data": "UPID:pve:00000000"}

        # WHEN: Cloning VM with custom name
        result = await clone_proxmox_vm(
            node="pve",
            vmid=100,
            new_vmid=200,
            name="cloned-vm-custom-name",
        )

        # THEN: Should succeed
        assert result["status"] == "success"

        # AND: Should include custom name in config
        call_args = mock_client.post.call_args[0]
        config = call_args[1]
        assert config["name"] == "cloned-vm-custom-name"


class TestDeleteProxmoxVM:
    """Test delete_proxmox_vm function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    @patch("src.homelab_mcp.proxmox_api.manage_proxmox_vm")
    async def test_delete_vm_success(self, mock_manage_vm, mock_get_client):
        """Test successful VM deletion."""
        # GIVEN: Mock client and manage function
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.delete.return_value = {"data": "OK"}
        mock_manage_vm.return_value = {"status": "success"}

        # WHEN: Deleting a VM
        result = await delete_proxmox_vm(node="pve", vmid=100)

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["vmid"] == 100
        assert "deleted successfully" in result["message"]

        # AND: Should stop VM first
        mock_manage_vm.assert_called_once_with("pve", 100, "stop", None, "qemu")

        # AND: Should delete VM
        mock_client.delete.assert_called_once_with("/nodes/pve/qemu/100")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    @patch("src.homelab_mcp.proxmox_api.manage_proxmox_vm")
    async def test_delete_vm_with_purge(self, mock_manage_vm, mock_get_client):
        """Test VM deletion with purge option."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.delete.return_value = {"data": "OK"}
        mock_manage_vm.return_value = {"status": "success"}

        # WHEN: Deleting VM with purge=True
        result = await delete_proxmox_vm(node="pve", vmid=100, purge=True)

        # THEN: Should succeed
        assert result["status"] == "success"

        # AND: Should include purge parameter
        mock_client.delete.assert_called_once_with("/nodes/pve/qemu/100?purge=1")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    @patch("src.homelab_mcp.proxmox_api.manage_proxmox_vm")
    async def test_delete_lxc_success(self, mock_manage_vm, mock_get_client):
        """Test successful LXC container deletion."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.delete.return_value = {"data": "OK"}
        mock_manage_vm.return_value = {"status": "success"}

        # WHEN: Deleting an LXC container
        result = await delete_proxmox_vm(node="pve", vmid=101, vm_type="lxc")

        # THEN: Should succeed
        assert result["status"] == "success"

        # AND: Should use LXC endpoint
        mock_manage_vm.assert_called_once_with("pve", 101, "stop", None, "lxc")
        mock_client.delete.assert_called_once_with("/nodes/pve/lxc/101")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client")
    @patch("src.homelab_mcp.proxmox_api.manage_proxmox_vm")
    async def test_delete_running_vm(self, mock_manage_vm, mock_get_client):
        """Test that running VM is stopped before deletion."""
        # GIVEN: Mock client with running VM
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.delete.return_value = {"data": "OK"}
        # Mock manage_vm to simulate stopping a running VM
        mock_manage_vm.return_value = {"status": "success", "action": "stop"}

        # WHEN: Deleting a running VM
        result = await delete_proxmox_vm(node="pve", vmid=100)

        # THEN: Should stop VM first
        mock_manage_vm.assert_called_once_with("pve", 100, "stop", None, "qemu")

        # AND: Should succeed with deletion
        assert result["status"] == "success"
        mock_client.delete.assert_called_once()
