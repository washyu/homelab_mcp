"""Handler functions for network topology and sitemap tools."""

import json
from typing import Any, Literal

from ..database import PostgreSQLAdapter, SQLiteAdapter, _purge_devices_by_filter
from ..sitemap import NetworkSiteMap, bulk_discover_and_store, discover_and_store
from ..validation import validate_hostname


async def handle_discover_and_map(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle discover_and_map tool."""
    validate_hostname(arguments["hostname"])
    sitemap = NetworkSiteMap()
    result = await discover_and_store(sitemap, **arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_bulk_discover_and_map(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle bulk_discover_and_map tool."""
    for target in arguments["targets"]:
        validate_hostname(target["hostname"])
    sitemap = NetworkSiteMap()
    result = await bulk_discover_and_store(sitemap, arguments["targets"])
    return {"content": [{"type": "text", "text": result}]}


async def handle_get_network_sitemap(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_network_sitemap tool."""
    sitemap = NetworkSiteMap()
    devices = sitemap.get_all_devices()
    result = json.dumps(
        {"status": "success", "total_devices": len(devices), "devices": devices},
        indent=2,
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_analyze_network_topology(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle analyze_network_topology tool."""
    sitemap = NetworkSiteMap()
    analysis = sitemap.analyze_network_topology()
    result = json.dumps({"status": "success", "analysis": analysis}, indent=2)
    return {"content": [{"type": "text", "text": result}]}


async def handle_suggest_deployments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle suggest_deployments tool."""
    sitemap = NetworkSiteMap()
    suggestions = sitemap.suggest_deployments()
    result = json.dumps({"status": "success", "suggestions": suggestions}, indent=2)
    return {"content": [{"type": "text", "text": result}]}


async def handle_get_device_changes(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_device_changes tool."""
    sitemap = NetworkSiteMap()
    changes = sitemap.get_device_changes(arguments["device_id"], arguments.get("limit", 10))
    result = json.dumps(
        {
            "status": "success",
            "device_id": arguments["device_id"],
            "changes": changes,
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_purge_failed_discoveries(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle purge_failed_discoveries tool."""
    dry_run = bool(arguments.get("dry_run", False))
    sitemap = NetworkSiteMap()
    removed = sitemap.purge_failed_devices(dry_run=dry_run)
    result = json.dumps(
        {
            "status": "success",
            "dry_run": dry_run,
            "purged_count": len(removed),
            "purged_devices": removed,
        },
        indent=2,
        default=str,
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_update_device_fingerprint(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update_device_fingerprint tool (Phase 38 D-05).

    The MCP framework does not validate inputSchema (RESEARCH.md §5), so the
    handler filters unknown top-level keys (D-05b) and returns a structured
    error envelope on missing hostname or malformed fingerprint dict.
    """
    RECOGNIZED_TOP_LEVEL = {
        "kernel_name",
        "kernel_version",
        "os_name",
        "os_version",
        "package_fingerprint",
        "capabilities",
    }
    validate_hostname(arguments["hostname"])
    fp_in = arguments.get("fingerprint", {})
    if not isinstance(fp_in, dict):
        # NOTE: error string is asserted exactly by test_update_device_fingerprint_malformed_dict_phase38.
        result_str = json.dumps(
            {
                "status": "error",
                "error": f"`fingerprint` must be an object (got {type(fp_in).__name__})",
                "hint": "Provide fingerprint as a JSON object with recognized top-level keys.",
            }
        )
        return {"content": [{"type": "text", "text": result_str}]}
    cleaned = {k: v for k, v in fp_in.items() if k in RECOGNIZED_TOP_LEVEL}

    sitemap = NetworkSiteMap()
    try:
        merged = sitemap.db_adapter.update_device_fingerprint(arguments["hostname"], cleaned)
    except ValueError as e:
        # NOTE: hint substring is asserted exactly by test_update_device_fingerprint_missing_hostname_phase38.
        result_str = json.dumps(
            {
                "status": "error",
                "error": str(e),
                "hint": "Run discover_and_map for this hostname first to add it to the sitemap.",
            }
        )
        return {"content": [{"type": "text", "text": result_str}]}

    result_str = json.dumps(
        {
            "status": "success",
            "hostname": arguments["hostname"],
            "fingerprint": merged,
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": result_str}]}


async def handle_update_device_fingerprint_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update_device_fingerprint_preview tool (Phase 38 D-05c, Plan 05).

    Read-only thin wrapper around merge_fingerprint: fetches the device row via
    get_all_devices, computes the would-be merge result, and returns it WITHOUT
    persisting. The adapter's update_device_fingerprint method is NOT called.

    Mirrors the validation/filtering of handle_update_device_fingerprint so the
    preview shape exactly matches what the real call would write.

    Side-effect contract (Phase 43 WR-03 clarification):
      * Preview path (this function): pure read — no DB write, no last_seen
        mutation, no updated_at mutation. Safe to call repeatedly.
      * Persist path (handle_update_device_fingerprint → adapter.update_device_fingerprint):
        bumps updated_at on the device row; preserves last_seen as set by the most
        recent discover_and_map run (Phase 38 REVIEW-FIX commit f53365c). Consumers
        of analyze_network_topology row ordering (which keys off last_seen) are
        NOT disturbed by fingerprint updates.
    """
    from ..database import merge_fingerprint  # local import — avoids circular issues

    RECOGNIZED_TOP_LEVEL = {
        "kernel_name",
        "kernel_version",
        "os_name",
        "os_version",
        "package_fingerprint",
        "capabilities",
    }
    validate_hostname(arguments["hostname"])
    fp_in = arguments.get("fingerprint", {})
    if not isinstance(fp_in, dict):
        result_str = json.dumps(
            {
                "status": "error",
                "error": f"`fingerprint` must be an object (got {type(fp_in).__name__})",
                "hint": "Provide fingerprint as a JSON object with recognized top-level keys.",
            }
        )
        return {"content": [{"type": "text", "text": result_str}]}
    cleaned = {k: v for k, v in fp_in.items() if k in RECOGNIZED_TOP_LEVEL}

    sitemap = NetworkSiteMap()
    devices = sitemap.db_adapter.get_all_devices()
    target = next((d for d in devices if d.get("hostname") == arguments["hostname"]), None)
    if target is None:
        result_str = json.dumps(
            {
                "status": "error",
                "error": f"Hostname not in sitemap: {arguments['hostname']!r}.",
                "hint": "Run discover_and_map for this hostname first to add it to the sitemap.",
            }
        )
        return {"content": [{"type": "text", "text": result_str}]}

    stored = target.get("fingerprint") or {}
    if isinstance(stored, str):
        # Some adapters may still surface a JSON string; normalize to dict before merge.
        try:
            stored = json.loads(stored)
        except json.JSONDecodeError:
            stored = {}
    if not isinstance(stored, dict):
        stored = {}

    merged = merge_fingerprint(stored, cleaned)
    result_str = json.dumps(
        {
            "status": "success",
            "hostname": arguments["hostname"],
            "fingerprint": merged,
            "preview": True,
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": result_str}]}
async def handle_remove_device(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle remove_device tool (Phase 44 D-06).

    Pure-SQL single-row delete on the sitemap row keyed by ``device_id``,
    with manual cascade to ``discovery_history``. No SSH dial, no Ansible
    runs, no Terraform plans, no keyring mutation — body-level scope is
    locked by tests/test_ast_regression.py::TestPhase44RemoveDeviceCallPath.

    Per D-06b: missing ``device_id`` returns a structured error envelope
    (NOT a raised exception). Per D-06a: success payload carries the full
    ``removed_device`` row dict. Per D-11a: dry_run path makes no DB write
    and the keyring entry bound via ``ssh_credential_id`` is preserved by
    construction (this handler never references keyring at all).
    """
    device_id = int(arguments["device_id"])
    dry_run = bool(arguments.get("dry_run", False))
    sitemap = NetworkSiteMap()
    removed = sitemap.db_adapter.delete_device_by_id(device_id, dry_run=dry_run)
    if removed is None:
        # NOTE: error string + hint substring are asserted exactly by
        # tests/test_remove_device.py::test_handle_remove_device_missing_id_phase44.
        result_str = json.dumps(
            {
                "status": "error",
                "error": f"Device {device_id} not found in sitemap",
                "hint": "Run get_network_sitemap to see current device IDs.",
            }
        )
        return {"content": [{"type": "text", "text": result_str}]}
    result = json.dumps(
        {
            "status": "success",
            "dry_run": dry_run,
            "removed_device": removed,
        },
        indent=2,
        default=str,
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_remove_device_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle remove_device_preview tool (Phase 44 D-11).

    Delegates to handle_remove_device with dry_run=True injected.
    No DB write, no keyring touch, no host-side action.
    """
    return await handle_remove_device({**arguments, "dry_run": True})


_VALID_FILTER_TYPES = {"hostname", "last_seen_older_than_days", "status", "ip_range"}


def _adapter_dialect(adapter: Any) -> Literal["sqlite", "postgres"]:
    """Determine the SQL dialect for the adapter so the orchestrator gets a
    precise dialect parameter (avoids isinstance branching inside the helper).

    The handler is the right place for this single concrete-class check —
    the helper itself stays adapter-agnostic per Phase 44 D-14.
    """
    if isinstance(adapter, PostgreSQLAdapter):
        return "postgres"
    if isinstance(adapter, SQLiteAdapter):
        return "sqlite"
    raise TypeError(
        f"Unknown adapter type {type(adapter).__name__}; expected SQLiteAdapter or "
        "PostgreSQLAdapter."
    )


def _value_hint_for(filter_type: str) -> str:
    """D-01b: per-filter_type hint string for bad-value-shape error envelopes."""
    return {
        "hostname": "Pass an exact hostname string, e.g., 'pve-test'.",
        "status": "Pass a status string, e.g., 'success' or 'error'.",
        "last_seen_older_than_days": "Pass an integer day count, e.g., 7.",
        "ip_range": "Pass a CIDR string, e.g., '192.168.1.0/24' or '2001:db8::/32'.",
    }.get(filter_type, "See the tool description for value-shape examples.")


async def handle_purge_devices(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle purge_devices tool (Phase 44 D-01).

    Generalized superset of purge_failed_discoveries. Single mutually-exclusive
    filter per call; filter_type enum is one of {hostname, last_seen_older_than_days,
    status, ip_range}. Value shape varies per filter_type and is validated at
    handler boundary per D-01b (MCP framework does not enforce inputSchema).

    Response shape mirrors purge_failed_discoveries (D-01a):
        {status, dry_run, purged_count, purged_devices}

    Zero-match returns success with empty list (D-01c, NEVER an error).

    purge_failed_discoveries alias: this handler does NOT cover the
    4-clause failed-discovery filter (D-08) — for that, use the
    purge_failed_discoveries tool directly. ``purge_devices(filter_type='status',
    value='error')`` matches ONLY status='error' rows; zombie hostnames need
    the alias.
    """
    filter_type = arguments.get("filter_type", "")
    value = arguments.get("value")
    dry_run = bool(arguments.get("dry_run", False))

    # D-01b: validate filter_type at handler boundary (JSON Schema enum is
    # advisory — MCP framework does not enforce inputSchema).
    if filter_type not in _VALID_FILTER_TYPES:
        result_str = json.dumps(
            {
                "status": "error",
                "error": (
                    f"Invalid filter_type: {filter_type!r}. "
                    f"Valid: hostname, last_seen_older_than_days, status, ip_range."
                ),
                "hint": (
                    "Pass filter_type as one of the four enum values; "
                    "see the tool description for value-shape examples."
                ),
            }
        )
        return {"content": [{"type": "text", "text": result_str}]}

    sitemap = NetworkSiteMap()
    dialect = _adapter_dialect(sitemap.db_adapter)
    try:
        removed = _purge_devices_by_filter(
            sitemap.db_adapter, dialect, filter_type, value, dry_run=dry_run
        )
    except ValueError as e:
        # D-01b: bad value shape (wrong type, invalid CIDR, etc.) → structured envelope.
        hint = _value_hint_for(filter_type)
        result_str = json.dumps(
            {
                "status": "error",
                "error": str(e),
                "hint": hint,
            }
        )
        return {"content": [{"type": "text", "text": result_str}]}

    result = json.dumps(
        {
            "status": "success",
            "dry_run": dry_run,
            "purged_count": len(removed),
            "purged_devices": removed,
        },
        indent=2,
        default=str,
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_purge_devices_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle purge_devices_preview tool (Phase 44 D-11).

    Delegates to handle_purge_devices with dry_run=True injected.
    No DB write, no host-side action.
    """
    return await handle_purge_devices({**arguments, "dry_run": True})
