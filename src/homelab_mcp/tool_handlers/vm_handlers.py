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
    result = await remove_vm(
        device_id=arguments["device_id"],
        platform=arguments["platform"],
        vm_name=arguments["vm_name"],
        force=arguments.get("force", False),
    )
    return {"content": [{"type": "text", "text": result}]}
