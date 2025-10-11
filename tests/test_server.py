"""Tests for the MCP server."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from src.homelab_mcp.server import HomelabMCPServer


@pytest.mark.asyncio
@patch('src.homelab_mcp.server.ensure_mcp_ssh_key')
async def test_server_initialize(mock_ensure_key):
    """Test server initialization response."""
    server = HomelabMCPServer()
    
    # Mock SSH key generation
    mock_ensure_key.return_value = "/home/user/.ssh/mcp_admin_rsa"
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    
    response = await server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["protocolVersion"] == "2024-11-05"
    assert response["result"]["serverInfo"]["name"] == "homelab-mcp"
    
    # Verify SSH key was generated on first initialization
    mock_ensure_key.assert_called_once()
    
    # Second initialization should not regenerate key
    response2 = await server.handle_request(request)
    assert response2["jsonrpc"] == "2.0"
    mock_ensure_key.assert_called_once()  # Still only called once


@pytest.mark.asyncio
async def test_tools_list():
    """Test listing available tools."""
    server = HomelabMCPServer()
    
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    response = await server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    assert "result" in response
    assert "tools" in response["result"]
    
    tools = response["result"]["tools"]
    assert len(tools) == 34  # All tools including SSH, sitemap, infrastructure, VM, service, and Ansible tools
    
    # Check tool names and descriptions
    tool_names = [tool.get("description") for tool in tools]
    assert any("SSH" in desc for desc in tool_names)
    assert any("setup mcp_admin" in desc for desc in tool_names)
    assert any("Verify" in desc for desc in tool_names)
    
    # Check new sitemap tools are included
    assert any("network site map" in desc for desc in tool_names)
    assert any("topology" in desc for desc in tool_names)
    assert any("deployment" in desc for desc in tool_names)


@pytest.mark.asyncio
async def test_unknown_method():
    """Test handling of unknown method."""
    server = HomelabMCPServer()
    
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "unknown/method",
        "params": {}
    }
    
    response = await server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 4
    assert "error" in response
    assert response["error"]["code"] == -32603
    assert "Unknown method" in response["error"]["message"]


@pytest.mark.asyncio
async def test_unknown_tool():
    """Test handling of unknown tool."""
    server = HomelabMCPServer()
    
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool"
        }
    }
    
    response = await server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 5
    assert "error" in response
    assert "Unknown tool" in response["error"]["message"]


@pytest.mark.asyncio
async def test_ssh_discover_tool_missing_params():
    """Test ssh_discover tool with missing required parameters."""
    server = HomelabMCPServer()
    
    request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "ssh_discover",
            "arguments": {
                "hostname": "192.168.1.100"
                # Missing username
            }
        }
    }
    
    response = await server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 6
    # Should get either direct error or error in content
    has_error = ("error" in response or 
                ("result" in response and "content" in response["result"] and 
                 "error" in str(response["result"]["content"])))
    assert has_error


@pytest.mark.asyncio
async def test_health_status_endpoint():
    """Test the health status endpoint."""
    server = HomelabMCPServer()
    
    request = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "health/status"
    }
    
    response = await server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 7
    assert "result" in response
    
    health_status = response["result"]
    assert "status" in health_status
    assert "uptime_seconds" in health_status
    assert "total_requests" in health_status
    assert "error_rate" in health_status


@pytest.mark.asyncio
async def test_server_timeout_handling():
    """Test that server handles tool timeouts gracefully."""
    server = HomelabMCPServer()
    
    # Mock a tool that will timeout
    with patch('src.homelab_mcp.tools.execute_tool') as mock_execute:
        async def slow_tool(*args, **kwargs):
            await asyncio.sleep(0.2)  # Longer than our test timeout
            return {"content": [{"type": "text", "text": "success"}]}
        
        mock_execute.side_effect = slow_tool
        
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "ssh_discover",
                "arguments": {"hostname": "test", "username": "test"}
            }
        }
        
        # Should timeout and return error, not crash
        response = await asyncio.wait_for(server.handle_request(request), timeout=0.5)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 8
        # Should get either direct error or error in content
        has_error = ("error" in response or 
                    ("result" in response and "content" in response["result"] and 
                     "error" in str(response["result"]["content"])))
        assert has_error


@pytest.mark.asyncio
@patch('src.homelab_mcp.server.ensure_mcp_ssh_key')
async def test_server_ssh_key_timeout(mock_ensure_key):
    """Test server handles SSH key initialization timeout."""
    # Make SSH key initialization timeout
    async def slow_key_gen():
        await asyncio.sleep(1.0)  # Long enough to trigger timeout in patched version
        return "/test/path"
    
    mock_ensure_key.side_effect = slow_key_gen
    
    # Patch the timeout to immediately raise TimeoutError for faster testing
    with patch('asyncio.wait_for') as mock_wait_for:
        mock_wait_for.side_effect = asyncio.TimeoutError()
        
        server = HomelabMCPServer()
        
        request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "initialize"
        }
        
        # Should timeout during SSH key generation
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 9
        # Should get either direct error or error in content
        has_error = ("error" in response or 
                    ("result" in response and "content" in response["result"] and 
                     "error" in str(response["result"]["content"])))
        assert has_error


@pytest.mark.asyncio
async def test_server_health_monitoring():
    """Test server health monitoring functionality."""
    from src.homelab_mcp.error_handling import health_checker
    
    # Reset health checker for clean test
    initial_requests = health_checker.request_count
    initial_errors = health_checker.error_count
    
    server = HomelabMCPServer()
    
    # Make a successful request
    request = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/list"
    }
    
    await server.handle_request(request)
    
    # Check that request was recorded
    assert health_checker.request_count > initial_requests
    
    # Make an error request
    error_request = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "nonexistent_tool"}
    }
    
    await server.handle_request(error_request)
    
    # Check that error was recorded
    assert health_checker.error_count > initial_errors


@pytest.mark.asyncio
async def test_server_exception_handling():
    """Test server handles unexpected exceptions gracefully."""
    server = HomelabMCPServer()
    
    # Mock execute_tool to raise unexpected exception
    with patch('src.homelab_mcp.tools.execute_tool') as mock_execute:
        mock_execute.side_effect = RuntimeError("Unexpected error")
        
        request = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "ssh_discover",
                "arguments": {"hostname": "test", "username": "test"}
            }
        }
        
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 12
        # Should get either direct error or error in content
        has_error = ("error" in response or 
                    ("result" in response and "content" in response["result"] and 
                     "error" in str(response["result"]["content"])))
        assert has_error
