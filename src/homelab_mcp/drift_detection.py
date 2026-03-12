"""Infrastructure drift detection for homelab MCP server."""

import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp
import asyncssh

from .database import DatabaseAdapter
from .proxmox_api import get_proxmox_vm_config, get_proxmox_vm_status

logger = logging.getLogger(__name__)

# Fields compared for config drift per DRFT-03 (CPU, memory, network)
CONFIG_DRIFT_FIELDS: list[str] = ["cores", "memory", "sockets", "net0", "net1", "net2"]


def _diff_vm_config(
    baseline: dict[str, Any],
    live: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Compare baseline and live VM configs for drift in CONFIG_DRIFT_FIELDS.

    Only fields present in CONFIG_DRIFT_FIELDS are checked. Fields absent
    from both dicts are not reported as drift. A field present in one dict
    but absent in the other is reported if values differ (absent treated as None).

    Args:
        baseline: Stored baseline config dict.
        live: Current live config dict from Proxmox.

    Returns:
        Tuple of (expected_subset, actual_subset, changed_fields) where subsets
        contain only the fields that differ.
    """
    changed_fields: list[str] = []
    expected_subset: dict[str, Any] = {}
    actual_subset: dict[str, Any] = {}

    for field in CONFIG_DRIFT_FIELDS:
        baseline_val = baseline.get(field)
        live_val = live.get(field)

        # Skip fields absent from both
        if baseline_val is None and live_val is None:
            continue

        if baseline_val != live_val:
            changed_fields.append(field)
            expected_subset[field] = baseline_val
            actual_subset[field] = live_val

    return expected_subset, actual_subset, changed_fields


async def scan_drift(
    session: aiohttp.ClientSession | None,
    db_adapter: DatabaseAdapter,
    node: str | None = None,
    vm_type: str = "all",
) -> dict[str, Any]:
    """Scan for infrastructure drift against stored baselines.

    Compares current Proxmox VM config and state against stored baselines.
    Config drift checks CONFIG_DRIFT_FIELDS. State drift checks Proxmox status
    and (when the VM has a known IP) attempts an SSH probe.

    Args:
        session: Optional shared aiohttp.ClientSession.
        db_adapter: Database adapter for accessing baselines and device records.
        node: Optional Proxmox node name to filter scanned VMs.
        vm_type: VM type filter: "all", "qemu", or "lxc".

    Returns:
        Structured drift report dict with config_drift, state_drift, summary keys.
    """
    scan_timestamp = datetime.now(UTC).isoformat()
    config_drift: list[dict[str, Any]] = []
    state_drift: list[dict[str, Any]] = []

    # Fetch all stored baselines
    baselines: list[dict[str, Any]] = db_adapter.get_all_drift_baselines()

    # Apply node filter
    if node is not None:
        baselines = [b for b in baselines if b.get("node") == node]

    # Apply vm_type filter
    if vm_type != "all":
        baselines = [b for b in baselines if b.get("vm_type") == vm_type]

    # Build a lookup dict of known device IPs: {hostname: ip_address}
    all_devices: list[dict[str, Any]] = db_adapter.get_all_devices()
    devices_by_hostname: dict[str, str] = {
        d["hostname"]: d["ip_address"] for d in all_devices if d.get("hostname") and d.get("ip_address")
    }

    for b in baselines:
        b_node: str = b["node"]
        b_vmid: int = b["vmid"]
        b_vm_type: str = b["vm_type"]
        baseline_config: dict[str, Any] = b["baseline_config"]

        # --- Config drift ---
        config_result = await get_proxmox_vm_config(
            node=b_node,
            vmid=b_vmid,
            vm_type=b_vm_type,
            session=session,
        )
        if config_result.get("status") == "success":
            live_config = config_result["data"]
            expected_subset, actual_subset, changed_fields = _diff_vm_config(baseline_config, live_config)
            if changed_fields:
                config_drift.append(
                    {
                        "drift_type": "config",
                        "resource_type": "proxmox_vm",
                        "node": b_node,
                        "vmid": b_vmid,
                        "vm_type": b_vm_type,
                        "expected": expected_subset,
                        "actual": actual_subset,
                        "changed_fields": changed_fields,
                        "scan_timestamp": scan_timestamp,
                    }
                )
        else:
            logger.warning(
                "Could not fetch VM config for drift check — node=%s vmid=%s: %s",
                b_node,
                b_vmid,
                config_result.get("message", "unknown error"),
            )

        # --- State drift ---
        status_result = await get_proxmox_vm_status(
            node=b_node,
            vmid=b_vmid,
            vm_type=b_vm_type,
            session=session,
        )
        if status_result.get("status") == "success":
            proxmox_state: str = status_result["data"].get("status", "unknown")

            if proxmox_state != "running":
                state_drift.append(
                    {
                        "drift_type": "state",
                        "observation": "vm_offline",
                        "resource_type": "proxmox_vm",
                        "node": b_node,
                        "vmid": b_vmid,
                        "vm_type": b_vm_type,
                        "expected": "running",
                        "actual": proxmox_state,
                        "scan_timestamp": scan_timestamp,
                    }
                )
            else:
                # Proxmox reports running — attempt SSH probe if IP is known
                ip: str | None = devices_by_hostname.get(b_node)
                if ip:
                    try:
                        conn = await asyncssh.connect(
                            ip,
                            known_hosts=None,
                            connect_timeout=10,
                        )
                        conn.close()
                    except (TimeoutError, asyncssh.Error, OSError):
                        state_drift.append(
                            {
                                "drift_type": "state",
                                "observation": "vm_offline",
                                "resource_type": "proxmox_vm",
                                "node": b_node,
                                "vmid": b_vmid,
                                "vm_type": b_vm_type,
                                "expected": "running",
                                "actual": "ssh_unreachable",
                                "scan_timestamp": scan_timestamp,
                            }
                        )
        else:
            logger.warning(
                "Could not fetch VM status for drift check — node=%s vmid=%s: %s",
                b_node,
                b_vmid,
                status_result.get("message", "unknown error"),
            )

    return {
        "status": "success",
        "scan_timestamp": scan_timestamp,
        "config_drift": config_drift,
        "state_drift": state_drift,
        "summary": {
            "config_drift_count": len(config_drift),
            "state_drift_count": len(state_drift),
            "total_vms_scanned": len(baselines),
            "baselines_available": len(baselines),
        },
    }


async def update_baseline_after_mutation(
    node: str,
    vmid: int,
    vm_type: str,
    tool_name: str,
    session: aiohttp.ClientSession | None,
    db_adapter: DatabaseAdapter,
) -> None:
    """Update the drift baseline for a VM after a mutating operation.

    Fetches the current live config from Proxmox and stores it as the new
    baseline, so future scans compare against the post-mutation state.

    Args:
        node: Proxmox node name.
        vmid: VM or container ID.
        vm_type: "qemu" or "lxc".
        tool_name: Name of the tool that triggered the mutation (for audit trail).
        session: Optional shared aiohttp.ClientSession.
        db_adapter: Database adapter for storing the updated baseline.
    """
    result = await get_proxmox_vm_config(
        node=node,
        vmid=vmid,
        vm_type=vm_type,
        session=session,
    )

    if result.get("status") == "error":
        logger.warning(
            "Could not update drift baseline after %s: %s",
            tool_name,
            result.get("message", "unknown error"),
        )
        return

    db_adapter.upsert_drift_baseline(
        node=node,
        vmid=vmid,
        vm_type=vm_type,
        baseline_config=result["data"],
        recorded_by=tool_name,
    )
    logger.debug("Drift baseline updated for %s:%s after %s", node, vmid, tool_name)
