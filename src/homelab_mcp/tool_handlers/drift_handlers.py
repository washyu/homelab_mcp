"""Handler functions for drift detection tools."""

import json
from typing import Any

from ..drift_detection import scan_drift


async def handle_scan_infrastructure_drift(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle scan_infrastructure_drift tool."""
    from ..server import get_resource_manager, set_latest_drift_report  # deferred

    rm = get_resource_manager()
    result = await scan_drift(
        session=rm.proxmox_session,
        db_adapter=rm.db_adapter,
        node=arguments.get("node"),
        vm_type=arguments.get("vm_type", "all"),
    )
    set_latest_drift_report(result)  # cache for homelab://drift/latest (DRFT-09)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
