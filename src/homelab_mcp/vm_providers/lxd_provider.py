"""LXD provider for VM operations."""

from typing import Any

from ..log_filter import sanitize_error
from .base import VMProvider


class LXDProvider(VMProvider):
    """LXD implementation of VM provider."""

    async def deploy_vm(self, conn: Any, vm_name: str, vm_config: dict[str, Any]) -> dict[str, Any]:
        """Deploy a new LXD container."""
        try:
            # Check if container already exists
            check_result = await self._run_command(conn, f"lxc info {vm_name}")
            if check_result["exit_status"] == 0:
                return self._format_error("deploy", vm_name, "Container already exists")

            # Extract configuration
            image = vm_config.get("image", "ubuntu:22.04")
            vm_type = vm_config.get("type", "container")  # container or virtual-machine
            profiles = vm_config.get("profiles", ["default"])
            config = vm_config.get("config", {})

            # Build lxc launch command
            cmd_parts = ["lxc", "launch", image, vm_name]

            # Add VM type if specified
            if vm_type == "virtual-machine":
                cmd_parts.extend(["--vm"])

            # Add profiles
            for profile in profiles:
                cmd_parts.extend(["-p", profile])

            # Add configuration options
            for key, value in config.items():
                cmd_parts.extend(["-c", f"{key}={value}"])

            # Execute deployment
            deploy_result = await self._run_command(conn, " ".join(cmd_parts))

            if deploy_result["exit_status"] == 0:
                # Get container details
                info_result = await self._run_command(conn, f"lxc info {vm_name}")
                if info_result["exit_status"] == 0:
                    # Parse LXD info output
                    info_lines = info_result["stdout"].split("\\n")
                    container_info = {}
                    for line in info_lines:
                        if ":" in line:
                            key, value = line.split(":", 1)
                            container_info[key.strip()] = value.strip()

                    return self._format_success(
                        "deploy",
                        vm_name,
                        {
                            "image": image,
                            "type": vm_type,
                            "profiles": profiles,
                            "container_status": container_info.get("Status", "unknown"),
                            "architecture": container_info.get("Architecture", "unknown"),
                        },
                    )
                else:
                    return self._format_success("deploy", vm_name, {"image": image, "type": vm_type})
            else:
                return self._format_error("deploy", vm_name, deploy_result["stderr"])

        except Exception as e:
            return self._format_error("deploy", vm_name, e)

    async def start_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Start an LXD container."""
        try:
            result = await self._run_command(conn, f"lxc start {vm_name}")

            if result["exit_status"] == 0:
                # Get updated status
                status_result = await self.get_vm_status(conn, vm_name)
                return self._format_success(
                    "start",
                    vm_name,
                    {
                        "message": "Container started successfully",
                        "container_status": status_result.get("container_status", "unknown"),
                    },
                )
            else:
                return self._format_error("start", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("start", vm_name, e)

    async def stop_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Stop an LXD container."""
        try:
            result = await self._run_command(conn, f"lxc stop {vm_name}")

            if result["exit_status"] == 0:
                return self._format_success("stop", vm_name, {"message": "Container stopped successfully"})
            else:
                return self._format_error("stop", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("stop", vm_name, e)

    async def restart_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Restart an LXD container."""
        try:
            result = await self._run_command(conn, f"lxc restart {vm_name}")

            if result["exit_status"] == 0:
                # Get updated status
                status_result = await self.get_vm_status(conn, vm_name)
                return self._format_success(
                    "restart",
                    vm_name,
                    {
                        "message": "Container restarted successfully",
                        "container_status": status_result.get("container_status", "unknown"),
                    },
                )
            else:
                return self._format_error("restart", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("restart", vm_name, e)

    async def get_vm_status(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Get LXD container status."""
        try:
            info_result = await self._run_command(conn, f"lxc info {vm_name}")

            if info_result["exit_status"] == 0:
                # Parse LXD info output
                info_lines = info_result["stdout"].split("\\n")
                container_info: dict[str, Any] = {}
                current_section = None

                for line in info_lines:
                    line = line.strip()
                    if not line:
                        continue

                    if line.endswith(":") and not line.startswith(" "):
                        current_section = line[:-1]
                        container_info[current_section] = {}
                    elif ":" in line and current_section:
                        key, value = line.split(":", 1)
                        container_info[current_section][key.strip()] = value.strip()
                    elif ":" in line:
                        key, value = line.split(":", 1)
                        container_info[key.strip()] = value.strip()

                # Get network information
                network_result = await self._run_command(conn, f"lxc list {vm_name} -c n --format csv")
                network_info = network_result["stdout"].strip() if network_result["exit_status"] == 0 else ""

                return {
                    "status": "success",
                    "vm_name": vm_name,
                    "container_status": container_info.get("Status", "unknown"),
                    "type": container_info.get("Type", "unknown"),
                    "architecture": container_info.get("Architecture", "unknown"),
                    "created": container_info.get("Created", "unknown"),
                    "network": network_info,
                    "pid": container_info.get("Pid", 0),
                    "processes": container_info.get("Processes", 0),
                }
            else:
                return self._format_error("get_status", vm_name, "Container not found")

        except Exception as e:
            return self._format_error("get_status", vm_name, e)

    async def list_vms(self, conn: Any) -> dict[str, Any]:
        """List all LXD containers."""
        try:
            # Get container list with details
            result = await self._run_command(conn, "lxc list --format csv -c ns4tS")

            if result["exit_status"] == 0:
                containers = []
                for line in result["stdout"].strip().split("\\n"):
                    if line.strip():
                        parts = line.split(",")
                        if len(parts) >= 2:
                            containers.append(
                                {
                                    "name": parts[0],
                                    "status": parts[1],
                                    "ipv4": parts[2] if len(parts) > 2 else "",
                                    "type": parts[3] if len(parts) > 3 else "container",
                                    "snapshots": parts[4] if len(parts) > 4 else "0",
                                }
                            )

                return {
                    "status": "success",
                    "platform": "lxd",
                    "total_containers": len(containers),
                    "containers": containers,
                }
            else:
                return {"status": "error", "platform": "lxd", "error": result["stderr"]}

        except Exception as e:
            return {
                "status": "error",
                "platform": "lxd",
                "error": str(e),
                "error_type": type(e).__name__,
                "detail": sanitize_error(e),
            }

    async def get_vm_logs(self, conn: Any, vm_name: str, lines: int = 100) -> dict[str, Any]:
        """Get LXD container logs."""
        try:
            # LXD doesn't have direct log command, so we'll get system logs
            result = await self._run_command(conn, f"lxc exec {vm_name} -- journalctl --no-pager -n {lines}")

            if result["exit_status"] == 0:
                return {
                    "status": "success",
                    "vm_name": vm_name,
                    "platform": "lxd",
                    "lines_requested": lines,
                    "logs": result["stdout"],
                    "log_type": "journalctl",
                }
            else:
                # Fallback to dmesg if journalctl fails
                dmesg_result = await self._run_command(conn, f"lxc exec {vm_name} -- dmesg | tail -n {lines}")
                if dmesg_result["exit_status"] == 0:
                    return {
                        "status": "success",
                        "vm_name": vm_name,
                        "platform": "lxd",
                        "lines_requested": lines,
                        "logs": dmesg_result["stdout"],
                        "log_type": "dmesg",
                    }
                else:
                    return self._format_error("get_logs", vm_name, "Unable to retrieve logs")

        except Exception as e:
            return self._format_error("get_logs", vm_name, e)

    async def remove_vm(self, conn: Any, vm_name: str, force: bool = False) -> dict[str, Any]:
        """Remove an LXD container."""
        try:
            # Stop container first if it's running (unless force is used)
            if not force:
                await self._run_command(conn, f"lxc stop {vm_name}")

            # Remove container
            force_flag = "--force" if force else ""
            result = await self._run_command(conn, f"lxc delete {force_flag} {vm_name}")

            if result["exit_status"] == 0:
                return self._format_success(
                    "remove",
                    vm_name,
                    {"message": "Container removed successfully", "forced": force},
                )
            else:
                return self._format_error("remove", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("remove", vm_name, e)

    async def create_snapshot(self, conn: Any, vm_name: str, snapshot_name: str) -> dict[str, Any]:
        """Create a snapshot of an LXD container."""
        try:
            result = await self._run_command(conn, f"lxc snapshot {vm_name} {snapshot_name}")

            if result["exit_status"] == 0:
                return self._format_success(
                    "snapshot",
                    vm_name,
                    {
                        "message": "Snapshot created successfully",
                        "snapshot_name": snapshot_name,
                    },
                )
            else:
                return self._format_error("snapshot", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("snapshot", vm_name, e)

    async def restore_snapshot(self, conn: Any, vm_name: str, snapshot_name: str) -> dict[str, Any]:
        """Restore an LXD container from a snapshot."""
        try:
            result = await self._run_command(conn, f"lxc restore {vm_name} {snapshot_name}")

            if result["exit_status"] == 0:
                return self._format_success(
                    "restore",
                    vm_name,
                    {
                        "message": "Snapshot restored successfully",
                        "snapshot_name": snapshot_name,
                    },
                )
            else:
                return self._format_error("restore", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("restore", vm_name, e)
