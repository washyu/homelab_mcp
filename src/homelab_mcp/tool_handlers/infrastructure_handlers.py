"""Handler functions for infrastructure CRUD operations."""

from typing import Any

from ..infrastructure_crud import (
    create_infrastructure_backup,
    decommission_network_device,
    deploy_infrastructure_plan,
    rollback_infrastructure_to_backup,
    scale_infrastructure_services,
    update_device_configuration,
    validate_infrastructure_plan,
)


async def handle_deploy_infrastructure(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle deploy_infrastructure tool."""
    result = await deploy_infrastructure_plan(
        deployment_plan=arguments["deployment_plan"],
        validate_only=arguments.get("validate_only", False),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_update_device_config(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update_device_config tool."""
    result = await update_device_configuration(
        device_id=arguments["device_id"],
        config_changes=arguments["config_changes"],
        backup_before_change=arguments.get("backup_before_change", True),
        validate_only=arguments.get("validate_only", False),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_decommission_device(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle decommission_device tool."""
    if arguments.get("dry_run", False):
        from ..dry_run import build_dry_run_response

        would_affect: list[dict[str, Any]] = [
            {"resource_type": "device", "device_id": arguments["device_id"]},
        ]
        return build_dry_run_response(
            tool_name="decommission_device",
            would_affect=would_affect,
            risk_level="high",
            reversible=False,
        )
    result = await decommission_network_device(
        device_id=arguments["device_id"],
        migration_plan=arguments.get("migration_plan"),
        force_removal=arguments.get("force_removal", False),
        validate_only=arguments.get("validate_only", False),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_scale_services(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle scale_services tool."""
    result = await scale_infrastructure_services(
        scaling_plan=arguments["scaling_plan"],
        validate_only=arguments.get("validate_only", False),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_validate_infrastructure_changes(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Handle validate_infrastructure_changes tool."""
    result = await validate_infrastructure_plan(
        change_plan=arguments["change_plan"],
        validation_level=arguments.get("validation_level", "comprehensive"),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_create_infrastructure_backup(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Handle create_infrastructure_backup tool."""
    result = await create_infrastructure_backup(
        backup_scope=arguments.get("backup_scope", "full"),
        device_ids=arguments.get("device_ids"),
        include_data=arguments.get("include_data", False),
        backup_name=arguments.get("backup_name"),
    )
    return {"content": [{"type": "text", "text": result}]}


async def handle_rollback_infrastructure_changes(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Handle rollback_infrastructure_changes tool."""
    if arguments.get("dry_run", False):
        from ..dry_run import build_dry_run_response

        would_affect: list[dict[str, Any]] = [
            {"resource_type": "infrastructure", "backup_id": arguments["backup_id"]},
        ]
        return build_dry_run_response(
            tool_name="rollback_infrastructure_changes",
            would_affect=would_affect,
            risk_level="high",
            reversible=False,
        )
    result = await rollback_infrastructure_to_backup(
        backup_id=arguments["backup_id"],
        rollback_scope=arguments.get("rollback_scope", "full"),
        device_ids=arguments.get("device_ids"),
        validate_only=arguments.get("validate_only", False),
    )
    return {"content": [{"type": "text", "text": result}]}
