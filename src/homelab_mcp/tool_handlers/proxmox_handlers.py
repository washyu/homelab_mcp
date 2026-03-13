"""Handler functions for Proxmox API and community scripts tools."""

import json
import logging
from typing import Any

from ..proxmox_api import (
    clone_proxmox_vm,
    create_proxmox_lxc,
    create_proxmox_vm,
    delete_proxmox_vm,
    get_proxmox_node_status,
    get_proxmox_vm_status,
    list_proxmox_resources,
    manage_proxmox_vm,
)
from ..proxmox_scripts import get_script_details, search_scripts
from ..validation import validate_hostname

logger = logging.getLogger(__name__)


async def handle_search_proxmox_scripts(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle search_proxmox_scripts tool."""
    results = await search_scripts(
        query=arguments["query"],
        category=arguments.get("category"),
        include_metadata=arguments.get("include_metadata", False),
    )
    result = {
        "status": "success",
        "query": arguments["query"],
        "total_found": len(results),
        "scripts": results,
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_get_proxmox_script_info(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_proxmox_script_info tool."""
    details = await get_script_details(
        script_name=arguments["script_name"],
        category=arguments.get("category"),
    )
    if details:
        result = {"status": "success", "script": details}
    else:
        result = {
            "status": "error",
            "message": f"Script '{arguments['script_name']}' not found",
        }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_list_proxmox_resources(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_proxmox_resources tool."""
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)
    result = await list_proxmox_resources(
        host=arguments.get("host"),
        resource_type=arguments.get("resource_type"),
        session=get_resource_manager().proxmox_session,
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_get_proxmox_node_status(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_proxmox_node_status tool."""
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)
    result = await get_proxmox_node_status(
        node=arguments["node"],
        host=arguments.get("host"),
        session=get_resource_manager().proxmox_session,
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_get_proxmox_vm_status(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_proxmox_vm_status tool."""
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)
    result = await get_proxmox_vm_status(
        node=arguments["node"],
        vmid=arguments["vmid"],
        host=arguments.get("host"),
        vm_type=arguments.get("vm_type", "qemu"),
        session=get_resource_manager().proxmox_session,
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_manage_proxmox_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle manage_proxmox_vm tool."""
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)
    result = await manage_proxmox_vm(
        node=arguments["node"],
        vmid=arguments["vmid"],
        action=arguments["action"],
        host=arguments.get("host"),
        vm_type=arguments.get("vm_type", "qemu"),
        session=get_resource_manager().proxmox_session,
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_create_proxmox_lxc(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle create_proxmox_lxc tool."""
    from ..drift_detection import update_baseline_after_mutation
    from ..server import get_resource_manager

    validate_hostname(arguments["hostname"])
    if host := arguments.get("host"):
        validate_hostname(host)
    result = await create_proxmox_lxc(
        node=arguments["node"],
        vmid=arguments["vmid"],
        hostname=arguments["hostname"],
        host=arguments.get("host"),
        ostemplate=arguments.get("ostemplate", "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"),
        storage=arguments.get("storage", "local-lvm"),
        memory=arguments.get("memory", 512),
        cores=arguments.get("cores", 1),
        rootfs_size=arguments.get("rootfs_size", 8),
        password=arguments.get("password"),
        start=arguments.get("start", False),
        session=get_resource_manager().proxmox_session,
    )
    if result.get("status") == "success":
        try:
            await update_baseline_after_mutation(
                node=arguments["node"],
                vmid=arguments["vmid"],
                vm_type="lxc",
                tool_name="create_proxmox_lxc",
                session=get_resource_manager().proxmox_session,
                db_adapter=get_resource_manager().db_adapter,
            )
        except Exception:
            logger.debug("Baseline update skipped for create_proxmox_lxc vmid=%s", arguments["vmid"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_create_proxmox_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle create_proxmox_vm tool."""
    from ..drift_detection import update_baseline_after_mutation
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)
    result = await create_proxmox_vm(
        node=arguments["node"],
        vmid=arguments["vmid"],
        name=arguments["name"],
        host=arguments.get("host"),
        memory=arguments.get("memory", 2048),
        cores=arguments.get("cores", 2),
        storage=arguments.get("storage", "local-lvm"),
        disk_size=arguments.get("disk_size", 32),
        iso=arguments.get("iso"),
        start=arguments.get("start", False),
        session=get_resource_manager().proxmox_session,
    )
    if result.get("status") == "success":
        try:
            await update_baseline_after_mutation(
                node=arguments["node"],
                vmid=arguments["vmid"],
                vm_type="qemu",
                tool_name="create_proxmox_vm",
                session=get_resource_manager().proxmox_session,
                db_adapter=get_resource_manager().db_adapter,
            )
        except Exception:
            logger.debug("Baseline update skipped for create_proxmox_vm vmid=%s", arguments["vmid"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_clone_proxmox_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle clone_proxmox_vm tool."""
    from ..drift_detection import update_baseline_after_mutation
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)
    result = await clone_proxmox_vm(
        node=arguments["node"],
        vmid=arguments["vmid"],
        new_vmid=arguments["new_vmid"],
        host=arguments.get("host"),
        name=arguments.get("name"),
        full=arguments.get("full", True),
        vm_type=arguments.get("vm_type", "qemu"),
        session=get_resource_manager().proxmox_session,
    )
    if result.get("status") == "success":
        try:
            await update_baseline_after_mutation(
                node=arguments["node"],
                vmid=arguments["new_vmid"],
                vm_type=arguments.get("vm_type", "qemu"),
                tool_name="clone_proxmox_vm",
                session=get_resource_manager().proxmox_session,
                db_adapter=get_resource_manager().db_adapter,
            )
        except Exception:
            logger.debug("Baseline update skipped for clone_proxmox_vm new_vmid=%s", arguments["new_vmid"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_delete_proxmox_vm(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle delete_proxmox_vm tool."""
    from ..server import get_resource_manager

    if host := arguments.get("host"):
        validate_hostname(host)

    if arguments.get("dry_run", False):
        from ..dry_run import build_dry_run_response

        vm_status = await get_proxmox_vm_status(
            node=arguments["node"],
            vmid=arguments["vmid"],
            host=arguments.get("host"),
            vm_type=arguments.get("vm_type", "qemu"),
            session=get_resource_manager().proxmox_session,
        )
        would_affect: list[dict[str, Any]] = [
            {
                "resource_type": "proxmox_vm",
                "node": arguments["node"],
                "vmid": arguments["vmid"],
                "vm_type": arguments.get("vm_type", "qemu"),
            }
        ]
        result = build_dry_run_response(
            tool_name="delete_proxmox_vm",
            would_affect=would_affect,
            risk_level="high",
            reversible=False,
            preview_details=vm_status,
        )
        return result

    result = await delete_proxmox_vm(
        node=arguments["node"],
        vmid=arguments["vmid"],
        host=arguments.get("host"),
        vm_type=arguments.get("vm_type", "qemu"),
        purge=arguments.get("purge", False),
        session=get_resource_manager().proxmox_session,
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def handle_delete_proxmox_vm_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle delete_proxmox_vm_preview tool.

    Delegates to handle_delete_proxmox_vm with dry_run=True injected.
    No VM is deleted.
    """
    return await handle_delete_proxmox_vm({**arguments, "dry_run": True})
