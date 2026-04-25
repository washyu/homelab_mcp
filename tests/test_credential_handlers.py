"""Unit tests for credential MCP handler functions (Phase 34 Plan 04 Task 2).

Tests the D-17a display tweak: cluster entries render with 'cluster:<name>'
hostname form instead of blank hostname in handle_list_keyring_credentials.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from homelab_mcp.tool_handlers.credential_handlers import handle_list_keyring_credentials


@pytest.mark.asyncio
async def test_handle_list_keyring_credentials_per_node_entry_renders_hostname() -> None:
    """Test 1: per-node entry renders with its hostname unchanged."""
    mock_entries = [
        {
            "hostname": "pve1.home",
            "username": "root@pam!tok",
            "credential_type": "proxmox",
            "scope": "node",
            "cluster_name": "",
        }
    ]
    with patch("homelab_mcp.tool_handlers.credential_handlers.list_credentials", return_value=mock_entries):
        result = await handle_list_keyring_credentials({"credential_type": "proxmox"})

    payload = json.loads(result["content"][0]["text"])
    assert payload["credentials"][0]["hostname"] == "pve1.home"


@pytest.mark.asyncio
async def test_handle_list_keyring_credentials_cluster_entry_renders_cluster_form() -> None:
    """Test 2 (D-17a): cluster entry renders as 'cluster:<name>' instead of blank hostname."""
    mock_entries = [
        {
            "hostname": "",
            "username": "root@pam!clustertok",
            "credential_type": "proxmox",
            "scope": "cluster",
            "cluster_name": "homelab-prod",
        }
    ]
    with patch("homelab_mcp.tool_handlers.credential_handlers.list_credentials", return_value=mock_entries):
        result = await handle_list_keyring_credentials({"credential_type": "proxmox"})

    payload = json.loads(result["content"][0]["text"])
    assert payload["credentials"][0]["hostname"] == "cluster:homelab-prod"


@pytest.mark.asyncio
async def test_handle_list_keyring_credentials_legacy_entry_uses_node_default() -> None:
    """Test 3: legacy entry without 'scope' field renders hostname unchanged (backward compat)."""
    mock_entries = [
        {
            "hostname": "old-host",
            "username": "alice",
            "credential_type": "ssh",
        }
    ]
    with patch("homelab_mcp.tool_handlers.credential_handlers.list_credentials", return_value=mock_entries):
        result = await handle_list_keyring_credentials({"credential_type": "ssh"})

    payload = json.loads(result["content"][0]["text"])
    assert payload["credentials"][0]["hostname"] == "old-host"


@pytest.mark.asyncio
async def test_handle_list_keyring_credentials_payload_shape_unchanged() -> None:
    """Test 4 (D-17a schema-non-change): top-level keys and types are unchanged.

    This is a display-level tweak only — the shape (status, credential_type,
    count, credentials) must remain identical to the pre-Phase-34 handler.
    """
    mock_entries = [
        {
            "hostname": "",
            "username": "root@pam!tok",
            "credential_type": "proxmox",
            "scope": "cluster",
            "cluster_name": "staging",
        },
        {
            "hostname": "pve1.home",
            "username": "root@pam!nodetok",
            "credential_type": "proxmox",
            "scope": "node",
            "cluster_name": "",
        },
    ]
    with patch("homelab_mcp.tool_handlers.credential_handlers.list_credentials", return_value=mock_entries):
        result = await handle_list_keyring_credentials({"credential_type": "proxmox"})

    # Outer shape: single content item of type text
    assert "content" in result
    assert len(result["content"]) == 1
    assert result["content"][0]["type"] == "text"

    # Payload shape
    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "success"
    assert payload["credential_type"] == "proxmox"
    assert payload["count"] == len(mock_entries)
    assert isinstance(payload["credentials"], list)
    assert len(payload["credentials"]) == 2

    # Each credential item must have exactly hostname and username keys
    for cred in payload["credentials"]:
        assert set(cred.keys()) == {"hostname", "username"}
