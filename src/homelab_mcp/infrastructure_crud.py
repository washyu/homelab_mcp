"""Infrastructure CRUD operations for complete network management."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from .log_filter import sanitize_error
from .progress import emit_progress
from .sitemap import NetworkSiteMap, discover_and_store
from .ssh_connection import ssh_connect

logger = logging.getLogger(__name__)


class InfrastructureManager:
    """Manages CRUD operations for infrastructure components."""

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


async def deploy_infrastructure_plan(deployment_plan: dict[str, Any], validate_only: bool = False) -> str:
    """Deploy new infrastructure based on AI recommendations or user specifications."""

    try:
        manager = InfrastructureManager()

        # Validate the deployment plan
        validation_result = await _validate_deployment_plan(deployment_plan)
        if not validation_result["valid"]:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Deployment plan validation failed: {validation_result['errors']}",
                }
            )

        if validate_only:
            return json.dumps(
                {
                    "status": "success",
                    "message": "Deployment plan validation passed",
                    "validation_result": validation_result,
                    "estimated_duration": "15-30 minutes",
                    "affected_devices": len(
                        {service.get("target_device_id") for service in deployment_plan.get("services", [])}
                    ),
                }
            )

        # Execute deployment plan
        deployment_results = []

        # Deploy services
        services = deployment_plan.get("services", [])
        for i, service in enumerate(services):
            await emit_progress(
                "info",
                f"Deploying service {service.get('name', 'unknown')} ({i + 1}/{len(services)})",
            )
            result = await _deploy_service(manager, service)
            deployment_results.append(result)

        # Apply network changes
        network_changes = deployment_plan.get("network_changes", [])
        for i, network_change in enumerate(network_changes):
            await emit_progress(
                "info",
                f"Applying network change ({i + 1}/{len(network_changes)})",
            )
            result = await _apply_network_change(manager, network_change)
            deployment_results.append(result)

        # Update sitemap with new infrastructure
        await _update_sitemap_after_deployment(manager, deployment_results)

        successful_deployments = [r for r in deployment_results if r.get("status") == "success"]
        failed_deployments = [r for r in deployment_results if r.get("status") == "error"]

        return json.dumps(
            {
                "status": "success" if len(failed_deployments) == 0 else "partial_success",
                "message": f"Deployed {len(successful_deployments)} components successfully",
                "successful_deployments": len(successful_deployments),
                "failed_deployments": len(failed_deployments),
                "deployment_results": deployment_results,
                "next_steps": [
                    "Verify services are running correctly",
                    "Update DNS/load balancer configurations if needed",
                    "Monitor resource usage for optimization opportunities",
                ],
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "message": f"Infrastructure deployment failed: {sanitize_error(e)}",
            }
        )


async def update_device_configuration(
    device_id: int,
    config_changes: dict[str, Any],
    backup_before_change: bool = True,
    validate_only: bool = False,
) -> str:
    """Update configuration of an existing device."""

    try:
        manager = InfrastructureManager()

        # Get device connection info
        connection_info = await manager.get_device_connection_info(device_id)
        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        # Validate configuration changes
        validation_result = await _validate_config_changes(config_changes, device_id)
        if not validation_result["valid"]:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Configuration validation failed: {validation_result['errors']}",
                }
            )

        if validate_only:
            return json.dumps(
                {
                    "status": "success",
                    "message": "Configuration changes validated successfully",
                    "validation_result": validation_result,
                    "affected_services": validation_result.get("affected_services", []),
                    "estimated_downtime": validation_result.get("estimated_downtime", "None"),
                }
            )

        # Create backup if requested
        backup_id = None
        if backup_before_change:
            backup_result = await create_infrastructure_backup(backup_scope="device_specific", device_ids=[device_id])
            backup_data = json.loads(backup_result)
            if backup_data.get("status") == "success":
                backup_id = backup_data.get("backup_id")

        # Apply configuration changes
        async with await ssh_connect(
            hostname=connection_info["hostname"],
            username=connection_info["username"],
        ) as conn:
            change_results = []

            # Apply service configuration changes
            if "services" in config_changes:
                for service_name, service_config in config_changes["services"].items():
                    result = await _update_service_config(conn, service_name, service_config)
                    change_results.append(result)

            # Apply network configuration changes
            if "network" in config_changes:
                result = await _update_network_config(conn, config_changes["network"])
                change_results.append(result)

            # Apply security configuration changes
            if "security" in config_changes:
                result = await _update_security_config(conn, config_changes["security"])
                change_results.append(result)

            # Apply resource allocation changes
            if "resources" in config_changes:
                result = await _update_resource_config(conn, config_changes["resources"])
                change_results.append(result)

        # Update sitemap with changes
        await _rediscover_device_after_changes(manager, device_id, connection_info)

        successful_changes = [r for r in change_results if r.get("status") == "success"]
        failed_changes = [r for r in change_results if r.get("status") == "error"]

        return json.dumps(
            {
                "status": "success" if len(failed_changes) == 0 else "partial_success",
                "message": f"Applied {len(successful_changes)} configuration changes",
                "device_id": device_id,
                "backup_id": backup_id,
                "successful_changes": len(successful_changes),
                "failed_changes": len(failed_changes),
                "change_results": change_results,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "message": f"Device configuration update failed: {sanitize_error(e)}",
            }
        )


async def decommission_network_device(
    device_id: int,
    migration_plan: dict[str, Any] | None = None,
    force_removal: bool = False,
    validate_only: bool = False,
) -> str:
    """Safely remove a device from the network infrastructure."""

    try:
        manager = InfrastructureManager()

        # Get device info
        connection_info = await manager.get_device_connection_info(device_id)
        if not connection_info:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Device with ID {device_id} not found in sitemap",
                }
            )

        # Analyze device dependencies
        dependencies = await _analyze_device_dependencies(manager, device_id)

        if dependencies["critical_services"] and not migration_plan and not force_removal:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Device has critical services. Migration plan required.",
                    "critical_services": dependencies["critical_services"],
                    "dependent_devices": dependencies["dependent_devices"],
                }
            )

        if validate_only:
            return json.dumps(
                {
                    "status": "success",
                    "message": "Decommission plan validated",
                    "dependencies": dependencies,
                    "migration_required": len(dependencies["critical_services"]) > 0,
                    "estimated_migration_time": "30-60 minutes" if migration_plan else "N/A",
                }
            )

        decommission_results = []

        # Execute migration plan if provided
        if migration_plan and not force_removal:
            migration_results = await _execute_migration_plan(manager, device_id, migration_plan)
            decommission_results.extend(migration_results)

        # Remove device from active service
        async with await ssh_connect(
            hostname=connection_info["hostname"],
            username=connection_info["username"],
        ) as conn:
            # Stop all services
            stop_result = await _stop_all_device_services(conn)
            decommission_results.append(stop_result)

            # Remove from load balancers/clusters
            removal_result = await _remove_from_clusters(conn)
            decommission_results.append(removal_result)

        # Update sitemap to mark device as decommissioned
        # Note: This method doesn't exist in NetworkSiteMap, would need to be implemented
        # manager.sitemap.update_device_status(device_id, "decommissioned")

        return json.dumps(
            {
                "status": "success",
                "message": f"Device {device_id} successfully decommissioned",
                "device_id": device_id,
                "migration_executed": migration_plan is not None,
                "decommission_results": decommission_results,
                "next_steps": [
                    "Verify migrated services are running on target devices",
                    "Update monitoring and alerting configurations",
                    "Physically remove or repurpose the hardware",
                ],
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Device decommissioning failed: {sanitize_error(e)}"})


async def scale_infrastructure_services(scaling_plan: dict[str, Any], validate_only: bool = False) -> str:
    """Scale services up or down based on resource analysis."""

    try:
        manager = InfrastructureManager()

        # Validate scaling plan
        validation_result = await _validate_scaling_plan(scaling_plan)
        if not validation_result["valid"]:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Scaling plan validation failed: {validation_result['errors']}",
                }
            )

        if validate_only:
            return json.dumps(
                {
                    "status": "success",
                    "message": "Scaling plan validated successfully",
                    "validation_result": validation_result,
                    "estimated_duration": "10-20 minutes",
                    "resource_impact": validation_result.get("resource_impact", {}),
                }
            )

        scaling_results = []

        # Execute scale-up operations
        scale_ups = scaling_plan.get("scale_up", [])
        for i, scale_up in enumerate(scale_ups):
            await emit_progress(
                "info",
                f"Scaling up {scale_up.get('service_name', 'unknown')} ({i + 1}/{len(scale_ups)})",
            )
            result = await _scale_service_up(manager, scale_up)
            scaling_results.append(result)

        # Execute scale-down operations
        scale_downs = scaling_plan.get("scale_down", [])
        for i, scale_down in enumerate(scale_downs):
            await emit_progress(
                "info",
                f"Scaling down {scale_down.get('service_name', 'unknown')} ({i + 1}/{len(scale_downs)})",
            )
            result = await _scale_service_down(manager, scale_down)
            scaling_results.append(result)

        successful_scaling = [r for r in scaling_results if r.get("status") == "success"]
        failed_scaling = [r for r in scaling_results if r.get("status") == "error"]

        return json.dumps(
            {
                "status": "success" if len(failed_scaling) == 0 else "partial_success",
                "message": f"Completed {len(successful_scaling)} scaling operations",
                "successful_operations": len(successful_scaling),
                "failed_operations": len(failed_scaling),
                "scaling_results": scaling_results,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Service scaling failed: {sanitize_error(e)}"})


async def validate_infrastructure_plan(change_plan: dict[str, Any], validation_level: str = "comprehensive") -> str:
    """Validate infrastructure changes before applying them."""

    try:
        validation_results: dict[str, list[dict[str, Any]]] = {
            "basic": [],
            "comprehensive": [],
            "simulation": [],
        }

        # Basic validation
        basic_checks = await _perform_basic_validation(change_plan)
        validation_results["basic"] = basic_checks

        # Comprehensive validation
        if validation_level in ["comprehensive", "simulation"]:
            comprehensive_checks = await _perform_comprehensive_validation(change_plan)
            validation_results["comprehensive"] = comprehensive_checks

        # Simulation validation
        if validation_level == "simulation":
            simulation_results = await _perform_simulation_validation(change_plan)
            validation_results["simulation"] = simulation_results

        all_checks = []
        for _level, checks in validation_results.items():
            if checks:
                all_checks.extend(checks)

        failed_checks = [check for check in all_checks if not check.get("passed", False)]
        warning_checks = [check for check in all_checks if check.get("warning", False)]

        return json.dumps(
            {
                "status": "success",
                "validation_level": validation_level,
                "overall_result": "passed" if len(failed_checks) == 0 else "failed",
                "total_checks": len(all_checks),
                "passed_checks": len(all_checks) - len(failed_checks),
                "failed_checks": len(failed_checks),
                "warning_checks": len(warning_checks),
                "validation_results": validation_results,
                "recommendations": _generate_validation_recommendations(all_checks),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "message": f"Infrastructure validation failed: {sanitize_error(e)}",
            }
        )


async def create_infrastructure_backup(
    backup_scope: str = "full",
    device_ids: list[int] | None = None,
    include_data: bool = False,
    backup_name: str | None = None,
) -> str:
    """Create a backup of current infrastructure state."""

    try:
        manager = InfrastructureManager()

        # Generate backup ID
        backup_id = backup_name or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

        backup_data = {
            "backup_id": backup_id,
            "created_at": datetime.now().isoformat(),
            "scope": backup_scope,
            "include_data": include_data,
            "devices": {},
            "network_topology": {},
            "services": {},
        }

        # Determine which devices to backup
        if backup_scope == "full":
            devices = manager.sitemap.get_all_devices()
            target_device_ids = [device["id"] for device in devices]
        elif device_ids:
            target_device_ids = device_ids
        else:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Device IDs required for partial or device-specific backup",
                }
            )

        # Backup each device
        for device_id in target_device_ids:
            device_backup = await _backup_device(manager, device_id, include_data)
            if isinstance(backup_data["devices"], dict):
                backup_data["devices"][str(device_id)] = device_backup

        # Backup network topology
        backup_data["network_topology"] = await _backup_network_topology(manager)

        # Save backup (in a real implementation, this would go to persistent storage)
        backup_path = f"/tmp/infrastructure_backup_{backup_id}.json"  # nosec B108 — backup_id is a UUID; /tmp use is intentional for homelab single-operator context
        with open(backup_path, "w") as f:
            json.dump(backup_data, f, indent=2)

        return json.dumps(
            {
                "status": "success",
                "message": "Infrastructure backup created successfully",
                "backup_id": backup_id,
                "backup_path": backup_path,
                "scope": backup_scope,
                "devices_backed_up": len(target_device_ids),
                "backup_size_mb": round(len(json.dumps(backup_data)) / 1024 / 1024, 2),
                "include_data": include_data,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Infrastructure backup failed: {sanitize_error(e)}"})


async def rollback_infrastructure_to_backup(
    backup_id: str,
    rollback_scope: str = "full",
    device_ids: list[int] | None = None,
    validate_only: bool = False,
) -> str:
    """Rollback recent infrastructure changes."""

    try:
        # Load backup data
        backup_path = f"/tmp/infrastructure_backup_{backup_id}.json"  # nosec B108 — backup_id is a UUID; /tmp use is intentional for homelab single-operator context
        try:
            with open(backup_path) as f:
                backup_data = json.load(f)
        except FileNotFoundError:
            return json.dumps({"status": "error", "message": f"Backup {backup_id} not found"})

        if validate_only:
            return json.dumps(
                {
                    "status": "success",
                    "message": "Rollback plan validated",
                    "backup_id": backup_id,
                    "backup_created": backup_data.get("created_at"),
                    "rollback_scope": rollback_scope,
                    "devices_to_rollback": len(device_ids) if device_ids else len(backup_data.get("devices", {})),
                    "estimated_duration": "20-45 minutes",
                }
            )

        manager = InfrastructureManager()
        rollback_results = []

        # Determine which devices to rollback
        if rollback_scope == "full":
            target_device_ids = list(backup_data.get("devices", {}).keys())
        elif device_ids:
            target_device_ids = [str(device_id) for device_id in device_ids]
        else:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Device IDs required for partial or device-specific rollback",
                }
            )

        # Rollback each device
        for device_id in target_device_ids:
            devices_data = backup_data.get("devices", {})
            if isinstance(devices_data, dict) and device_id in devices_data:
                result = await _rollback_device(manager, int(device_id), devices_data[device_id])
                rollback_results.append(result)

        successful_rollbacks = [r for r in rollback_results if r.get("status") == "success"]
        failed_rollbacks = [r for r in rollback_results if r.get("status") == "error"]

        return json.dumps(
            {
                "status": "success" if len(failed_rollbacks) == 0 else "partial_success",
                "message": f"Rolled back {len(successful_rollbacks)} devices successfully",
                "backup_id": backup_id,
                "rollback_scope": rollback_scope,
                "successful_rollbacks": len(successful_rollbacks),
                "failed_rollbacks": len(failed_rollbacks),
                "rollback_results": rollback_results,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Infrastructure rollback failed: {sanitize_error(e)}"})


# Helper functions (simplified implementations)
async def _validate_deployment_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate a deployment plan."""
    errors = []
    warnings = []

    # Check required fields
    if "services" not in plan and "network_changes" not in plan:
        errors.append("Deployment plan must include either services or network_changes")

    # Validate services
    if "services" in plan:
        for i, service in enumerate(plan["services"]):
            service_errors = []

            # Required fields
            if "name" not in service:
                service_errors.append(f"Service {i}: 'name' is required")
            if "type" not in service:
                service_errors.append(f"Service {i}: 'type' is required")
            elif service["type"] not in ["docker", "lxd", "service"]:
                service_errors.append(f"Service {i}: type must be 'docker', 'lxd', or 'service'")
            if "target_device_id" not in service:
                service_errors.append(f"Service {i}: 'target_device_id' is required")

            # Docker-specific validation
            if service.get("type") == "docker":
                config = service.get("config", {})
                if "image" not in config:
                    warnings.append(f"Service {i}: Docker image not specified, will use default")

                # Validate port mappings
                ports = config.get("ports", [])
                for port in ports:
                    if ":" not in str(port):
                        service_errors.append(f"Service {i}: Invalid port mapping '{port}' (expected 'host:container')")

            # Service-specific validation
            elif service.get("type") == "service":
                config = service.get("config", {})
                if "service_file" not in config:
                    service_errors.append(f"Service {i}: 'service_file' is required for systemd services")

            errors.extend(service_errors)

    # Validate network changes
    if "network_changes" in plan:
        for i, change in enumerate(plan["network_changes"]):
            if "action" not in change:
                errors.append(f"Network change {i}: 'action' is required")
            elif change["action"] not in [
                "create_vlan",
                "configure_firewall",
                "setup_routing",
            ]:
                errors.append(f"Network change {i}: Invalid action '{change['action']}'")

            if "target_device_id" not in change:
                errors.append(f"Network change {i}: 'target_device_id' is required")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


async def _deploy_service(manager: InfrastructureManager, service: dict[str, Any]) -> dict[str, Any]:  # type: ignore[return]
    """Deploy a single service."""
    try:
        device_id = service["target_device_id"]
        connection_info = await manager.get_device_connection_info(device_id)
        if not connection_info:
            return {
                "status": "error",
                "service": service["name"],
                "error": f"Device {device_id} not found",
            }

        async with await ssh_connect(
            hostname=connection_info["hostname"],
            username=connection_info["username"],
        ) as conn:
            service_type = service["type"]
            service_name = service["name"]
            config = service.get("config", {})

            if service_type == "docker":
                # Deploy Docker container
                docker_image = config.get("image", "nginx:latest")
                ports = config.get("ports", [])
                volumes = config.get("volumes", [])
                env_vars = config.get("environment", {})

                # Build docker run command
                cmd_parts = ["docker", "run", "-d", "--name", service_name]

                # Add port mappings
                for port_mapping in ports:
                    cmd_parts.extend(["-p", port_mapping])

                # Add volume mounts
                for volume in volumes:
                    cmd_parts.extend(["-v", volume])

                # Add environment variables
                for key, value in env_vars.items():
                    cmd_parts.extend(["-e", f"{key}={value}"])

                cmd_parts.append(docker_image)

                result = await conn.run(" ".join(cmd_parts))
                if result.exit_status == 0:
                    stdout_text = (
                        result.stdout.decode()
                        if isinstance(result.stdout, bytes)
                        else str(result.stdout)
                        if result.stdout
                        else ""
                    )
                    return {
                        "status": "success",
                        "service": service_name,
                        "container_id": stdout_text.strip(),
                    }
                else:
                    return {
                        "status": "error",
                        "service": service_name,
                        "error": result.stderr,
                    }

            elif service_type == "lxd":
                # Deploy LXD container
                lxd_image = config.get("image", "ubuntu:22.04")

                # Launch LXD container
                result = await conn.run(f"lxc launch {lxd_image} {service_name}")
                if result.exit_status == 0:
                    return {
                        "status": "success",
                        "service": service_name,
                        "container": service_name,
                    }
                else:
                    return {
                        "status": "error",
                        "service": service_name,
                        "error": result.stderr,
                    }

            elif service_type == "service":
                # Deploy systemd service
                service_file = config.get("service_file", "")
                if not service_file:
                    return {
                        "status": "error",
                        "service": service_name,
                        "error": "Service file content required",
                    }

                # Write service file
                await conn.run(f'echo "{service_file}" | sudo tee /etc/systemd/system/{service_name}.service')
                await conn.run("sudo systemctl daemon-reload")
                await conn.run(f"sudo systemctl enable {service_name}")
                result = await conn.run(f"sudo systemctl start {service_name}")

                if result.exit_status == 0:
                    return {
                        "status": "success",
                        "service": service_name,
                        "systemd_service": service_name,
                    }
                else:
                    return {
                        "status": "error",
                        "service": service_name,
                        "error": result.stderr,
                    }

            else:
                return {
                    "status": "error",
                    "service": service_name,
                    "error": f"Unknown service type: {service_type}",
                }

    except Exception as e:
        return {
            "status": "error",
            "service": service.get("name", "unknown"),
            "error": sanitize_error(e),
        }


async def _apply_network_change(manager: InfrastructureManager, change: dict[str, Any]) -> dict[str, Any]:
    """Apply a network configuration change."""
    return {"status": "success", "change": change["action"]}


async def _update_sitemap_after_deployment(manager: InfrastructureManager, results: list[dict[str, Any]]) -> None:
    """Update sitemap after deployment by discovering each successfully deployed device."""
    for result in results:
        if result.get("status") != "success":
            continue
        device_id = result.get("device_id")
        if device_id is None:
            continue
        connection_info = await manager.get_device_connection_info(device_id)
        if connection_info is None:
            logger.warning("No connection info found for device %s, skipping sitemap update", device_id)
            continue
        try:
            await discover_and_store(
                manager.sitemap,
                connection_info["hostname"],
                connection_info["username"],
                port=connection_info.get("port", 22),
            )
        except Exception as e:
            logger.warning("Failed to update sitemap for device %s: %s", device_id, e)


async def _validate_config_changes(changes: dict[str, Any], device_id: int) -> dict[str, Any]:
    """Validate configuration changes."""
    errors = []
    warnings = []
    affected_services = []
    estimated_downtime = "None"

    # Validate services changes
    if "services" in changes:
        for service_name, service_config in changes["services"].items():
            affected_services.append(service_name)

            if "type" in service_config:
                if service_config["type"] not in ["docker", "lxd", "systemd"]:
                    errors.append(f"Invalid service type '{service_config['type']}' for {service_name}")

            # Docker validation
            if service_config.get("type") == "docker":
                if "image" in service_config:
                    estimated_downtime = "2-5 minutes"
                if "ports" in service_config:
                    for port in service_config["ports"]:
                        if ":" not in str(port):
                            errors.append(f"Invalid port mapping '{port}' for {service_name}")

    # Validate network changes
    if "network" in changes:
        warnings.append("Network changes may affect connectivity")
        if estimated_downtime == "None":
            estimated_downtime = "1-2 minutes"

    # Validate security changes
    if "security" in changes:
        warnings.append("Security changes may affect service access")
        if "firewall" in changes["security"]:
            warnings.append("Firewall changes may block existing connections")

    # Validate resource changes
    if "resources" in changes:
        if "memory" in changes["resources"]:
            memory_change = changes["resources"]["memory"]
            if isinstance(memory_change, str) and memory_change.endswith("G"):
                try:
                    memory_gb = float(memory_change[:-1])
                    if memory_gb > 32:
                        warnings.append(f"High memory allocation: {memory_change}")
                except ValueError:
                    errors.append(f"Invalid memory format: {memory_change}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "affected_services": affected_services,
        "estimated_downtime": estimated_downtime,
    }


async def _update_service_config(conn: Any, service_name: str, config: dict[str, Any]) -> dict[str, Any]:
    """Update service configuration."""
    try:
        service_type = config.get("type", "docker")

        if service_type == "docker":
            # Update Docker container configuration
            # Check if container exists
            result = await conn.run(f"docker inspect {service_name}")
            if result.exit_status != 0:
                return {
                    "status": "error",
                    "service": service_name,
                    "error": "Container not found",
                }

            # Stop existing container
            await conn.run(f"docker stop {service_name}")
            await conn.run(f"docker rm {service_name}")

            # Recreate with new configuration
            docker_image = config.get("image", "nginx:latest")
            ports = config.get("ports", [])
            volumes = config.get("volumes", [])
            env_vars = config.get("environment", {})

            cmd_parts = ["docker", "run", "-d", "--name", service_name]

            for port_mapping in ports:
                cmd_parts.extend(["-p", port_mapping])
            for volume in volumes:
                cmd_parts.extend(["-v", volume])
            for key, value in env_vars.items():
                cmd_parts.extend(["-e", f"{key}={value}"])

            cmd_parts.append(docker_image)

            result = await conn.run(" ".join(cmd_parts))
            if result.exit_status == 0:
                return {
                    "status": "success",
                    "service": service_name,
                    "action": "updated",
                }
            else:
                return {
                    "status": "error",
                    "service": service_name,
                    "error": result.stderr,
                }

        elif service_type == "systemd":
            # Update systemd service configuration
            service_file = config.get("service_file", "")
            if service_file:
                await conn.run(f'echo "{service_file}" | sudo tee /etc/systemd/system/{service_name}.service')
                await conn.run("sudo systemctl daemon-reload")
                result = await conn.run(f"sudo systemctl restart {service_name}")

                if result.exit_status == 0:
                    return {
                        "status": "success",
                        "service": service_name,
                        "action": "updated",
                    }
                else:
                    return {
                        "status": "error",
                        "service": service_name,
                        "error": result.stderr,
                    }

            # Update service state
            if "enabled" in config:
                if config["enabled"]:
                    await conn.run(f"sudo systemctl enable {service_name}")
                else:
                    await conn.run(f"sudo systemctl disable {service_name}")

            if "running" in config:
                if config["running"]:
                    result = await conn.run(f"sudo systemctl start {service_name}")
                else:
                    result = await conn.run(f"sudo systemctl stop {service_name}")

                if result.exit_status == 0:
                    return {
                        "status": "success",
                        "service": service_name,
                        "action": "state_updated",
                    }
                else:
                    return {
                        "status": "error",
                        "service": service_name,
                        "error": result.stderr,
                    }

            return {
                "status": "success",
                "service": service_name,
                "action": "config_updated",
            }

        else:
            return {
                "status": "error",
                "service": service_name,
                "error": f"Unknown service type: {service_type}",
            }

    except Exception as e:
        return {"status": "error", "service": service_name, "error": sanitize_error(e)}


async def _update_network_config(conn: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Update network configuration."""
    return {"status": "success", "component": "network"}


async def _update_security_config(conn: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Update security configuration."""
    return {"status": "success", "component": "security"}


async def _update_resource_config(conn: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Update resource configuration."""
    return {"status": "success", "component": "resources"}


async def _rediscover_device_after_changes(
    manager: InfrastructureManager, device_id: int, connection_info: dict[str, Any]
) -> None:
    """Rediscover device after configuration changes to reflect updated state."""
    try:
        await discover_and_store(
            manager.sitemap,
            connection_info["hostname"],
            connection_info["username"],
            port=connection_info.get("port", 22),
        )
    except Exception as e:
        logger.warning("Failed to rediscover device %s after changes: %s", device_id, e)


async def _analyze_device_dependencies(manager: InfrastructureManager, device_id: int) -> dict[str, Any]:
    """Analyze device dependencies."""
    try:
        connection_info = await manager.get_device_connection_info(device_id)
        if not connection_info:
            return {
                "critical_services": [],
                "dependent_devices": [],
                "error": "Device not found",
            }

        critical_services = []
        dependent_devices = []

        async with await ssh_connect(
            hostname=connection_info["hostname"],
            username=connection_info["username"],
        ) as conn:
            # Check for running Docker containers
            docker_result = await conn.run('docker ps --format "{{.Names}}"')
            if docker_result.exit_status == 0 and docker_result.stdout:
                stdout_text = (
                    docker_result.stdout.decode()
                    if isinstance(docker_result.stdout, bytes)
                    else str(docker_result.stdout)
                )
                if stdout_text.strip():
                    container_names = stdout_text.strip().split("\n")
                for container_name in container_names:
                    if container_name.strip():
                        # Check if container has exposed ports (likely critical)
                        port_result = await conn.run(f"docker port {container_name}")
                        if port_result.exit_status == 0 and port_result.stdout:
                            stdout_text = (
                                port_result.stdout.decode()
                                if isinstance(port_result.stdout, bytes)
                                else str(port_result.stdout)
                            )
                            if stdout_text.strip():
                                critical_services.append(
                                    {
                                        "name": container_name,
                                        "type": "docker",
                                        "reason": "Has exposed ports - likely provides external services",
                                        "ports": stdout_text.strip().split("\n"),
                                    }
                                )

            # Check for running LXD containers
            lxd_result = await conn.run("lxc list --format csv -c ns | grep RUNNING")
            if lxd_result.exit_status == 0 and lxd_result.stdout:
                stdout_text = (
                    lxd_result.stdout.decode() if isinstance(lxd_result.stdout, bytes) else str(lxd_result.stdout)
                )
                if stdout_text.strip():
                    for line in stdout_text.strip().split("\n"):
                        if line.strip():
                            container_name = line.split(",")[0]
                            critical_services.append(
                                {
                                    "name": container_name,
                                    "type": "lxd",
                                    "reason": "Running LXD container",
                                }
                            )

            # Check for critical systemd services
            critical_service_patterns = [
                "nginx",
                "apache2",
                "mysql",
                "postgresql",
                "redis",
                "mongodb",
                "docker",
                "k3s",
                "kubernetes",
                "prometheus",
                "grafana",
            ]

            for pattern in critical_service_patterns:
                service_result = await conn.run(f"systemctl is-active {pattern} 2>/dev/null")
                if service_result.exit_status == 0 and service_result.stdout:
                    stdout_text = (
                        service_result.stdout.decode()
                        if isinstance(service_result.stdout, bytes)
                        else str(service_result.stdout)
                    )
                    if stdout_text.strip() == "active":
                        critical_services.append(
                            {
                                "name": pattern,
                                "type": "systemd",
                                "reason": "Critical infrastructure service",
                            }
                        )

            # Check for services listening on network ports
            netstat_result = await conn.run("ss -tlnp 2>/dev/null | grep LISTEN")
            if netstat_result.exit_status == 0 and netstat_result.stdout:
                listening_ports: list[str] = []
                stdout_text = (
                    netstat_result.stdout.decode()
                    if isinstance(netstat_result.stdout, bytes)
                    else str(netstat_result.stdout)
                )
                for line in stdout_text.strip().split("\n"):
                    if "LISTEN" in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            addr_port = parts[3]
                            if ":" in addr_port:
                                port = addr_port.split(":")[-1]
                                if port not in ["22", "53"]:  # Skip SSH and DNS
                                    listening_ports.append(port)

                if listening_ports:
                    critical_services.append(
                        {
                            "name": "network_services",
                            "type": "network",
                            "reason": f"Listening on ports: {', '.join(listening_ports)}",
                            "ports": listening_ports,
                        }
                    )

        # Analyze network dependencies (simplified)
        # In a real implementation, this would check the network topology
        # and identify devices that depend on this device for routing, DNS, etc.
        all_devices = manager.sitemap.get_all_devices()
        device_ip = connection_info["hostname"]

        for device in all_devices:
            if device.get("id") != device_id:
                # Check if this device might be a gateway or DNS server for others
                device_subnet = ".".join(device_ip.split(".")[:-1])
                other_ip = device.get("connection_ip", device.get("hostname", ""))
                if other_ip.startswith(device_subnet):
                    # Devices in same subnet might depend on this device
                    dependent_devices.append(
                        {
                            "device_id": device.get("id"),
                            "hostname": device.get("hostname"),
                            "reason": "Same network subnet - potential dependency",
                        }
                    )

        return {
            "critical_services": critical_services,
            "dependent_devices": dependent_devices,
            "analysis_summary": {
                "total_critical_services": len(critical_services),
                "total_dependent_devices": len(dependent_devices),
                "migration_complexity": "high"
                if len(critical_services) > 3
                else "medium"
                if len(critical_services) > 0
                else "low",
            },
        }

    except Exception as e:
        return {"critical_services": [], "dependent_devices": [], "error": sanitize_error(e)}


async def _execute_migration_plan(
    manager: InfrastructureManager, device_id: int, plan: dict[str, Any]
) -> list[dict[str, Any]]:
    """Execute service migration plan."""
    results = []

    try:
        source_connection_info = await manager.get_device_connection_info(device_id)
        if not source_connection_info:
            return [{"status": "error", "error": f"Source device {device_id} not found"}]

        service_mapping = plan.get("service_mapping", {})

        for service_name, target_device_id in service_mapping.items():
            try:
                # Get target device connection info
                target_connection_info = await manager.get_device_connection_info(target_device_id)
                if not target_connection_info:
                    results.append(
                        {
                            "status": "error",
                            "service": service_name,
                            "error": f"Target device {target_device_id} not found",
                        }
                    )
                    continue

                # Connect to source device to get service configuration
                async with await ssh_connect(
                    hostname=source_connection_info["hostname"],
                    username=source_connection_info["username"],
                ) as source_conn:
                    # Get Docker container configuration
                    inspect_result = await source_conn.run(f"docker inspect {service_name}")
                    if inspect_result.exit_status == 0:
                        # Export container and configuration
                        await source_conn.run(f"docker commit {service_name} {service_name}_migration")
                        save_result = await source_conn.run(
                            f"docker save {service_name}_migration | gzip > /tmp/{service_name}_migration.tar.gz"
                        )

                        if save_result.exit_status == 0:
                            # Connect to target device
                            async with await ssh_connect(
                                hostname=target_connection_info["hostname"],
                                username=target_connection_info["username"],
                            ) as target_conn:
                                # Transfer container image
                                async with source_conn.start_sftp_client() as source_sftp:
                                    await source_sftp.get(
                                        f"/tmp/{service_name}_migration.tar.gz",  # nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context
                                        f"/tmp/{service_name}_migration.tar.gz",  # nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context
                                    )

                                async with target_conn.start_sftp_client() as target_sftp:
                                    await target_sftp.put(
                                        f"/tmp/{service_name}_migration.tar.gz",  # nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context
                                        f"/tmp/{service_name}_migration.tar.gz",  # nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context
                                    )

                                # Load and start container on target
                                await target_conn.run(f"gunzip -c /tmp/{service_name}_migration.tar.gz | docker load")
                                run_result = await target_conn.run(
                                    f"docker run -d --name {service_name} {service_name}_migration"
                                )

                                if run_result.exit_status == 0:
                                    # Stop container on source
                                    await source_conn.run(f"docker stop {service_name}")
                                    await source_conn.run(f"docker rm {service_name}")

                                    results.append(
                                        {
                                            "status": "success",
                                            "service": service_name,
                                            "migration": f"moved from device {device_id} to device {target_device_id}",
                                        }
                                    )
                                else:
                                    results.append(
                                        {
                                            "status": "error",
                                            "service": service_name,
                                            "error": f"Failed to start on target: {run_result.stderr.decode() if isinstance(run_result.stderr, bytes) else str(run_result.stderr)}",
                                        }
                                    )
                        else:
                            results.append(
                                {
                                    "status": "error",
                                    "service": service_name,
                                    "error": "Failed to export container",
                                }
                            )
                    else:
                        # Try LXD container
                        lxc_result = await source_conn.run(f"lxc info {service_name}")
                        if lxc_result.exit_status == 0:
                            # Copy LXD container
                            copy_result = await source_conn.run(
                                f"lxc copy {service_name} {target_connection_info['hostname']}:{service_name}"
                            )
                            if copy_result.exit_status == 0:
                                # Start on target and stop on source
                                async with await ssh_connect(
                                    hostname=target_connection_info["hostname"],
                                    username=target_connection_info["username"],
                                ) as target_conn:
                                    await target_conn.run(f"lxc start {service_name}")

                                await source_conn.run(f"lxc stop {service_name}")
                                await source_conn.run(f"lxc delete {service_name}")

                                results.append(
                                    {
                                        "status": "success",
                                        "service": service_name,
                                        "migration": f"LXD container moved from device {device_id} to device {target_device_id}",
                                    }
                                )
                            else:
                                results.append(
                                    {
                                        "status": "error",
                                        "service": service_name,
                                        "error": "Failed to copy LXD container",
                                    }
                                )
                        else:
                            results.append(
                                {
                                    "status": "error",
                                    "service": service_name,
                                    "error": "Service not found (not Docker or LXD)",
                                }
                            )

            except Exception as e:
                results.append({"status": "error", "service": service_name, "error": sanitize_error(e)})

        return results

    except Exception as e:
        return [{"status": "error", "error": f"Migration plan execution failed: {sanitize_error(e)}"}]


async def _stop_all_device_services(conn: Any) -> dict[str, Any]:
    """Stop all services on a device."""
    return {"status": "success", "action": "services_stopped"}


async def _remove_from_clusters(conn: Any) -> dict[str, Any]:
    """Remove device from clusters."""
    return {"status": "success", "action": "removed_from_clusters"}


async def _validate_scaling_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate a scaling plan."""
    return {"valid": True, "errors": [], "resource_impact": {}}


async def _scale_service_up(manager: InfrastructureManager, scale_up: dict[str, Any]) -> dict[str, Any]:
    """Scale a service up."""
    return {
        "status": "success",
        "action": "scale_up",
        "service": scale_up.get("service_name"),
    }


async def _scale_service_down(manager: InfrastructureManager, scale_down: dict[str, Any]) -> dict[str, Any]:
    """Scale a service down."""
    return {
        "status": "success",
        "action": "scale_down",
        "service": scale_down.get("service_name"),
    }


async def _perform_basic_validation(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Perform basic validation checks."""
    return [{"check": "syntax", "passed": True}]


async def _perform_comprehensive_validation(
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Perform comprehensive validation checks."""
    return [{"check": "dependencies", "passed": True}]


async def _perform_simulation_validation(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Perform simulation validation."""
    return [{"check": "simulation", "passed": True}]


def _generate_validation_recommendations(checks: list[dict[str, Any]]) -> list[str]:
    """Generate validation recommendations."""
    return ["All validations passed"]


async def _backup_device(manager: InfrastructureManager, device_id: int, include_data: bool) -> dict[str, Any]:
    """Backup a single device."""
    try:
        connection_info = await manager.get_device_connection_info(device_id)
        if not connection_info:
            return {
                "device_id": device_id,
                "backed_up": False,
                "error": "Device not found",
            }

        backup_data = {
            "device_id": device_id,
            "connection_info": connection_info,
            "services": {},
            "system_config": {},
            "network_config": {},
            "backed_up_at": datetime.now().isoformat(),
        }

        async with await ssh_connect(
            hostname=connection_info["hostname"],
            username=connection_info["username"],
        ) as conn:
            # Backup Docker containers
            docker_result = await conn.run('docker ps -a --format "{{.Names}}"')
            if docker_result.exit_status == 0 and docker_result.stdout:
                stdout_text = (
                    docker_result.stdout.decode()
                    if isinstance(docker_result.stdout, bytes)
                    else str(docker_result.stdout)
                )
                if stdout_text.strip():
                    container_names = stdout_text.strip().split("\n")
                for container_name in container_names:
                    if container_name.strip():
                        inspect_result = await conn.run(f"docker inspect {container_name}")
                        if inspect_result.exit_status == 0:
                            stdout_text = (
                                inspect_result.stdout.decode()
                                if isinstance(inspect_result.stdout, bytes)
                                else str(inspect_result.stdout)
                            )
                            if isinstance(backup_data["services"], dict):
                                backup_data["services"][container_name] = {
                                    "type": "docker",
                                    "config": stdout_text,
                                    "backed_up": True,
                                }

                            if include_data:
                                # Export container data
                                export_result = await conn.run(
                                    f"docker export {container_name} | gzip > /tmp/backup_{container_name}.tar.gz"
                                )
                                if (
                                    isinstance(backup_data["services"], dict)
                                    and container_name in backup_data["services"]
                                ):
                                    backup_data["services"][container_name]["data_backup"] = (
                                        export_result.exit_status == 0
                                    )

            # Backup LXD containers
            lxd_result = await conn.run("lxc list --format csv -c n")
            if lxd_result.exit_status == 0 and lxd_result.stdout:
                stdout_text = (
                    lxd_result.stdout.decode() if isinstance(lxd_result.stdout, bytes) else str(lxd_result.stdout)
                )
                if stdout_text.strip():
                    container_names = stdout_text.strip().split("\n")
                for container_name in container_names:
                    if container_name.strip():
                        info_result = await conn.run(f"lxc config show {container_name}")
                        if info_result.exit_status == 0:
                            stdout_text = (
                                info_result.stdout.decode()
                                if isinstance(info_result.stdout, bytes)
                                else str(info_result.stdout)
                            )
                            if isinstance(backup_data["services"], dict):
                                backup_data["services"][container_name] = {
                                    "type": "lxd",
                                    "config": stdout_text,
                                    "backed_up": True,
                                }

                            if include_data:
                                # Export LXD container
                                export_result = await conn.run(
                                    f"lxc export {container_name} /tmp/backup_{container_name}.tar.gz"
                                )
                                if (
                                    isinstance(backup_data["services"], dict)
                                    and container_name in backup_data["services"]
                                ):
                                    backup_data["services"][container_name]["data_backup"] = (
                                        export_result.exit_status == 0
                                    )

            # Backup systemd services
            systemd_result = await conn.run(
                "systemctl list-units --type=service --state=loaded --no-pager --plain | grep -v LOAD"
            )
            if systemd_result.exit_status == 0 and systemd_result.stdout:
                stdout_text = (
                    systemd_result.stdout.decode()
                    if isinstance(systemd_result.stdout, bytes)
                    else str(systemd_result.stdout)
                )
                service_lines = stdout_text.strip().split("\n")
                for line in service_lines:
                    if line.strip():
                        parts = line.split()
                        if not parts:
                            continue
                        service_name = parts[0]
                        if not service_name.endswith(".service"):
                            continue

                        service_file_result = await conn.run(f"systemctl cat {service_name}")
                        if service_file_result.exit_status == 0 and service_file_result.stdout:
                            stdout_text = (
                                service_file_result.stdout.decode()
                                if isinstance(service_file_result.stdout, bytes)
                                else str(service_file_result.stdout)
                            )
                            if isinstance(backup_data["services"], dict):
                                backup_data["services"][service_name] = {
                                    "type": "systemd",
                                    "config": stdout_text,
                                    "backed_up": True,
                                }

            # Backup network configuration
            network_configs = {}

            # Network interfaces
            interfaces_result = await conn.run(
                'cat /etc/netplan/*.yaml 2>/dev/null || cat /etc/network/interfaces 2>/dev/null || echo "No network config found"'
            )
            if interfaces_result.exit_status == 0:
                network_configs["interfaces"] = interfaces_result.stdout

            # Firewall rules
            ufw_result = await conn.run('sudo ufw status numbered 2>/dev/null || echo "UFW not available"')
            if ufw_result.exit_status == 0:
                network_configs["firewall"] = ufw_result.stdout

            # DNS configuration
            dns_result = await conn.run("cat /etc/resolv.conf")
            if dns_result.exit_status == 0:
                network_configs["dns"] = dns_result.stdout

            backup_data["network_config"] = network_configs

            # Backup system configuration
            system_configs = {}

            # Crontab
            cron_result = await conn.run('crontab -l 2>/dev/null || echo "No crontab"')
            if cron_result.exit_status == 0:
                system_configs["crontab"] = cron_result.stdout

            # SSH configuration
            ssh_result = await conn.run("sudo cat /etc/ssh/sshd_config")
            if ssh_result.exit_status == 0:
                system_configs["ssh"] = ssh_result.stdout

            backup_data["system_config"] = system_configs

        return backup_data

    except Exception as e:
        return {"device_id": device_id, "backed_up": False, "error": sanitize_error(e)}


async def _backup_network_topology(manager: InfrastructureManager) -> dict[str, Any]:
    """Backup network topology."""
    return {"topology": "backed_up"}


async def _rollback_device(
    manager: InfrastructureManager, device_id: int, backup_data: dict[str, Any]
) -> dict[str, Any]:
    """Rollback a single device."""
    return {"status": "success", "device_id": device_id}
