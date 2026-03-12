"""
Proxmox VE API integration.

Provides tools for managing Proxmox Virtual Environment via REST API.
Supports both password and API token authentication.
"""

import logging
import os
from typing import Any

import aiohttp

from .log_filter import sanitize_error

logger = logging.getLogger(__name__)


class ProxmoxAPIClient:
    """Client for interacting with Proxmox VE API."""

    def __init__(
        self,
        host: str,
        port: int = 8006,
        verify_ssl: bool = True,
        username: str | None = None,
        password: str | None = None,
        api_token: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """
        Initialize Proxmox API client.

        Args:
            host: Proxmox host IP or hostname
            port: API port (default: 8006)
            verify_ssl: Whether to verify SSL certificates
            username: Username (e.g., 'root@pam')
            password: Password for authentication
            api_token: API token (format: 'user@realm!tokenid=secret')
            session: Optional shared aiohttp.ClientSession (from ResourceManager)
        """
        self.host = host
        self.port = port
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{host}:{port}/api2/json"

        # Authentication
        self.username = username
        self.password = password
        self.api_token = api_token
        self._auth_cookie: str | None = None
        self._csrf_token: str | None = None

        # Shared session (from ResourceManager)
        self._shared_session = session

    async def _authenticate(self, session: aiohttp.ClientSession) -> None:
        """Authenticate with Proxmox API using password."""
        if self._auth_cookie:
            return  # Already authenticated

        if not self.username or not self.password:
            raise ValueError("Username and password required for authentication")

        auth_url = f"{self.base_url}/access/ticket"
        data = {"username": self.username, "password": self.password}

        async with session.post(auth_url, data=data, ssl=self.verify_ssl) as response:
            response.raise_for_status()
            result = await response.json()

            if "data" not in result:
                raise ValueError("Authentication failed: Invalid response")

            self._auth_cookie = result["data"]["ticket"]
            self._csrf_token = result["data"]["CSRFPreventionToken"]

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests."""
        headers: dict[str, str] = {}

        if self.api_token:
            # API token authentication
            headers["Authorization"] = f"PVEAPIToken={self.api_token}"
        elif self._csrf_token:
            # Cookie-based authentication
            headers["CSRFPreventionToken"] = self._csrf_token

        return headers

    def _get_cookies(self) -> dict[str, str]:
        """Get cookies for API requests."""
        if self._auth_cookie:
            return {"PVEAuthCookie": self._auth_cookie}
        return {}

    async def request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make an API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/nodes')
            data: Request body data
            params: Query parameters

        Returns:
            API response data
        """
        url = f"{self.base_url}{endpoint}"

        if self._shared_session is not None:
            # Use the shared session from ResourceManager
            return await self._do_request(self._shared_session, method, url, data, params)
        else:
            # Fallback: create a per-request session (backward compatibility)
            connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
            async with aiohttp.ClientSession(connector=connector) as session:
                return await self._do_request(session, method, url, data, params)

    async def _do_request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request using the given session.

        Args:
            session: aiohttp.ClientSession to use
            method: HTTP method
            url: Full request URL
            data: Request body data
            params: Query parameters

        Returns:
            API response data
        """
        # Authenticate if using password
        if not self.api_token and self.username and self.password:
            await self._authenticate(session)

        headers = self._get_headers()
        cookies = self._get_cookies()

        async with session.request(
            method=method,
            url=url,
            headers=headers,
            cookies=cookies,
            json=data,
            params=params,
        ) as response:
            response.raise_for_status()
            result = await response.json()

            if "data" not in result:
                raise ValueError(f"Invalid API response: {result}")

            return result["data"]  # type: ignore[no-any-return]

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request."""
        return await self.request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: dict[str, Any]) -> Any:
        """Make a POST request."""
        return await self.request("POST", endpoint, data=data)

    async def put(self, endpoint: str, data: dict[str, Any]) -> Any:
        """Make a PUT request."""
        return await self.request("PUT", endpoint, data=data)

    async def delete(self, endpoint: str) -> Any:
        """Make a DELETE request."""
        return await self.request("DELETE", endpoint)


def get_proxmox_client(
    host: str | None = None,
    port: int = 8006,
    verify_ssl: bool | None = None,
    username: str | None = None,
    password: str | None = None,
    api_token: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> ProxmoxAPIClient:
    """
    Get a Proxmox API client with credentials from environment or parameters.

    Args:
        host: Proxmox host (defaults to PROXMOX_HOST env var)
        port: API port (default: 8006)
        verify_ssl: Verify SSL (defaults to PROXMOX_VERIFY_SSL env var)
        username: Username (defaults to PROXMOX_USER env var)
        password: Password (defaults to PROXMOX_PASSWORD env var)
        api_token: API token (defaults to PROXMOX_API_TOKEN env var)
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        Configured ProxmoxAPIClient instance
    """
    # Get from environment if not provided
    host = host or os.getenv("PROXMOX_HOST")
    if not host:
        raise ValueError("Proxmox host must be provided or set in PROXMOX_HOST env var")

    if verify_ssl is None:
        verify_ssl = os.getenv("PROXMOX_VERIFY_SSL", "true").lower() != "false"

    username = username or os.getenv("PROXMOX_USER")
    password = password or os.getenv("PROXMOX_PASSWORD")
    api_token = api_token or os.getenv("PROXMOX_API_TOKEN")

    # Must have either API token or username+password
    if not api_token and not (username and password):
        raise ValueError("Must provide either PROXMOX_API_TOKEN or PROXMOX_USER+PROXMOX_PASSWORD")

    return ProxmoxAPIClient(
        host=host,
        port=port,
        verify_ssl=verify_ssl,
        username=username,
        password=password,
        api_token=api_token,
        session=session,
    )


async def list_proxmox_resources(
    host: str | None = None,
    resource_type: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    List Proxmox cluster resources.

    Args:
        host: Proxmox host (optional, uses env var if not provided)
        resource_type: Filter by type: 'vm', 'lxc', 'node', 'storage', etc.
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        List of resources with their details
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        resources = await client.get("/cluster/resources")

        # Filter by type if specified
        if resource_type:
            resources = [r for r in resources if r.get("type") == resource_type]

        return {
            "status": "success",
            "total": len(resources),
            "resources": resources,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error listing Proxmox resources: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to list resources: {sanitize_error(e)}",
        }


async def get_proxmox_node_status(
    node: str,
    host: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    Get status of a Proxmox node.

    Args:
        node: Node name
        host: Proxmox host (optional, uses env var if not provided)
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        Node status information
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        status = await client.get(f"/nodes/{node}/status")

        return {
            "status": "success",
            "node": node,
            "data": status,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error getting node status: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to get node status: {sanitize_error(e)}",
        }


async def get_proxmox_vm_status(
    node: str,
    vmid: int,
    host: str | None = None,
    vm_type: str = "qemu",
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    Get status of a VM or container.

    Args:
        node: Node name
        vmid: VM/Container ID
        host: Proxmox host (optional)
        vm_type: 'qemu' for VM or 'lxc' for container
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        VM/Container status information
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        status = await client.get(f"/nodes/{node}/{vm_type}/{vmid}/status/current")

        return {
            "status": "success",
            "node": node,
            "vmid": vmid,
            "type": vm_type,
            "data": status,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error getting VM status: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to get VM status: {sanitize_error(e)}",
        }


async def get_proxmox_vm_config(
    node: str,
    vmid: int,
    host: str | None = None,
    vm_type: str = "qemu",
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    Get the persistent config of a VM or container.

    Returns cores, memory, sockets, net0/net1/net2 — the fields used for
    config drift detection. This is distinct from status/current (runtime stats).

    Args:
        node: Node name
        vmid: VM/Container ID
        host: Proxmox host (optional)
        vm_type: 'qemu' for VM or 'lxc' for container
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        VM/Container persistent configuration
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        config = await client.get(f"/nodes/{node}/{vm_type}/{vmid}/config")

        return {
            "status": "success",
            "node": node,
            "vmid": vmid,
            "type": vm_type,
            "data": config,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error getting VM config: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to get VM config: {sanitize_error(e)}",
        }


async def manage_proxmox_vm(
    node: str,
    vmid: int,
    action: str,
    host: str | None = None,
    vm_type: str = "qemu",
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    Manage a VM or container (start, stop, shutdown, reboot, reset, suspend, resume).

    Args:
        node: Node name
        vmid: VM/Container ID
        action: Action to perform ('start', 'stop', 'shutdown', 'reboot', 'reset', 'suspend', 'resume')
        host: Proxmox host (optional)
        vm_type: 'qemu' for VM or 'lxc' for container
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        Operation result
    """
    client = get_proxmox_client(host=host, session=session)

    valid_actions = [
        "start",
        "stop",
        "shutdown",
        "reboot",
        "reset",
        "suspend",
        "resume",
    ]
    if action not in valid_actions:
        return {
            "status": "error",
            "message": f"Invalid action. Must be one of: {', '.join(valid_actions)}",
        }

    try:
        endpoint = f"/nodes/{node}/{vm_type}/{vmid}/status/{action}"
        result = await client.post(endpoint, {})

        return {
            "status": "success",
            "node": node,
            "vmid": vmid,
            "action": action,
            "data": result,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error managing VM: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to {action} VM: {sanitize_error(e)}",
        }


async def create_proxmox_lxc(
    node: str,
    vmid: int,
    hostname: str,
    host: str | None = None,
    ostemplate: str = "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
    storage: str = "local-lvm",
    memory: int = 512,
    swap: int = 512,
    cores: int = 1,
    rootfs_size: int = 8,
    password: str | None = None,
    ssh_public_keys: str | None = None,
    unprivileged: bool = True,
    start: bool = False,
    session: aiohttp.ClientSession | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create a new LXC container.

    Args:
        node: Node name
        vmid: Container ID
        hostname: Container hostname
        host: Proxmox host (optional)
        ostemplate: Template to use
        storage: Storage for rootfs
        memory: RAM in MB
        swap: Swap in MB
        cores: Number of CPU cores
        rootfs_size: Root filesystem size in GB
        password: Root password
        ssh_public_keys: SSH public keys
        unprivileged: Create unprivileged container
        start: Start after creation
        session: Optional shared aiohttp.ClientSession (from ResourceManager)
        **kwargs: Additional LXC parameters

    Returns:
        Creation result
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        # Build container config
        config: dict[str, Any] = {
            "vmid": vmid,
            "hostname": hostname,
            "ostemplate": ostemplate,
            "storage": storage,
            "memory": memory,
            "swap": swap,
            "cores": cores,
            "rootfs": f"{storage}:{rootfs_size}",
            "unprivileged": 1 if unprivileged else 0,
            "start": 1 if start else 0,
        }

        if password:
            config["password"] = password
        if ssh_public_keys:
            config["ssh-public-keys"] = ssh_public_keys

        # Add any additional parameters
        config.update(kwargs)

        result = await client.post(f"/nodes/{node}/lxc", config)

        return {
            "status": "success",
            "node": node,
            "vmid": vmid,
            "hostname": hostname,
            "message": f"LXC container {vmid} created successfully",
            "data": result,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error creating LXC container: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to create LXC container: {sanitize_error(e)}",
        }


async def create_proxmox_vm(
    node: str,
    vmid: int,
    name: str,
    host: str | None = None,
    memory: int = 2048,
    cores: int = 2,
    sockets: int = 1,
    storage: str = "local-lvm",
    disk_size: int = 32,
    iso: str | None = None,
    cdrom: str | None = None,
    net0: str = "virtio,bridge=vmbr0",
    ostype: str = "l26",
    start: bool = False,
    session: aiohttp.ClientSession | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create a new VM (QEMU).

    Args:
        node: Node name
        vmid: VM ID
        name: VM name
        host: Proxmox host (optional)
        memory: RAM in MB
        cores: Number of CPU cores
        sockets: Number of CPU sockets
        storage: Storage for disks
        disk_size: Disk size in GB
        iso: ISO image to attach
        cdrom: CDROM image
        net0: Network configuration
        ostype: OS type
        start: Start after creation
        session: Optional shared aiohttp.ClientSession (from ResourceManager)
        **kwargs: Additional VM parameters

    Returns:
        Creation result
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        # Build VM config
        config: dict[str, Any] = {
            "vmid": vmid,
            "name": name,
            "memory": memory,
            "cores": cores,
            "sockets": sockets,
            "scsi0": f"{storage}:{disk_size}",
            "net0": net0,
            "ostype": ostype,
        }

        if iso:
            config["ide2"] = f"{iso},media=cdrom"
        elif cdrom:
            config["cdrom"] = cdrom

        # Add any additional parameters
        config.update(kwargs)

        result = await client.post(f"/nodes/{node}/qemu", config)

        # Start if requested
        if start and result:
            await manage_proxmox_vm(node, vmid, "start", host, "qemu", session=session)

        return {
            "status": "success",
            "node": node,
            "vmid": vmid,
            "name": name,
            "message": f"VM {vmid} created successfully",
            "data": result,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error creating VM: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to create VM: {sanitize_error(e)}",
        }


async def clone_proxmox_vm(
    node: str,
    vmid: int,
    new_vmid: int,
    host: str | None = None,
    name: str | None = None,
    full: bool = True,
    vm_type: str = "qemu",
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    Clone a VM or container.

    Args:
        node: Node name
        vmid: Source VM/Container ID
        new_vmid: New VM/Container ID
        host: Proxmox host (optional)
        name: New VM name
        full: Full clone (True) or linked clone (False)
        vm_type: 'qemu' for VM or 'lxc' for container
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        Clone operation result
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        config: dict[str, Any] = {
            "newid": new_vmid,
            "full": 1 if full else 0,
        }

        if name:
            config["name"] = name

        result = await client.post(f"/nodes/{node}/{vm_type}/{vmid}/clone", config)

        return {
            "status": "success",
            "node": node,
            "source_vmid": vmid,
            "new_vmid": new_vmid,
            "message": f"VM {vmid} cloned to {new_vmid} successfully",
            "data": result,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error cloning VM: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to clone VM: {sanitize_error(e)}",
        }


async def delete_proxmox_vm(
    node: str,
    vmid: int,
    host: str | None = None,
    vm_type: str = "qemu",
    purge: bool = False,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    Delete a VM or container.

    Args:
        node: Node name
        vmid: VM/Container ID
        host: Proxmox host (optional)
        vm_type: 'qemu' for VM or 'lxc' for container
        purge: Remove from all related configurations
        session: Optional shared aiohttp.ClientSession (from ResourceManager)

    Returns:
        Deletion result
    """
    client = get_proxmox_client(host=host, session=session)

    try:
        # Stop VM first if running
        try:
            await manage_proxmox_vm(node, vmid, "stop", host, vm_type, session=session)
        except Exception:
            logger.debug("VM %s on node %s may already be stopped, continuing with deletion", vmid, node)

        # Delete
        endpoint = f"/nodes/{node}/{vm_type}/{vmid}"
        if purge:
            endpoint += "?purge=1"

        result = await client.delete(endpoint)

        return {
            "status": "success",
            "node": node,
            "vmid": vmid,
            "message": f"VM {vmid} deleted successfully",
            "data": result,
        }

    except (aiohttp.ClientError, ValueError) as e:
        logger.error("Error deleting VM: %s", str(e))
        return {
            "status": "error",
            "message": f"Failed to delete VM: {sanitize_error(e)}",
        }
