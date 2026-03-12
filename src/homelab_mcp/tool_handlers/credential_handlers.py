"""Handler functions for server credential management tools."""

from typing import Any

from ..ssh_tools import (
    list_registered_servers,
    register_server,
    remove_server,
    update_server_credentials,
)


async def handle_register_server(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle register_server tool."""
    result = await register_server(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_list_registered_servers(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_registered_servers tool."""
    result = list_registered_servers(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_update_server_credentials(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update_server_credentials tool."""
    result = update_server_credentials(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_remove_server(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle remove_server tool."""
    if arguments.get("dry_run", False):
        from ..database import get_database_adapter
        from ..dry_run import build_dry_run_response

        db = get_database_adapter()
        db.connect()
        db.init_schema()
        credential_id = arguments.get("credential_id")
        hostname = arguments.get("hostname", "")
        # Sync lookup — do NOT await
        if credential_id is not None:
            cred = db.get_credential(int(credential_id))
            if cred:
                hostname = cred.get("hostname", hostname)
        else:
            cred = db.get_credential_by_hostname(hostname) if hostname else None
        db.close()
        if not cred:
            identifier = hostname or str(credential_id)
            would_affect: list[dict[str, Any]] = []
            preview_details: dict[str, Any] | None = {"error": f"Server '{identifier}' not found"}
        else:
            would_affect = [{"resource_type": "server_credential", "hostname": hostname}]
            preview_details = {"hostname": hostname}
        return build_dry_run_response(
            tool_name="remove_server",
            would_affect=would_affect,
            risk_level="medium",
            reversible=False,
            preview_details=preview_details,
        )
    # Remove dry_run key before passing to remove_server (it doesn't accept that arg)
    clean_args = {k: v for k, v in arguments.items() if k != "dry_run"}
    result = remove_server(**clean_args)
    return {"content": [{"type": "text", "text": result}]}
