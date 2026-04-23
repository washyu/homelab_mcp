"""
Proxmox VE API integration.

Provides tools for managing Proxmox Virtual Environment via REST API.
Supports both password and API token authentication.
"""

import logging
import os
from typing import Any, Literal

import aiohttp

from .credential_store import get_credential, list_credentials
from .log_filter import sanitize_error
from .ssh_tools import CredentialNotFoundError  # noqa: F401 — re-exported for consumers

logger = logging.getLogger(__name__)

# D-05a: in-memory cache for successful host→cluster_name mappings. Process-lifetime only.
_HOST_CLUSTER_CACHE: dict[str, str] = {}


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


async def resolve_proxmox_credentials(
    host: str,
    session: aiohttp.ClientSession | None = None,
) -> tuple[str, Literal["node", "cluster"], str | None]:
    """Resolve Proxmox API credentials for a host via per-node → cluster → error tiers.

    Two-tier resolution (v1.6 Phase 34, D-09/D-10):
      1. **Per-node registry entry exists for host** → return its token+scope="node"+None.
         ``/cluster/status`` is NEVER called in this tier (D-10 bullet 1; Success Criterion 5).
      2. **Cluster walk** — iterate registry entries with scope=="cluster", probing
         ``GET /cluster/status`` on ``host`` with each candidate token; first entry whose
         response contains a ``type=="cluster"`` row with ``name == entry["cluster_name"]`` wins.
         Successful ``host → cluster_name`` mapping is cached in ``_HOST_CLUSTER_CACHE``
         for the lifetime of the process (D-05a).

    Returns:
        (api_token, scope, cluster_name) — api_token is the full
        ``"user@realm!tokenid=SECRET"`` form ProxmoxAPIClient expects. scope is
        "node" or "cluster". cluster_name is the string cluster name for
        cluster-scope results, None for node-scope results.

    Raises:
        CredentialNotFoundError: when neither tier matches. Message names every
            cluster entry that was tried and includes the ``credentials add
            --type proxmox`` CLI pointer (D-05, D-15).
    """
    entries = list_credentials(credential_type="proxmox")

    # Tier 1: per-node short-circuit (D-10 bullet 1; SC-5 requires /cluster/status is never called here).
    node_matches = [e for e in entries if e.get("scope", "node") == "node" and e["hostname"] == host]
    logger.debug("proxmox resolve host=%s tier=node candidates=%d", host, len(node_matches))
    if node_matches:
        entry = node_matches[0]
        secret = get_credential(entry["hostname"], entry["username"], credential_type="proxmox")
        if secret is None:
            logger.warning(
                "Credential desync for %s (user: %s): registry entry exists but keyring "
                "returned None — re-run 'homelab-mcp credentials add --type proxmox %s %s' to restore",
                entry["hostname"],
                entry["username"],
                entry["hostname"],
                entry["username"],
            )
        else:
            api_token = f"{entry['username']}={secret}"
            logger.debug("proxmox resolve host=%s source=node", host)
            return (api_token, "node", None)
    logger.debug("proxmox resolve host=%s tier=node MISS", host)

    # Tier 2 cache hit (D-05a).
    cluster_entries = [e for e in entries if e.get("scope", "node") == "cluster"]
    cached_cluster = _HOST_CLUSTER_CACHE.get(host)
    if cached_cluster is not None:
        for entry in cluster_entries:
            if entry.get("cluster_name", "") == cached_cluster:
                secret = get_credential(
                    "",
                    entry["username"],
                    credential_type="proxmox",
                    scope="cluster",
                    cluster_name=cached_cluster,
                )
                if secret is not None:
                    api_token = f"{entry['username']}={secret}"
                    logger.debug(
                        "proxmox resolve host=%s source=cluster cache_hit cluster=%s",
                        host,
                        cached_cluster,
                    )
                    return (api_token, "cluster", cached_cluster)
                # Desync on cached entry → fall through to re-walk.
                break

    # Tier 2 walk (D-04, D-05b).
    cluster_names_tried = [e.get("cluster_name", "") for e in cluster_entries]
    logger.debug(
        "proxmox resolve host=%s tier=cluster entries=%s",
        host,
        cluster_names_tried,
    )
    for entry in cluster_entries:
        cluster_name = entry.get("cluster_name", "")
        if not cluster_name:
            continue
        secret = get_credential(
            "",
            entry["username"],
            credential_type="proxmox",
            scope="cluster",
            cluster_name=cluster_name,
        )
        if secret is None:
            logger.warning(
                "Credential desync for cluster:%s (user: %s): registry entry exists but keyring "
                "returned None — re-run 'homelab-mcp credentials add --type proxmox --scope cluster:%s %s' to restore",
                cluster_name,
                entry["username"],
                cluster_name,
                entry["username"],
            )
            continue
        candidate_token = f"{entry['username']}={secret}"
        # Throwaway client per candidate — reuses existing ProxmoxAPIClient session+auth logic.
        probe_client = ProxmoxAPIClient(host=host, api_token=candidate_token, session=session)
        try:
            status = await probe_client.get("/cluster/status")
        except (aiohttp.ClientError, ValueError) as exc:
            logger.debug(
                "proxmox resolve host=%s tier=cluster candidate=%s probe failed — skip: %s",
                host,
                cluster_name,
                sanitize_error(exc),
            )
            continue
        # ProxmoxAPIClient.get() strips the "data" wrapper — status is the list directly.
        rows = status if isinstance(status, list) else []
        cluster_row = next(
            (r for r in rows if isinstance(r, dict) and r.get("type") == "cluster" and r.get("name") == cluster_name),
            None,
        )
        if cluster_row is not None:
            _HOST_CLUSTER_CACHE[host] = cluster_name
            logger.debug("proxmox resolve host=%s tier=cluster MATCH cluster=%s", host, cluster_name)
            logger.debug("proxmox resolve host=%s source=cluster", host)
            return (candidate_token, "cluster", cluster_name)

    # Terminal: no credential anywhere (D-05, D-15).
    tried = ", ".join(c for c in cluster_names_tried if c) or "<none>"
    raise CredentialNotFoundError(
        f"No Proxmox credentials found for {host}. "
        f"Cluster entries tried: {tried}. "
        f"Run `homelab-mcp credentials add --type proxmox {host} <username>` "
        "in your terminal to register this node explicitly, "
        "or run `homelab-mcp credentials add --type proxmox --scope cluster:<name> <token_id>` "
        "if this host belongs to a Proxmox cluster."
    )


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

    if verify_ssl is None:
        verify_ssl = os.getenv("PROXMOX_VERIFY_SSL", "true").lower() != "false"

    username = username or os.getenv("PROXMOX_USER")
    password = password or os.getenv("PROXMOX_PASSWORD")
    api_token = api_token or os.getenv("PROXMOX_API_TOKEN")

    # Keyring fallback (INJECT-03): only when env vars are insufficient
    # Single-homelab assumption: if PROXMOX_HOST is absent, take first registry entry.
    # If PROXMOX_HOST is set but auth is missing, match by host (or skip if no match).
    if not host or (not api_token and not (username and password)):
        registry_entries = list_credentials(credential_type="proxmox")
        if registry_entries:
            entry = registry_entries[0]
            keyring_host = entry["hostname"]
            keyring_username = entry["username"]
            # Only use this entry if: no host set, OR the env host matches the entry host
            if not host or host == keyring_host:
                keyring_secret = get_credential(keyring_host, keyring_username, credential_type="proxmox")
                if keyring_secret:
                    host = host or keyring_host
                    # Proxmox API tokens use "user@realm!tokenid=secret" format.
                    # The registry username holds the token ID (e.g. root@pam!mcp_test),
                    # the keyring holds the secret UUID.
                    api_token = api_token or f"{keyring_username}={keyring_secret}"
                    logger.debug("Auto-injected Proxmox keyring credential for %s", host)

    # Validation gates
    if not host:
        raise ValueError("Proxmox host must be provided or set in PROXMOX_HOST env var")

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
