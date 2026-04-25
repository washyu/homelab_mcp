"""Infrastructure drift detection for homelab MCP server.

Phase 36 (v1.7) — sitemap is the single source of truth for drift detection.
The parallel drift_baselines table has been dropped; scan_drift iterates sitemap
rows directly and resolves Proxmox credentials via the get_proxmox_client funnel.

Phase 36 ships a 2-bucket interim shape (probed_ok / unreachable). Phase 37 will
expand to 4 buckets (DRFT-13/14); Phase 39 will add unknown / missing / changed
detection (DRFT-17/18/19).
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .database import DatabaseAdapter
from .log_filter import sanitize_error
from .proxmox_api import (
    CredentialNotFoundError,
    get_proxmox_client,
    resolve_proxmox_credentials,
)

logger = logging.getLogger(__name__)


async def scan_drift(
    session: aiohttp.ClientSession | None,
    db_adapter: DatabaseAdapter,
    node: str | None = None,
    vm_type: str = "all",
) -> dict[str, Any]:
    """Scan for infrastructure drift against the sitemap (2-bucket interim).

    For each non-degenerate sitemap row:
      1. Attempt to resolve Proxmox credentials via get_proxmox_client.
         CredentialNotFoundError -> silent skip (row is not a Proxmox host).
      2. Probe GET /cluster/status. Success -> probed_ok bucket.
         aiohttp/timeout/value error -> unreachable bucket with sanitized error.

    The (scope, cluster_name) tuple from resolve_proxmox_credentials is captured
    via a second cache-hit call after get_proxmox_client succeeds — this keeps
    telemetry surfaced in the per-row record without modifying ProxmoxAPIClient.

    Args:
        session: Optional shared aiohttp session for connection pooling.
        db_adapter: Database adapter (single funnel for sitemap reads).
        node: Inert passthrough — Phase 37 (DRFT-13) will define filter semantics.
        vm_type: Inert passthrough — same.

    Returns:
        {
            "status": "success",
            "scan_timestamp": ISO-8601 UTC,
            "scanned": int,
            "probed_ok": [<per-row record per CONTEXT D-02>, ...],
            "unreachable": [<per-row record>, ...],
        }
    """
    scan_timestamp = datetime.now(UTC).isoformat()
    probed_ok: list[dict[str, Any]] = []
    unreachable: list[dict[str, Any]] = []

    rows = db_adapter.get_all_devices()
    for row in rows:
        hostname = row.get("hostname")
        # D-10a: skip degenerate Phase-35 fallback rows (zombies, errors, empty hostnames)
        if hostname in ("", "unknown", None) or row.get("status") == "error":
            continue

        try:
            client = await get_proxmox_client(host=hostname, session=session)
        except CredentialNotFoundError:
            # D-10: row is not a registered Proxmox host -> silently skip
            continue
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            # Resolver-during-cluster-walk failure
            unreachable.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": "unknown",
                "cluster_name": None,
                "status": "unreachable",
                "error": sanitize_error(exc),
                "scan_timestamp": scan_timestamp,
            })
            continue

        # Capture (scope, cluster_name) telemetry for D-02. Second call hits
        # _HOST_CLUSTER_CACHE (proxmox_api.py:243-265) so cost is microseconds.
        try:
            _token, scope, cluster_name = await resolve_proxmox_credentials(
                hostname, session=session,
            )
        except CredentialNotFoundError:
            # Defensive — should not happen after get_proxmox_client succeeded.
            continue

        try:
            status = await client.get("/cluster/status")
            if not isinstance(status, list):
                raise ValueError(
                    f"unexpected /cluster/status payload type: {type(status).__name__}"
                )
            probed_ok.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": scope,
                "cluster_name": cluster_name,
                "status": "probed-ok",
                "error": None,
                "scan_timestamp": scan_timestamp,
            })
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            unreachable.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": scope,
                "cluster_name": cluster_name,
                "status": "unreachable",
                "error": sanitize_error(exc),
                "scan_timestamp": scan_timestamp,
            })

    return {
        "status": "success",
        "scan_timestamp": scan_timestamp,
        "scanned": len(probed_ok) + len(unreachable),
        "probed_ok": probed_ok,
        "unreachable": unreachable,
    }
