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
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
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
from .ssh_tools import _probe_universal_core, resolve_ssh_for_sitemap_row

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


def _parse_last_seen(raw: str | datetime | None) -> datetime | None:
    """RESEARCH Pitfall 4: sitemap writes ``datetime.now().isoformat()`` (naive,
    no tzinfo). Drift compares against ``datetime.now(UTC)`` (aware). Normalize
    parse to UTC-aware; return ``None`` for missing / malformed values so the
    caller defaults to ``unreachable`` (not ``missing``) — defensive default
    per T-39-02.

    WR-01: accepts ``datetime`` objects directly so Postgres adapters that
    type-map ``last_seen`` to a ``datetime`` (rather than the raw ISO
    string SQLite returns) are normalized through the same UTC-coercion
    path. The downstream ``record["last_seen"]`` field is then guaranteed
    to flow through ``isoformat()`` regardless of adapter.

    WR-03 (Phase 39 review): the unconditional ``replace(tzinfo=UTC)`` is
    a known imprecision. ``sitemap.py`` writes
    ``datetime.now().isoformat()`` — *local* wall-clock time, no offset
    suffix. On a server whose local time is not UTC, a 6-hour-old record
    looks 6 hours into the future or 30 hours in the past depending on
    direction; on a host that crosses a DST boundary the offset shifts
    by 1 hour mid-scan. The practical effect: a configured threshold of
    7 days has a true tolerance of "7 days +/- machine TZ offset" (and
    similarly for any other threshold), so a 1-day threshold can take
    up to 47 hours to fire on a UTC-12 server.

    The proper fix is in sitemap.py — switch the writer to
    ``datetime.now(UTC).isoformat()`` (a follow-up phase) and treat naive
    timestamps as malformed here. Until that ships, operators relying on
    sub-day precision should run the server in UTC.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
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
    # WR-07 (Phase 39 review): use a full timedelta comparison rather than
    # ``(now - parsed).days``. ``timedelta.days`` floors to integer days,
    # so a host last seen exactly 7 days + 23 hours ago yields ``.days == 7``
    # and the boundary check ``7 > 7`` is False — the host stays
    # ``unreachable`` for nearly an extra day. Operators with
    # ``HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS=1`` saw promotion delays of
    # up to 47 hours. Comparing the raw ``timedelta`` objects gives
    # second-level precision instead of day-floor.
    if parsed is not None and (now - parsed) > timedelta(days=threshold_days):
        hostname = row.get("hostname", "")
        message = (
            f"Host last seen {parsed.isoformat()} (>{threshold_days}d ago). "
            f"If decommissioned, run `decommission_device {hostname}` or "
            f"`purge_failed_discoveries` to clean up."
        )
        return ("missing", message)
    return ("unreachable", sanitize_error(exc))


_MISSING = object()  # WR-05 sentinel for "key not present on this side"


def _diff_fingerprints(
    stored: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """D-08, D-09a: walk two fingerprint dicts and emit per-leaf diffs with
    dotted-path keys.

    WR-05 (Phase 39 review): drift surfaces ASYMMETRIC one-sided keys.
      - keys present in ``stored`` but absent from ``current``  → SUPPRESSED
        (per D-09a — drift never re-probes capabilities, so a missing
        capability sub-key is expected, not a drift signal)
      - keys present in ``current`` but absent from ``stored``  → EMITTED
        (a freshly-added probe field, e.g., a host that just got dpkg
        installed and now reports ``package_fingerprint``, IS a drift
        signal — the user needs to know the host's capability surface
        grew so they can re-run ``configure_host_fingerprint``)
      - keys present in BOTH with differing values                → EMITTED

    The previous implementation walked only ``stored.keys() & current.keys()``,
    which suppressed BOTH directions and missed legitimate
    capability-additions on the first scan after a host's probe surface
    grew.

    Returns ``{path: {"stored": s, "current": c}}`` for each emitted leaf.
    For current-only keys, ``stored`` is ``None`` in the emitted record
    (clients can detect the asymmetric add via ``"stored": None``).
    Empty dict when fingerprints are equal.
    """
    diffs: dict[str, dict[str, Any]] = {}

    def _walk(s: Any, c: Any, path: list[str]) -> None:
        if isinstance(s, dict) and isinstance(c, dict):
            # WR-05: walk the union of keys. For each key:
            #   - present in stored only  -> suppress (D-09a capability drop)
            #   - present in current only -> recurse with stored=_MISSING
            #     so the leaf branch emits stored=None
            #   - present in both         -> recurse normally
            # AST guard scope (Phase 39 D-11(b)) forbids ``continue`` in
            # this helper body, so use a comprehension that filters
            # out the suppressed case before iterating.
            keys_to_walk = [k for k in s.keys() | c.keys() if k in c]
            for k in keys_to_walk:
                _walk(s.get(k, _MISSING), c[k], path + [k])
        elif s is _MISSING:
            # WR-05: current-only leaf — emit with stored=None so clients
            # can detect the asymmetric add. Equality check is moot
            # because there's no stored value.
            diffs[".".join(path)] = {"stored": None, "current": c}
        elif c is _MISSING:
            # Defensive — comprehension above strips current-missing keys
            # at the dict level, so this branch only fires if a non-dict
            # call passes _MISSING for current. Suppress per D-09a.
            return
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

    BL-03: when ``_HOST_CLUSTER_CACHE`` is cold (e.g., first scan after a
    server restart), ``_enumerate_proxmox_vms`` cannot dedupe per cluster
    and instead enumerates ``/cluster/resources`` once per host, producing
    N copies of every VM in an N-node cluster. Defend at the consumer by
    deduping on ``(vm_name_lower, vmid)``. The closure-captured ``seen``
    set keeps this loop-free with respect to ``continue`` (locked by the
    Phase 39 D-11(b) AST guard) — duplicates are suppressed by
    ``_make_row`` returning ``None`` to ``filter(None, ...)``.
    """
    unknown: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, int]] = set()

    def _make_row(vm: dict[str, Any], hypervisor: str) -> dict[str, Any] | None:
        name = (vm.get("name") or "").strip()
        if not name or name.lower() in sitemap_hostnames:
            return None
        # BL-02: guard against malformed vmid (non-numeric, None, list, ...).
        # Without this, a single garbage VM record raises TypeError/ValueError
        # out of the generator and aborts the whole scan_drift call —
        # violating the D-10 contract that enumeration failures don't move
        # hosts out of their bucket.
        try:
            vmid = int(vm.get("vmid", 0))
        except (ValueError, TypeError):
            logger.debug(
                "Skipping malformed vmid in /cluster/resources for %s: %r",
                hypervisor,
                vm.get("vmid"),
            )
            return None
        # BL-03 + WR-A: dedupe by (hypervisor, vm_name_lower, vmid). The
        # cold-cache N-copy case (BL-03) collapses because all N copies
        # come from the SAME hypervisor representative — caller dedupes
        # ``_enumerate_proxmox_vms`` keys by (cluster_name OR hostname),
        # so cluster_vm_map carries one entry per cluster, not per node.
        # Including ``hypervisor`` in the dedupe key prevents WR-A:
        # multi-cluster homelabs where two unrelated VMs in different
        # clusters legitimately share both name and vmid (Proxmox vmids
        # are only unique within a cluster, not across) used to collapse
        # to a single unknown[] entry. With the hypervisor component,
        # each distinct cluster surfaces its own row.
        key = (hypervisor, name.lower(), vmid)
        if key in seen_keys:
            return None
        seen_keys.add(key)
        return {
            "hypervisor_hostname": hypervisor,
            "node": vm.get("node", ""),
            "vmid": vmid,
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
    host_to_binding: Mapping[str, str | None],
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

    Phase 39.1 R6-regression closure: ``host_to_binding`` is the
    hostname→credential_id side-map built by ``scan_drift`` from
    ``row.get('proxmox_credential_id')``. ``_enum_one`` threads it as
    ``credential_id=`` into ``get_proxmox_client(...)`` so the Phase 38.1 R6
    binding contract holds inside the VM-enumeration helper too. ``None``
    values are legitimate (cluster-served rows fall through to Tier-1/Tier-2
    walk, matching scan_drift row-loop semantics at lines 744-752).
    """
    pairs: list[tuple[str, str, str | None]] = []
    for record in probed_ok_records:
        hostname = record.get("hostname") or ""
        if not hostname:
            continue  # NOTE: outside scan_drift row loop; outside Phase 38.1 D-15 guard.
        connection_ip = record.get("connection_ip") or hostname
        cluster_name = _HOST_CLUSTER_CACHE.get(hostname)
        pairs.append((hostname, connection_ip, cluster_name))

    # Loop-free de-dupe: one entry per (cluster_name OR hostname). When two
    # hosts share a cluster_name, only the second-seen triple survives — both
    # would have produced identical /cluster/resources output anyway. The
    # dedupe key is (cluster_name OR hostname) — NOT connection_ip — to keep
    # the cluster-cache invariant: hostname is the canonical resolver/cache key.
    targets = list({(c or h): (h, ci, c) for h, ci, c in pairs}.values())

    async def _enum_one(h: str, dial_host: str, _c: str | None) -> tuple[str, list[dict[str, Any]]]:
        binding = host_to_binding.get(h)  # None for cluster-served rows
        try:
            # Phase 41-06 WR-01: pair host=h (resolver/cache key — matches
            # _HOST_CLUSTER_CACHE.get(hostname) above and host_to_binding map
            # keys) with dial_host (carried as connection_ip from the
            # probed_ok record). Plan 41-04 only addressed the ssh_connect
            # dial site in _probe_one and scan_drift's get_proxmox_client; the
            # cluster-resources enumeration was missed. Plan 41-06 closes the
            # gap so cluster-dedupe survives hostname != connection_ip rows.
            client = await get_proxmox_client(
                host=h,
                dial_host=dial_host,
                session=session,
                credential_id=binding,
            )
            resources = await client.get("/cluster/resources")
            if not isinstance(resources, list):
                return (h, [])
            vms = [r for r in resources if isinstance(r, dict) and r.get("type") in ("qemu", "lxc")]
            return (h, vms)
        except (aiohttp.ClientError, TimeoutError, ValueError, CredentialNotFoundError) as exc:
            # BL-04: enumeration failures must be visible to operators. The
            # host stays in probed_ok (D-10), unknown[] gains no entries from
            # this host, and there's otherwise no observable signal that
            # VM-level drift detection silently broke. sanitize_error redacts
            # secrets so warning-level logging is safe.
            logger.warning(
                "VM enumeration failed for %s; unknown[] will not include VMs from this host: %s",
                h,
                sanitize_error(exc),
            )
            return (h, [])

    if not targets:
        return {}
    results = await asyncio.gather(*[_enum_one(h, ci, c) for h, ci, c in targets])
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

    BL-01: the result map is keyed on ``hostname``, so two rows that
    legitimately share a hostname (migration overlap, stale-row purge race,
    same host discovered under two connection_ips, or a degenerate row with
    hostname="") collapse into a single entry whose value is whichever
    probe finished last. The row loop in ``scan_drift`` then attributes
    that probe to BOTH rows, which produces phantom ``changed[]`` entries
    when row A's stored fingerprint is diffed against row B's probe
    result. Dedupe on hostname here so duplicate rows are silently dropped
    rather than overwriting each other.
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
                # Phase 41 Bug AA: route through the shared row-binding-aware
                # helper so Plan 05's AST guard locks the shared-helper
                # invariant on the drift side.
                creds, matched_row = resolve_ssh_for_sitemap_row(hostname)
                # Phase 41 Bug V (Pitfall 4): dial row.connection_ip when
                # truthy; fall back to hostname when empty/None or row missing.
                dial_target = (matched_row.get("connection_ip") if matched_row else None) or hostname
                async with await ssh_connect(
                    hostname=dial_target,
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
        # Phase 41-06 WR-04: removed the unreachable belt-and-braces raise.
        # The bare ``except Exception`` above catches every exception type;
        # any future refactor that narrows it must add its own logged
        # sentinel-return path here, not rely on a structurally-unreachable
        # raise (would crash inside asyncio.gather(return_exceptions=False)
        # and abort the entire scan, defeating D-10). Sentinel return below
        # is required only for mypy's exhaustiveness check; runtime is
        # unreachable per the comment above.
        return (hostname, {"_error": "probe_one_unreachable_fallthrough"})

    # BL-01: dedupe by hostname BEFORE gather. The probe map is keyed on
    # hostname; if two rows share a hostname, only one probe survives in
    # the result dict, which then gets attributed to both rows in the
    # scan_drift row loop (phantom changed[] entries). Skip duplicates.
    # Empty/None hostnames are dropped here too — they would all collide
    # on the same "" key.
    seen_hostnames: set[str] = set()
    eligible: list[dict[str, Any]] = []
    for r in rows:
        h = r.get("hostname") or ""
        if not h or not r.get("ssh_credential_id") or h in seen_hostnames:
            continue
        seen_hostnames.add(h)
        eligible.append(r)
    pairs = await asyncio.gather(
        *[_probe_one(r) for r in eligible],
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

    Per-row record shape (probed_ok and unreachable.status == "unreachable",
    unchanged from Phase 36 D-02 — 7 canonical keys):
        {
            "hostname": str,
            "connection_ip": str,
            "scope": "node" | "cluster" | "unknown",
            "cluster_name": str | None,
            "status": "probed-ok" | "unreachable",
            "error": str | None,               # sanitize_error() on unreachable
            "scan_timestamp": str,             # same value across all records
        }

    Per-row record shape extension (unreachable.status == "missing", Phase 39
    DRFT-18 — adds two keys to the 7-key base for a total of 9 keys):
        {
            ... (all 7 keys above), plus:
            "last_seen": str | None,           # ISO-8601 string; None when
                                               #   row's last_seen was unparseable
            "message": str,                    # human-readable, includes
                                               #   decommission_device /
                                               #   purge_failed_discoveries pointer
        }
    Clients iterating the unreachable[] bucket should branch on
    ``record.get("status")`` to distinguish the two shapes; the 7-key
    "unreachable" sub-shape remains stable for backward compatibility,
    and the 9-key "missing" sub-shape is additive (does not remove or
    rename existing keys). WR-02 (Phase 39 review): drove this docstring
    correction — the original Phase 36 D-02 7-key contract did not
    acknowledge the conditional missing-extension shipped in Phase 39.

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
    #
    # WR-08: degenerate rows (hostname None/''/'unknown' or status=='error')
    # must be filtered out BEFORE the bulk probe call. Otherwise a stale
    # ssh_credential_id on a degenerate row triggers an unintended SSH
    # connect attempt — worst case to a wrong host (the credential's stored
    # hostname rather than the row's empty hostname), best case extra
    # latency equal to the SSH connection timeout. The row loop below still
    # routes these rows to not_eligible (D-17); we just don't probe them.
    ssh_eligible_rows = [
        r
        for r in rows
        if r.get("hostname")
        and r.get("hostname") not in ("", "unknown")
        and r.get("status") != "error"
        and r.get("ssh_credential_id")
    ]
    try:
        ssh_probe_results: dict[str, dict[str, Any]] = await asyncio.wait_for(
            _bulk_universal_core_probes(ssh_eligible_rows),
            timeout=120.0,
        )
    except TimeoutError:
        logger.warning("scan_drift: SSH pre-pass exceeded 120s; proceeding with empty probe results")
        ssh_probe_results = {}

    for row in rows:
        hostname = row.get("hostname")
        binding = row.get("proxmox_credential_id")  # Phase 38.1 R6
        # WR-06 (Phase 39 review): reset scope / cluster_name explicitly
        # at the top of each iteration. Python doesn't scope variables
        # to ``for`` blocks, so without this reset a future refactor
        # that forgets to re-bind these names in the resolver-success
        # ``else`` branch could attach the *previous* row's cluster_name
        # to the current row's record. Make the per-iteration default
        # audible.
        scope: str = "unknown"
        cluster_name: str | None = None

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
                # Phase 41-06 CR-01: keep hostname as the canonical resolver/cache
                # key (matches _HOST_CLUSTER_CACHE writes + the
                # get_resolution_telemetry(hostname, binding) lookup below);
                # pass connection_ip as the TCP dial target only via dial_host=.
                # Plan 41-04 had set host=connection_ip, forcing
                # resolve_proxmox_credentials to write the telemetry cache as
                # (connection_ip, binding) while the very next
                # get_resolution_telemetry(hostname, binding) call read by
                # hostname — guaranteed miss when hostname != connection_ip,
                # defeating the WR-04 double-resolve guard.
                dial_host = row.get("connection_ip") or hostname
                client = await get_proxmox_client(
                    host=hostname,
                    dial_host=dial_host,
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
                # OR missing per Phase 39 D-01/D-02 _classify_unreachable.
                substatus, classify_msg = _classify_unreachable(row, exc, _missing_threshold_days(), datetime.now(UTC))
                record: dict[str, Any] = {
                    "hostname": hostname,
                    "connection_ip": row.get("connection_ip", ""),
                    "scope": "unknown",
                    "cluster_name": None,
                    "status": substatus,
                    "error": sanitize_error(exc),
                    "scan_timestamp": scan_timestamp,
                }
                if substatus == "missing":
                    # WR-01: normalize last_seen to ISO-8601 string. SQLite
                    # adapters return strings, but Postgres adapters may
                    # return datetime objects depending on type-mapping.
                    # The drift response is downstream JSON-serialized;
                    # mixed types break clients that assume the field is
                    # always a string.
                    # WR-E (Phase 39 re-review): when _parse_last_seen
                    # fails, coerce the raw adapter value to ``str(...)``
                    # rather than returning it as-is. The fallback used
                    # to emit whatever type the adapter returned —
                    # integer epoch timestamps, ``date`` objects, vendor-
                    # format strings — and downstream JSON encoders
                    # either serialize them as numbers (breaking string-
                    # expecting clients) or fail outright (date objects
                    # are not JSON-encodable). Stringify here so JSON
                    # serialization is total regardless of adapter.
                    parsed = _parse_last_seen(row.get("last_seen"))
                    raw_last_seen = row.get("last_seen")
                    if parsed is not None:
                        record["last_seen"] = parsed.isoformat()
                    elif raw_last_seen is not None:
                        record["last_seen"] = str(raw_last_seen)
                    else:
                        record["last_seen"] = None
                    record["message"] = classify_msg
                unreachable.append(record)
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
                # WR-C (Phase 39 re-review): the resolver's cluster-walk path
                # can raise aiohttp.ClientError / TimeoutError / ValueError as
                # well as CredentialNotFoundError. The prior except clause
                # caught only the credential variant, so any transient
                # network/timeout failure on the fallback path would
                # propagate uncaught all the way out of scan_drift,
                # aborting the entire scan and losing every other row's
                # classification (the BL-02 contract). Widen the except to
                # cover the same exception family that the surrounding
                # /cluster/status block handles, and route to unreachable
                # via a parallel sentinel — keeping the D-15 "no continue
                # in row loop" invariant.
                transient_resolver_exc: aiohttp.ClientError | TimeoutError | ValueError | None = None
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
                    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                        transient_resolver_exc = exc
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
                elif transient_resolver_exc is not None:
                    # WR-C: transient resolver-fallback failure — treat
                    # as if /cluster/status itself had failed. Route to
                    # unreachable (with possible 'missing' promotion) so
                    # the row remains classified rather than crashing
                    # the scan. cluster_name is unknown here because the
                    # resolver didn't complete; record None.
                    substatus_r, classify_msg_r = _classify_unreachable(
                        row, transient_resolver_exc, _missing_threshold_days(), datetime.now(UTC)
                    )
                    record_resolver: dict[str, Any] = {
                        "hostname": hostname,
                        "connection_ip": row.get("connection_ip", ""),
                        "scope": "unknown",
                        "cluster_name": None,
                        "status": substatus_r,
                        "error": sanitize_error(transient_resolver_exc),
                        "scan_timestamp": scan_timestamp,
                    }
                    if substatus_r == "missing":
                        # WR-01 + WR-E: normalize last_seen and stringify
                        # the fallback so JSON serialization cannot fail.
                        parsed_r = _parse_last_seen(row.get("last_seen"))
                        raw_last_seen_r = row.get("last_seen")
                        if parsed_r is not None:
                            record_resolver["last_seen"] = parsed_r.isoformat()
                        elif raw_last_seen_r is not None:
                            record_resolver["last_seen"] = str(raw_last_seen_r)
                        else:
                            record_resolver["last_seen"] = None
                        record_resolver["message"] = classify_msg_r
                    unreachable.append(record_resolver)
                else:
                    try:
                        status = await client.get("/cluster/status")
                        if not isinstance(status, list):
                            raise ValueError(f"unexpected /cluster/status payload type: {type(status).__name__}")
                        # Phase 39 DRFT-19 (D-08/D-09a/D-10): consult SSH
                        # pre-pass result; if a non-empty diff vs stored
                        # fingerprint exists, route to changed[]; otherwise
                        # probed_ok[]. D-04b: drift never updates the stored
                        # fingerprint — diff is read-only.
                        probe = ssh_probe_results.get(hostname or "", {})
                        stored_fp = row.get("fingerprint", {}) or {}
                        current_fp = probe.get("fingerprint", {}) if "fingerprint" in probe else {}
                        # WR-D (Phase 39 re-review): when the SSH pre-pass
                        # records ``_error`` for a host that has a stored
                        # fingerprint, drift comparison silently degrades
                        # to "no diff" and the host lands in probed_ok
                        # indistinguishable from a clean match. This
                        # quietly disables drift detection on every
                        # subsequent scan until SSH is fixed. The
                        # 7-key probed_ok shape is locked by the
                        # ``test_per_row_record_shape_preserved_for_probed_ok``
                        # AST contract so we cannot expand the record
                        # itself; surface the failure to operators via
                        # warning-level logging instead. ``sanitize_error``
                        # has already redacted secrets in the probe map.
                        if stored_fp and "_error" in probe and "fingerprint" not in probe:
                            logger.warning(
                                "SSH probe failed for %r with a non-empty stored "
                                "fingerprint; drift comparison skipped and host "
                                "routes to probed_ok with no diff signal. SSH "
                                "error: %s",
                                hostname,
                                probe.get("_error"),
                            )
                        diff = _diff_fingerprints(stored_fp, current_fp) if (stored_fp and current_fp) else {}
                        if diff:
                            changed.append(
                                {
                                    "hostname": hostname,
                                    "connection_ip": row.get("connection_ip", ""),
                                    "scope": scope,
                                    "cluster_name": cluster_name,
                                    "status": "changed",
                                    "changed_fields": diff,
                                    "scan_timestamp": scan_timestamp,
                                    "message": (
                                        "Universal-core fingerprint changed; "
                                        "re-run `configure_host_fingerprint` to "
                                        "refresh capability tracking, then "
                                        "`discover_and_map` to accept."
                                    ),
                                }
                            )
                        else:
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
                        # Phase 39 DRFT-18 (D-01/D-02): classify unreachable
                        # vs missing sub-status using last_seen + threshold.
                        substatus, classify_msg = _classify_unreachable(
                            row, exc, _missing_threshold_days(), datetime.now(UTC)
                        )
                        record_inner: dict[str, Any] = {
                            "hostname": hostname,
                            "connection_ip": row.get("connection_ip", ""),
                            "scope": scope,
                            "cluster_name": cluster_name,
                            "status": substatus,
                            "error": sanitize_error(exc),
                            "scan_timestamp": scan_timestamp,
                        }
                        if substatus == "missing":
                            # WR-01 + WR-E: normalize last_seen to ISO-8601
                            # string. See sibling site above for full
                            # rationale — DB adapters can return datetime
                            # objects, integer epochs, or date objects;
                            # stringifying the parse-fail fallback ensures
                            # JSON serialization is total regardless of
                            # adapter type-mapping.
                            parsed = _parse_last_seen(row.get("last_seen"))
                            raw_last_seen_inner = row.get("last_seen")
                            if parsed is not None:
                                record_inner["last_seen"] = parsed.isoformat()
                            elif raw_last_seen_inner is not None:
                                record_inner["last_seen"] = str(raw_last_seen_inner)
                            else:
                                record_inner["last_seen"] = None
                            record_inner["message"] = classify_msg
                        unreachable.append(record_inner)

    # Phase 39 DRFT-17 (D-05/D-06/D-07): enumerate unknown VMs across every
    # successfully-probed host (probed_ok OR changed — Phase 39 D-10 keeps
    # unknown[] as a parallel per-VM surface independent of host bucket).
    # Cluster-scope rows that share a cluster_name de-dupe to one
    # /cluster/resources call total; standalone hosts hit the same endpoint
    # keyed by themselves. An enumeration failure on the host does not move
    # it out of its host bucket.
    sitemap_hostnames: set[str] = {(row.get("hostname") or "").lower() for row in rows if row.get("hostname")}
    # Phase 39.1 R6-regression closure: build hostname→binding side-map from the
    # SAME source-of-truth used at line 718 in the row loop (row.get("proxmox_credential_id")).
    # Passed to _enumerate_proxmox_vms so _enum_one threads credential_id=binding into
    # get_proxmox_client, matching the row-loop binding contract (Phase 38.1 R6).
    # None values for cluster-served rows are legitimate — get_proxmox_client falls through
    # to Tier-1/Tier-2 cluster walk in that case, identical to scan_drift's row-loop
    # binding-NULL semantics at the row loop's get_proxmox_client call (which passes
    # credential_id=binding and falls through to Tier-1/Tier-2 cluster walk when binding is None).
    #
    # WR-01 (Phase 39.1 review): "first-write-wins" policy on duplicate hostnames.
    # Phase 35 D-14 (store_device hostname-only match) makes true duplicates rare,
    # but a transient race during discover_and_map (concurrent inserts both passing
    # the unique constraint, or a not-yet-purged failed-discovery row sharing a
    # hostname with a fresh row) can yield two rows with the same hostname and
    # potentially different proxmox_credential_id values. Match the dedupe policy
    # of _bulk_universal_core_probes (above) so the side-map and SSH probe map
    # agree on which row each hostname maps to — without this, the cluster-dedupe
    # in _enumerate_proxmox_vms (which picks ONE representative per cluster) could
    # pick a different row's hostname than the side-map's last-write-wins entry,
    # yielding a quietly-mis-attributed credential.
    host_to_binding: dict[str, str | None] = {}
    for binding_row in rows:
        binding_hostname = binding_row.get("hostname")
        if not binding_hostname or binding_hostname in host_to_binding:
            continue
        host_to_binding[binding_hostname] = binding_row.get("proxmox_credential_id")
    cluster_vm_map = await _enumerate_proxmox_vms(probed_ok + changed, session, host_to_binding)
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
