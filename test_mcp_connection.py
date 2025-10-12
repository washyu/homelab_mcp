#!/usr/bin/env python3
"""
Quick test script to verify MCP server is working.
Run this to test your MCP server before connecting to Claude.
"""

import json
import os
import subprocess
import sys


def test_mcp_server():
    """Test basic MCP server functionality."""

    # Change to the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    print("🧪 Testing Homelab MCP Server...")
    print(f"📁 Working directory: {os.getcwd()}")

    # Test 1: Initialize
    print("\n1️⃣ Testing server initialization...")
    init_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}

    result = run_mcp_request(init_request)
    if result and "result" in result:
        print("✅ Server initialization successful")
        print(
            f"   Protocol version: {result['result'].get('protocolVersion', 'unknown')}"
        )
        print(
            f"   Server name: {result['result'].get('serverInfo', {}).get('name', 'unknown')}"
        )
    else:
        print("❌ Server initialization failed")
        return False

    # Test 2: List tools
    print("\n2️⃣ Testing tools list...")
    tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    result = run_mcp_request(tools_request)
    if result and "result" in result and "tools" in result["result"]:
        tools = result["result"]["tools"]
        print(f"✅ Found {len(tools)} available tools:")

        # Group tools by category
        ssh_tools = [
            t
            for t in tools
            if any(
                keyword in t.get("description", "").lower()
                for keyword in ["ssh", "admin", "hello"]
            )
        ]
        network_tools = [
            t
            for t in tools
            if any(
                keyword in t.get("description", "").lower()
                for keyword in ["network", "discover", "topology", "sitemap"]
            )
        ]
        crud_tools = [
            t
            for t in tools
            if any(
                keyword in t.get("description", "").lower()
                for keyword in ["deploy", "infrastructure", "backup", "scale"]
            )
        ]
        vm_tools = [
            t
            for t in tools
            if any(
                keyword in t.get("description", "").lower()
                for keyword in ["vm", "container", "control"]
            )
        ]

        print(f"   🔐 SSH & Admin tools: {len(ssh_tools)}")
        print(f"   🌐 Network Discovery tools: {len(network_tools)}")
        print(f"   🏗️  Infrastructure CRUD tools: {len(crud_tools)}")
        print(f"   🖥️  VM Management tools: {len(vm_tools)}")

        if len(tools) != 23:
            print(f"⚠️  Expected 23 tools, found {len(tools)}")
    else:
        print("❌ Failed to get tools list")
        return False

    # Test 3: Hello world
    print("\n3️⃣ Testing hello_world tool...")
    hello_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "hello_world"},
    }

    result = run_mcp_request(hello_request)
    if result and "result" in result:
        content = result["result"].get("content", [])
        if content and len(content) > 0:
            print("✅ Hello world tool working")
            print(f"   Response: {content[0].get('text', 'No text')}")
        else:
            print("❌ Hello world tool returned empty content")
            return False
    else:
        print("❌ Hello world tool failed")
        return False

    print("\n🎉 All tests passed! Your MCP server is ready to connect to Claude.")
    print("\n📋 Next steps:")
    print("1. Copy claude_desktop_config.json to Claude's config directory")
    print("2. Update the paths in the config file to match your system")
    print("3. Restart Claude Desktop")
    print("4. Look for the MCP connection indicator in Claude")

    return True


def run_mcp_request(request):
    """Run a single MCP request and return the response."""
    try:
        # Convert request to JSON
        request_json = json.dumps(request)

        # Run the MCP server with the request
        process = subprocess.Popen(
            [sys.executable, "run_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = process.communicate(input=request_json, timeout=10)

        if process.returncode != 0:
            print(f"❌ Server process failed with return code {process.returncode}")
            if stderr:
                print(f"   Error: {stderr}")
            return None

        # Parse the response
        try:
            return json.loads(stdout.strip())
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse server response as JSON: {e}")
            print(f"   Raw output: {stdout}")
            return None

    except subprocess.TimeoutExpired:
        print("❌ Request timed out")
        process.kill()
        return None
    except Exception as e:
        print(f"❌ Error running request: {e}")
        return None


if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)
