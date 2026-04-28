"""
Proxmox VE API integration.

Provides tools for managing Proxmox Virtual Environment via REST API.
Supports both password and API token authentication.
"""

import logging
import os
import uuid
from typing import Any, Literal

import aiohttp

from .credential_store import find_credential_by_id, get_credential, list_credentials
from .log_filter import sanitize_error
from .ssh_tools import CredentialNotFoundError  # noqa: F401 — re-exported for consumers

logger = logging.getLogger(__name__)

# D-05a: in-memory cache for successful host→cluster_name mappings. Process-lifetime only.
_HOST_CLUSTER_CACHE: dict[str, str] = {}

# WR-04 (Phase 38.1 review): in-memory cache for the (scope, cluster_name)
# telemetry of the most recent successful resolution per (host, credential_id).
# Drift's second resolver call after get_proxmox_client succeeds previously
# re-executed Tier-0 / Tier-1 logic (registry load + keyring round-trip) on
# every probe — on flaky keyring backends that succeeded the first call but
# failed the second, drift would mis-route a perfectly reachable host into
# not_eligible. Populating this cache from EVERY successful tier (not just
# Tier-2 cluster-walk hits like _HOST_CLUSTER_CACHE) lets drift cheaply
# recover the telemetry without re-invoking the resolver.
_RESOLUTION_TELEMETRY_CACHE: dict[tuple[str, str | None], tuple[Literal["node", "cluster"], str | None]] = {}


def get_resolution_telemetry(
    host: str,
    credential_id: str | None = None,
) -> tuple[Literal["node", "cluster"], str | None] | None:
    """Return the cached (scope, cluster_name) for a previously-resolved host.

    Returns ``None`` when no cache entry exists. Used by drift_detection.scan_drift
    to avoid a second ``resolve_proxmox_credentials`` call when telemetry was
    already captured during the first resolution. WR-04 (Phase 38.1 review).
    """
    return _RESOLUTION_TELEMETRY_CACHE.get((host, credential_id))


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
    *,
    session: aiohttp.ClientSession | None = None,
    credential_id: str | None = None,
) -> tuple[str, Literal["node", "cluster"], str | None]:
    """Resolve Proxmox API credentials for a host via Tier-0 → per-node → cluster → error.

    Resolution tiers (v1.7 Phase 38.1 D-11/D-12/D-13/D-14 + v1.6 Phase 34 D-09/D-10):
      0. **UUID short-circuit** (when ``credential_id`` is supplied) — look up
         the entry by UUID via :func:`credential_store.find_credential_by_id`.
         UUID wins (D-13): ``host`` is used only for log/error context; hostname
         mismatch between sitemap row and registry entry is the WHOLE POINT of
         the binding. NEVER falls back to per-node hostname-exact-match (D-11)
         — that would mask rotation cleanup bugs.
      1. **Per-node registry entry exists for host** → return its token+scope="node"+None.
         ``/cluster/status`` is NEVER called in this tier (D-10 bullet 1; Success Criterion 5).
      2. **Cluster walk** — iterate registry entries with scope=="cluster", probing
         ``GET /cluster/status`` on ``host`` with each candidate token; first entry whose
         response contains a ``type=="cluster"`` row with ``name == entry["cluster_name"]`` wins.
         Successful ``host → cluster_name`` mapping is cached in ``_HOST_CLUSTER_CACHE``
         for the lifetime of the process (D-05a).

    Args:
        host: Hostname (used for lookup in tier-1/tier-2; only log/error context
            in tier-0).
        session: Optional shared aiohttp.ClientSession (now keyword-only, D-14).
        credential_id: Optional UUID from a sitemap row's
            ``proxmox_credential_id`` column. When supplied, triggers the
            tier-0 UUID short-circuit (keyword-only, D-14).

    Returns:
        (api_token, scope, cluster_name) — api_token is the full
        ``"user@realm!tokenid=SECRET"`` form ProxmoxAPIClient expects. scope is
        "node" or "cluster". cluster_name is the string cluster name for
        cluster-scope results, None for node-scope results.

    Raises:
        CredentialNotFoundError: when no tier matches. Tier-0 raises with
            ``.reason_hint`` set to ``"binding_stale"`` (UUID not in registry
            or wrong credential_type — D-11) or ``"keyring_desync"`` (UUID
            found but keyring miss — D-12). Tier-1/Tier-2 paths leave
            ``.reason_hint`` unset (drift maps these to ``"unbound"``).
    """
    # Phase 38.1 Tier-0: UUID short-circuit (D-11/D-12/D-13).
    if credential_id is not None:
        # T-38.1-05-01: validate UUID format defensively. Hand-edited registry
        # entries with malformed credential_id would otherwise pass string
        # equality in find_credential_by_id.
        try:
            uuid.UUID(credential_id)
        except (ValueError, AttributeError) as exc:
            raise CredentialNotFoundError(f"binding stale: malformed credential_id {credential_id!r}") from exc

        entry = find_credential_by_id(credential_id)
        if entry is None:
            # D-11: never fall back to hostname-exact-match (would mask
            # rotation cleanup bugs — the same silent-skip class we are closing).
            exc_inst = CredentialNotFoundError(
                f"binding stale: UUID {credential_id} not in registry. "
                f"Run `homelab-mcp credentials add --type proxmox {host} <username>` "
                f"to register, or `homelab-mcp credentials unlink {host} --type proxmox` "
                f"to clear the stale binding."
            )
            exc_inst.reason_hint = "binding_stale"
            raise exc_inst
        if entry.get("credential_type") != "proxmox":
            # T-38.1-05-02 defensive: caller passed an SSH UUID to the proxmox resolver.
            exc_inst = CredentialNotFoundError(
                f"binding type mismatch: credential_id {credential_id} is type "
                f"{entry.get('credential_type')!r}, expected 'proxmox'."
            )
            exc_inst.reason_hint = "binding_stale"
            raise exc_inst

        scope_str = "cluster" if entry.get("scope") == "cluster" else "node"
        entry_cluster_name = entry.get("cluster_name") or None
        secret = get_credential(
            entry["hostname"],
            entry["username"],
            credential_type="proxmox",
            scope=scope_str,
            cluster_name=entry.get("cluster_name", ""),
        )
        if secret is None:
            # D-12: keyring desync (registry hit, keyring miss).
            exc_inst = CredentialNotFoundError(
                f"keyring desync for credential_id={credential_id}: "
                f"registry entry exists but keyring returned None — "
                f"re-run `homelab-mcp credentials add --type proxmox "
                f"{entry['hostname']} {entry['username']}` to restore."
            )
            exc_inst.reason_hint = "keyring_desync"
            raise exc_inst
        logger.debug(
            "proxmox resolve host=%s source=tier0_uuid credential_id=%s scope=%s",
            host,
            credential_id,
            scope_str,
        )
        # Narrow scope_str back to Literal for the function return type.
        scope_literal: Literal["node", "cluster"] = "cluster" if scope_str == "cluster" else "node"
        # WR-04: populate telemetry cache for drift's second-call optimization.
        _RESOLUTION_TELEMETRY_CACHE[(host, credential_id)] = (scope_literal, entry_cluster_name)
        return (f"{entry['username']}={secret}", scope_literal, entry_cluster_name)

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
            # WR-04: populate telemetry cache for drift's second-call optimization.
            _RESOLUTION_TELEMETRY_CACHE[(host, credential_id)] = ("node", None)
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
                    # WR-04: populate telemetry cache.
                    _RESOLUTION_TELEMETRY_CACHE[(host, credential_id)] = ("cluster", cached_cluster)
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
            # WR-04: populate telemetry cache.
            _RESOLUTION_TELEMETRY_CACHE[(host, credential_id)] = ("cluster", cluster_name)
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


async def get_proxmox_client(
    host: str | None = None,
    port: int = 8006,
    verify_ssl: bool | None = None,
    username: str | None = None,
    password: str | None = None,
    api_token: str | None = None,
    session: aiohttp.ClientSession | None = None,
    *,
    credential_id: str | None = None,
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
        credential_id: Optional UUID from a sitemap row's
            ``proxmox_credential_id`` column (Phase 38.1 D-14 keyword-only).
            When supplied and ``host`` is set with no explicit auth,
            triggers the tier-0 UUID short-circuit on the resolver.

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

    # D-10: resolver fires only when host is known AND no explicit auth was provided.
    # Explicit api_token / username+password (from kwargs or env vars picked up above)
    # bypasses the resolver entirely — preserves SC-5 back-compat for environments
    # that have always configured Proxmox via PROXMOX_* env vars.
    #
    # CR-04 (Phase 38.1 review): when an env-var/explicit auth is in play AND
    # the caller threaded a sitemap binding via credential_id, emit a warning
    # so operators can detect that the binding is being silently overridden by
    # env vars. Drift's not_eligible bucket relies on the resolver actually
    # being invoked — under env-var dominance, every probe succeeds with
    # env creds regardless of binding state, and stale bindings become
    # invisible to drift. Logging the override surfaces this for observability.
    if host:
        has_explicit_auth = bool(api_token or (username and password))
        if credential_id is not None and has_explicit_auth:
            logger.warning(
                "Sitemap binding %s ignored for host=%s — explicit/env-var "
                "credentials take precedence. Drift reports against env-creds, "
                "not the bound UUID.",
                credential_id,
                host,
            )
        if not has_explicit_auth:
            resolved_token, scope, cluster_name = await resolve_proxmox_credentials(
                host,
                session=session,
                credential_id=credential_id,
            )
            api_token = resolved_token
            logger.debug(
                "Proxmox credential resolved for host=%s via source=%s cluster=%s",
                host,
                scope,
                cluster_name,
            )

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
    client = await get_proxmox_client(host=host, session=session)

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
    client = await get_proxmox_client(host=host, session=session)

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


def _classify_vm_status_error(
    exc: Exception,
    *,
    node: str,
    vmid: int,
    vm_type: Literal["qemu", "lxc"],
    host: str,
) -> dict[str, Any] | None:
    """POL-01 D-01/D-02: classify a Proxmox VM-status failure as `vm_not_found`.

    Detects ``aiohttp.ClientResponseError`` with ``status`` 500 (Proxmox's
    quirk for missing-VMID) or 404 (defensive: missing-node case) whose
    rendered message contains either the literal substring ``"does not
    exist"`` or the supplied ``vmid`` as a substring (covers both QEMU and
    LXC error wording variants).

    On match → returns the structured ``vm_not_found`` dict per D-02.
    On no-match → returns ``None``; caller falls through to the existing
    generic-error response shape (graceful degradation if Proxmox changes
    its error format).

    The returned ``message`` is constructed from the input parameters only.
    The exception's URL fields are never read, which is what closes the
    URL-leak in this code path (Bug I).
    """
    if not isinstance(exc, aiohttp.ClientResponseError):
        return None
    if exc.status not in (500, 404):
        return None
    rendered = f"{getattr(exc, 'message', '')} {exc!s}"
    if "does not exist" not in rendered and str(vmid) not in rendered:
        logger.warning(
            "Proxmox VM-status error did not match vm_not_found heuristic "
            "(status=%s, vmid=%s, message-snippet=%r); falling through to "
            "generic error path. May indicate Proxmox error-format drift.",
            exc.status,
            vmid,
            rendered[:120],
        )
        return None
    return {
        "status": "error",
        "error_kind": "vm_not_found",
        "node": node,
        "vmid": vmid,
        "vm_type": vm_type,
        "host": host,
        "message": (
            f"VM {vmid} ({vm_type}) not found on node {node!r} at host {host!r}. "
            f"Run list_proxmox_resources to see available VMs."
        ),
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
    client = await get_proxmox_client(host=host, session=session)

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
        classified = _classify_vm_status_error(
            e,
            node=node,
            vmid=vmid,
            vm_type=vm_type,  # type: ignore[arg-type]
            host=host or "",
        )
        if classified is not None:
            return classified
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
    client = await get_proxmox_client(host=host, session=session)

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
    client = await get_proxmox_client(host=host, session=session)

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
    client = await get_proxmox_client(host=host, session=session)

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
    client = await get_proxmox_client(host=host, session=session)

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
    client = await get_proxmox_client(host=host, session=session)

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
    client = await get_proxmox_client(host=host, session=session)

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
