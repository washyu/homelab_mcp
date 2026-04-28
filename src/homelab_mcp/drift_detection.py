"""Infrastructure drift detection for homelab MCP server.

v1.7 — sitemap is the single source of truth for drift detection. The parallel
baseline cache table was dropped in Phase 36; scan_drift iterates sitemap rows
directly, resolves Proxmox credentials via the get_proxmox_client funnel, and
classifies each row into one of FIVE buckets:

  - probed_ok    — credential resolved, GET /cluster/status returned a list
  - unreachable  — credential resolved, probe raised a network/timeout/value error
                   (Phase 39 DRFT-18 will enrich rows in this bucket with
                   last-seen and decommission/purge pointers)
  - not_eligible — credential resolution itself failed for a structural reason
                   (Phase 38.1: unbound, binding_stale, keyring_desync, degenerate).
                   Replaces the v1.7 silent-skip behavior at the original
                   drift_detection.py:148-149 (Bug O).
  - unknown      — reserved for Phase 39 (DRFT-17): VMs/LXC present on a Proxmox
                   hypervisor but absent from the sitemap. Always [] in Phase 38.1.
  - changed      — reserved for Phase 39 (DRFT-19): sitemap fields differ from
                   current probe values. Depends on Phase 38's fingerprint
                   schema. Always [] in Phase 38.1.

The response envelope is stable: every scan returns the same shape regardless of
filter scope. Filters that match zero rows return status="success" with all five
buckets empty and a top-level "guidance" field pointing to the sitemap CRUD tools.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any, Literal

import aiohttp
import asyncssh

from .database import DatabaseAdapter
from .log_filter import sanitize_error
from .proxmox_api import (
    _HOST_CLUSTER_CACHE,
    CredentialNotFoundError,
    get_proxmox_client,
    get_resolution_telemetry,
    resolve_proxmox_credentials,
)
from .ssh_connection import ssh_connect
from .ssh_tools import _probe_universal_core, resolve_ssh_credentials

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


def _classify_credential_failure(exc: CredentialNotFoundError, binding: str | None) -> str:
    """Map (CredentialNotFoundError, binding-context) → reason enum (D-08).

    Reads the ``.reason_hint`` attribute set by the resolver Tier-0 path
    (Phase 38.1 Wave 2 — proxmox_api.py / ssh_tools.py). When the sitemap
    row's binding column is NULL, the failure is definitionally
    ``"unbound"`` (no UUID was supplied; nothing to be stale or desynced
    about). When binding is non-NULL, prefer the resolver's hint
    (``binding_stale`` for D-11 / ``keyring_desync`` for D-12); fall back
    to ``"binding_stale"`` if the hint is missing — a bound row whose
    resolver raised CredentialNotFoundError must, by elimination, have a
    stale or otherwise-broken binding.
    """
    # If the row had no binding, the failure is definitionally "unbound"
    # — even if a passed-through credential_id (somehow non-None) hinted otherwise.
    if binding is None:
        return "unbound"
    hint = getattr(exc, "reason_hint", None)
    if hint == "binding_stale":
        return "binding_stale"
    if hint == "keyring_desync":
        return "keyring_desync"
    # Default: a bound row whose resolver raised — by elimination the binding
    # is stale (the real Tier-0 resolver always sets reason_hint, but be
    # defensive against fakes / future code paths that don't).
    # WR-08 (Phase 38.1 review): log when we hit the fallback so a future
    # code path that forgets to set reason_hint (or a flaky probe causing
    # the wrong root-cause classification) is detectable in logs. The
    # binding_stale recommendation may not match the true cause.
    logger.warning(
        "Resolver raised CredentialNotFoundError without reason_hint for "
        "bound row (binding=%s). Defaulting to binding_stale; this indicates "
        "a code path that should set reason_hint explicitly.",
        binding,
    )
    return "binding_stale"


def _reason_message(reason: str, hostname: str, credential_type: str) -> str:
    """Human-readable message for the not_eligible bucket (D-08)."""
    if reason == "unbound":
        return (
            f"No {credential_type} credential bound; run "
            f"`homelab-mcp credentials add --type {credential_type} {hostname} <username>` "
            f"to bind."
        )
    if reason == "binding_stale":
        return (
            f"Binding UUID is stale (no matching registry entry); run "
            f"`homelab-mcp credentials unlink {hostname} --type {credential_type}` "
            f"or re-add the credential."
        )
    if reason == "keyring_desync":
        return (
            f"Registry entry exists but keyring secret is missing; re-run "
            f"`homelab-mcp credentials add --type {credential_type} {hostname} <username>` "
            f"to restore."
        )
    if reason == "degenerate":
        return (
            "Sitemap row has degenerate hostname or status=error; run "
            "`homelab-mcp purge_failed_discoveries` to clean up."
        )
    return f"Unknown not_eligible reason: {reason!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 39 helpers (DRFT-17/18/19) — pure functions composed by scan_drift in
# Plans 02 and 03. Each helper is loop-free with respect to bucket-list appends
# (D-11(b)): the existing Phase 38.1 D-15 AST guard ("no `continue` inside
# scan_drift row loop") stays unaffected because these helpers are siblings,
# not nested inside scan_drift.
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_THRESHOLD_DAYS: int = 7


def _missing_threshold_days() -> int:
    """D-02: read ``HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS`` (env), clamp to a
    positive int, default 7. Garbage / negative / zero values fall back to
    ``_DEFAULT_THRESHOLD_DAYS`` rather than crashing the scan (T-39-01).
    """
    raw = os.getenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", str(_DEFAULT_THRESHOLD_DAYS))
    try:
        v = int(raw)
    except (ValueError, TypeError):
        return _DEFAULT_THRESHOLD_DAYS
    return v if v > 0 else _DEFAULT_THRESHOLD_DAYS


def _parse_last_seen(raw: str | None) -> datetime | None:
    """RESEARCH Pitfall 4: sitemap writes ``datetime.now().isoformat()`` (naive,
    no tzinfo). Drift compares against ``datetime.now(UTC)`` (aware). Normalize
    parse to UTC-aware; return ``None`` for missing / malformed values so the
    caller defaults to ``unreachable`` (not ``missing``) — defensive default
    per T-39-02.
    """
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _classify_unreachable(
    row: dict[str, Any],
    exc: Exception,
    threshold_days: int,
    now: datetime,
) -> tuple[Literal["unreachable", "missing"], str]:
    """D-01: classify a probe failure into ``unreachable`` (transient) or
    ``missing`` (host gone — last_seen older than threshold). ``missing`` is
    a sub-status of the unreachable bucket, NOT a 6th bucket.

    The ``missing`` branch's message points the user at the sitemap CRUD
    cleanup tools (``decommission_device`` / ``purge_failed_discoveries``)
    per Phase 37 D-08 conventions. The ``unreachable`` branch's message is
    routed through ``sanitize_error`` (T-39-03) to redact secret-shaped
    substrings.
    """
    parsed = _parse_last_seen(row.get("last_seen"))
    if parsed is not None and (now - parsed).days > threshold_days:
        hostname = row.get("hostname", "")
        message = (
            f"Host last seen {parsed.isoformat()} (>{threshold_days}d ago). "
            f"If decommissioned, run `decommission_device {hostname}` or "
            f"`purge_failed_discoveries` to clean up."
        )
        return ("missing", message)
    return ("unreachable", sanitize_error(exc))


def _diff_fingerprints(
    stored: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """D-08, D-09a: walk two fingerprint dicts and emit per-leaf diffs with
    dotted-path keys. Only leaves present in BOTH sides are diffed —
    capability sub-keys absent from ``current`` (drift never re-probes
    capabilities, D-09) silently skip rather than fire spurious "removed"
    diffs every scan.

    Returns ``{path: {"stored": s, "current": c}}`` for each differing leaf.
    Empty dict when fingerprints are equal.
    """
    diffs: dict[str, dict[str, Any]] = {}

    def _walk(s: Any, c: Any, path: list[str]) -> None:
        if isinstance(s, dict) and isinstance(c, dict):
            # Leaf-level "present in both": only recurse on the key
            # intersection. One-sided keys silently skip (D-09a).
            for k in s.keys() & c.keys():
                _walk(s[k], c[k], path + [k])
        elif s != c:
            diffs[".".join(path)] = {"stored": s, "current": c}

    _walk(stored, current, [])
    return diffs


def _enumerate_unknown_vms(
    cluster_vm_map: dict[str, list[dict[str, Any]]],
    sitemap_hostnames: set[str],  # caller pre-lowercases
    scan_timestamp: str,
) -> list[dict[str, Any]]:
    """D-05/D-06/D-07: build the unknown[] per-VM rows. Caller pre-computes
    ``sitemap_hostnames`` (lowercased) so the helper does no sitemap-row
    iteration of its own — it only flattens the cluster_vm_map output of the
    ``/cluster/resources`` enumeration pre-pass into per-VM rows that don't
    match a known sitemap hostname.

    Match key: case-insensitive ``vm.name == sitemap.hostname`` (D-06). Each
    unmatched VM produces a record with ``hypervisor_hostname / node / vmid /
    vm_type / vm_name / vm_status / scan_timestamp / message``. The message
    points the user at ``discover_and_map`` per Phase 37 D-08.

    Loop-free w.r.t. bucket appends (D-11(b)): the only loop is
    ``for hypervisor, vms in cluster_vm_map.items():`` and its body is a
    single ``unknown.extend(filter(None, ...))``. No ``continue`` statements.
    """
    unknown: list[dict[str, Any]] = []

    def _make_row(vm: dict[str, Any], hypervisor: str) -> dict[str, Any] | None:
        name = (vm.get("name") or "").strip()
        if not name or name.lower() in sitemap_hostnames:
            return None
        return {
            "hypervisor_hostname": hypervisor,
            "node": vm.get("node", ""),
            "vmid": int(vm.get("vmid", 0)),
            "vm_type": vm.get("type", "qemu"),  # qemu | lxc
            "vm_name": name,
            "vm_status": vm.get("status", "unknown"),
            "scan_timestamp": scan_timestamp,
            "message": (
                f"VM '{name}' (vmid={vm.get('vmid')}) on node "
                f"'{vm.get('node')}' not in sitemap; run "
                f"`discover_and_map <ip-or-hostname>` to adopt."
            ),
        }

    for hypervisor, vms in cluster_vm_map.items():
        unknown.extend(filter(None, (_make_row(vm, hypervisor) for vm in vms)))

    return unknown


async def _enumerate_proxmox_vms(
    probed_ok_records: list[dict[str, Any]],
    session: aiohttp.ClientSession | None,
) -> dict[str, list[dict[str, Any]]]:
    """D-05: enumerate VMs/LXC across every probed_ok Proxmox host, deduping by
    ``cluster_name`` so each cluster yields exactly one ``/cluster/resources``
    call per scan. Standalone (non-cluster) hosts hit
    ``/cluster/resources`` keyed by their hostname (no cached cluster name).

    Returns ``{representative_hostname: [vm_record, ...]}``. Filters the
    response to ``type in ("qemu", "lxc")`` only — ``node`` / ``storage`` /
    ``sdn`` records are not VMs (D-07 implicit).

    Enumeration failure on any host (T-39-07): logged via ``sanitize_error`` at
    debug level and returns ``(host, [])``. The host stays in ``probed_ok``;
    just contributes no unknown[] entries (D-10).

    Loop-free w.r.t. bucket appends (D-11(b)): the only mutation is via the
    final ``dict(results)``. The inner ``for record in probed_ok_records:`` is
    target-building, NOT bucket-feeding — it lives outside the AST guard's
    targeted scope (Phase 38.1 D-15 covers ``scan_drift``'s row loop only;
    Phase 39 D-12 keeps the guard scope targeted).
    """
    pairs: list[tuple[str, str | None]] = []
    for record in probed_ok_records:
        hostname = record.get("hostname") or ""
        if not hostname:
            continue  # NOTE: outside scan_drift row loop; outside Phase 38.1 D-15 guard.
        cluster_name = _HOST_CLUSTER_CACHE.get(hostname)
        pairs.append((hostname, cluster_name))

    # Loop-free de-dupe: one entry per (cluster_name OR hostname). When two
    # hosts share a cluster_name, only the second-seen pair survives — both
    # would have produced identical /cluster/resources output anyway.
    targets = list({(c or h): (h, c) for h, c in pairs}.values())

    async def _enum_one(h: str, _c: str | None) -> tuple[str, list[dict[str, Any]]]:
        try:
            client = await get_proxmox_client(host=h, session=session)
            resources = await client.get("/cluster/resources")
            if not isinstance(resources, list):
                return (h, [])
            vms = [r for r in resources if isinstance(r, dict) and r.get("type") in ("qemu", "lxc")]
            return (h, vms)
        except (aiohttp.ClientError, TimeoutError, ValueError, CredentialNotFoundError) as exc:
            logger.debug("VM enum failed for %s: %s", h, sanitize_error(exc))
            return (h, [])

    if not targets:
        return {}
    results = await asyncio.gather(*[_enum_one(h, c) for h, c in targets])
    return dict(results)


async def _bulk_universal_core_probes(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """SSH pre-pass: run universal-core probes against rows with ssh_credential_id.

    Phase 35 D-02 pattern: per-scan ``Semaphore(10)`` + ``asyncio.gather``. Each
    per-host probe is bounded by ``asyncio.wait_for(45s)`` to cap worst-case
    when the remote conn hangs (Pitfall 3 outer-bound). Returns a mapping
    ``{hostname: probe_result_dict}`` where ``probe_result_dict`` is either:

      - ``{"fingerprint": dict, "partial": bool, "timed_out_commands": list}``
        on success, OR
      - ``{"_error": str}`` (sanitize_error-redacted) on failure.

    Rows without ``ssh_credential_id`` are filtered out by the caller and do
    NOT appear in the result. The whole call is wrapped in
    ``asyncio.wait_for(120s)`` by ``scan_drift`` per Phase 39 D-04a.

    Loop-free w.r.t. bucket appends (D-11(b)): only loop is a list-comprehension
    over rows; per-row work happens inside ``_probe_one`` (no ``continue``).
    """
    semaphore = asyncio.Semaphore(10)

    async def _probe_one(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        hostname = row.get("hostname", "")
        binding = row.get("ssh_credential_id")
        # Caller filters by ssh_credential_id, but be defensive against
        # external callers that don't.
        if binding is None:
            return (hostname, {"_error": "no_ssh_credential_id"})
        async with semaphore:
            try:
                creds = resolve_ssh_credentials(hostname, credential_id=binding)
                async with await ssh_connect(
                    hostname=creds.hostname,
                    username=creds.username,
                    port=creds.port,
                    password=creds.password,
                    key_path=creds.key_path,
                ) as conn:
                    timed_out: list[str] = []
                    fp = await asyncio.wait_for(
                        _probe_universal_core(conn, timed_out),
                        timeout=45.0,
                    )
                    return (
                        hostname,
                        {
                            "fingerprint": fp,
                            "partial": bool(timed_out),
                            "timed_out_commands": timed_out,
                        },
                    )
            except (asyncssh.Error, OSError, TimeoutError, ValueError) as exc:
                return (hostname, {"_error": sanitize_error(exc)})
            except Exception as exc:  # CredentialNotFoundError + defensive
                # CredentialNotFoundError is a sibling of Exception (raised by
                # resolve_ssh_credentials); catching here keeps drift's SSH
                # pre-pass non-fatal when a row's binding is stale or desynced.
                return (hostname, {"_error": sanitize_error(exc)})
        # Defensive fallthrough — should never execute (try-block returns or
        # an except branch returns). Present so mypy can prove all paths return.
        return (hostname, {"_error": "unreachable_fallthrough"})

    pairs = await asyncio.gather(
        *[_probe_one(r) for r in rows if r.get("ssh_credential_id")],
        return_exceptions=False,
    )
    return dict(pairs)


async def scan_drift(
    session: aiohttp.ClientSession | None,
    db_adapter: DatabaseAdapter,
    node: str | None = None,
    vm_type: str = "all",
) -> dict[str, Any]:
    """Scan for infrastructure drift against the sitemap (Phase 38.1 5-bucket shape).

    Iterates sitemap rows and classifies each one into exactly one of five
    buckets: probed_ok, unreachable, not_eligible, unknown, changed. The
    ``unknown`` and ``changed`` buckets are reserved for Phase 39
    (DRFT-17/19) and are always empty in Phase 38.1 — they exist in the
    response so client code can iterate without defensive
    ``dict.get(..., [])`` checks. The ``not_eligible`` bucket replaces
    the v1.7 silent-skip behavior (Bug O) — every credential-resolution
    failure now produces a row with a reason enum and recovery message.

    Filter semantics (Phase 37 DRFT-13):
      - node: exact hostname match against sitemap rows (no wildcards, no
        case folding). Filter applies BEFORE the degenerate-row routing.
        A no-match returns status="success" with all five buckets empty
        and a top-level "guidance" field — never status="error".
      - vm_type: reserved for Phase 39 per-VM detection; currently filters
        at the host level only (no-op until per-VM enumeration ships).

    For each sitemap row that survives the filter:
      0. Phase 38.1 D-15/D-17 (Bug O fix): CredentialNotFoundError no longer
         skips silently — routes to ``not_eligible`` with reason enum (D-08).
         Degenerate rows (hostname None/''/'unknown' or status='error')
         also route to ``not_eligible`` with reason="degenerate".
      1. Resolve Proxmox credentials via get_proxmox_client, threading
         ``credential_id=row.get('proxmox_credential_id')`` (Phase 38.1 R6).
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
        vm_type: Reserved for Phase 39 per-VM detection; inert in Phase 38.1.

    Returns:
        {
            "status": "success",
            "scan_timestamp": ISO-8601 UTC,
            "scanned": int,                    # sum across all five buckets
            "counts": {
                "probed_ok": int,
                "unreachable": int,
                "not_eligible": int,           # Phase 38.1 R7
                "unknown": int,                # Phase 39 DRFT-17: per-VM unmatched count
                "changed": int,                # always 0 in Phase 38.1
            },
            "guidance": str,                   # PRESENT only when scanned == 0
            "probed_ok": [<per-row record>, ...],
            "unreachable": [<per-row record>, ...],
            "not_eligible": [<per-row record>, ...],   # Phase 38.1 R7
            "unknown": [<per-VM record>, ...],         # Phase 39 DRFT-17 (D-07 shape)
            "changed": [],                     # reserved for Phase 39 DRFT-19
        }

    Per-VM record shape (unknown, Phase 39 D-07):
        {
            "hypervisor_hostname": str,        # Proxmox host that reported the VM
            "node": str,                       # Proxmox node name (cluster member)
            "vmid": int,
            "vm_type": "qemu" | "lxc",
            "vm_name": str,                    # Proxmox-reported `name` field
            "vm_status": str,                  # e.g., "running" | "stopped"
            "scan_timestamp": str,             # same value across all records
            "message": str,                    # discover_and_map adoption pointer
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

    Per-row record shape (not_eligible, Phase 38.1 D-08):
        {
            "hostname": str,                   # may be empty string for degenerate rows
            "connection_ip": str,
            "scope": "unknown",
            "reason": "unbound" | "binding_stale" | "keyring_desync" | "degenerate",
            "message": str,                    # human-readable, includes recovery command
        }
    """
    scan_timestamp = datetime.now(UTC).isoformat()
    probed_ok: list[dict[str, Any]] = []
    unreachable: list[dict[str, Any]] = []
    not_eligible: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []  # Phase 39 DRFT-17: populated by post-loop enumeration
    changed: list[dict[str, Any]] = []  # reserved for Phase 39 DRFT-19

    rows = db_adapter.get_all_devices()

    # D-01: hostname exact-match filter applied BEFORE degenerate-row routing.
    # node=None means "no filter"; non-None reduces rows to exact matches only.
    # No-match (zero remaining rows) is a successful empty-result, NOT an error.
    if node is not None:
        rows = [row for row in rows if row.get("hostname") == node]

    # Phase 39 D-04/D-04a: SSH pre-pass for universal-core fingerprint probes.
    # Bulk Semaphore(10) + gather (Phase 35 D-02 pattern) bounded by
    # asyncio.wait_for(120.0) — Phase 35 D-02 ceiling per CONTEXT D-04a-narrowed.
    # Per-host probe bounded internally by wait_for(45.0); per-probe by
    # _run_with_timeout(10.0). On outer-timeout, proceed with empty probe
    # results so the row loop still classifies every row.
    try:
        ssh_probe_results: dict[str, dict[str, Any]] = await asyncio.wait_for(
            _bulk_universal_core_probes(rows),
            timeout=120.0,
        )
    except TimeoutError:
        logger.warning(
            "scan_drift: SSH pre-pass exceeded 120s; proceeding with empty probe results"
        )
        ssh_probe_results = {}
    # Read in Plan 03 Task 3: per-row diff classification consults
    # ``ssh_probe_results.get(hostname)`` inside the row loop's success branch.
    _ = ssh_probe_results  # noqa: F841 — wired by next commit

    for row in rows:
        hostname = row.get("hostname")
        binding = row.get("proxmox_credential_id")  # Phase 38.1 R6

        # D-17: degenerate rows route to not_eligible (no continue — D-15 invariant).
        # These are legitimate sitemap rows for failed discoveries / non-Proxmox
        # infrastructure. Routing to not_eligible (instead of silently skipping)
        # makes the row visible to the user with a recovery pointer.
        if hostname is None or hostname in ("", "unknown") or row.get("status") == "error":
            not_eligible.append(
                {
                    "hostname": hostname or "",
                    "connection_ip": row.get("connection_ip", ""),
                    "scope": "unknown",
                    "reason": "degenerate",
                    "message": _reason_message("degenerate", hostname or "<empty>", "proxmox"),
                }
            )
        else:
            # Phase 38.1 R6: pass binding UUID to resolver. When binding is None,
            # resolver falls through to Tier-1/Tier-2 (cluster walk handles
            # cluster-served rows per D-09).
            try:
                client = await get_proxmox_client(
                    host=hostname,
                    session=session,
                    credential_id=binding,
                )
            except CredentialNotFoundError as exc:
                reason = _classify_credential_failure(exc, binding)
                not_eligible.append(
                    {
                        "hostname": hostname,
                        "connection_ip": row.get("connection_ip", ""),
                        "scope": "unknown",
                        "reason": reason,
                        "message": _reason_message(reason, hostname, "proxmox"),
                    }
                )
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                # Resolver-during-cluster-walk failure — surface as unreachable
                unreachable.append(
                    {
                        "hostname": hostname,
                        "connection_ip": row.get("connection_ip", ""),
                        "scope": "unknown",
                        "cluster_name": None,
                        "status": "unreachable",
                        "error": sanitize_error(exc),
                        "scan_timestamp": scan_timestamp,
                    }
                )
            else:
                # WR-04 (Phase 38.1 review): use the resolution telemetry cache
                # populated by resolve_proxmox_credentials on the just-completed
                # successful resolution. Avoids re-invoking the resolver (which
                # on flaky keyring backends could fail the second call and
                # mis-route a perfectly reachable host into not_eligible).
                # Fall back to a fresh resolver call only when the cache is
                # cold (defensive — should not happen since get_proxmox_client
                # just populated it via the same code path).
                telemetry = get_resolution_telemetry(hostname, binding)
                resolver_exc: CredentialNotFoundError | None = None
                if telemetry is not None:
                    scope, cluster_name = telemetry
                else:
                    try:
                        _token, scope, cluster_name = await resolve_proxmox_credentials(
                            hostname,
                            session=session,
                            credential_id=binding,
                        )
                    except CredentialNotFoundError as exc:
                        resolver_exc = exc
                if resolver_exc is not None:
                    # Defensive — should not happen after get_proxmox_client succeeded.
                    # Route to not_eligible (NOT continue) per D-15 invariant.
                    reason = _classify_credential_failure(resolver_exc, binding)
                    not_eligible.append(
                        {
                            "hostname": hostname,
                            "connection_ip": row.get("connection_ip", ""),
                            "scope": "unknown",
                            "reason": reason,
                            "message": _reason_message(reason, hostname, "proxmox"),
                        }
                    )
                else:
                    try:
                        status = await client.get("/cluster/status")
                        if not isinstance(status, list):
                            raise ValueError(f"unexpected /cluster/status payload type: {type(status).__name__}")
                        probed_ok.append(
                            {
                                "hostname": hostname,
                                "connection_ip": row.get("connection_ip", ""),
                                "scope": scope,
                                "cluster_name": cluster_name,
                                "status": "probed-ok",
                                "error": None,
                                "scan_timestamp": scan_timestamp,
                            }
                        )
                    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                        unreachable.append(
                            {
                                "hostname": hostname,
                                "connection_ip": row.get("connection_ip", ""),
                                "scope": scope,
                                "cluster_name": cluster_name,
                                "status": "unreachable",
                                "error": sanitize_error(exc),
                                "scan_timestamp": scan_timestamp,
                            }
                        )

    # Phase 39 DRFT-17 (D-05/D-06/D-07): enumerate unknown VMs across every
    # probed_ok host. Cluster-scope rows that share a cluster_name de-dupe to
    # one /cluster/resources call total; standalone hosts hit the same endpoint
    # keyed by themselves. Per D-10 the unknown[] surface is parallel to host
    # buckets — a probed_ok host can still emit unknown VM rows, and an
    # enumeration failure on the host does not move it out of probed_ok.
    sitemap_hostnames: set[str] = {
        (row.get("hostname") or "").lower()
        for row in rows
        if row.get("hostname")
    }
    cluster_vm_map = await _enumerate_proxmox_vms(probed_ok, session)
    unknown = _enumerate_unknown_vms(cluster_vm_map, sitemap_hostnames, scan_timestamp)

    # D-07: counts sub-dict mirrors bucket sizes.
    counts: dict[str, int] = {
        "probed_ok": len(probed_ok),
        "unreachable": len(unreachable),
        "not_eligible": len(not_eligible),
        "unknown": len(unknown),  # Phase 39 DRFT-17: per-VM unmatched count
        "changed": len(changed),  # always 0 in Phase 38.1
    }
    # scanned = sum across all five buckets (defensive vs. Phase 39 expansion).
    scanned = sum(counts.values())

    # D-04/D-05/D-07 (Phase 37) + Phase 38.1 D-08: locked envelope key order —
    # status, scan_timestamp, scanned, counts, [guidance,] probed_ok, unreachable,
    #   not_eligible, unknown, changed
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
    response["not_eligible"] = not_eligible
    response["unknown"] = unknown
    response["changed"] = changed

    return response
