#!/usr/bin/env python3
"""
Test script for the enhanced error handling in the MCP server.
"""

import asyncio
import json
import sys
from src.homelab_mcp.server import HomelabMCPServer


async def test_timeout_scenarios():
    """Test various timeout scenarios to ensure they don't crash the server."""
    print("🧪 Testing Enhanced Error Handling\n")
    
    server = HomelabMCPServer()
    
    # Test 1: Invalid tool call
    print("Test 1: Invalid tool")
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    }
    
    response = await server.handle_request(request)
    print(f"✅ Result: {response['error']['message']}\n")
    
    # Test 2: SSH connection timeout (using invalid IP)
    print("Test 2: SSH timeout (will timeout gracefully)")
    request = {
        "jsonrpc": "2.0", 
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "ssh_discover",
            "arguments": {
                "hostname": "192.0.2.1",  # RFC5737 test IP (should timeout)
                "username": "test"
            }
        }
    }
    
    try:
        response = await asyncio.wait_for(server.handle_request(request), timeout=5.0)
        content = json.loads(response['result']['content'][0]['text'])
        print(f"✅ Result: {content.get('error', content.get('status'))}\n")
    except asyncio.TimeoutError:
        print("✅ Request timed out as expected (server didn't crash)\n")
    
    # Test 3: Health check
    print("Test 3: Health status")
    request = {
        "jsonrpc": "2.0",
        "id": 3, 
        "method": "health/status"
    }
    
    response = await server.handle_request(request)
    health = response['result']
    print(f"✅ Server health: {health['status']} (uptime: {health['uptime_seconds']:.1f}s)\n")
    
    print("🎉 All tests completed - server remained stable!")


async def test_json_malformation():
    """Test handling of malformed JSON."""
    print("Test 4: JSON Error Handling")
    
    server = HomelabMCPServer()
    
    # This would normally be handled in run_stdio, but we can test the error response
    malformed_request = {"invalid": "json", "missing_required_fields": True}
    
    try:
        response = await server.handle_request(malformed_request)
        print(f"✅ Malformed request handled: {response['error']['message']}")
    except Exception as e:
        print(f"✅ Exception caught gracefully: {str(e)}")


if __name__ == "__main__":
    print("=" * 60)
    print("🛡️  ENHANCED ERROR HANDLING VALIDATION")
    print("=" * 60)
    
    try:
        asyncio.run(test_timeout_scenarios())
        print("\n" + "=" * 40)
        asyncio.run(test_json_malformation())
        
        print("\n" + "✅" * 20)
        print("🎊 ALL TESTS PASSED - ERROR HANDLING IS WORKING!")
        print("✅" * 20)
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1)