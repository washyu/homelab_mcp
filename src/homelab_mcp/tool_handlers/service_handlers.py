"""Handler functions for service installation and management tools."""

import json
from typing import Any

from ..service_installer import ServiceInstaller


async def handle_list_available_services(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_available_services tool."""
    installer = ServiceInstaller()
    services = installer.get_available_services()
    result_dict = {"available_services": services, "count": len(services)}
    return {"content": [{"type": "text", "text": json.dumps(result_dict, indent=2)}]}


async def handle_get_service_info(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_service_info tool."""
    installer = ServiceInstaller()
    service_info = installer.get_service_info(arguments["service_name"])
    if service_info:
        return {"content": [{"type": "text", "text": json.dumps(service_info, indent=2)}]}
    else:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Service '{arguments['service_name']}' not found",
                }
            ]
        }


async def handle_check_service_requirements(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Handle check_service_requirements tool."""
    installer = ServiceInstaller()
    requirements_result = await installer.check_service_requirements(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(requirements_result, indent=2)}]}


async def handle_install_service(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle install_service tool."""
    installer = ServiceInstaller()
    install_result = await installer.install_service(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(install_result, indent=2)}]}


async def handle_get_service_status(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_service_status tool."""
    installer = ServiceInstaller()
    status_result = await installer.get_service_status(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(status_result, indent=2)}]}


async def handle_plan_terraform_service(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle plan_terraform_service tool."""
    installer = ServiceInstaller()
    plan_result = await installer.plan_terraform_service(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(plan_result, indent=2)}]}


async def handle_destroy_terraform_service(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle destroy_terraform_service tool."""
    installer = ServiceInstaller()
    destroy_result = await installer.destroy_terraform_service(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(destroy_result, indent=2)}]}


async def handle_refresh_terraform_service(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle refresh_terraform_service tool."""
    installer = ServiceInstaller()
    refresh_result = await installer.refresh_terraform_service(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(refresh_result, indent=2)}]}


async def handle_check_ansible_service(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle check_ansible_service tool."""
    installer = ServiceInstaller()
    ansible_result = await installer.check_ansible_service(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(ansible_result, indent=2)}]}


async def handle_run_ansible_playbook(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle run_ansible_playbook tool."""
    installer = ServiceInstaller()
    playbook_result = await installer.run_ansible_playbook(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(playbook_result, indent=2)}]}
