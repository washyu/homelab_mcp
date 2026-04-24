"""Network site mapping and device tracking functionality."""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .database import calculate_data_hash, get_database_adapter
from .log_filter import sanitize_error
from .progress import emit_progress

logger = logging.getLogger(__name__)


def _has_threshold_data(device: dict[str, Any], *fields: str) -> bool:
    """Phase 35 D-11: gate a threshold comparison on required fields being non-None/non-empty.

    Truthy-empty-string is treated as missing (consistent with existing
    ``if device.get("disk_use_percent"):`` truthy guards at sitemap.py:179, 269).
    ``None`` is treated as missing. ``0`` is NOT treated as missing — a device
    with ``cpu_cores=0`` is a valid (albeit unusual) low-resource device and
    should be included in the comparison (the comparison itself is what
    determines the classification).
    """
    for field_name in fields:
        value = device.get(field_name)
        if value is None or value == "":
            return False
    return True


@dataclass
class NetworkDevice:
    """Represents a discovered network device."""

    hostname: str
    connection_ip: str
    last_seen: str
    status: str  # success, error
    cpu_model: str | None = None
    cpu_cores: int | None = None
    memory_total: str | None = None
    memory_used: str | None = None
    memory_free: str | None = None
    memory_available: str | None = None
    disk_filesystem: str | None = None
    disk_size: str | None = None
    disk_used: str | None = None
    disk_available: str | None = None
    disk_use_percent: str | None = None
    disk_mount: str | None = None
    network_interfaces: str | None = None  # JSON string
    usb_devices: str | None = None  # JSON string (Phase 35 D-09b)
    pci_devices: str | None = None  # JSON string (Phase 35 D-09b)
    block_devices: str | None = None  # JSON string (Phase 35 D-09b)
    uptime: str | None = None
    os_info: str | None = None
    error_message: str | None = None


class NetworkSiteMap:
    """Manages the network site map database."""

    def __init__(self, db_path: str | None = None, db_type: str | None = None, **db_kwargs: Any):
        """Initialize the site map with database connection."""
        self.db_adapter = get_database_adapter(db_type=db_type, db_path=db_path, **db_kwargs)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database schema."""
        self.db_adapter.init_schema()

    def parse_discovery_output(self, discovery_json: str) -> NetworkDevice:
        """Parse SSH discovery output into a NetworkDevice object."""
        try:
            data = json.loads(discovery_json)

            device = NetworkDevice(
                hostname=data.get("hostname", ""),
                connection_ip=data.get("connection_ip", ""),
                last_seen=datetime.now().isoformat(),
                status=data.get("status", "error"),
            )

            if data.get("status") == "success" and "data" in data:
                discovery_data = data["data"]

                # CPU information
                if "cpu" in discovery_data:
                    cpu_info = discovery_data["cpu"]
                    device.cpu_model = cpu_info.get("model")
                    try:
                        device.cpu_cores = int(cpu_info.get("cores", 0))
                    except (ValueError, TypeError):
                        device.cpu_cores = None

                # Memory information
                if "memory" in discovery_data:
                    mem_info = discovery_data["memory"]
                    device.memory_total = mem_info.get("total")
                    device.memory_used = mem_info.get("used")
                    device.memory_free = mem_info.get("free")
                    device.memory_available = mem_info.get("available")

                # Disk information
                if "disk" in discovery_data:
                    disk_info = discovery_data["disk"]
                    device.disk_filesystem = disk_info.get("filesystem")
                    device.disk_size = disk_info.get("size")
                    device.disk_used = disk_info.get("used")
                    device.disk_available = disk_info.get("available")
                    device.disk_use_percent = disk_info.get("use_percent")
                    device.disk_mount = disk_info.get("mount")

                # Network interfaces (store as JSON)
                if "network" in discovery_data:
                    device.network_interfaces = json.dumps(discovery_data["network"])

                # USB / PCI / block devices (Phase 35 D-09b: store as JSON)
                if "usb_devices" in discovery_data:
                    device.usb_devices = json.dumps(discovery_data["usb_devices"])
                if "pci_devices" in discovery_data:
                    device.pci_devices = json.dumps(discovery_data["pci_devices"])
                if "block_devices" in discovery_data:
                    device.block_devices = json.dumps(discovery_data["block_devices"])

                # System information
                device.uptime = discovery_data.get("uptime")
                device.os_info = discovery_data.get("os")

            elif data.get("status") == "error":
                device.error_message = data.get("error", "Unknown error")

            return device

        except json.JSONDecodeError as e:
            # Create error device for invalid JSON
            return NetworkDevice(
                hostname="unknown",
                connection_ip="unknown",
                last_seen=datetime.now().isoformat(),
                status="error",
                error_message=f"JSON parse error: {sanitize_error(e)}",
            )

    def store_device(self, device: NetworkDevice) -> int:
        """Store or update a device in the database."""
        device_data = asdict(device)
        return self.db_adapter.store_device(device_data)

    def store_discovery_history(self, device_id: int, discovery_data: str) -> None:
        """Store discovery data in history for change tracking."""
        data_hash = calculate_data_hash(discovery_data)
        self.db_adapter.store_discovery_history(device_id, discovery_data, data_hash)

    def get_all_devices(self) -> list[dict[str, Any]]:
        """Get all devices from the database."""
        return self.db_adapter.get_all_devices()

    def get_device_changes(self, device_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get change history for a specific device."""
        return self.db_adapter.get_device_changes(device_id, limit)

    def analyze_network_topology(self) -> dict[str, Any]:
        """Analyze the network topology and provide insights."""
        devices = self.get_all_devices()

        analysis = {
            "total_devices": len(devices),
            "online_devices": len([d for d in devices if d["status"] == "success"]),
            "offline_devices": len([d for d in devices if d["status"] == "error"]),
            "operating_systems": {},
            "cpu_architectures": {},
            "network_segments": {},
            "resource_utilization": {
                "high_memory_usage": [],
                "high_disk_usage": [],
                "low_resources": [],
            },
        }

        for device in devices:
            if device["status"] != "success":
                continue

            # OS distribution
            os_info = device.get("os_info", "Unknown")
            if isinstance(analysis["operating_systems"], dict):
                analysis["operating_systems"][os_info] = analysis["operating_systems"].get(os_info, 0) + 1

            # CPU models
            cpu_model = device.get("cpu_model", "Unknown")
            if isinstance(analysis["cpu_architectures"], dict):
                analysis["cpu_architectures"][cpu_model] = analysis["cpu_architectures"].get(cpu_model, 0) + 1

            # Network segments (by IP prefix)
            connection_ip = device.get("connection_ip", "")
            if "." in connection_ip:
                network_prefix = ".".join(connection_ip.split(".")[:3]) + ".0/24"
                if isinstance(analysis["network_segments"], dict):
                    analysis["network_segments"][network_prefix] = (
                        analysis["network_segments"].get(network_prefix, 0) + 1
                    )

            # Resource utilization analysis
            if device.get("disk_use_percent"):
                try:
                    disk_usage = int(device["disk_use_percent"].rstrip("%"))
                    if disk_usage > 80:
                        if (
                            isinstance(analysis["resource_utilization"], dict)
                            and "high_disk_usage" in analysis["resource_utilization"]
                        ):
                            analysis["resource_utilization"]["high_disk_usage"].append(
                                {
                                    "hostname": device["hostname"],
                                    "usage": device["disk_use_percent"],
                                }
                            )
                except (ValueError, AttributeError):
                    logger.debug(
                        "Skipping device %s in topology analysis: unable to parse disk usage",
                        device.get("hostname", "unknown"),
                    )

            # Identify resource-constrained devices
            cpu_cores = device.get("cpu_cores")
            if cpu_cores is not None and cpu_cores <= 2:
                memory_total = device.get("memory_total")
                if memory_total:
                    memory_gb = self._parse_memory_gb(str(memory_total))
                    if (
                        memory_gb <= 2
                        and isinstance(analysis["resource_utilization"], dict)
                        and "low_resources" in analysis["resource_utilization"]
                    ):
                        analysis["resource_utilization"]["low_resources"].append(
                            {
                                "hostname": device["hostname"],
                                "cpu_cores": device["cpu_cores"],
                                "memory": device["memory_total"],
                            }
                        )

        return analysis

    def _parse_memory_gb(self, memory_str: str) -> float:
        """Parse memory string and return value in GB."""
        if not memory_str:
            return 0.0

        memory_str = str(memory_str).strip()
        if memory_str.endswith("Gi"):
            try:
                return float(memory_str.rstrip("Gi"))
            except (ValueError, AttributeError):
                return 0.0
        elif memory_str.endswith("G"):
            try:
                return float(memory_str.rstrip("G"))
            except (ValueError, AttributeError):
                return 0.0
        else:
            return 0.0

    def suggest_deployments(self) -> dict[str, Any]:
        """Suggest optimal deployment locations based on current network state."""
        devices = self.get_all_devices()
        online_devices = [d for d in devices if d["status"] == "success"]

        suggestions: dict[str, list[dict[str, str]]] = {
            "load_balancer_candidates": [],
            "database_candidates": [],
            "monitoring_targets": [],
            "upgrade_recommendations": [],
        }

        for device in online_devices:
            hostname = device["hostname"]

            # Load balancer candidates (high CPU, good memory)
            # Phase 35 D-10/D-13: skip devices with null cpu_cores or memory_total
            # rather than coercing to 0/"" (which produces false negatives here and
            # false positives in the upgrade_recommendations path below).
            if not _has_threshold_data(device, "cpu_cores", "memory_total"):
                logger.debug(
                    "Skipping device %s in deployment suggestion: missing cpu_cores or memory_total",
                    hostname,
                )
            else:
                cpu_cores = device["cpu_cores"]
                if cpu_cores >= 4:
                    memory_gb = self._parse_memory_gb(str(device["memory_total"]))
                    if memory_gb >= 4:
                        suggestions["load_balancer_candidates"].append(
                            {
                                "hostname": hostname,
                                "reason": f"{cpu_cores} cores, {device['memory_total']} RAM",
                            }
                        )

            # Database candidates (good disk space, memory)
            if device.get("disk_use_percent"):
                try:
                    disk_usage = int(device["disk_use_percent"].rstrip("%"))
                    if disk_usage < 50:  # Plenty of disk space
                        memory_total = device.get("memory_total")
                        memory_gb = self._parse_memory_gb(str(memory_total) if memory_total else "")

                        if memory_gb >= 8:
                            suggestions["database_candidates"].append(
                                {
                                    "hostname": hostname,
                                    "reason": f"Low disk usage ({device['disk_use_percent']}), {device['memory_total']} RAM",
                                }
                            )
                except (ValueError, AttributeError):
                    logger.debug("Skipping device %s for deployment suggestion: unable to parse disk usage", hostname)

            # Monitoring targets (all online devices should be monitored)
            suggestions["monitoring_targets"].append(
                {
                    "hostname": hostname,
                    "connection_ip": device["connection_ip"],
                    "os": device.get("os_info", "Unknown"),
                }
            )

            # Upgrade recommendations
            # Phase 35 D-10/D-13: skip devices with null cpu_cores or memory_total;
            # prior behavior coerced None -> 0 and flagged every null-cpu device as a
            # low-resource upgrade candidate (false positive).
            if not _has_threshold_data(device, "cpu_cores", "memory_total"):
                logger.debug(
                    "Skipping device %s in upgrade recommendation: missing cpu_cores or memory_total",
                    hostname,
                )
            else:
                cpu_cores = device["cpu_cores"]
                if cpu_cores <= 2:
                    memory_gb = self._parse_memory_gb(str(device["memory_total"]))
                    if memory_gb <= 4:
                        suggestions["upgrade_recommendations"].append(
                            {
                                "hostname": hostname,
                                "reason": f"Limited resources: {cpu_cores} cores, {device['memory_total']} RAM",
                            }
                        )

        return suggestions


async def discover_and_store(
    sitemap: NetworkSiteMap,
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> str:
    """Discover a device and store it in the site map.

    Phase 33.1 D-06: ``username`` defaults to ``None``. When omitted, the
    keyring-registered user for ``hostname`` is resolved inside
    :func:`ssh_tools.resolve_ssh_credentials` via the Plan-01 registry-scan
    helper — no hardcoded-default fallback.
    """
    from .ssh_tools import ssh_discover_system

    # Perform discovery
    discovery_result = await ssh_discover_system(hostname, username, password, key_path, port)

    # Parse and store the result
    device = sitemap.parse_discovery_output(discovery_result)
    device_id = sitemap.store_device(device)
    sitemap.store_discovery_history(device_id, discovery_result)

    return json.dumps(
        {
            "status": device.status,
            "device_id": device_id,
            "hostname": device.hostname,
            "discovery_status": device.status,
            "stored_at": datetime.now().isoformat(),
        },
        indent=2,
    )


async def bulk_discover_and_store(sitemap: NetworkSiteMap, targets: list[dict[str, Any]]) -> str:
    """Discover multiple devices and store them in the site map.

    Phase 35 D-07: parallelized with ``asyncio.gather`` gated by
    ``asyncio.Semaphore(10)`` so N unreachable hosts do not stack serially
    against the ``ssh_discover_system`` outer timeout. The concurrency cap
    (10) prevents FD exhaustion / SSH-session flood on larger inventories.

    Phase 35 D-07a: progress emits are per-completion (not per-position in
    ``targets``), so the counter increments by completion order — this is
    interleaved but acceptable for the homelab UX.
    """
    total = len(targets)
    semaphore = asyncio.Semaphore(10)
    completed = 0
    counter_lock = asyncio.Lock()

    async def _discover_one(target: dict[str, Any]) -> dict[str, Any]:
        nonlocal completed
        hostname_label = target.get("hostname", "unknown")
        async with semaphore:
            async with counter_lock:
                completed += 1
                local_i = completed
            await emit_progress(
                "info",
                f"Discovering {hostname_label} ({local_i}/{total})",
            )
            try:
                result = await discover_and_store(
                    sitemap,
                    target["hostname"],
                    # Phase 33.1 D-07: no hardcoded-default fallback — None propagates
                    # to resolve_ssh_credentials, which scans the keyring registry
                    # by hostname (Plan 01) to pick the registered user.
                    target.get("username"),
                    target.get("password"),
                    target.get("key_path"),
                    target.get("port", 22),
                )
                await emit_progress(
                    "info",
                    f"Completed {hostname_label} ({local_i}/{total})",
                )
                return json.loads(result)  # type: ignore[no-any-return]
            except Exception as e:
                return {
                    "status": "error",
                    "hostname": hostname_label,
                    "error": sanitize_error(e),
                }

    # Phase 35 D-07: return_exceptions=True matches CONTEXT D-07 verbatim —
    # any coroutine-setup or surprise raise (outside the _discover_one try)
    # lands as an exception object in `raw_results` rather than aborting the
    # whole gather. Coerce any stray exception object back into an
    # error-shaped dict so the downstream json.dumps(results) sees a
    # homogeneous list[dict[str, Any]].
    raw_results = await asyncio.gather(
        *[_discover_one(t) for t in targets],
        return_exceptions=True,
    )
    results: list[dict[str, Any]] = [
        r if isinstance(r, dict)
        else {"status": "error", "message": str(r)}
        for r in raw_results
    ]

    await emit_progress("info", f"Bulk discovery complete: {total} targets processed")

    return json.dumps(
        {
            "status": "success",
            "total_targets": total,
            "results": results,
            "completed_at": datetime.now().isoformat(),
        },
        indent=2,
    )
