"""Integration tests for SSH functionality with real containers."""

import json
from pathlib import Path

import pytest

from src.homelab_mcp.ssh_tools import (
    ensure_mcp_ssh_key,
    get_mcp_ssh_key_path,
    setup_remote_mcp_admin,
    ssh_discover_system,
    verify_mcp_admin_access,
)

pytestmark = pytest.mark.integration


class TestSSHIntegration:
    """Integration tests for SSH functionality."""

    @pytest.mark.asyncio
    async def test_ssh_key_generation(self):
        """Test that SSH key generation works."""
        # Clean up any existing keys for this test
        key_path = get_mcp_ssh_key_path()
        pub_key_path = Path(str(key_path) + ".pub")

        if key_path.exists():
            key_path.unlink()
        if pub_key_path.exists():
            pub_key_path.unlink()

        # Generate new keys
        result_path = await ensure_mcp_ssh_key()

        # Verify keys were created
        assert key_path.exists()
        assert pub_key_path.exists()
        assert str(key_path) == result_path

        # Verify permissions (Windows has different permission system)
        import platform

        if platform.system() != "Windows":
            assert oct(key_path.stat().st_mode)[-3:] == "600"
            assert oct(pub_key_path.stat().st_mode)[-3:] == "644"
        else:
            # On Windows, just verify the files have some permissions set
            assert key_path.stat().st_mode > 0
            assert pub_key_path.stat().st_mode > 0

        # Verify key content format
        with open(pub_key_path) as f:
            pub_key_content = f.read()

        assert pub_key_content.startswith("ssh-rsa ")
        assert "mcp_admin@" in pub_key_content

    @pytest.mark.asyncio
    async def test_full_mcp_admin_setup_workflow(self, clean_container):
        """Test the complete workflow: setup -> verify -> discover."""
        container_info = clean_container

        # Ensure we have SSH keys
        await ensure_mcp_ssh_key()

        # Step 1: Setup mcp_admin user (use port 2222 for Docker)
        setup_result = await setup_remote_mcp_admin(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
        )

        setup_data = json.loads(setup_result)
        assert setup_data["status"] == "success"
        assert setup_data["mcp_admin_setup"]["user_creation"] in [
            "Success: mcp_admin user created",
            "User already exists",
        ]
        assert setup_data["mcp_admin_setup"]["sudo_access"] == "Success: Added to sudo group"
        assert "Success: SSH key" in setup_data["mcp_admin_setup"]["ssh_key"]
        assert setup_data["mcp_admin_setup"]["passwordless_sudo"] == "Success: Passwordless sudo enabled"
        assert setup_data["mcp_admin_setup"]["test_access"] == "Success: mcp_admin access verified"

        # Step 2: Verify access works
        verify_result = await verify_mcp_admin_access(hostname=container_info["hostname"], port=container_info["port"])

        verify_data = json.loads(verify_result)
        assert verify_data["status"] == "success"
        assert verify_data["mcp_admin"]["ssh_access"] == "Success: Connected with SSH key"
        assert verify_data["mcp_admin"]["sudo_access"] == "Success: Passwordless sudo working"
        assert verify_data["mcp_admin"]["username"] == "mcp_admin"

        # Step 3: Use ssh_discover with mcp_admin (no password needed)
        discover_result = await ssh_discover_system(
            hostname=container_info["hostname"],
            username="mcp_admin",
            port=container_info["port"],
        )

        discover_data = json.loads(discover_result)
        assert discover_data["status"] == "success"
        assert discover_data["hostname"] == "test-ubuntu"
        assert "data" in discover_data

        # Verify we got system information (CPU might not be available in containers)
        system_data = discover_data["data"]
        assert "memory" in system_data
        assert "disk" in system_data
        assert "os" in system_data
        assert "network" in system_data
        # CPU might not be available in container environments
        if "cpu" in system_data:
            # CPU data should have at least cores or model info
            assert "cores" in system_data["cpu"] or "model" in system_data["cpu"]

    @pytest.mark.asyncio
    async def test_force_update_key_scenario(self, clean_container):
        """Test updating SSH key when mcp_admin already exists."""
        container_info = clean_container

        # Ensure we have SSH keys
        await ensure_mcp_ssh_key()

        # First setup
        setup_result1 = await setup_remote_mcp_admin(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
        )

        setup_data1 = json.loads(setup_result1)
        assert setup_data1["status"] == "success"

        # Modify the SSH key to simulate a different key
        key_path = get_mcp_ssh_key_path()
        pub_key_path = Path(str(key_path) + ".pub")
        with open(pub_key_path) as f:
            original_key = f.read()

        # Create a fake "different" key by modifying the comment
        modified_key = original_key.replace("mcp_admin@", "mcp_admin_old@")
        with open(pub_key_path, "w") as f:
            f.write(modified_key)

        # Second setup with force update (should update the key)
        setup_result2 = await setup_remote_mcp_admin(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
            force_update_key=True,
        )

        setup_data2 = json.loads(setup_result2)
        assert setup_data2["status"] == "success"
        assert setup_data2["mcp_admin_setup"]["user_creation"] == "User already exists"
        assert setup_data2["mcp_admin_setup"]["ssh_key"] == "Success: SSH key updated"

        # Restore original key for verification
        with open(pub_key_path, "w") as f:
            f.write(original_key)

        # Verify access still works
        verify_result = await verify_mcp_admin_access(hostname=container_info["hostname"], port=container_info["port"])

        verify_data = json.loads(verify_result)
        assert verify_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_ssh_discover_authentication_methods(self, clean_container):
        """Test different authentication methods for ssh_discover."""
        container_info = clean_container

        # Test 1: SSH with password (regular user)
        discover_result1 = await ssh_discover_system(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
        )

        discover_data1 = json.loads(discover_result1)
        assert discover_data1["status"] == "success"

        # Test 2: Setup mcp_admin and test key-based auth
        await ensure_mcp_ssh_key()
        setup_result = await setup_remote_mcp_admin(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
        )

        setup_data = json.loads(setup_result)
        assert setup_data["status"] == "success"

        # Test 3: SSH with mcp_admin (automatic key usage)
        discover_result2 = await ssh_discover_system(
            hostname=container_info["hostname"],
            username="mcp_admin",
            port=container_info["port"],
        )

        discover_data2 = json.loads(discover_result2)
        assert discover_data2["status"] == "success"
        assert discover_data2["hostname"] == "test-ubuntu"

    @pytest.mark.asyncio
    async def test_error_scenarios(self, clean_container):
        """Test various error scenarios."""
        container_info = clean_container

        # Test 1: Wrong password
        discover_result1 = await ssh_discover_system(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password="wrongpassword",
            port=container_info["port"],
        )

        discover_data1 = json.loads(discover_result1)
        assert discover_data1["status"] == "error"
        assert "authentication failed" in discover_data1["error"].lower()

        # Test 2: Verify mcp_admin access when not set up
        verify_result = await verify_mcp_admin_access(hostname=container_info["hostname"], port=container_info["port"])

        verify_data = json.loads(verify_result)
        assert verify_data["status"] == "error"
        assert "authentication failed" in verify_data["error"].lower()

        # Test 3: Wrong hostname
        discover_result2 = await ssh_discover_system(
            hostname="nonexistent-host",
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
        )

        discover_data2 = json.loads(discover_result2)
        assert discover_data2["status"] == "error"

    @pytest.mark.asyncio
    async def test_no_force_update_preserves_existing_keys(self, clean_container):
        """Test that existing keys are preserved when force_update_key=False."""
        container_info = clean_container

        # Ensure we have SSH keys
        await ensure_mcp_ssh_key()

        # First setup
        setup_result1 = await setup_remote_mcp_admin(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
        )

        setup_data1 = json.loads(setup_result1)
        assert setup_data1["status"] == "success"

        # Second setup with force_update_key=False
        setup_result2 = await setup_remote_mcp_admin(
            hostname=container_info["hostname"],
            username=container_info["admin_user"],
            password=container_info["admin_pass"],
            port=container_info["port"],
            force_update_key=False,
        )

        setup_data2 = json.loads(setup_result2)
        assert setup_data2["status"] == "success"
        assert setup_data2["mcp_admin_setup"]["ssh_key"] == "SSH key already exists"
