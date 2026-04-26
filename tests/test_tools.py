"""Tests for MCP tools."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.homelab_mcp.tools import execute_tool, get_available_tools


def test_get_available_tools():
    """Test getting available tools."""
    tools = get_available_tools()

    assert (
        len(tools) == 54
    )  # Phase 33 removed setup_mcp_admin, update_server_credentials, remove_server, remove_server_preview; Phase 33.1 removed update_mcp_admin_groups, verify_mcp_admin; v1.6.x added purge_failed_discoveries; Phase 38 added update_device_fingerprint + update_device_fingerprint_preview (Plan 05)
    assert "ssh_discover" in tools
    assert "purge_failed_discoveries" in tools  # v1.6.x: sitemap CRUD completion
    assert "update_device_fingerprint" in tools  # Phase 38
    assert "update_device_fingerprint_preview" in tools  # Phase 38 D-05c (Plan 05)
    assert "setup_mcp_admin" not in tools  # D-10: removed in Phase 33
    assert "verify_mcp_admin" not in tools  # D-05: removed in Phase 33.1
    assert "update_mcp_admin_groups" not in tools  # D-05: removed in Phase 33.1

    # Server registration tools (Phase 33: update_server_credentials and remove_server removed)
    assert "register_server" in tools
    assert "list_registered_servers" in tools
    assert "update_server_credentials" not in tools  # D-20: removed
    assert "remove_server" not in tools  # D-21: replaced by CLI credentials remove

    # New sitemap tools
    assert "discover_and_map" in tools
    assert "bulk_discover_and_map" in tools
    assert "get_network_sitemap" in tools
    assert "analyze_network_topology" in tools
    assert "suggest_deployments" in tools
    assert "get_device_changes" in tools

    # New CRUD infrastructure tools
    assert "deploy_infrastructure" in tools
    assert "update_device_config" in tools
    assert "decommission_device" in tools
    assert "scale_services" in tools
    assert "validate_infrastructure_changes" in tools
    assert "create_infrastructure_backup" in tools
    assert "rollback_infrastructure_changes" in tools

    # New VM management tools
    assert "deploy_vm" in tools
    assert "control_vm" in tools
    assert "get_vm_status" in tools
    assert "list_vms" in tools
    assert "get_vm_logs" in tools
    assert "remove_vm" in tools

    # Service and Ansible tools
    assert "install_service" in tools
    assert "run_ansible_playbook" in tools
    assert "check_ansible_service" in tools

    # Check ssh_discover tool schema
    ssh_tool = tools["ssh_discover"]
    assert "description" in ssh_tool
    assert "inputSchema" in ssh_tool
    assert "hostname" in ssh_tool["inputSchema"]["properties"]
    assert "username" in ssh_tool["inputSchema"]["properties"]


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    """Test executing unknown tool returns structured error response."""
    result = await execute_tool("nonexistent_tool", {})

    # Should return structured error response, not raise exception
    assert "content" in result
    assert len(result["content"]) == 1
    assert result["content"][0]["type"] == "text"

    # Parse the error response
    error_data = json.loads(result["content"][0]["text"])
    assert error_data["status"] == "error"
    assert "Unknown tool" in error_data["error"]
    assert "nonexistent_tool" in error_data["error"]


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.ssh_handlers.ssh_discover_system")
async def test_execute_ssh_discover(mock_ssh_discover):
    """Test executing ssh_discover tool."""
    # Mock the SSH discovery response
    mock_response = json.dumps(
        {
            "status": "success",
            "hostname": "test-host",
            "data": {
                "cpu": {"model": "Test CPU", "cores": "4"},
                "memory": {"total": "8G", "used": "4G"},
            },
        },
        indent=2,
    )
    mock_ssh_discover.return_value = mock_response

    result = await execute_tool(
        "ssh_discover",
        {"hostname": "test-host", "username": "test-user", "password": "test-pass"},
    )

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the SSH function was called with correct arguments
    mock_ssh_discover.assert_called_once_with(hostname="test-host", username="test-user", password="test-pass")


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.discover_and_store")
async def test_execute_discover_and_map(mock_discover_and_store):
    """Test executing discover_and_map tool."""
    # Mock the discover and store response
    mock_response = json.dumps(
        {
            "status": "success",
            "device_id": 1,
            "hostname": "test-server",
            "discovery_status": "success",
        }
    )
    mock_discover_and_store.return_value = mock_response

    result = await execute_tool(
        "discover_and_map",
        {"hostname": "test-host", "username": "test-user", "password": "test-pass"},
    )

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_discover_and_store.assert_called_once()


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.bulk_discover_and_store")
async def test_execute_bulk_discover_and_map(mock_bulk_discover):
    """Test executing bulk_discover_and_map tool."""
    # Mock the bulk discovery response
    mock_response = json.dumps(
        {
            "status": "success",
            "total_targets": 2,
            "results": [
                {"status": "success", "hostname": "host1"},
                {"status": "success", "hostname": "host2"},
            ],
        }
    )
    mock_bulk_discover.return_value = mock_response

    targets = [
        {"hostname": "host1", "username": "user1"},
        {"hostname": "host2", "username": "user2"},
    ]

    result = await execute_tool("bulk_discover_and_map", {"targets": targets})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called with targets
    mock_bulk_discover.assert_called_once_with(mock_bulk_discover.call_args[0][0], targets)


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_execute_get_network_sitemap(mock_sitemap_class):
    """Test executing get_network_sitemap tool."""
    # Mock the sitemap instance and its methods
    mock_sitemap = MagicMock()
    mock_sitemap.get_all_devices.return_value = [
        {"id": 1, "hostname": "test-server", "status": "success"},
        {"id": 2, "hostname": "test-server2", "status": "error"},
    ]
    mock_sitemap_class.return_value = mock_sitemap

    result = await execute_tool("get_network_sitemap", {})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Parse the JSON response
    response_data = json.loads(result["content"][0]["text"])
    assert response_data["status"] == "success"
    assert response_data["total_devices"] == 2
    assert len(response_data["devices"]) == 2


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_execute_analyze_network_topology(mock_sitemap_class):
    """Test executing analyze_network_topology tool."""
    # Mock the sitemap instance and its methods
    mock_sitemap = MagicMock()
    mock_sitemap.analyze_network_topology.return_value = {
        "total_devices": 3,
        "online_devices": 2,
        "offline_devices": 1,
        "operating_systems": {"Ubuntu 22.04": 2},
        "network_segments": {"192.168.1.0/24": 3},
    }
    mock_sitemap_class.return_value = mock_sitemap

    result = await execute_tool("analyze_network_topology", {})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Parse the JSON response
    response_data = json.loads(result["content"][0]["text"])
    assert response_data["status"] == "success"
    assert "analysis" in response_data
    assert response_data["analysis"]["total_devices"] == 3


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_execute_suggest_deployments(mock_sitemap_class):
    """Test executing suggest_deployments tool."""
    # Mock the sitemap instance and its methods
    mock_sitemap = MagicMock()
    mock_sitemap.suggest_deployments.return_value = {
        "load_balancer_candidates": [{"hostname": "high-spec-server", "reason": "8 cores, 16G RAM"}],
        "database_candidates": [{"hostname": "storage-server", "reason": "Low disk usage (20%), 32G RAM"}],
        "monitoring_targets": [{"hostname": "server1", "connection_ip": "192.168.1.10"}],
        "upgrade_recommendations": [],
    }
    mock_sitemap_class.return_value = mock_sitemap

    result = await execute_tool("suggest_deployments", {})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Parse the JSON response
    response_data = json.loads(result["content"][0]["text"])
    assert response_data["status"] == "success"
    assert "suggestions" in response_data
    assert len(response_data["suggestions"]["load_balancer_candidates"]) == 1


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_execute_get_device_changes(mock_sitemap_class):
    """Test executing get_device_changes tool."""
    # Mock the sitemap instance and its methods
    mock_sitemap = MagicMock()
    mock_sitemap.get_device_changes.return_value = [
        {
            "data": {"hostname": "test-server", "status": "success"},
            "discovered_at": "2024-01-01T12:00:00",
        },
        {
            "data": {"hostname": "test-server", "status": "success"},
            "discovered_at": "2024-01-01T11:00:00",
        },
    ]
    mock_sitemap_class.return_value = mock_sitemap

    result = await execute_tool("get_device_changes", {"device_id": 1, "limit": 5})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Parse the JSON response
    response_data = json.loads(result["content"][0]["text"])
    assert response_data["status"] == "success"
    assert response_data["device_id"] == 1
    assert len(response_data["changes"]) == 2


def test_sitemap_tool_schemas():
    """Test that all sitemap tools have proper schemas."""
    tools = get_available_tools()

    # Test discover_and_map schema
    discover_tool = tools["discover_and_map"]
    assert "description" in discover_tool
    assert "inputSchema" in discover_tool
    assert "hostname" in discover_tool["inputSchema"]["properties"]
    assert "username" in discover_tool["inputSchema"]["properties"]
    assert discover_tool["inputSchema"]["required"] == ["hostname"]

    # Test bulk_discover_and_map schema
    bulk_tool = tools["bulk_discover_and_map"]
    assert "targets" in bulk_tool["inputSchema"]["properties"]
    assert bulk_tool["inputSchema"]["properties"]["targets"]["type"] == "array"

    # Test get_device_changes schema
    changes_tool = tools["get_device_changes"]
    assert "device_id" in changes_tool["inputSchema"]["properties"]
    assert changes_tool["inputSchema"]["required"] == ["device_id"]

    # Test tools with no required parameters
    for tool_name in [
        "get_network_sitemap",
        "analyze_network_topology",
        "suggest_deployments",
    ]:
        tool = tools[tool_name]
        assert tool["inputSchema"]["required"] == []


def test_discover_and_map_schema_no_password_no_mcp_admin_default() -> None:
    """D-01, D-03, D-12: network schema drops password property and mcp_admin default."""
    from homelab_mcp.tool_schemas.network_tools_schema import NETWORK_TOOLS

    discover = NETWORK_TOOLS["discover_and_map"]["inputSchema"]["properties"]
    assert "password" not in discover, "D-01: discover_and_map must not expose password property"
    assert "default" not in discover["username"], "D-03: username must have no default"
    assert "Defaults to 'mcp_admin'" not in discover["username"]["description"], (
        "D-12: description must not claim mcp_admin default"
    )

    bulk_target_props = NETWORK_TOOLS["bulk_discover_and_map"]["inputSchema"]["properties"]["targets"]["items"][
        "properties"
    ]
    assert "password" not in bulk_target_props, "D-01: bulk_discover_and_map targets must not expose password property"
    assert "default" not in bulk_target_props["username"], "D-03: bulk target username must have no default"


# test_update_mcp_admin_groups_schema_no_password REMOVED in Phase 33.1 (D-05).
# update_mcp_admin_groups schema deleted entirely — Phase 33.1 D-02 became moot
# because the whole tool was removed, not just its password property.


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.infrastructure_handlers.deploy_infrastructure_plan")
async def test_execute_deploy_infrastructure(mock_deploy):
    """Test executing deploy_infrastructure tool."""
    mock_response = json.dumps(
        {
            "status": "success",
            "message": "Deployed 2 components successfully",
            "successful_deployments": 2,
            "failed_deployments": 0,
        }
    )
    mock_deploy.return_value = mock_response

    deployment_plan = {
        "services": [
            {
                "name": "nginx",
                "type": "docker",
                "target_device_id": 1,
                "config": {"image": "nginx:latest", "ports": ["80:80"]},
            }
        ]
    }

    result = await execute_tool(
        "deploy_infrastructure",
        {"deployment_plan": deployment_plan, "validate_only": False},
    )

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_deploy.assert_called_once_with(deployment_plan=deployment_plan, validate_only=False)


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.infrastructure_handlers.update_device_configuration")
async def test_execute_update_device_config(mock_update):
    """Test executing update_device_config tool."""
    mock_response = json.dumps(
        {
            "status": "success",
            "message": "Applied 1 configuration changes",
            "device_id": 1,
            "successful_changes": 1,
            "failed_changes": 0,
        }
    )
    mock_update.return_value = mock_response

    config_changes = {
        "services": {
            "nginx": {
                "type": "docker",
                "image": "nginx:1.21",
                "ports": ["80:80", "443:443"],
            }
        }
    }

    result = await execute_tool(
        "update_device_config",
        {
            "device_id": 1,
            "config_changes": config_changes,
            "backup_before_change": True,
            "validate_only": False,
        },
    )

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_update.assert_called_once_with(
        device_id=1,
        config_changes=config_changes,
        backup_before_change=True,
        validate_only=False,
    )


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.infrastructure_handlers.create_infrastructure_backup")
async def test_execute_create_backup(mock_backup):
    """Test executing create_infrastructure_backup tool."""
    mock_response = json.dumps(
        {
            "status": "success",
            "message": "Infrastructure backup created successfully",
            "backup_id": "backup_20240101_120000_abc12345",
            "devices_backed_up": 3,
            "backup_size_mb": 2.5,
        }
    )
    mock_backup.return_value = mock_response

    result = await execute_tool("create_infrastructure_backup", {"backup_scope": "full", "include_data": False})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_backup.assert_called_once_with(backup_scope="full", device_ids=None, include_data=False, backup_name=None)


def test_crud_tool_schemas():
    """Test that all CRUD tools have proper schemas."""
    tools = get_available_tools()

    # Test deploy_infrastructure schema
    deploy_tool = tools["deploy_infrastructure"]
    assert "deployment_plan" in deploy_tool["inputSchema"]["properties"]
    assert "validate_only" in deploy_tool["inputSchema"]["properties"]
    assert deploy_tool["inputSchema"]["required"] == ["deployment_plan"]

    # Test update_device_config schema
    update_tool = tools["update_device_config"]
    assert "device_id" in update_tool["inputSchema"]["properties"]
    assert "config_changes" in update_tool["inputSchema"]["properties"]
    assert "backup_before_change" in update_tool["inputSchema"]["properties"]
    assert update_tool["inputSchema"]["required"] == ["device_id", "config_changes"]

    # Test decommission_device schema
    decommission_tool = tools["decommission_device"]
    assert "device_id" in decommission_tool["inputSchema"]["properties"]
    assert "migration_plan" in decommission_tool["inputSchema"]["properties"]
    assert "force_removal" in decommission_tool["inputSchema"]["properties"]
    assert decommission_tool["inputSchema"]["required"] == ["device_id"]

    # Test create_infrastructure_backup schema
    backup_tool = tools["create_infrastructure_backup"]
    assert "backup_scope" in backup_tool["inputSchema"]["properties"]
    assert "device_ids" in backup_tool["inputSchema"]["properties"]
    assert "include_data" in backup_tool["inputSchema"]["properties"]
    assert backup_tool["inputSchema"]["required"] == []

    # Test rollback_infrastructure_changes schema
    rollback_tool = tools["rollback_infrastructure_changes"]
    assert "backup_id" in rollback_tool["inputSchema"]["properties"]
    assert "rollback_scope" in rollback_tool["inputSchema"]["properties"]
    assert rollback_tool["inputSchema"]["required"] == ["backup_id"]


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.vm_handlers.deploy_vm")
async def test_execute_deploy_vm(mock_deploy_vm):
    """Test executing deploy_vm tool."""
    mock_response = json.dumps(
        {
            "status": "success",
            "vm_name": "test-nginx",
            "device_id": 1,
            "platform": "docker",
            "container_id": "abc123",
        }
    )
    mock_deploy_vm.return_value = mock_response

    vm_config = {
        "image": "nginx:latest",
        "ports": ["80:80"],
        "environment": {"ENV": "production"},
    }

    result = await execute_tool(
        "deploy_vm",
        {
            "device_id": 1,
            "platform": "docker",
            "vm_name": "test-nginx",
            "vm_config": vm_config,
        },
    )

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_deploy_vm.assert_called_once_with(device_id=1, platform="docker", vm_name="test-nginx", vm_config=vm_config)


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.vm_handlers.control_vm_state")
async def test_execute_control_vm(mock_control_vm):
    """Test executing control_vm tool."""
    mock_response = json.dumps(
        {
            "status": "success",
            "operation": "start",
            "vm_name": "test-container",
            "device_id": 1,
            "platform": "docker",
        }
    )
    mock_control_vm.return_value = mock_response

    result = await execute_tool(
        "control_vm",
        {
            "device_id": 1,
            "platform": "docker",
            "vm_name": "test-container",
            "action": "start",
        },
    )

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_control_vm.assert_called_once_with(device_id=1, platform="docker", vm_name="test-container", action="start")


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.vm_handlers.list_vms_on_device")
async def test_execute_list_vms(mock_list_vms):
    """Test executing list_vms tool."""
    mock_response = json.dumps(
        {
            "status": "success",
            "device_id": 1,
            "total_vms": 3,
            "vms": [
                {"name": "nginx", "platform": "docker", "status": "running"},
                {"name": "redis", "platform": "docker", "status": "stopped"},
                {"name": "ubuntu", "platform": "lxd", "status": "running"},
            ],
        }
    )
    mock_list_vms.return_value = mock_response

    result = await execute_tool("list_vms", {"device_id": 1, "platforms": ["docker", "lxd"]})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_list_vms.assert_called_once_with(device_id=1, platforms=["docker", "lxd"])


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.vm_handlers.get_vm_logs")
async def test_execute_get_vm_logs(mock_get_logs):
    """Test executing get_vm_logs tool."""
    mock_response = json.dumps(
        {
            "status": "success",
            "vm_name": "test-container",
            "device_id": 1,
            "platform": "docker",
            "lines_requested": 100,
            "logs": "Starting nginx\\nReady to accept connections",
        }
    )
    mock_get_logs.return_value = mock_response

    result = await execute_tool(
        "get_vm_logs",
        {
            "device_id": 1,
            "platform": "docker",
            "vm_name": "test-container",
            "lines": 100,
        },
    )

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Verify the function was called
    mock_get_logs.assert_called_once_with(device_id=1, platform="docker", vm_name="test-container", lines=100)


def test_start_interactive_shell_schema_mentions_http() -> None:
    """start_interactive_shell description must mention HTTP server mode or --http (SHELL-05)."""
    tools = get_available_tools()
    desc = tools["start_interactive_shell"]["description"]
    assert "--http" in desc or "HTTP server mode" in desc, (
        f"start_interactive_shell description must mention --http or HTTP server mode; got: {desc!r}"
    )


def test_ssh_discover_description_contains_credential_recovery() -> None:
    """ssh_discover description must mention list_keyring_credentials for recovery (CRED-03)."""
    tools = get_available_tools()
    desc = tools["ssh_discover"]["description"]
    assert "list_keyring_credentials" in desc, (
        f"ssh_discover description must mention list_keyring_credentials; got: {desc!r}"
    )


def test_ssh_execute_command_description_contains_credential_recovery() -> None:
    """ssh_execute_command description must mention list_keyring_credentials for recovery (CRED-03)."""
    tools = get_available_tools()
    desc = tools["ssh_execute_command"]["description"]
    assert "list_keyring_credentials" in desc, (
        f"ssh_execute_command description must mention list_keyring_credentials; got: {desc!r}"
    )


def test_vm_tool_schemas():
    """Test that all VM tools have proper schemas."""
    tools = get_available_tools()

    # Test deploy_vm schema
    deploy_tool = tools["deploy_vm"]
    assert "device_id" in deploy_tool["inputSchema"]["properties"]
    assert "platform" in deploy_tool["inputSchema"]["properties"]
    assert "vm_name" in deploy_tool["inputSchema"]["properties"]
    assert "vm_config" in deploy_tool["inputSchema"]["properties"]
    assert deploy_tool["inputSchema"]["required"] == [
        "device_id",
        "platform",
        "vm_name",
    ]

    # Test control_vm schema
    control_tool = tools["control_vm"]
    assert "device_id" in control_tool["inputSchema"]["properties"]
    assert "platform" in control_tool["inputSchema"]["properties"]
    assert "vm_name" in control_tool["inputSchema"]["properties"]
    assert "action" in control_tool["inputSchema"]["properties"]
    assert control_tool["inputSchema"]["required"] == [
        "device_id",
        "platform",
        "vm_name",
        "action",
    ]

    # Test get_vm_status schema
    status_tool = tools["get_vm_status"]
    assert "device_id" in status_tool["inputSchema"]["properties"]
    assert "platform" in status_tool["inputSchema"]["properties"]
    assert "vm_name" in status_tool["inputSchema"]["properties"]
    assert status_tool["inputSchema"]["required"] == [
        "device_id",
        "platform",
        "vm_name",
    ]

    # Test list_vms schema
    list_tool = tools["list_vms"]
    assert "device_id" in list_tool["inputSchema"]["properties"]
    assert "platforms" in list_tool["inputSchema"]["properties"]
    assert list_tool["inputSchema"]["required"] == ["device_id"]

    # Test get_vm_logs schema
    logs_tool = tools["get_vm_logs"]
    assert "device_id" in logs_tool["inputSchema"]["properties"]
    assert "platform" in logs_tool["inputSchema"]["properties"]
    assert "vm_name" in logs_tool["inputSchema"]["properties"]
    assert "lines" in logs_tool["inputSchema"]["properties"]
    assert logs_tool["inputSchema"]["required"] == ["device_id", "platform", "vm_name"]

    # Test remove_vm schema
    remove_tool = tools["remove_vm"]
    assert "device_id" in remove_tool["inputSchema"]["properties"]
    assert "platform" in remove_tool["inputSchema"]["properties"]
    assert "vm_name" in remove_tool["inputSchema"]["properties"]
    assert "force" in remove_tool["inputSchema"]["properties"]
    assert remove_tool["inputSchema"]["required"] == [
        "device_id",
        "platform",
        "vm_name",
    ]


def test_list_keyring_credentials_in_registry():
    """Test that list_keyring_credentials exists in the tool registry."""
    tools = get_available_tools()
    assert "list_keyring_credentials" in tools
    tool = tools["list_keyring_credentials"]
    assert "description" in tool
    assert "inputSchema" in tool
    assert "credential_type" in tool["inputSchema"]["properties"]
    assert tool["inputSchema"]["required"] == []


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.credential_handlers.list_credentials")
async def test_handle_list_keyring_credentials_returns_entries(mock_list_creds):
    """list_keyring_credentials handler returns JSON with status=success and credentials array."""
    mock_list_creds.return_value = [
        {"hostname": "host1", "username": "alice", "credential_type": "ssh"},
        {"hostname": "host2", "username": "bob", "credential_type": "ssh"},
    ]

    from src.homelab_mcp.tool_handlers.credential_handlers import handle_list_keyring_credentials

    result = await handle_list_keyring_credentials({})
    assert "content" in result
    assert len(result["content"]) == 1
    data = json.loads(result["content"][0]["text"])
    assert data["status"] == "success"
    assert data["count"] == 2
    assert data["credentials"] == [
        {"hostname": "host1", "username": "alice"},
        {"hostname": "host2", "username": "bob"},
    ]
    assert data["credential_type"] == "ssh"


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.credential_handlers.list_credentials")
async def test_handle_list_keyring_credentials_passes_credential_type(mock_list_creds):
    """list_keyring_credentials handler passes credential_type argument through."""
    mock_list_creds.return_value = []

    from src.homelab_mcp.tool_handlers.credential_handlers import handle_list_keyring_credentials

    result = await handle_list_keyring_credentials({"credential_type": "proxmox"})
    mock_list_creds.assert_called_once_with(credential_type="proxmox")
    data = json.loads(result["content"][0]["text"])
    assert data["credential_type"] == "proxmox"
    assert data["count"] == 0


# test_setup_mcp_admin_schema_password_not_required REMOVED in Phase 33 (D-10).
# setup_mcp_admin MCP tool is intentionally deleted; replaced by test_tools.py::test_setup_mcp_admin_removed_from_tool_handlers.


# test_update_mcp_admin_groups_schema_password_not_required REMOVED in Phase 33.1 (D-05).
# update_mcp_admin_groups tool deleted entirely; no schema to assert against.


def test_no_tool_has_password_required():
    """Audit guard: no tool schema should have 'password' in its required array.

    SSH tools use keyring auto-inject. Proxmox LXC 'password' is for container root, not SSH auth,
    but it is also optional. If a future tool legitimately needs a required password field,
    update this test with an explicit allowlist.
    """
    tools = get_available_tools()
    for tool_name, tool_def in tools.items():
        schema = tool_def.get("inputSchema", {})
        required = schema.get("required", [])
        assert "password" not in required, (
            f"Tool '{tool_name}' has 'password' in required — "
            f"use resolve_ssh_credentials() for SSH auth or make it optional"
        )


def test_create_proxmox_vm_schema_phase26_parameters():
    """create_proxmox_vm schema exposes sockets, cdrom, net0, ostype (Phase 26-03)."""
    tools = get_available_tools()
    schema = tools["create_proxmox_vm"]["inputSchema"]["properties"]
    assert "sockets" in schema
    assert schema["sockets"]["default"] == 1
    assert "cdrom" in schema
    # cdrom has no default (None in handler, not in schema)
    assert "net0" in schema
    assert schema["net0"]["default"] == "virtio,bridge=vmbr0"
    assert "ostype" in schema
    assert schema["ostype"]["default"] == "l26"


def test_create_proxmox_lxc_schema_phase26_parameters():
    """create_proxmox_lxc schema exposes swap, ssh_public_keys, unprivileged (Phase 26-03)."""
    tools = get_available_tools()
    schema = tools["create_proxmox_lxc"]["inputSchema"]["properties"]
    assert "swap" in schema
    assert schema["swap"]["default"] == 512
    assert "ssh_public_keys" in schema
    # ssh_public_keys has no default (None in handler, not in schema)
    assert "unprivileged" in schema
    assert schema["unprivileged"]["default"] is True


# test_setup_mcp_admin_schema_has_timeout REMOVED in Phase 33 (D-10).
# setup_mcp_admin MCP tool is intentionally deleted.


# test_verify_mcp_admin_schema_has_timeout REMOVED in Phase 33.1 (D-05).
# verify_mcp_admin tool deleted entirely; Phase 26-02 timeout assertion is moot.


def test_ssh_execute_command_schema_no_timeout():
    """ssh_execute_command must NOT have timeout in schema (Phase 26-02 regression guard)."""
    tools = get_available_tools()
    schema = tools["ssh_execute_command"]["inputSchema"]["properties"]
    assert "timeout" not in schema, "ssh_execute_command should not expose timeout parameter"


# test_update_mcp_admin_groups_schema_has_key_path REMOVED in Phase 33.1 (D-05).
# update_mcp_admin_groups tool deleted entirely; Phase 26-02 key_path assertion is moot.


def test_no_service_tool_has_port_property():
    """No service tool schema has port property (Phase 26-01 regression guard).

    Phase 26-01 removed phantom port parameters from all service tools.
    ServiceInstaller has no port parameter; including port in schema causes
    TypeError at runtime when handlers pass **arguments directly.
    """
    from src.homelab_mcp.tool_schemas.service_tools_schema import SERVICE_TOOLS

    for tool_name, tool_def in SERVICE_TOOLS.items():
        props = tool_def.get("inputSchema", {}).get("properties", {})
        assert "port" not in props, (
            f"Service tool '{tool_name}' has phantom 'port' property — "
            f"ServiceInstaller has no port parameter (Phase 26-01)"
        )


def test_all_tool_schema_properties_are_valid_dicts():
    """Every property in every tool schema is a dict with type or description.

    Lightweight structural audit to catch malformed schema entries across
    all tools. Does not validate specific property values.
    """
    tools = get_available_tools()
    for tool_name, tool_def in tools.items():
        props = tool_def.get("inputSchema", {}).get("properties", {})
        for prop_name, prop_def in props.items():
            assert isinstance(prop_def, dict), (
                f"Tool '{tool_name}' property '{prop_name}' is not a dict: {type(prop_def)}"
            )
            has_type = "type" in prop_def
            has_desc = "description" in prop_def
            has_oneof = "oneOf" in prop_def
            has_anyof = "anyOf" in prop_def
            assert has_type or has_desc or has_oneof or has_anyof, (
                f"Tool '{tool_name}' property '{prop_name}' missing type/description/oneOf/anyOf"
            )


# --- Regression guards (v1.5 / PR #39) ---


def test_sch01_credential_type_rejects_non_enum_values() -> None:
    """SCH-01 regression: list_keyring_credentials.credential_type has enum=['ssh','proxmox'].

    Before commit bdb76bb the schema accepted arbitrary strings for credential_type, so
    MCP clients could call `list_keyring_credentials(credential_type='bogus')` and reach
    the handler with an invalid value. The fix adds `enum: ["ssh", "proxmox"]` to the
    property, causing the MCP framework to reject non-matching values at the JSON Schema
    validation step before the handler runs.

    Revert-proof: reverting commit bdb76bb (removing the `enum: ["ssh", "proxmox"]` line
    from credential_tools_schema.py) causes this test to fail on the
    `prop["enum"] == ["ssh", "proxmox"]` assertion because the `enum` key is absent
    (KeyError) or has a different value.
    """
    tools = get_available_tools()

    assert "list_keyring_credentials" in tools, "list_keyring_credentials must be registered in the tool registry"
    tool = tools["list_keyring_credentials"]

    assert "inputSchema" in tool
    props = tool["inputSchema"]["properties"]
    assert "credential_type" in props, "list_keyring_credentials must expose credential_type in its inputSchema"
    prop = props["credential_type"]

    # Core SCH-01 assertions:
    assert prop["type"] == "string", f"credential_type type must be 'string'; got {prop!r}"
    assert prop["enum"] == ["ssh", "proxmox"], (
        f"credential_type must restrict values to enum ['ssh', 'proxmox']; "
        f"got enum={prop.get('enum')!r} — SCH-01 regression would allow arbitrary strings"
    )


# Phase 33 regression tests — RED until implementation plans land (D-10, D-20, D-21)


def test_setup_mcp_admin_removed_from_tool_handlers() -> None:
    """D-10: setup_mcp_admin must not be in TOOL_HANDLERS dispatch."""
    from src.homelab_mcp.tool_handlers import TOOL_HANDLERS

    assert "setup_mcp_admin" not in TOOL_HANDLERS, "setup_mcp_admin must be removed from TOOL_HANDLERS dispatch (D-10)"


def test_update_server_credentials_removed_from_tool_handlers() -> None:
    """D-20: update_server_credentials must not be in TOOL_HANDLERS dispatch."""
    from src.homelab_mcp.tool_handlers import TOOL_HANDLERS

    assert "update_server_credentials" not in TOOL_HANDLERS


def test_remove_server_removed_from_tool_handlers() -> None:
    """D-21: remove_server must not be in TOOL_HANDLERS dispatch."""
    from src.homelab_mcp.tool_handlers import TOOL_HANDLERS

    assert "remove_server" not in TOOL_HANDLERS
    assert "remove_server_preview" not in TOOL_HANDLERS


# Phase 38 — update_device_fingerprint MCP routing tests


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_execute_update_device_fingerprint_success_phase38(mock_sitemap_cls):
    """Phase 38 D-05: handler routes successfully and returns merged fingerprint dict."""
    mock_adapter = MagicMock()
    mock_adapter.update_device_fingerprint.return_value = {
        "kernel_name": "Linux",
        "kernel_version": "6.5.13",
    }
    mock_sitemap_cls.return_value.db_adapter = mock_adapter
    result = await execute_tool(
        "update_device_fingerprint",
        {"hostname": "test-host", "fingerprint": {"kernel_name": "Linux"}},
    )
    assert "content" in result
    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "success"
    assert payload["fingerprint"]["kernel_name"] == "Linux"


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_update_device_fingerprint_filters_unknown_top_level_phase38(mock_sitemap_cls):
    """Phase 38 D-05b: handler drops unknown top-level keys before adapter call."""
    mock_adapter = MagicMock()
    mock_adapter.update_device_fingerprint.return_value = {"kernel_name": "X"}
    mock_sitemap_cls.return_value.db_adapter = mock_adapter
    await execute_tool(
        "update_device_fingerprint",
        {"hostname": "h", "fingerprint": {"kernel_name": "X", "bogus_key": "Y"}},
    )
    # Adapter is called with cleaned dict — bogus_key dropped
    call_args = mock_adapter.update_device_fingerprint.call_args
    cleaned = call_args[0][1]  # second positional arg
    assert "kernel_name" in cleaned
    assert "bogus_key" not in cleaned


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_update_device_fingerprint_missing_hostname_phase38(mock_sitemap_cls):
    """W3 fix: assert on EXACT handler-emitted hint substring, not just 'discover_and_map'.

    The substring 'discover_and_map' alone could appear in the tool description or in
    a 'Unknown tool' envelope from the dispatcher; tightening to the exact handler hint
    proves the handler's error envelope path is hit specifically.
    """
    mock_adapter = MagicMock()
    mock_adapter.update_device_fingerprint.side_effect = ValueError(
        "Hostname not in sitemap: 'unknown.local'. Run discover_and_map first to add the device."
    )
    mock_sitemap_cls.return_value.db_adapter = mock_adapter
    result = await execute_tool(
        "update_device_fingerprint",
        {"hostname": "unknown.local", "fingerprint": {}},
    )
    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "error"
    # Exact substring from the handler's hint (Task 3 will emit this).
    assert "Run discover_and_map for this hostname first" in payload.get("hint", "")


def test_update_device_fingerprint_annotations_phase38():
    """Phase 38: tool annotations registered with idempotentHint=True."""
    from src.homelab_mcp.tool_annotations import get_tool_annotations

    ann = get_tool_annotations("update_device_fingerprint")
    assert ann is not None
    assert ann.idempotentHint is True
    assert ann.readOnlyHint is False
    assert ann.destructiveHint is False


@pytest.mark.asyncio
async def test_update_device_fingerprint_malformed_dict_phase38():
    """W3 fix: assert handler's exact malformed-dict error string.

    Authored in Task 3 (after handler registration) so it specifically exercises the
    handler's `if not isinstance(fp_in, dict)` branch — NOT a dispatcher 'Unknown tool'
    envelope. The exact substring "`fingerprint` must be an object" is unique to the
    handler's malformed-dict branch and would not appear in any other error path.
    """
    result = await execute_tool(
        "update_device_fingerprint",
        {"hostname": "h", "fingerprint": "not a dict"},
    )
    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "error"
    # Exact substring from the handler's malformed-dict branch.
    assert "`fingerprint` must be an object" in payload["error"]


# Phase 38 Plan 05 — update_device_fingerprint_preview MCP routing tests


@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap")
async def test_execute_update_device_fingerprint_preview_phase38(mock_sitemap_cls):
    """Phase 38 D-05c (Plan 05): preview returns the merge result without persisting.

    The preview reads via get_all_devices, does NOT call the adapter's
    update_device_fingerprint method. Verifies BOTH the previously-stored
    capability (vulkan) and the incoming capability (cuda) appear in the
    returned merged dict.
    """
    mock_adapter = MagicMock()
    # Preview reads the current row via get_all_devices.
    mock_adapter.get_all_devices.return_value = [
        {
            "hostname": "h",
            "fingerprint": {
                "kernel_version": "6.0.0",
                "capabilities": {"vulkan": {"available": True}},
            },
        }
    ]
    mock_sitemap_cls.return_value.db_adapter = mock_adapter

    result = await execute_tool(
        "update_device_fingerprint_preview",
        {"hostname": "h", "fingerprint": {"capabilities": {"cuda": {"driver_version": "535"}}}},
    )

    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "success"
    # Preview returns the merged dict — both vulkan (preserved) and cuda (incoming) present
    assert "vulkan" in payload["fingerprint"]["capabilities"]
    assert "cuda" in payload["fingerprint"]["capabilities"]
    # Adapter's update method MUST NOT be called (preview is read-only)
    mock_adapter.update_device_fingerprint.assert_not_called()


def test_update_device_fingerprint_preview_in_read_only_tools_phase38():
    """Phase 38 D-05c (Plan 05): preview tool registered in _READ_ONLY_TOOLS, NOT in MUTATING_TOOLS.

    The preview wrapper is read-only — adding to MUTATING_TOOLS would fire spurious
    notifications/resources/list_changed events for what is a no-op merge calculation.
    """
    from src.homelab_mcp.server import MUTATING_TOOLS
    from src.homelab_mcp.tool_annotations import _READ_ONLY_TOOLS

    assert "update_device_fingerprint_preview" in _READ_ONLY_TOOLS
    assert "update_device_fingerprint_preview" not in MUTATING_TOOLS
