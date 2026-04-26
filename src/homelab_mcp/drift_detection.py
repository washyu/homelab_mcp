"""Infrastructure drift detection for homelab MCP server.

v1.7 — sitemap is the single source of truth for drift detection. The parallel
baseline cache table was dropped in Phase 36; scan_drift iterates sitemap rows
directly, resolves Proxmox credentials via the get_proxmox_client funnel, and
classifies each row into one of four buckets:

  - probed_ok    — credential resolved, GET /cluster/status returned a list
  - unreachable  — credential resolved, probe raised a network/timeout/value error
                   (Phase 39 DRFT-18 will enrich rows in this bucket with
                   last-seen and decommission/purge pointers)
  - unknown      — reserved for Phase 39 (DRFT-17): VMs/LXC present on a Proxmox
                   hypervisor but absent from the sitemap. Always [] in Phase 37.
  - changed      — reserved for Phase 39 (DRFT-19): sitemap fields differ from
                   current probe values. Depends on Phase 38's fingerprint
                   schema. Always [] in Phase 37.

The response envelope is stable in Phase 37: every scan returns the same shape
regardless of filter scope. Filters that match zero rows (empty sitemap, no-match
node filter) return status="success" with all four buckets empty and a top-level
"guidance" field pointing to the sitemap CRUD tools.
"""

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


# Phase 37 D-09: shared guidance text for both "empty sitemap" and
# "filter-narrowed-to-zero" cases. Mentions sitemap CRUD tools by name.
# References only tool names, no env-var credentials (closes Bug B;
# locked by tests/test_ast_regression.py Phase 37 D-11 AST guard).
_EMPTY_SCAN_GUIDANCE = (
    "No Proxmox hosts in sitemap matched this scan. "
    "Run discover_and_map to populate the sitemap, "
    "get_network_sitemap to inspect what's tracked, or "
    "purge_failed_discoveries to clean stale rows. "
    "If a host is decommissioned, use decommission_device."
)


async def scan_drift(
    session: aiohttp.ClientSession | None,
    db_adapter: DatabaseAdapter,
    node: str | None = None,
    vm_type: str = "all",
) -> dict[str, Any]:
    """Scan for infrastructure drift against the sitemap (Phase 37 stable shape).

    Iterates sitemap rows and classifies each one into one of four buckets:
    probed_ok, unreachable, unknown, changed. The unknown and changed buckets
    are reserved for Phase 39 (DRFT-17/19) and are always empty in Phase 37 —
    they exist in the response so client code can iterate without defensive
    `dict.get(..., [])` checks.

    Filter semantics (Phase 37 DRFT-13):
      - node: exact hostname match against sitemap rows (no wildcards, no
        case folding). Filter applies BEFORE the degenerate-row skip. A
        no-match returns status="success" with all four buckets empty and
        a top-level "guidance" field — never status="error".
      - vm_type: reserved for Phase 39 per-VM detection; currently filters
        at the host level only (no-op until per-VM enumeration ships).

    For each non-degenerate sitemap row that survives the filter:
      1. Resolve Proxmox credentials via get_proxmox_client.
         CredentialNotFoundError -> silent skip (row is not a Proxmox host).
      2. Probe GET /cluster/status. Success -> probed_ok bucket.
         aiohttp.ClientError / TimeoutError / ValueError -> unreachable bucket
         with sanitize_error()-redacted message.

    The (scope, cluster_name) tuple from resolve_proxmox_credentials is captured
    via a second cache-hit call after get_proxmox_client succeeds — keeps
    telemetry surfaced in the per-row record without modifying ProxmoxAPIClient.

    Args:
        session: Optional shared aiohttp session for connection pooling.
        db_adapter: Database adapter (single funnel for sitemap reads).
        node: Optional exact-hostname filter. None means "no filter".
        vm_type: Reserved for Phase 39 per-VM detection; inert in Phase 37.

    Returns:
        {
            "status": "success",
            "scan_timestamp": ISO-8601 UTC,
            "scanned": int,                    # sum across all four buckets
            "counts": {
                "probed_ok": int,
                "unreachable": int,
                "unknown": int,                # always 0 in Phase 37
                "changed": int,                # always 0 in Phase 37
            },
            "guidance": str,                   # PRESENT only when scanned == 0
            "probed_ok": [<per-row record>, ...],
            "unreachable": [<per-row record>, ...],
            "unknown": [],                     # reserved for Phase 39 DRFT-17
            "changed": [],                     # reserved for Phase 39 DRFT-19
        }

    Per-row record shape (probed_ok and unreachable, unchanged from Phase 36 D-02):
        {
            "hostname": str,
            "connection_ip": str,
            "scope": "node" | "cluster" | "unknown",
            "cluster_name": str | None,
            "status": "probed-ok" | "unreachable",
            "error": str | None,               # sanitize_error() on unreachable
            "scan_timestamp": str,             # same value across all records
        }
    """
    scan_timestamp = datetime.now(UTC).isoformat()
    probed_ok: list[dict[str, Any]] = []
    unreachable: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []  # reserved for Phase 39 DRFT-17
    changed: list[dict[str, Any]] = []  # reserved for Phase 39 DRFT-19

    rows = db_adapter.get_all_devices()

    # D-01: hostname exact-match filter applied BEFORE degenerate-row skip.
    # node=None means "no filter"; non-None reduces rows to exact matches only.
    # No-match (zero remaining rows) is a successful empty-result, NOT an error.
    if node is not None:
        rows = [row for row in rows if row.get("hostname") == node]

    for row in rows:
        hostname = row.get("hostname")
        # D-10a (Phase 36): skip degenerate Phase-35 fallback rows
        # (zombies, errors, empty hostnames). Defense in depth — these are
        # legitimate sitemap rows for non-Proxmox infrastructure or failed
        # discoveries; they get filtered before any cred-resolution attempt.
        if hostname is None or hostname in ("", "unknown") or row.get("status") == "error":
            continue

        try:
            client = await get_proxmox_client(host=hostname, session=session)
        except CredentialNotFoundError:
            # D-10 (Phase 36): row is not a registered Proxmox host -> silently skip
            continue
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            # Resolver-during-cluster-walk failure — surface as unreachable
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

        # Capture (scope, cluster_name) telemetry for the per-row record.
        # Second resolver call hits _HOST_CLUSTER_CACHE in proxmox_api.py
        # (microsecond cost on warm runs).
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
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            unreachable.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": scope,
                "cluster_name": cluster_name,
                "status": "unreachable",
                "error": sanitize_error(exc),
                "scan_timestamp": scan_timestamp,
            })

    # D-07: counts sub-dict mirrors bucket sizes.
    counts: dict[str, int] = {
        "probed_ok": len(probed_ok),
        "unreachable": len(unreachable),
        "unknown": len(unknown),  # always 0 in Phase 37
        "changed": len(changed),  # always 0 in Phase 37
    }
    # scanned = sum across all four buckets (defensive vs. Phase 39 expansion).
    scanned = sum(counts.values())

    # D-04/D-05/D-07: locked envelope key order —
    # status, scan_timestamp, scanned, counts, [guidance,] probed_ok, unreachable, unknown, changed
    response: dict[str, Any] = {
        "status": "success",
        "scan_timestamp": scan_timestamp,
        "scanned": scanned,
        "counts": counts,
    }
    # D-09: top-level guidance present iff scanned == 0 (empty sitemap OR
    # filter narrowed everything out). Single shared text for both cases.
    if scanned == 0:
        response["guidance"] = _EMPTY_SCAN_GUIDANCE

    response["probed_ok"] = probed_ok
    response["unreachable"] = unreachable
    response["unknown"] = unknown
    response["changed"] = changed

    return response
