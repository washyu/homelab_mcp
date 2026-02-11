"""Docker provider for VM operations."""

import json
from typing import Any

from .base import VMProvider


class DockerProvider(VMProvider):
    """Docker implementation of VM provider."""

    async def deploy_vm(self, conn: Any, vm_name: str, vm_config: dict[str, Any]) -> dict[str, Any]:
        """Deploy a new Docker container."""
        try:
            # Check if container already exists
            check_result = await self._run_command(conn, f"docker inspect {vm_name}")
            if check_result["exit_status"] == 0:
                return self._format_error("deploy", vm_name, "Container already exists")

            # Extract configuration
            image = vm_config.get("image", "ubuntu:22.04")
            ports = vm_config.get("ports", [])
            volumes = vm_config.get("volumes", [])
            environment = vm_config.get("environment", {})
            network = vm_config.get("network", "bridge")
            restart_policy = vm_config.get("restart_policy", "unless-stopped")

            # Build docker run command
            cmd_parts = ["docker", "run", "-d"]
            cmd_parts.extend(["--name", vm_name])
            cmd_parts.extend(["--restart", restart_policy])
            cmd_parts.extend(["--network", network])

            # Add port mappings
            for port in ports:
                cmd_parts.extend(["-p", port])

            # Add volume mounts
            for volume in volumes:
                cmd_parts.extend(["-v", volume])

            # Add environment variables
            for key, value in environment.items():
                cmd_parts.extend(["-e", f"{key}={value}"])

            # Add the image
            cmd_parts.append(image)

            # Add command if specified
            if "command" in vm_config:
                cmd_parts.extend(vm_config["command"].split())

            # Execute deployment
            deploy_result = await self._run_command(conn, " ".join(cmd_parts))

            if deploy_result["exit_status"] == 0:
                container_id = deploy_result["stdout"].strip()

                # Get container details
                inspect_result = await self._run_command(conn, f"docker inspect {vm_name}")
                if inspect_result["exit_status"] == 0:
                    container_info = json.loads(inspect_result["stdout"])[0]

                    return self._format_success(
                        "deploy",
                        vm_name,
                        {
                            "container_id": container_id,
                            "image": image,
                            "network": network,
                            "ports": container_info.get("NetworkSettings", {}).get("Ports", {}),
                            "container_status": container_info.get("State", {}).get("Status", "unknown"),
                        },
                    )
                else:
                    return self._format_success("deploy", vm_name, {"container_id": container_id})
            else:
                return self._format_error("deploy", vm_name, deploy_result["stderr"])

        except Exception as e:
            return self._format_error("deploy", vm_name, str(e))

    async def start_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Start a Docker container."""
        try:
            result = await self._run_command(conn, f"docker start {vm_name}")

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
            return self._format_error("start", vm_name, str(e))

    async def stop_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Stop a Docker container."""
        try:
            result = await self._run_command(conn, f"docker stop {vm_name}")

            if result["exit_status"] == 0:
                return self._format_success("stop", vm_name, {"message": "Container stopped successfully"})
            else:
                return self._format_error("stop", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("stop", vm_name, str(e))

    async def restart_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Restart a Docker container."""
        try:
            result = await self._run_command(conn, f"docker restart {vm_name}")

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
            return self._format_error("restart", vm_name, str(e))

    async def get_vm_status(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Get Docker container status."""
        try:
            inspect_result = await self._run_command(conn, f"docker inspect {vm_name}")

            if inspect_result["exit_status"] == 0:
                container_info = json.loads(inspect_result["stdout"])[0]
                state = container_info.get("State", {})

                return {
                    "status": "success",
                    "vm_name": vm_name,
                    "container_status": state.get("Status", "unknown"),
                    "running": state.get("Running", False),
                    "pid": state.get("Pid", 0),
                    "started_at": state.get("StartedAt", ""),
                    "finished_at": state.get("FinishedAt", ""),
                    "exit_code": state.get("ExitCode", 0),
                    "image": container_info.get("Config", {}).get("Image", ""),
                    "ports": container_info.get("NetworkSettings", {}).get("Ports", {}),
                    "mounts": [
                        mount["Source"] + ":" + mount["Destination"] for mount in container_info.get("Mounts", [])
                    ],
                }
            else:
                return self._format_error("get_status", vm_name, "Container not found")

        except Exception as e:
            return self._format_error("get_status", vm_name, str(e))

    async def list_vms(self, conn: Any) -> dict[str, Any]:
        """List all Docker containers."""
        try:
            # Get all containers (running and stopped)
            result = await self._run_command(
                conn,
                "docker ps -a --format '{{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'",
            )

            if result["exit_status"] == 0:
                containers = []
                for line in result["stdout"].strip().split("\\n"):
                    if line.strip():
                        parts = line.split("\\t")
                        if len(parts) >= 3:
                            containers.append(
                                {
                                    "name": parts[0],
                                    "image": parts[1],
                                    "status": parts[2],
                                    "ports": parts[3] if len(parts) > 3 else "",
                                }
                            )

                return {
                    "status": "success",
                    "platform": "docker",
                    "total_containers": len(containers),
                    "containers": containers,
                }
            else:
                return {
                    "status": "error",
                    "platform": "docker",
                    "error": result["stderr"],
                }

        except Exception as e:
            return {"status": "error", "platform": "docker", "error": str(e)}

    async def get_vm_logs(self, conn: Any, vm_name: str, lines: int = 100) -> dict[str, Any]:
        """Get Docker container logs."""
        try:
            result = await self._run_command(conn, f"docker logs --tail {lines} {vm_name}")

            if result["exit_status"] == 0:
                return {
                    "status": "success",
                    "vm_name": vm_name,
                    "platform": "docker",
                    "lines_requested": lines,
                    "logs": result["stdout"],
                }
            else:
                return self._format_error("get_logs", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("get_logs", vm_name, str(e))

    async def remove_vm(self, conn: Any, vm_name: str, force: bool = False) -> dict[str, Any]:
        """Remove a Docker container."""
        try:
            # Stop container first if it's running (unless force is used)
            if not force:
                await self._run_command(conn, f"docker stop {vm_name}")

            # Remove container
            force_flag = "-f" if force else ""
            result = await self._run_command(conn, f"docker rm {force_flag} {vm_name}")

            if result["exit_status"] == 0:
                return self._format_success(
                    "remove",
                    vm_name,
                    {"message": "Container removed successfully", "forced": force},
                )
            else:
                return self._format_error("remove", vm_name, result["stderr"])

        except Exception as e:
            return self._format_error("remove", vm_name, str(e))
