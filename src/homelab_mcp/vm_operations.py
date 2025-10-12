"""VM operations for MCP integration."""

import json
from typing import Any

import asyncssh

from .sitemap import NetworkSiteMap
from .vm_providers import get_vm_provider


class VMManager:
    """Manager for VM operations across different platforms."""

    def __init__(self) -> None:
        self.sitemap = NetworkSiteMap()

    async def get_device_connection_info(self, device_id: int) -> dict[str, Any] | None:
        """Get SSH connection info for a device from the sitemap."""
        devices = self.sitemap.get_all_devices()
        for device in devices:
            if device.get("id") == device_id:
                return {
                    "hostname": device.get("connection_ip", device.get("hostname")),
                    "username": "mcp_admin",  # Use the admin account we set up
                    "port": 22,
                }
        return None


async def deploy_vm(
    device_id: int, platform: str, vm_name: str, vm_config: dict[str, Any]
) -> str:
    """Deploy a new VM/container on a specific device."""
    try:
        manager = VMManager()
        connection_info = await manager.get_device_connection_info(device_id)

        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        provider = get_vm_provider(platform)

        async with asyncssh.connect(
            connection_info["hostname"],
            username=connection_info["username"],
            known_hosts=None,
        ) as conn:
            result = await provider.deploy_vm(conn, vm_name, vm_config)
            result["device_id"] = device_id
            result["platform"] = platform

            return json.dumps(result, indent=2)

    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)})
    except Exception as e:
        return json.dumps(
            {"status": "error", "message": f"VM deployment failed: {str(e)}"}
        )


async def control_vm_state(
    device_id: int, platform: str, vm_name: str, action: str
) -> str:
    """Control VM state (start, stop, restart)."""
    try:
        manager = VMManager()
        connection_info = await manager.get_device_connection_info(device_id)

        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        provider = get_vm_provider(platform)

        async with asyncssh.connect(
            connection_info["hostname"],
            username=connection_info["username"],
            known_hosts=None,
        ) as conn:
            result = await provider.control_vm(conn, vm_name, action)
            result["device_id"] = device_id
            result["platform"] = platform

            return json.dumps(result, indent=2)

    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)})
    except Exception as e:
        return json.dumps(
            {"status": "error", "message": f"VM control failed: {str(e)}"}
        )


async def get_vm_status(device_id: int, platform: str, vm_name: str) -> str:
    """Get detailed status of a specific VM."""
    try:
        manager = VMManager()
        connection_info = await manager.get_device_connection_info(device_id)

        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        provider = get_vm_provider(platform)

        async with asyncssh.connect(
            connection_info["hostname"],
            username=connection_info["username"],
            known_hosts=None,
        ) as conn:
            result = await provider.get_vm_status(conn, vm_name)
            result["device_id"] = device_id
            result["platform"] = platform

            return json.dumps(result, indent=2)

    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)})
    except Exception as e:
        return json.dumps(
            {"status": "error", "message": f"Failed to get VM status: {str(e)}"}
        )


async def list_vms_on_device(device_id: int, platforms: list[str] | None = None) -> str:
    """List all VMs on a specific device across platforms."""
    try:
        manager = VMManager()
        connection_info = await manager.get_device_connection_info(device_id)

        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        if platforms is None:
            platforms = ["docker", "lxd"]

        async with asyncssh.connect(
            connection_info["hostname"],
            username=connection_info["username"],
            known_hosts=None,
        ) as conn:
            all_vms = []
            platform_results = {}

            for platform in platforms:
                try:
                    provider = get_vm_provider(platform)
                    result = await provider.list_vms(conn)

                    if result.get("status") == "success":
                        vms = result.get("containers", [])
                        for vm in vms:
                            vm["platform"] = platform
                        all_vms.extend(vms)
                        platform_results[platform] = {
                            "status": "success",
                            "count": len(vms),
                        }
                    else:
                        platform_results[platform] = {
                            "status": "error",
                            "error": result.get("error", "Unknown error"),
                        }

                except ValueError:
                    platform_results[platform] = {
                        "status": "error",
                        "error": "Unsupported platform",
                    }
                except Exception as e:
                    platform_results[platform] = {"status": "error", "error": str(e)}

            return json.dumps(
                {
                    "status": "success",
                    "device_id": device_id,
                    "hostname": connection_info["hostname"],
                    "total_vms": len(all_vms),
                    "platforms_checked": list(platforms),
                    "platform_results": platform_results,
                    "vms": all_vms,
                },
                indent=2,
            )

    except Exception as e:
        return json.dumps(
            {"status": "error", "message": f"Failed to list VMs: {str(e)}"}
        )


async def get_vm_logs(
    device_id: int, platform: str, vm_name: str, lines: int = 100
) -> str:
    """Get logs from a specific VM."""
    try:
        manager = VMManager()
        connection_info = await manager.get_device_connection_info(device_id)

        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        provider = get_vm_provider(platform)

        async with asyncssh.connect(
            connection_info["hostname"],
            username=connection_info["username"],
            known_hosts=None,
        ) as conn:
            result = await provider.get_vm_logs(conn, vm_name, lines)
            result["device_id"] = device_id
            result["platform"] = platform

            return json.dumps(result, indent=2)

    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)})
    except Exception as e:
        return json.dumps(
            {"status": "error", "message": f"Failed to get VM logs: {str(e)}"}
        )


async def remove_vm(
    device_id: int, platform: str, vm_name: str, force: bool = False
) -> str:
    """Remove a VM/container from a device."""
    try:
        manager = VMManager()
        connection_info = await manager.get_device_connection_info(device_id)

        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        provider = get_vm_provider(platform)

        async with asyncssh.connect(
            connection_info["hostname"],
            username=connection_info["username"],
            known_hosts=None,
        ) as conn:
            result = await provider.remove_vm(conn, vm_name, force)
            result["device_id"] = device_id
            result["platform"] = platform

            return json.dumps(result, indent=2)

    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)})
    except Exception as e:
        return json.dumps(
            {"status": "error", "message": f"VM removal failed: {str(e)}"}
        )
