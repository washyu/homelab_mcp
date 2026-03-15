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
    assert any(
        keyword in combined_text for keyword in ("pre-flight", "preflight", "ssh_discover", "list_installed_services")
    )


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
    combined_text = " ".join(
        msg.content.text for msg in result.messages if hasattr(msg.content, "text")
    ).lower()
    assert "setup_mcp_admin" in combined_text
    assert "credentials add" in combined_text
    assert "register_server" in combined_text
    assert "ssh_discover" in combined_text
    assert "discover_and_map" in combined_text
    assert "verify_mcp_admin" in combined_text
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
