"""CRED-06 / D-10: setup_mcp_admin and peer removed tools must not appear in openapi allow-lists."""
from __future__ import annotations


def test_setup_mcp_admin_absent() -> None:
    """D-10: setup_mcp_admin must not appear in _SSH_TOOLS_WITH_HOSTNAME or TOOL_CATEGORIES['SSH']."""
    from homelab_mcp.openapi_app import _SSH_TOOLS_WITH_HOSTNAME, TOOL_CATEGORIES

    assert "setup_mcp_admin" not in _SSH_TOOLS_WITH_HOSTNAME, (
        "setup_mcp_admin must be removed from _SSH_TOOLS_WITH_HOSTNAME (D-10)"
    )
    assert "setup_mcp_admin" not in TOOL_CATEGORIES.get("SSH", []), (
        "setup_mcp_admin must be removed from TOOL_CATEGORIES['SSH'] (D-10)"
    )


def test_update_server_credentials_absent() -> None:
    """D-20: update_server_credentials tool must not appear in any openapi allow-list."""
    from homelab_mcp.openapi_app import _SSH_TOOLS_WITH_HOSTNAME, TOOL_CATEGORIES

    for category, tools in TOOL_CATEGORIES.items():
        assert "update_server_credentials" not in tools, (
            f"update_server_credentials must be removed from TOOL_CATEGORIES[{category!r}] (D-20)"
        )
    assert "update_server_credentials" not in _SSH_TOOLS_WITH_HOSTNAME


def test_remove_server_absent() -> None:
    """D-21: remove_server tool must not appear in any openapi allow-list."""
    from homelab_mcp.openapi_app import _SSH_TOOLS_WITH_HOSTNAME, TOOL_CATEGORIES

    for category, tools in TOOL_CATEGORIES.items():
        assert "remove_server" not in tools, (
            f"remove_server must be removed from TOOL_CATEGORIES[{category!r}] (D-21)"
        )
    assert "remove_server" not in _SSH_TOOLS_WITH_HOSTNAME
