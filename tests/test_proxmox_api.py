"""
Tests for Proxmox API integration.

Tests the Proxmox VE API client and all Proxmox management tools.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

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
    get_proxmox_vm_config,
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
    """Test the get_proxmox_client factory function.

    All tests are async after Plan 03 converted get_proxmox_client to async def.
    Tests that supply explicit username+password or api_token bypass the resolver
    (SC-5 back-compat) so no resolver mock is needed for those paths.
    """

    @pytest.mark.asyncio
    @patch.dict(
        os.environ,
        {
            "PROXMOX_HOST": "192.168.1.100",
            "PROXMOX_USER": "root@pam",
            "PROXMOX_PASSWORD": "secret",
        },
    )
    async def test_client_from_env_vars(self):
        """Test creating client from environment variables (explicit auth via env bypasses resolver)."""
        # WHEN: Creating client without parameters (env vars supply host+auth → resolver bypassed)
        client = await get_proxmox_client()

        # THEN: Should use environment variables
        assert client.host == "192.168.1.100"
        assert client.username == "root@pam"
        assert client.password == "secret"

    @pytest.mark.asyncio
    @patch(
        "src.homelab_mcp.proxmox_api.resolve_proxmox_credentials",
        new_callable=AsyncMock,
    )
    @patch.dict(os.environ, {"PROXMOX_HOST": "192.168.1.100"}, clear=True)
    async def test_client_missing_credentials(self, mock_resolver):
        """Test client creation with host but no auth — resolver is called, raises on miss."""
        from src.homelab_mcp.ssh_tools import CredentialNotFoundError

        mock_resolver.side_effect = CredentialNotFoundError("No credentials for 192.168.1.100")
        # WHEN/THEN: Should raise CredentialNotFoundError (resolver finds nothing)
        with pytest.raises(CredentialNotFoundError):
            await get_proxmox_client()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=True)
    async def test_client_missing_host(self):
        """Test client creation without host."""
        # WHEN/THEN: Should raise ValueError if no host (resolver not called — no host to resolve)
        with pytest.raises(ValueError, match="Proxmox host must be provided or set in PROXMOX_HOST"):
            await get_proxmox_client()

    @pytest.mark.asyncio
    @patch.dict(
        os.environ,
        {
            "PROXMOX_HOST": "proxmox.local",
            "PROXMOX_API_TOKEN": "root@pam!token=secret",
        },
    )
    async def test_client_with_api_token_from_env(self):
        """Test creating client with API token from environment (explicit token bypasses resolver)."""
        # WHEN: Creating client
        client = await get_proxmox_client()

        # THEN: Should use API token
        assert client.api_token == "root@pam!token=secret"
        assert client.username is None
        assert client.password is None

    @pytest.mark.asyncio
    async def test_client_with_explicit_params_override_env(self):
        """Test that explicit parameters override environment variables."""
        # GIVEN: Environment has one host
        with patch.dict(os.environ, {"PROXMOX_HOST": "env-host.local"}):
            # WHEN: Creating client with explicit host+auth (bypasses resolver)
            client = await get_proxmox_client(
                host="explicit-host.local",
                username="admin@pam",
                password="test",
            )

            # THEN: Should use explicit parameters
            assert client.host == "explicit-host.local"


class TestListProxmoxResources:
    """Test list_proxmox_resources function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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


class TestGetProxmoxVMConfig:
    """Test get_proxmox_vm_config function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
    async def test_get_vm_config_qemu_success(self, mock_get_client):
        """Test getting config of a QEMU VM."""
        # GIVEN: Mock client with VM config
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = {
            "cores": 2,
            "memory": 2048,
            "sockets": 1,
            "net0": "virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0",
        }

        # WHEN: Getting VM config
        result = await get_proxmox_vm_config(node="pve", vmid=100, vm_type="qemu")

        # THEN: Should return success with config fields
        assert result["status"] == "success"
        assert result["node"] == "pve"
        assert result["vmid"] == 100
        assert result["type"] == "qemu"
        assert result["data"]["cores"] == 2
        assert result["data"]["memory"] == 2048

        # AND: Should call the /config endpoint (not /status/current)
        mock_client.get.assert_called_once_with("/nodes/pve/qemu/100/config")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
    async def test_get_vm_config_lxc_success(self, mock_get_client):
        """Test getting config of an LXC container."""
        # GIVEN: Mock client with container config
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = {
            "cores": 1,
            "memory": 512,
            "hostname": "mycontainer",
        }

        # WHEN: Getting LXC config
        result = await get_proxmox_vm_config(node="pve", vmid=101, vm_type="lxc")

        # THEN: Should return success with container config
        assert result["status"] == "success"
        assert result["type"] == "lxc"
        assert result["vmid"] == 101

        # AND: Should call LXC config endpoint
        mock_client.get.assert_called_once_with("/nodes/pve/lxc/101/config")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
    async def test_get_vm_config_vm_not_found(self, mock_get_client):
        """Test getting config of non-existent VM returns error."""
        # GIVEN: Mock client that raises exception
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.side_effect = ClientError("VM 999 does not exist")

        # WHEN: Getting config of non-existent VM
        result = await get_proxmox_vm_config(node="pve", vmid=999)

        # THEN: Should return error with message
        assert result["status"] == "error"
        assert "Failed to get VM config" in result["message"]

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
    async def test_get_vm_config_default_type_is_qemu(self, mock_get_client):
        """Test that default VM type is qemu."""
        # GIVEN: Mock client
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = {"cores": 4, "memory": 4096}

        # WHEN: Getting VM config without specifying type
        result = await get_proxmox_vm_config(node="pve", vmid=100)

        # THEN: Should default to qemu
        assert result["type"] == "qemu"
        mock_client.get.assert_called_once_with("/nodes/pve/qemu/100/config")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
    async def test_get_vm_config_value_error_returns_error(self, mock_get_client):
        """Test that ValueError is also caught and returned as error."""
        # GIVEN: Mock client that raises ValueError
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.get.side_effect = ValueError("Invalid API response: {}")

        # WHEN: Getting VM config
        result = await get_proxmox_vm_config(node="pve", vmid=100)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "Failed to get VM config" in result["message"]


class TestManageProxmoxVM:
    """Test manage_proxmox_vm function."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
        mock_manage_vm.assert_called_once_with("pve", 100, "start", None, "qemu", session=None)

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
        mock_manage_vm.assert_called_once_with("pve", 100, "stop", None, "qemu", session=None)

        # AND: Should delete VM
        mock_client.delete.assert_called_once_with("/nodes/pve/qemu/100")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
        mock_manage_vm.assert_called_once_with("pve", 101, "stop", None, "lxc", session=None)
        mock_client.delete.assert_called_once_with("/nodes/pve/lxc/101")

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
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
        mock_manage_vm.assert_called_once_with("pve", 100, "stop", None, "qemu", session=None)

        # AND: Should succeed with deletion
        assert result["status"] == "success"
        mock_client.delete.assert_called_once()


class AsyncContextManagerMock:
    """Helper to create an async context manager from a return value."""

    def __init__(self, return_value: AsyncMock) -> None:
        self._return_value = return_value

    async def __aenter__(self) -> AsyncMock:
        return self._return_value

    async def __aexit__(self, *args: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Phase 34 Plan 03: async get_proxmox_client wiring tests (D-10, D-12, SC-5)
# ---------------------------------------------------------------------------


class TestGetProxmoxClientAsync:
    """Tests for async get_proxmox_client after Plan 03 wiring (D-10, D-12, SC-5)."""

    @pytest.mark.asyncio
    @patch(
        "src.homelab_mcp.proxmox_api.resolve_proxmox_credentials",
        new_callable=AsyncMock,
    )
    async def test_get_proxmox_client_async_explicit_api_token_bypasses_resolver(
        self,
        mock_resolver: AsyncMock,
    ) -> None:
        """SC-5: explicit api_token bypasses the resolver entirely."""
        mock_resolver.side_effect = AssertionError("resolver must NOT be called when api_token is explicit")

        client = await get_proxmox_client(host="pve1", api_token="root@pam!t=s")

        assert isinstance(client, ProxmoxAPIClient)
        assert client.api_token == "root@pam!t=s"
        mock_resolver.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "src.homelab_mcp.proxmox_api.resolve_proxmox_credentials",
        new_callable=AsyncMock,
    )
    async def test_get_proxmox_client_async_explicit_username_password_bypasses_resolver(
        self,
        mock_resolver: AsyncMock,
    ) -> None:
        """SC-5: explicit username+password bypasses the resolver entirely."""
        mock_resolver.side_effect = AssertionError("resolver must NOT be called when username+password is explicit")

        client = await get_proxmox_client(host="pve1", username="root@pam", password="pw")

        assert isinstance(client, ProxmoxAPIClient)
        assert client.username == "root@pam"
        assert client.password == "pw"
        mock_resolver.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "src.homelab_mcp.proxmox_api.resolve_proxmox_credentials",
        new_callable=AsyncMock,
    )
    async def test_get_proxmox_client_async_delegates_to_resolver_when_host_only(
        self,
        mock_resolver: AsyncMock,
    ) -> None:
        """D-10: when only host is provided, get_proxmox_client awaits resolve_proxmox_credentials."""
        mock_resolver.return_value = ("root@pam!tok=uuid", "cluster", "homelab-prod")

        client = await get_proxmox_client(host="pve1")

        assert isinstance(client, ProxmoxAPIClient)
        assert client.api_token == "root@pam!tok=uuid"
        mock_resolver.assert_awaited_once_with("pve1", session=None)

    @pytest.mark.asyncio
    @patch(
        "src.homelab_mcp.proxmox_api.resolve_proxmox_credentials",
        new_callable=AsyncMock,
    )
    async def test_get_proxmox_client_no_host_raises_proxmox_host_valueerror(
        self,
        mock_resolver: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """D-12: when no host can be determined, ValueError names PROXMOX_HOST env var."""
        monkeypatch.delenv("PROXMOX_HOST", raising=False)
        monkeypatch.delenv("PROXMOX_API_TOKEN", raising=False)
        monkeypatch.delenv("PROXMOX_USER", raising=False)
        monkeypatch.delenv("PROXMOX_PASSWORD", raising=False)

        with pytest.raises(ValueError) as exc_info:
            await get_proxmox_client()

        assert "PROXMOX_HOST" in str(exc_info.value)
        mock_resolver.assert_not_called()


class TestProxmoxSharedSession:
    """Test ProxmoxAPIClient shared session support."""

    def test_client_init_with_shared_session(self):
        """Test client initialization with an externally-provided session."""
        # GIVEN: An external aiohttp.ClientSession mock
        mock_session = AsyncMock()

        # WHEN: Creating a client with a shared session
        client = ProxmoxAPIClient(
            host="192.168.1.100",
            api_token="root@pam!token=secret",
            session=mock_session,
        )

        # THEN: The shared session should be stored
        assert client._shared_session is mock_session

    def test_client_init_without_shared_session(self):
        """Test client initialization without a shared session (backward compat)."""
        # WHEN: Creating a client without session parameter
        client = ProxmoxAPIClient(
            host="192.168.1.100",
            api_token="root@pam!token=secret",
        )

        # THEN: No shared session should be set
        assert client._shared_session is None

    @pytest.mark.asyncio
    async def test_request_uses_shared_session(self):
        """Test that request() uses shared session instead of creating a new one."""
        # GIVEN: A client with a shared session
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = AsyncMock(return_value={"data": {"nodes": []}})

        # Create a proper async context manager for session.request()
        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=AsyncContextManagerMock(mock_response))

        client = ProxmoxAPIClient(
            host="192.168.1.100",
            api_token="root@pam!token=secret",
            session=mock_session,
        )

        # WHEN: Making a request
        with (
            patch("src.homelab_mcp.proxmox_api.aiohttp.ClientSession") as mock_session_cls,
            patch("src.homelab_mcp.proxmox_api.aiohttp.TCPConnector"),
        ):
            await client.request("GET", "/nodes")

            # THEN: No new ClientSession should be created
            mock_session_cls.assert_not_called()

        # AND: The shared session should have been used
        mock_session.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_falls_back_to_per_request_session(self):
        """Test that request() creates a session when no shared session is provided."""
        # GIVEN: A client WITHOUT a shared session
        client = ProxmoxAPIClient(
            host="192.168.1.100",
            api_token="root@pam!token=secret",
        )

        # WHEN: Making a request with aioresponses mocking
        with aioresponses() as mocked:
            mocked.get(
                "https://192.168.1.100:8006/api2/json/nodes",
                payload={"data": [{"node": "pve"}]},
            )
            result = await client.request("GET", "/nodes")

        # THEN: Request should succeed (per-request session was created)
        assert result == [{"node": "pve"}]

    @pytest.mark.asyncio
    async def test_shared_session_auth_works(self):
        """Test that authentication still works with a shared session."""
        # GIVEN: A client with shared session and password auth
        mock_auth_response = AsyncMock()
        mock_auth_response.raise_for_status = lambda: None
        mock_auth_response.json = AsyncMock(
            return_value={"data": {"ticket": "PVE-ticket", "CSRFPreventionToken": "csrf-123"}}
        )

        mock_data_response = AsyncMock()
        mock_data_response.raise_for_status = lambda: None
        mock_data_response.json = AsyncMock(return_value={"data": {"nodes": []}})

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=AsyncContextManagerMock(mock_auth_response))
        mock_session.request = MagicMock(return_value=AsyncContextManagerMock(mock_data_response))

        client = ProxmoxAPIClient(
            host="192.168.1.100",
            username="root@pam",
            password="secret",
            session=mock_session,
        )

        # WHEN: Making a request that requires authentication
        await client.request("GET", "/nodes")

        # THEN: Auth should have been called on the shared session
        assert client._auth_cookie == "PVE-ticket"
        assert client._csrf_token == "csrf-123"

    @pytest.mark.asyncio
    async def test_get_proxmox_client_with_session(self):
        """Test get_proxmox_client() accepts and passes through a session."""
        # GIVEN: An external session
        mock_session = AsyncMock()

        # WHEN: Creating client via factory with session (explicit api_token bypasses resolver)
        client = await get_proxmox_client(
            host="192.168.1.100",
            api_token="root@pam!token=secret",
            session=mock_session,
        )

        # THEN: Client should have the shared session
        assert client._shared_session is mock_session


class TestProxmoxSSLVerification:
    """Test SSL verification defaults and configuration."""

    def test_ssl_verify_default_true(self):
        """Test that ProxmoxAPIClient defaults to verify_ssl=True."""
        # GIVEN: No explicit verify_ssl parameter
        client = ProxmoxAPIClient(host="pve")

        # THEN: verify_ssl should default to True
        assert client.verify_ssl is True

    def test_config_ssl_defaults(self):
        """Test MCPConfig has proxmox_verify_ssl=True and proxmox_ca_cert=None by default."""
        from src.homelab_mcp.config import MCPConfig

        # GIVEN: No environment variables set for Proxmox SSL
        with patch.dict(os.environ, {}, clear=False):
            # Remove any existing Proxmox SSL env vars
            env = os.environ.copy()
            env.pop("PROXMOX_VERIFY_SSL", None)
            env.pop("PROXMOX_CA_CERT", None)
            with patch.dict(os.environ, env, clear=True):
                config = MCPConfig()

                # THEN: SSL defaults should be secure
                assert config.proxmox_verify_ssl is True
                assert config.proxmox_ca_cert is None

    def test_config_create_ssl_context_default_returns_true(self):
        """Test create_ssl_context() returns True when verify_ssl=True and no CA cert."""
        from src.homelab_mcp.config import MCPConfig

        with patch.dict(os.environ, {}, clear=False):
            env = os.environ.copy()
            env.pop("PROXMOX_VERIFY_SSL", None)
            env.pop("PROXMOX_CA_CERT", None)
            with patch.dict(os.environ, env, clear=True):
                config = MCPConfig()
                result = config.create_ssl_context()

                # THEN: Should return True (use system CA)
                assert result is True

    def test_config_create_ssl_context_with_ca_cert(self):
        """Test create_ssl_context() returns SSLContext when CA cert is set."""
        import ssl

        from src.homelab_mcp.config import MCPConfig

        with patch.dict(
            os.environ,
            {"PROXMOX_CA_CERT": "/path/to/cert.pem"},
            clear=False,
        ):
            config = MCPConfig()

            # Mock ssl.create_default_context to avoid needing a real cert
            mock_ctx = MagicMock(spec=ssl.SSLContext)
            with patch("ssl.create_default_context", return_value=mock_ctx) as mock_create:
                result = config.create_ssl_context()

                # THEN: Should return an SSLContext
                mock_create.assert_called_once_with(cafile="/path/to/cert.pem")
                assert result is mock_ctx

    def test_config_create_ssl_context_verify_false(self):
        """Test create_ssl_context() returns False when verify_ssl=False."""
        from src.homelab_mcp.config import MCPConfig

        with patch.dict(
            os.environ,
            {"PROXMOX_VERIFY_SSL": "false"},
            clear=False,
        ):
            config = MCPConfig()
            result = config.create_ssl_context()

            # THEN: Should return False (disable verification)
            assert result is False

    @pytest.mark.asyncio
    async def test_ssl_verify_false_override_via_env(self):
        """Test get_proxmox_client with PROXMOX_VERIFY_SSL=false sets verify_ssl=False."""
        with patch.dict(
            os.environ,
            {
                "PROXMOX_HOST": "pve.local",
                "PROXMOX_VERIFY_SSL": "false",
                "PROXMOX_API_TOKEN": "root@pam!token=secret",
            },
        ):
            # explicit api_token in env → resolver bypassed
            client = await get_proxmox_client()

            # THEN: verify_ssl should be False
            assert client.verify_ssl is False

    @pytest.mark.asyncio
    async def test_get_proxmox_client_default_verify_ssl_true(self):
        """Test get_proxmox_client defaults to verify_ssl=True."""
        with patch.dict(
            os.environ,
            {
                "PROXMOX_HOST": "pve.local",
                "PROXMOX_API_TOKEN": "root@pam!token=secret",
            },
            clear=False,
        ):
            # Remove PROXMOX_VERIFY_SSL if set
            env = os.environ.copy()
            env.pop("PROXMOX_VERIFY_SSL", None)
            with patch.dict(os.environ, env, clear=True):
                # Also ensure our test vars are present
                os.environ["PROXMOX_HOST"] = "pve.local"
                os.environ["PROXMOX_API_TOKEN"] = "root@pam!token=secret"
                # explicit api_token in env → resolver bypassed
                client = await get_proxmox_client()

                # THEN: verify_ssl should default to True
                assert client.verify_ssl is True


class TestHandlerSessionThreading:
    """Test that Proxmox handlers pass the shared session to API functions.

    Since get_resource_manager is imported inside each handler function
    (to avoid circular imports), we patch it at its source in homelab_mcp.server
    and patch the proxmox_api functions at the module level in proxmox_handlers.
    """

    @pytest.mark.asyncio
    async def test_handler_uses_shared_session_list_resources(self):
        """handle_list_proxmox_resources passes session=rm.proxmox_session."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_list_proxmox_resources

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_list = AsyncMock(return_value={"status": "success", "resources": [], "total": 0})

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "list_proxmox_resources", mock_list),
        ):
            await handle_list_proxmox_resources({})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs.get("session") is mock_session, (
            f"Expected session={mock_session!r} in call, got {call_kwargs}"
        )

    @pytest.mark.asyncio
    async def test_handler_uses_shared_session_node_status(self):
        """handle_get_proxmox_node_status passes session=rm.proxmox_session."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_get_proxmox_node_status

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_fn = AsyncMock(return_value={"status": "success", "node": "pve", "data": {}})

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "get_proxmox_node_status", mock_fn),
        ):
            await handle_get_proxmox_node_status({"node": "pve"})

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args
        assert call_kwargs.kwargs.get("session") is mock_session, (
            f"Expected session={mock_session!r} in call, got {call_kwargs}"
        )

    @pytest.mark.asyncio
    async def test_handler_uses_shared_session_manage_vm(self):
        """handle_manage_proxmox_vm passes session=rm.proxmox_session."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_manage_proxmox_vm

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_fn = AsyncMock(
            return_value={
                "status": "success",
                "node": "pve",
                "vmid": 100,
                "action": "start",
                "data": {},
            }
        )

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "manage_proxmox_vm", mock_fn),
        ):
            await handle_manage_proxmox_vm({"node": "pve", "vmid": 100, "action": "start"})

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args
        assert call_kwargs.kwargs.get("session") is mock_session, (
            f"Expected session={mock_session!r} in call, got {call_kwargs}"
        )

    @pytest.mark.asyncio
    async def test_handler_uses_shared_session_delete_vm(self):
        """handle_delete_proxmox_vm passes session=rm.proxmox_session."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_delete_proxmox_vm

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_fn = AsyncMock(
            return_value={
                "status": "success",
                "node": "pve",
                "vmid": 100,
                "message": "deleted",
                "data": {},
            }
        )

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "delete_proxmox_vm", mock_fn),
        ):
            await handle_delete_proxmox_vm({"node": "pve", "vmid": 100})

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args
        assert call_kwargs.kwargs.get("session") is mock_session, (
            f"Expected session={mock_session!r} in call, got {call_kwargs}"
        )

    @pytest.mark.asyncio
    async def test_handle_create_proxmox_vm_passes_explicit_params(self):
        """handle_create_proxmox_vm passes explicit sockets/cdrom/net0/ostype to create_proxmox_vm."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_vm

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_rm.db_adapter = MagicMock()
        mock_fn = AsyncMock(return_value={"status": "success", "node": "pve", "vmid": 100, "message": "created"})

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "create_proxmox_vm", mock_fn),
        ):
            await handle_create_proxmox_vm(
                {
                    "node": "pve",
                    "vmid": 100,
                    "name": "test-vm",
                    "sockets": 2,
                    "cdrom": "local:iso/debian.iso",
                    "net0": "virtio,bridge=vmbr1",
                    "ostype": "win10",
                }
            )

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs.get("sockets") == 2, f"Expected sockets=2, got {call_kwargs.get('sockets')}"
        assert call_kwargs.get("cdrom") == "local:iso/debian.iso", (
            f"Expected cdrom='local:iso/debian.iso', got {call_kwargs.get('cdrom')}"
        )
        assert call_kwargs.get("net0") == "virtio,bridge=vmbr1", (
            f"Expected net0='virtio,bridge=vmbr1', got {call_kwargs.get('net0')}"
        )
        assert call_kwargs.get("ostype") == "win10", f"Expected ostype='win10', got {call_kwargs.get('ostype')}"

    @pytest.mark.asyncio
    async def test_handle_create_proxmox_vm_uses_defaults(self):
        """handle_create_proxmox_vm uses correct defaults when optional params omitted."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_vm

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_rm.db_adapter = MagicMock()
        mock_fn = AsyncMock(return_value={"status": "success", "node": "pve", "vmid": 100, "message": "created"})

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "create_proxmox_vm", mock_fn),
        ):
            await handle_create_proxmox_vm({"node": "pve", "vmid": 100, "name": "test-vm"})

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs.get("sockets") == 1, f"Expected sockets=1, got {call_kwargs.get('sockets')}"
        assert call_kwargs.get("cdrom") is None, f"Expected cdrom=None, got {call_kwargs.get('cdrom')}"
        assert call_kwargs.get("net0") == "virtio,bridge=vmbr0", (
            f"Expected net0='virtio,bridge=vmbr0', got {call_kwargs.get('net0')}"
        )
        assert call_kwargs.get("ostype") == "l26", f"Expected ostype='l26', got {call_kwargs.get('ostype')}"

    @pytest.mark.asyncio
    async def test_handle_create_proxmox_lxc_passes_explicit_params(self):
        """handle_create_proxmox_lxc passes explicit swap/ssh_public_keys/unprivileged to create_proxmox_lxc."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_lxc

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_rm.db_adapter = MagicMock()
        mock_fn = AsyncMock(return_value={"status": "success", "node": "pve", "vmid": 200, "message": "created"})

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "create_proxmox_lxc", mock_fn),
        ):
            await handle_create_proxmox_lxc(
                {
                    "node": "pve",
                    "vmid": 200,
                    "hostname": "test-ct",
                    "swap": 1024,
                    "ssh_public_keys": "ssh-ed25519 AAAA... user@host",
                    "unprivileged": False,
                }
            )

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs.get("swap") == 1024, f"Expected swap=1024, got {call_kwargs.get('swap')}"
        assert call_kwargs.get("ssh_public_keys") == "ssh-ed25519 AAAA... user@host", (
            f"Expected ssh_public_keys='ssh-ed25519 AAAA... user@host', got {call_kwargs.get('ssh_public_keys')}"
        )
        assert call_kwargs.get("unprivileged") is False, (
            f"Expected unprivileged=False, got {call_kwargs.get('unprivileged')}"
        )

    @pytest.mark.asyncio
    async def test_handle_create_proxmox_lxc_uses_defaults(self):
        """handle_create_proxmox_lxc uses correct defaults when optional params omitted."""
        import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
        from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_lxc

        mock_rm = MagicMock()
        mock_session = MagicMock()
        mock_rm.proxmox_session = mock_session
        mock_rm.db_adapter = MagicMock()
        mock_fn = AsyncMock(return_value={"status": "success", "node": "pve", "vmid": 200, "message": "created"})

        with (
            patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
            patch.object(_ph_mod, "create_proxmox_lxc", mock_fn),
        ):
            await handle_create_proxmox_lxc({"node": "pve", "vmid": 200, "hostname": "test-ct"})

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs.get("swap") == 512, f"Expected swap=512, got {call_kwargs.get('swap')}"
        assert call_kwargs.get("ssh_public_keys") is None, (
            f"Expected ssh_public_keys=None, got {call_kwargs.get('ssh_public_keys')}"
        )
        assert call_kwargs.get("unprivileged") is True, (
            f"Expected unprivileged=True, got {call_kwargs.get('unprivileged')}"
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
    @patch("src.homelab_mcp.proxmox_api.manage_proxmox_vm")
    async def test_delete_proxmox_vm_threads_session_to_manage(self, mock_manage_vm, mock_get_client):
        """delete_proxmox_vm passes its session param to its internal manage_proxmox_vm call."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.delete.return_value = {"data": "OK"}
        mock_manage_vm.return_value = {"status": "success"}

        mock_session = MagicMock()

        await delete_proxmox_vm(node="pve", vmid=100, session=mock_session)

        # manage_proxmox_vm should have been called with session=mock_session
        mock_manage_vm.assert_called_once()
        call_kwargs = mock_manage_vm.call_args
        assert call_kwargs.kwargs.get("session") is mock_session, (
            f"Expected session={mock_session!r} in manage_proxmox_vm call, got {call_kwargs}"
        )


# --- Wave 0 RED test: INJECT-03 (deleted by Plan 03 D-12) ---
# The test_get_proxmox_client_keyring_fallback test that verified the INJECT-03
# "first registry entry" shortcut has been removed because D-12 intentionally
# deletes that shortcut. The new behavior is: get_proxmox_client() with no host
# raises ValueError naming PROXMOX_HOST (see test_client_missing_host above).
# The resolver path is covered by TestGetProxmoxClientAsync.


# ---------------------------------------------------------------------------
# Phase 38.1 — Wave 0 RED tests: resolver credential_id kwarg (R5, D-11, D-12, D-13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.find_credential_by_id")
@patch("homelab_mcp.proxmox_api.list_credentials")
@patch("homelab_mcp.proxmox_api.get_credential")
async def test_resolve_credential_id_short_circuit_phase381(
    mock_get_cred,
    mock_list_creds,
    mock_find_by_id,
) -> None:
    """D-13: resolve_proxmox_credentials(host='pve', credential_id=<uuid>) short-circuits to registry UUID."""
    from homelab_mcp.proxmox_api import resolve_proxmox_credentials  # noqa: PLC0415

    test_uuid = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    # Registry entry keyed by IP — different from host='pve'
    mock_list_creds.return_value = []  # hostname-exact-match tier finds nothing
    mock_find_by_id.return_value = {
        "credential_id": test_uuid,
        "hostname": "192.168.10.20",
        "username": "root@pam!tok",
        "credential_type": "proxmox",
        "scope": "node",
        "cluster_name": "",
    }
    mock_get_cred.return_value = "test-api-token"

    # Phase 38.1 R5: credential_id kwarg must exist and short-circuit lookup
    # This MUST FAIL until Plan 02 adds the credential_id parameter
    result = await resolve_proxmox_credentials(host="pve", credential_id=test_uuid)
    assert result is not None
    assert isinstance(result, tuple)


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.find_credential_by_id")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolve_proxmox_credentials_with_unknown_uuid_raises_binding_stale_phase381(
    mock_list_creds,
    mock_find_by_id,
) -> None:
    """D-11: resolve_proxmox_credentials with UUID not in registry raises CredentialNotFoundError (binding stale)."""
    from homelab_mcp.proxmox_api import CredentialNotFoundError, resolve_proxmox_credentials  # noqa: PLC0415

    mock_list_creds.return_value = []  # empty registry
    mock_find_by_id.return_value = None  # UUID not in registry

    # Phase 38.1 D-11: unknown UUID → CredentialNotFoundError with 'binding stale' message
    with pytest.raises(CredentialNotFoundError) as exc_info:
        await resolve_proxmox_credentials(
            host="pve",
            credential_id="00000000-0000-4000-8000-000000000000",
        )
    error_msg = str(exc_info.value)
    assert "binding stale" in error_msg, (
        f"Phase 38.1 D-11: expected 'binding stale' in error, got: {error_msg!r}"
    )
    assert "credentials add --type proxmox pve" in error_msg, (
        f"Phase 38.1 D-11: error must include recovery command, got: {error_msg!r}"
    )
    assert getattr(exc_info.value, "reason_hint", None) == "binding_stale", (
        f"Phase 38.1 D-08: expected reason_hint='binding_stale', got: "
        f"{getattr(exc_info.value, 'reason_hint', None)!r}"
    )


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.find_credential_by_id")
@patch("homelab_mcp.proxmox_api.list_credentials")
@patch("homelab_mcp.proxmox_api.get_credential")
async def test_resolve_proxmox_credentials_with_uuid_keyring_miss_raises_desync_phase381(
    mock_get_cred,
    mock_list_creds,
    mock_find_by_id,
) -> None:
    """D-12: UUID found in registry but keyring returns None → CredentialNotFoundError (keyring_desync)."""
    from homelab_mcp.proxmox_api import CredentialNotFoundError, resolve_proxmox_credentials  # noqa: PLC0415

    test_uuid = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    mock_list_creds.return_value = []  # tier-1 hostname match empty
    mock_find_by_id.return_value = {
        "credential_id": test_uuid,
        "hostname": "192.168.10.20",
        "username": "root@pam!tok",
        "credential_type": "proxmox",
        "scope": "node",
        "cluster_name": "",
    }
    mock_get_cred.return_value = None  # keyring desync

    # Phase 38.1 D-12: UUID hits registry entry, but keyring returns None
    with pytest.raises(CredentialNotFoundError) as exc_info:
        await resolve_proxmox_credentials(host="pve", credential_id=test_uuid)

    error_msg = str(exc_info.value)
    # Must not fall back silently — must surface desync
    assert exc_info.type is CredentialNotFoundError
    assert "keyring desync" in error_msg, (
        f"Phase 38.1 D-12: expected 'keyring desync' in error, got: {error_msg!r}"
    )
    assert getattr(exc_info.value, "reason_hint", None) == "keyring_desync", (
        f"Phase 38.1 D-08: expected reason_hint='keyring_desync', got: "
        f"{getattr(exc_info.value, 'reason_hint', None)!r}"
    )


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.find_credential_by_id")
@patch("homelab_mcp.proxmox_api.list_credentials")
@patch("homelab_mcp.proxmox_api.get_credential")
async def test_resolve_proxmox_credentials_with_credential_id_ignores_host_arg_phase381(
    mock_get_cred,
    mock_list_creds,
    mock_find_by_id,
) -> None:
    """D-13: UUID wins over host — hostname mismatch is expected, not an error."""
    from homelab_mcp.proxmox_api import resolve_proxmox_credentials  # noqa: PLC0415

    # Registry entry keyed by IP; host passed as short name — mismatch is the point
    test_uuid = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    mock_list_creds.return_value = []
    mock_find_by_id.return_value = {
        "credential_id": test_uuid,
        "hostname": "192.168.10.20",  # registry hostname
        "username": "root@pam!tok",
        "credential_type": "proxmox",
        "scope": "node",
        "cluster_name": "",
    }
    mock_get_cred.return_value = "valid-token"

    # Phase 38.1 D-13: UUID short-circuit means host mismatch is irrelevant
    # This MUST FAIL until Plan 02 adds credential_id support
    result = await resolve_proxmox_credentials(
        host="pve",  # sitemap short hostname
        credential_id=test_uuid,  # UUID for '192.168.10.20' entry
    )
    assert result is not None  # must not raise


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.list_credentials")
@patch("homelab_mcp.proxmox_api.get_credential")
async def test_resolve_proxmox_credentials_legacy_positional_backward_compat_phase381(
    mock_get_cred,
    mock_list_creds,
) -> None:
    """Existing callers without credential_id still work (backward compat — D-14)."""
    from homelab_mcp.proxmox_api import resolve_proxmox_credentials  # noqa: PLC0415

    mock_list_creds.return_value = [
        {
            "hostname": "pve-legacy",
            "username": "root@pam!tok",
            "credential_type": "proxmox",
            "scope": "node",
            "cluster_name": "",
        }
    ]
    mock_get_cred.return_value = "legacy-token"

    # Phase 38.1 D-14: legacy call without credential_id must still work
    result = await resolve_proxmox_credentials("pve-legacy")
    assert result is not None
    assert isinstance(result, tuple)


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.find_credential_by_id")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolve_proxmox_credentials_with_uuid_of_wrong_type_raises_type_mismatch_phase381(
    mock_list_creds,
    mock_find_by_id,
) -> None:
    """T-38.1-05-02: caller passes SSH UUID to proxmox resolver → 'binding type mismatch'."""
    from homelab_mcp.proxmox_api import CredentialNotFoundError, resolve_proxmox_credentials  # noqa: PLC0415

    test_uuid = "11111111-1111-4111-8111-111111111111"
    mock_list_creds.return_value = []
    # Registry entry exists but is an SSH credential, not proxmox
    mock_find_by_id.return_value = {
        "credential_id": test_uuid,
        "hostname": "192.168.10.20",
        "username": "root",
        "credential_type": "ssh",  # WRONG TYPE
        "scope": "node",
        "cluster_name": "",
    }

    with pytest.raises(CredentialNotFoundError) as exc_info:
        await resolve_proxmox_credentials(host="pve", credential_id=test_uuid)

    error_msg = str(exc_info.value)
    assert "binding type mismatch" in error_msg, (
        f"Phase 38.1 T-38.1-05-02: expected 'binding type mismatch', got: {error_msg!r}"
    )
    assert "expected 'proxmox'" in error_msg, (
        f"Phase 38.1 T-38.1-05-02: expected target type in message, got: {error_msg!r}"
    )


@pytest.mark.asyncio
async def test_resolve_proxmox_credentials_with_malformed_credential_id_phase381() -> None:
    """T-38.1-05-01: malformed (non-UUID) credential_id → CredentialNotFoundError 'binding stale: malformed'."""
    from homelab_mcp.proxmox_api import CredentialNotFoundError, resolve_proxmox_credentials  # noqa: PLC0415

    with pytest.raises(CredentialNotFoundError) as exc_info:
        await resolve_proxmox_credentials(host="pve", credential_id="not-a-uuid")

    error_msg = str(exc_info.value)
    assert "binding stale" in error_msg, (
        f"Phase 38.1 T-38.1-05-01: expected 'binding stale' for malformed UUID, got: {error_msg!r}"
    )
    assert "malformed" in error_msg, (
        f"Phase 38.1 T-38.1-05-01: expected 'malformed' marker, got: {error_msg!r}"
    )
