"""Handler functions for VM/container operations."""

from typing import Any

from ..vm_operations import (
    control_vm_state,
    deploy_vm,
    get_vm_logs,
    get_vm_status,
    list_vms_on_device,
    remove_vm,
)


async def handle_deploy_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle deploy_vm tool."""
    result = await deploy_vm(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
        vm_config=arguments.get("vm_config", {}),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_control_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle control_vm tool."""
    result = await control_vm_state(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
        action=arguments["action"],
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_get_vm_status(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_vm_status tool."""
    result = await get_vm_status(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_list_vms(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_vms tool."""
    result = await list_vms_on_device(device_id=arguments["device_id"], platforms=arguments.get("platforms"))
    return {"content": [{"type": "text", "text": result}]}


async def handle_get_vm_logs(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_vm_logs tool."""
    result = await get_vm_logs(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
        lines=arguments.get("lines", 100),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_remove_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle remove_vm tool."""
    if arguments.get("dry_run", False):
        from ..dry_run import build_dry_run_response
        from ..vm_operations import VMManager

        manager = VMManager()
        connection_info = await manager.get_device_connection_info(arguments["device_id"])
        if not connection_info:
            would_affect: list[dict[str, Any]] = []
            preview_details: dict[str, Any] | None = {
                "error": f"Device {arguments['device_id']} not found"
            }
        else:
            would_affect = [
                {
                    "resource_type": "vm",
                    "name": arguments["vm_name"],
                    "platform": arguments["platform"],
                    "device_id": arguments["device_id"],
                    "host": connection_info["hostname"],
                }
            ]
            preview_details = None
        return build_dry_run_response(
            tool_name="remove_vm",
            would_affect=would_affect,
            risk_level="high",
            reversible=False,
            preview_details=preview_details,
        )
    result = await remove_vm(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
        force=arguments.get("force", False),
    )
    return {"content": [{"type": "text", "text": result}]}
