"""Tests for MCP Prompts capability (Phase 14, PRMT-01..04).

Wave 0: Tests are intentionally RED — prompt_registry.py does not exist yet.
pytest --collect-only must succeed; individual tests will fail.
"""

from __future__ import annotations

import pytest


def test_prompts_capability_advertised() -> None:
    """PRMT-01: server.get_capabilities() advertises prompts capability.

    Will be RED until Plan 02 registers prompt handlers in server.py.
    """
    from mcp.server.lowlevel import NotificationOptions  # type: ignore[import]

    from homelab_mcp.server import server  # type: ignore[attr-defined]

    caps = server.get_capabilities(NotificationOptions(), {})
    assert caps.prompts is not None


def test_list_prompts_returns_prompts() -> None:
    """PRMT-01: HOMELAB_PROMPTS contains at least 4 prompts with required names.

    Will be RED until Plan 02 creates prompt_registry.py with HOMELAB_PROMPTS.
    """
    from homelab_mcp.prompt_registry import HOMELAB_PROMPTS  # type: ignore[import]

    assert len(HOMELAB_PROMPTS) >= 4
    prompt_names = [p.name for p in HOMELAB_PROMPTS.values()]
    assert "decommission_device_workflow" in prompt_names
    assert "deploy_service_workflow" in prompt_names
    assert "homelab_health_check" in prompt_names
    assert "connect_to_device" in prompt_names


def test_decommission_workflow_prompt() -> None:
    """PRMT-02: decommission_device_workflow prompt returns structured guidance.

    Will be RED until Plan 02 implements get_prompt_result in prompt_registry.py.
    """
    from mcp.types import GetPromptResult  # type: ignore[import]

    from homelab_mcp.prompt_registry import get_prompt_result  # type: ignore[import]

    result = get_prompt_result("decommission_device_workflow", {"hostname": "test-host"})
    assert isinstance(result, GetPromptResult)
    assert len(result.messages) >= 1
    combined_text = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text")).lower()
    assert "decommission_device_preview" in combined_text
    assert "confirm" in combined_text
    assert "get_network_sitemap" in combined_text, (
        "CLI-02: prompt must instruct AI to call get_network_sitemap to resolve hostname to device_id"
    )
    assert "device_id" in combined_text, (
        "CLI-02: prompt must use device_id (integer) not hostname — decommission_device schema requires device_id"
    )


def test_deploy_service_workflow_prompt() -> None:
    """PRMT-03: deploy_service_workflow prompt includes pre-flight guidance.

    Will be RED until Plan 02 implements get_prompt_result in prompt_registry.py.
    """
    from homelab_mcp.prompt_registry import get_prompt_result  # type: ignore[import]

    result = get_prompt_result(
        "deploy_service_workflow",
        {"service_name": "nginx", "target_host": "test-host"},
    )
    assert len(result.messages) >= 1
    combined_text = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text")).lower()
    assert "pre-flight" in combined_text or "preflight" in combined_text
    assert "ssh_discover" in combined_text
    assert "get_service_status" in combined_text


def test_health_check_prompt_resources() -> None:
    """PRMT-04: homelab_health_check prompt references all three MCP resources.

    Will be RED until Plan 02 implements get_prompt_result in prompt_registry.py.
    """
    from homelab_mcp.prompt_registry import get_prompt_result  # type: ignore[import]

    result = get_prompt_result("homelab_health_check", {})
    assert len(result.messages) >= 1
    combined_text = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text"))
    assert "homelab://vms" in combined_text
    assert "homelab://devices" in combined_text
    assert "homelab://drift/latest" in combined_text


def test_connect_to_device_prompt() -> None:
    """TOFU-03: connect_to_device prompt returns full device onboarding sequence.

    Will be RED until Plan 23-01 adds connect_to_device to prompt_registry.py.
    """
    from mcp.types import GetPromptResult  # type: ignore[import]

    from homelab_mcp.prompt_registry import get_prompt_result  # type: ignore[import]

    result = get_prompt_result("connect_to_device", {"hostname": "test-host"})
    assert isinstance(result, GetPromptResult)
    assert len(result.messages) >= 1
    combined_text = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text")).lower()
    assert "setup_mcp_admin" not in combined_text, (
        "D-14: connect_to_device prompt must not reference setup_mcp_admin after Phase 33"
    )
    assert "credentials add" in combined_text, (
        "D-13 step 2: prompt must instruct user to run `homelab-mcp credentials add`"
    )
    assert "register_server" in combined_text, (
        "D-13 step 3: prompt must instruct AI to call register_server"
    )
    assert "ssh_discover" in combined_text
    assert "discover_and_map" in combined_text
    # D-05/D-05b: verify_mcp_admin tool removed in Phase 33.1; prompt Step 6
    # now calls ssh_execute_command with `sudo -n true` to verify sudo access.
    assert "verify_mcp_admin" not in combined_text, (
        "D-05: connect_to_device prompt must not reference removed verify_mcp_admin tool"
    )
    assert "ssh_execute_command" in combined_text, (
        "D-05b: prompt Step 6 must use ssh_execute_command for sudo verification"
    )
    assert "sudo -n true" in combined_text, (
        "D-05b: prompt Step 6 must use `sudo -n true` as the sudo verification command"
    )
    assert "test-host" in combined_text


def test_get_unknown_prompt_raises_mcp_error() -> None:
    """PRMT-01: get_prompt_result raises McpError for unknown prompt names.

    Will be RED until Plan 02 implements error handling in prompt_registry.py.
    """
    from mcp.shared.exceptions import McpError  # type: ignore[import]

    from homelab_mcp.prompt_registry import get_prompt_result  # type: ignore[import]

    with pytest.raises(McpError) as exc_info:
        get_prompt_result("nonexistent_prompt", {})
    assert exc_info.value.error.code == -32002


def test_connect_to_device_prompt_parameter_names() -> None:
    """TOFU-03: connect_to_device prompt uses hostname= not host= for all tool calls."""
    from homelab_mcp.prompt_registry import get_prompt_result

    result = get_prompt_result("connect_to_device", {"hostname": "myhost"})
    combined = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text"))
    # All tools in this prompt use hostname=, never host=
    assert "host=" not in combined, f"Prompt must use hostname= not host= for tool parameters. Found: {combined}"
    # Each tool step must use hostname= with the interpolated value.
    # D-05/D-05b: verify_mcp_admin was removed; Step 6 now calls ssh_execute_command.
    for tool in ("register_server", "ssh_discover", "discover_and_map", "ssh_execute_command"):
        assert f"{tool}" in combined, f"Missing tool reference: {tool}"
    assert 'hostname="myhost"' in combined, "hostname= must appear with interpolated value"


def test_deploy_service_workflow_prompt_parameter_names() -> None:
    """TOFU-03: deploy_service_workflow prompt uses hostname= not host= for all tool calls."""
    from homelab_mcp.prompt_registry import get_prompt_result

    result = get_prompt_result(
        "deploy_service_workflow",
        {"service_name": "nginx", "target_host": "myhost"},
    )
    combined = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text"))
    assert "host=" not in combined, f"Prompt must use hostname= not host= for tool parameters. Found: {combined}"
    assert "hostname=" in combined, "hostname= must appear in deploy workflow prompt"


def test_deploy_service_workflow_no_phantom_tool() -> None:
    """Phase 29: deploy_service_workflow must not reference unregistered list_installed_services."""
    from homelab_mcp.prompt_registry import get_prompt_result

    result = get_prompt_result(
        "deploy_service_workflow",
        {"service_name": "nginx", "target_host": "myhost"},
    )
    combined = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text"))
    assert "list_installed_services" not in combined, (
        "deploy_service_workflow must not reference phantom tool list_installed_services"
    )
    assert "get_service_status" in combined, (
        "deploy_service_workflow step 2 must use registered get_service_status tool"
    )


def test_connect_to_device_no_verify_bypass() -> None:
    """D-14: connect_to_device prompt must not name verify_connection=False bypass."""
    from homelab_mcp.prompt_registry import _build_connect_to_device_result

    result = _build_connect_to_device_result({"hostname": "test.local"})
    combined = " ".join(
        msg.content.text if hasattr(msg.content, "text") else str(msg.content)
        for msg in result.messages
    )
    assert "verify_connection=False" not in combined, (
        "D-14: prompt must not reference the removed verify_connection=False bypass"
    )
    assert "verify_connection" not in combined, (
        "D-07: prompt must not reference the removed verify_connection parameter"
    )


def test_connect_to_device_mentions_credentials_cli() -> None:
    """D-22: prompt must tell the user to run `homelab-mcp credentials add` in their terminal."""
    from homelab_mcp.prompt_registry import _build_connect_to_device_result

    result = _build_connect_to_device_result({"hostname": "test.local"})
    combined = " ".join(
        msg.content.text if hasattr(msg.content, "text") else str(msg.content)
        for msg in result.messages
    )
    assert "homelab-mcp credentials add" in combined, (
        "D-22: prompt step 2 must name the CLI command `homelab-mcp credentials add`"
    )
    # D-18: no mcp_admin specificity — user can pick any username
    assert "mcp_admin" not in combined or "<username>" in combined, (
        "D-18/D-22: prompt must not mandate mcp_admin; should use <username> placeholder"
    )
