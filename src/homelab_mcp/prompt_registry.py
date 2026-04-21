"""Static prompt registry for homelab MCP server.

Contains HOMELAB_PROMPTS dict and get_prompt_result() dispatcher.
Only imports mcp.types and mcp.shared.exceptions — no homelab_mcp imports
(circular import prevention per architectural decision in STATE.md).
"""

from __future__ import annotations

import mcp.types as types
from mcp.shared.exceptions import McpError

RESOURCE_NOT_FOUND = -32002

# ---------------------------------------------------------------------------
# Prompt metadata registry
# ---------------------------------------------------------------------------

HOMELAB_PROMPTS: dict[str, types.Prompt] = {
    "decommission_device_workflow": types.Prompt(
        name="decommission_device_workflow",
        description="Safe guided workflow for decommissioning a homelab device",
        arguments=[
            types.PromptArgument(
                name="hostname",
                description="Hostname or IP of the device to decommission",
                required=True,
            )
        ],
    ),
    "deploy_service_workflow": types.Prompt(
        name="deploy_service_workflow",
        description="Pre-flight checked service deployment workflow",
        arguments=[
            types.PromptArgument(
                name="service_name",
                description="Name of the service to deploy",
                required=True,
            ),
            types.PromptArgument(
                name="target_host",
                description="Target host for deployment",
                required=True,
            ),
        ],
    ),
    "homelab_health_check": types.Prompt(
        name="homelab_health_check",
        description="Read all infrastructure resources and summarize homelab state",
        arguments=[],
    ),
    "connect_to_device": types.Prompt(
        name="connect_to_device",
        description="Step-by-step onboarding workflow for connecting a new device to the homelab",
        arguments=[
            types.PromptArgument(
                name="hostname",
                description="Hostname or IP address of the new device to onboard",
                required=True,
            )
        ],
    ),
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_user_message(text: str) -> types.PromptMessage:
    """Wrap text in a user-role PromptMessage."""
    return types.PromptMessage(
        role="user",
        content=types.TextContent(type="text", text=text),
    )


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_decommission_result(args: dict[str, str]) -> types.GetPromptResult:
    """Build the decommission_device_workflow prompt result (PRMT-02, CLI-02)."""
    hostname = args.get("hostname", "<hostname>")
    text = f"""Follow these steps to safely decommission {hostname}:

1. Call get_network_sitemap to retrieve all tracked devices. Find the entry \
where hostname matches "{hostname}" and note its device_id (integer).
2. Call decommission_device_preview with device_id=<device_id from step 1> to \
preview the operation.
3. Present the preview result to the user and ask for explicit confirmation \
before proceeding.
4. Only if the user confirms: call decommission_device with \
device_id=<device_id from step 1>.
5. Report the result to the user.

Do not proceed to step 4 without explicit user confirmation."""
    return types.GetPromptResult(
        description="Safe device decommission workflow",
        messages=[_make_user_message(text)],
    )


def _build_deploy_service_result(args: dict[str, str]) -> types.GetPromptResult:
    """Build the deploy_service_workflow prompt result (PRMT-03)."""
    service_name = args.get("service_name", "<service_name>")
    target_host = args.get("target_host", "<target_host>")
    text = f"""Follow these steps to deploy {service_name} on {target_host}:

Pre-flight checks:
1. Call ssh_discover with hostname="{target_host}" to verify SSH connectivity.
2. Call get_service_status with service_name="{service_name}" and hostname="{target_host}" to check whether {service_name} is already installed.

If pre-flight checks pass:
3. Call install_service with service_name="{service_name}" and hostname="{target_host}".
4. Report the installation result to the user."""
    return types.GetPromptResult(
        description="Service deployment with pre-flight checks",
        messages=[_make_user_message(text)],
    )


def _build_connect_to_device_result(args: dict[str, str]) -> types.GetPromptResult:
    """Build the connect_to_device prompt result (TOFU-03, Phase 33 D-13/D-18/D-22)."""
    hostname = args.get("hostname", "<hostname>")
    text = f"""Follow these steps to onboard {hostname} into your homelab:

1. Ensure you have an SSH-accessible user on {hostname} with sudo privileges. \
The username can be anything — you will specify it in the next step.

2. Run the CLI command in your terminal: homelab-mcp credentials add {hostname} \
<username> — this stores the SSH credential in your OS keyring. For key-based auth: \
homelab-mcp credentials add {hostname} <username> --key-path <path>.

3. Call register_server with hostname="{hostname}" and username="<username>" to \
verify the stored credential end-to-end.

4. Call ssh_discover with hostname="{hostname}" to collect hardware and system info \
and record it in the database.

5. Call discover_and_map with hostname="{hostname}" to add the device to the network \
sitemap.

6. Call verify_mcp_admin with hostname="{hostname}" to confirm that the registered \
user has sudo access.

If any step fails, fix the issue before proceeding to the next step."""
    return types.GetPromptResult(
        description="Full device onboarding workflow",
        messages=[_make_user_message(text)],
    )


def _build_health_check_result(args: dict[str, str]) -> types.GetPromptResult:
    """Build the homelab_health_check prompt result (PRMT-04)."""
    text = """Read the following MCP resources and summarize homelab infrastructure state:

1. Read homelab://vms — list all VMs and containers
2. Read homelab://devices — list all tracked network devices
3. Read homelab://drift/latest — check for infrastructure drift

Summarize: total VM count, total device count, any drift detected (drift_detected field),
and flag any items that need attention. If homelab://drift/latest shows drift_detected is
true, list the drifted items prominently."""
    return types.GetPromptResult(
        description="Homelab infrastructure health check",
        messages=[_make_user_message(text)],
    )


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------


def get_prompt_result(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    """Return rendered GetPromptResult for the named prompt.

    Args:
        name: Prompt name — must be a key in HOMELAB_PROMPTS.
        arguments: Optional dict of argument values to interpolate into the prompt text.

    Returns:
        GetPromptResult with one or more PromptMessage objects.

    Raises:
        McpError: With code -32002 if ``name`` is not a known prompt.
    """
    args = arguments or {}
    if name == "decommission_device_workflow":
        return _build_decommission_result(args)
    elif name == "deploy_service_workflow":
        return _build_deploy_service_result(args)
    elif name == "homelab_health_check":
        return _build_health_check_result(args)
    elif name == "connect_to_device":
        return _build_connect_to_device_result(args)
    else:
        raise McpError(
            types.ErrorData(
                code=RESOURCE_NOT_FOUND,
                message=f"Prompt not found: {name}",
                data={"name": name},
            )
        )
