"""Integration tests for SSH functionality with real containers."""

from pathlib import Path

import pytest

from src.homelab_mcp.ssh_tools import (
    ensure_mcp_ssh_key,
    get_mcp_ssh_key_path,
)

pytestmark = pytest.mark.integration


# Tests for setup_remote_mcp_admin and verify_mcp_admin_access were removed in
# Phase 33 (D-11) and 33.1 (D-05) when those functions were deleted as part of
# the keyring-only credential migration. Future docker-based integration tests
# should onboard via the `credentials add` CLI fixture, not the deleted helpers.


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
