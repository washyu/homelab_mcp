"""
Integration tests for Proxmox API.

These tests make REAL calls to a Proxmox server.
They verify that:
1. The Proxmox API hasn't changed
2. Our code correctly interacts with real Proxmox
3. End-to-end workflows work

Requirements:
- PROXMOX_HOST environment variable set
- PROXMOX_USER and PROXMOX_PASSWORD (or PROXMOX_API_TOKEN)
- A real Proxmox server (can be a test instance)
- Permission to create/delete test VMs

Run with:
    export PROXMOX_HOST=192.168.1.100
    export PROXMOX_USER=root@pam
    export PROXMOX_PASSWORD=yourpassword
    uv run pytest tests/integration/test_proxmox_integration.py -v -m integration
"""

import os

import pytest

from src.homelab_mcp.proxmox_api import (
    create_proxmox_lxc,
    delete_proxmox_vm,
    get_proxmox_node_status,
    get_proxmox_vm_status,
    list_proxmox_resources,
    manage_proxmox_vm,
)

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


# ============================================================================
# INTEGRATION TEST EXAMPLE #1: List Resources
# ============================================================================


@pytest.mark.asyncio
async def test_list_proxmox_resources_real():
    """
    Test listing real Proxmox resources.

    This test:
    - Makes a REAL API call to Proxmox
    - Verifies the response has the expected structure
    - Catches if the API response format changes
    """
    # Skip if no Proxmox credentials available
    if not os.getenv("PROXMOX_HOST"):
        pytest.skip("PROXMOX_HOST not set - skipping integration test")

    # WHEN: Calling the real API (no mocks!)
    result = await list_proxmox_resources()

    # THEN: Should get real data back
    assert result["status"] == "success", f"API call failed: {result}"
    assert "resources" in result
    assert "total" in result
    assert isinstance(result["resources"], list)

    # AND: Resources should have expected fields
    if len(result["resources"]) > 0:
        first_resource = result["resources"][0]
        assert "type" in first_resource, "API response missing 'type' field"
        # If this fails, Proxmox API response format changed!


# ============================================================================
# INTEGRATION TEST EXAMPLE #2: Full VM Lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_vm_lifecycle_end_to_end():
    """
    Test complete VM lifecycle: Create → Start → Stop → Delete

    This is a comprehensive test that:
    - Creates a real LXC container
    - Starts it
    - Checks status
    - Stops it
    - Deletes it

    Catches:
    - API endpoint changes
    - API parameter changes
    - API response format changes
    - Real-world errors
    """
    if not os.getenv("PROXMOX_HOST"):
        pytest.skip("PROXMOX_HOST not set")

    # Use a high VMID to avoid conflicts with real VMs
    test_vmid = 9999
    test_node = os.getenv("PROXMOX_TEST_NODE", "pve")

    try:
        # STEP 1: Create a test container
        print(f"\n[1/5] Creating test container {test_vmid}...")
        create_result = await create_proxmox_lxc(
            node=test_node,
            vmid=test_vmid,
            hostname="integration-test",
            memory=256,
            cores=1,
            rootfs_size=2,
        )

        # Verify creation worked
        assert create_result["status"] == "success", f"Create failed: {create_result}"
        print(f"✅ Container created: {create_result['message']}")

        # STEP 2: Start the container
        print(f"\n[2/5] Starting container {test_vmid}...")
        start_result = await manage_proxmox_vm(node=test_node, vmid=test_vmid, action="start", vm_type="lxc")

        assert start_result["status"] == "success", f"Start failed: {start_result}"
        print("✅ Container started")

        # STEP 3: Check status (should be running)
        print("\n[3/5] Checking status...")
        status_result = await get_proxmox_vm_status(node=test_node, vmid=test_vmid, vm_type="lxc")

        assert status_result["status"] == "success"
        # This will catch if Proxmox changes status field names!
        assert "data" in status_result
        print(f"✅ Status retrieved: {status_result['data'].get('status', 'unknown')}")

        # STEP 4: Stop the container
        print("\n[4/5] Stopping container...")
        stop_result = await manage_proxmox_vm(node=test_node, vmid=test_vmid, action="stop", vm_type="lxc")

        assert stop_result["status"] == "success", f"Stop failed: {stop_result}"
        print("✅ Container stopped")

        # STEP 5: Delete the container
        print("\n[5/5] Deleting container...")
        delete_result = await delete_proxmox_vm(node=test_node, vmid=test_vmid, vm_type="lxc")

        assert delete_result["status"] == "success", f"Delete failed: {delete_result}"
        print("✅ Container deleted")

        print("\n🎉 Full lifecycle test completed successfully!")

    except Exception as e:
        # Cleanup: Try to delete the test VM if it exists
        print("\n⚠️  Test failed, attempting cleanup...")
        try:
            await delete_proxmox_vm(node=test_node, vmid=test_vmid, vm_type="lxc")
            print("✅ Cleanup successful")
        except Exception:
            print(f"❌ Cleanup failed - VM {test_vmid} may need manual deletion")

        # Re-raise original exception
        raise e


# ============================================================================
# INTEGRATION TEST EXAMPLE #3: Node Status
# ============================================================================


@pytest.mark.asyncio
async def test_get_node_status_real():
    """
    Test getting real node status.

    Verifies:
    - API endpoint still works
    - Response has expected fields
    - Data types are correct
    """
    if not os.getenv("PROXMOX_HOST"):
        pytest.skip("PROXMOX_HOST not set")

    test_node = os.getenv("PROXMOX_TEST_NODE", "pve")

    # WHEN: Getting real node status
    result = await get_proxmox_node_status(node=test_node)

    # THEN: Should have expected structure
    assert result["status"] == "success"
    assert result["node"] == test_node
    assert "data" in result

    # AND: Data should have CPU/memory info (Proxmox always returns these)
    data = result["data"]
    assert "cpu" in data or "cpuinfo" in data, "Proxmox API response format changed!"
    assert "memory" in data or "mem" in data, "Proxmox API response format changed!"

    print("\n✅ Node status test passed")
    print(f"   CPU: {data.get('cpu', 'N/A')}")
    print(f"   Memory: {data.get('memory', 'N/A')}/{data.get('maxmem', 'N/A')}")


# ============================================================================
# INTEGRATION TEST EXAMPLE #4: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_vm_returns_error():
    """
    Test that invalid VM IDs are handled gracefully.

    This verifies:
    - Error handling works with real API
    - Error messages are meaningful
    - No crashes on bad input
    """
    if not os.getenv("PROXMOX_HOST"):
        pytest.skip("PROXMOX_HOST not set")

    test_node = os.getenv("PROXMOX_TEST_NODE", "pve")

    # WHEN: Trying to get status of non-existent VM
    result = await get_proxmox_vm_status(
        node=test_node,
        vmid=99999,  # Very unlikely to exist
        vm_type="qemu",
    )

    # THEN: Should return error gracefully (not crash)
    assert result["status"] == "error"
    assert "message" in result

    print("\n✅ Error handling test passed")
    print(f"   Error message: {result['message']}")


# ============================================================================
# INTEGRATION TEST EXAMPLE #5: API Version Detection
# ============================================================================


@pytest.mark.asyncio
async def test_proxmox_api_version():
    """
    Detect which Proxmox API version we're testing against.

    This is informational - helps you know if tests fail
    because you're testing against a different Proxmox version.
    """
    if not os.getenv("PROXMOX_HOST"):
        pytest.skip("PROXMOX_HOST not set")

    # Get version from /version endpoint
    from src.homelab_mcp.proxmox_api import get_proxmox_client

    client = get_proxmox_client()

    try:
        version_data = await client.get("/version")

        print("\n📋 Proxmox Environment Info:")
        print(f"   Version: {version_data.get('version', 'unknown')}")
        print(f"   Release: {version_data.get('release', 'unknown')}")
        print(f"   Repo ID: {version_data.get('repoid', 'unknown')}")

        # You could add version-specific test logic here
        # Example: if version >= 8.0, expect new response format

    except Exception as e:
        print(f"\n⚠️  Could not detect Proxmox version: {e}")


# ============================================================================
# NOTES FOR DEVELOPERS
# ============================================================================

"""
HOW TO RUN THESE TESTS:

1. Setup environment:
   export PROXMOX_HOST=192.168.1.100
   export PROXMOX_USER=root@pam
   export PROXMOX_PASSWORD=yourpassword
   export PROXMOX_TEST_NODE=pve  # Optional, defaults to 'pve'

2. Run integration tests:
   uv run pytest tests/integration/test_proxmox_integration.py -v -m integration

3. Run ONLY the lifecycle test:
   uv run pytest tests/integration/test_proxmox_integration.py::test_vm_lifecycle_end_to_end -v -s

4. Run in CI/CD (nightly):
   Add this to .github/workflows/main.yml under a scheduled job


WHAT THESE TESTS CATCH:

✅ Proxmox API endpoint changes
✅ Proxmox API response format changes
✅ Proxmox API parameter changes
✅ Real authentication issues
✅ Real network/connectivity issues
✅ Version compatibility issues

WHAT THESE TESTS DON'T CATCH:

❌ Logic bugs in YOUR code (unit tests catch those)
❌ Performance issues (need performance tests)
❌ Security issues (need security scans)


BEST PRACTICES:

1. Run unit tests on every commit (fast)
2. Run integration tests nightly or weekly (slow)
3. Use a dedicated test Proxmox instance (not production!)
4. Clean up test VMs in the test (use try/finally)
5. Use high VMID numbers (9000+) to avoid conflicts
"""
