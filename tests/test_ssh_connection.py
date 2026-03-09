"""Tests for SSH connection helper with TOFU host key verification."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def known_hosts_path(tmp_path: Path) -> Path:
    """Create a temporary known_hosts file path."""
    return tmp_path / "known_hosts"


@pytest.fixture
def mock_ssh_key() -> MagicMock:
    """Create a mock SSH key that behaves like asyncssh.SSHKey."""
    key = MagicMock()
    key.get_algorithm.return_value = "ssh-ed25519"
    key.export_public_key.return_value = b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey123"
    return key


@pytest.fixture
def mock_ssh_key_different() -> MagicMock:
    """Create a different mock SSH key for mismatch tests."""
    key = MagicMock()
    key.get_algorithm.return_value = "ssh-ed25519"
    key.export_public_key.return_value = b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDifferentKey456"
    return key


class TestTOFUFirstConnection:
    """Test TOFU behavior on first connection to unknown host."""

    @pytest.mark.asyncio
    async def test_tofu_first_connection_accepts_and_stores_key(
        self, known_hosts_path: Path, mock_ssh_key: MagicMock
    ) -> None:
        """First connection to unknown host should accept key and store it."""
        from homelab_mcp.ssh_connection import TOFUSSHClient

        # Create empty known_hosts file
        known_hosts_path.touch()

        client = TOFUSSHClient(known_hosts_path)
        result = client.validate_host_public_key("192.168.1.100", None, 22, mock_ssh_key)

        # For async validation, handle both sync and coroutine returns
        if asyncio.iscoroutine(result):
            result = await result

        assert result is True

        # Verify key was stored
        content = known_hosts_path.read_text()
        assert "192.168.1.100" in content
        assert "ssh-ed25519" in content


class TestTOFUKnownKeyMatch:
    """Test TOFU behavior when connecting to host with matching key."""

    @pytest.mark.asyncio
    async def test_ssh_connect_passes_known_hosts_path(
        self, known_hosts_path: Path
    ) -> None:
        """ssh_connect should pass known_hosts file path to asyncssh.connect."""
        from homelab_mcp.ssh_connection import ssh_connect

        # Pre-populate known_hosts
        known_hosts_path.write_text("192.168.1.100 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey123\n")

        with patch("homelab_mcp.ssh_connection.asyncssh") as mock_asyncssh:
            mock_conn = AsyncMock()
            mock_asyncssh.connect = AsyncMock(return_value=mock_conn)

            await ssh_connect(
                hostname="192.168.1.100",
                username="testuser",
                known_hosts_path=known_hosts_path,
            )

            # Verify known_hosts was passed as string path
            call_kwargs = mock_asyncssh.connect.call_args
            assert call_kwargs.kwargs.get("known_hosts") == str(known_hosts_path)


class TestTOFUKeyMismatch:
    """Test TOFU behavior when host key has changed (possible MITM)."""

    @pytest.mark.asyncio
    async def test_tofu_rejects_mismatch(
        self, known_hosts_path: Path, mock_ssh_key_different: MagicMock
    ) -> None:
        """Connection to host with changed key should be rejected."""
        from homelab_mcp.ssh_connection import TOFUSSHClient

        # Pre-populate with a key for this host
        known_hosts_path.write_text(
            "192.168.1.100 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOriginalKey789\n"
        )

        client = TOFUSSHClient(known_hosts_path)
        result = client.validate_host_public_key(
            "192.168.1.100", None, 22, mock_ssh_key_different
        )

        if asyncio.iscoroutine(result):
            result = await result

        assert result is False


class TestKnownHostsFile:
    """Test known_hosts file management."""

    @pytest.mark.asyncio
    async def test_known_hosts_file_created_if_not_exists(
        self, tmp_path: Path
    ) -> None:
        """ssh_connect should create known_hosts file and parent dir if missing."""
        from homelab_mcp.ssh_connection import ssh_connect

        kh_path = tmp_path / "subdir" / "known_hosts"
        assert not kh_path.exists()

        with patch("homelab_mcp.ssh_connection.asyncssh") as mock_asyncssh:
            mock_conn = AsyncMock()
            mock_asyncssh.connect = AsyncMock(return_value=mock_conn)

            await ssh_connect(
                hostname="192.168.1.100",
                username="testuser",
                known_hosts_path=kh_path,
            )

        assert kh_path.exists()

    @pytest.mark.asyncio
    async def test_non_standard_port_format(
        self, known_hosts_path: Path, mock_ssh_key: MagicMock
    ) -> None:
        """Non-standard port should use [host]:port format in known_hosts."""
        from homelab_mcp.ssh_connection import TOFUSSHClient

        known_hosts_path.touch()

        client = TOFUSSHClient(known_hosts_path)
        result = client.validate_host_public_key("192.168.1.100", None, 2222, mock_ssh_key)

        if asyncio.iscoroutine(result):
            result = await result

        assert result is True

        content = known_hosts_path.read_text()
        assert "[192.168.1.100]:2222" in content

    @pytest.mark.asyncio
    async def test_standard_port_uses_plain_host(
        self, known_hosts_path: Path, mock_ssh_key: MagicMock
    ) -> None:
        """Standard port 22 should use plain hostname (no brackets)."""
        from homelab_mcp.ssh_connection import TOFUSSHClient

        known_hosts_path.touch()

        client = TOFUSSHClient(known_hosts_path)
        result = client.validate_host_public_key("192.168.1.100", None, 22, mock_ssh_key)

        if asyncio.iscoroutine(result):
            result = await result

        content = known_hosts_path.read_text()
        assert "192.168.1.100 " in content
        assert "[192.168.1.100]" not in content


class TestSSHConnectKwargs:
    """Test that ssh_connect passes correct parameters to asyncssh.connect."""

    @pytest.mark.asyncio
    async def test_ssh_connect_passes_correct_kwargs(
        self, known_hosts_path: Path
    ) -> None:
        """ssh_connect should pass known_hosts and client_factory to asyncssh."""
        from homelab_mcp.ssh_connection import TOFUSSHClient, ssh_connect

        known_hosts_path.touch()

        with patch("homelab_mcp.ssh_connection.asyncssh") as mock_asyncssh:
            mock_conn = AsyncMock()
            mock_asyncssh.connect = AsyncMock(return_value=mock_conn)
            # Make SSHClient available for isinstance checks
            mock_asyncssh.SSHClient = type("SSHClient", (), {})

            await ssh_connect(
                hostname="192.168.1.100",
                username="testuser",
                port=2222,
                password="secret",
                key_path="/path/to/key",
                known_hosts_path=known_hosts_path,
            )

            call_kwargs = mock_asyncssh.connect.call_args.kwargs
            assert call_kwargs["host"] == "192.168.1.100"
            assert call_kwargs["username"] == "testuser"
            assert call_kwargs["port"] == 2222
            assert call_kwargs["known_hosts"] == str(known_hosts_path)
            assert call_kwargs["password"] == "secret"
            assert call_kwargs["client_keys"] == ["/path/to/key"]
            assert "client_factory" in call_kwargs
