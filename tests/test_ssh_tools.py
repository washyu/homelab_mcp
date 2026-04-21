"""Tests for SSH tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from src.homelab_mcp.ssh_tools import (
    _sudo_run,
    ensure_mcp_ssh_key,
    ssh_discover_system,
    verify_mcp_admin_access,
)


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_success(mock_connect):
    """Test successful SSH discovery."""
    # Mock command results - in the order they are executed by ssh_discover_system
    # Only the commands that will actually be executed when CPU model succeeds on first try
    hostname_result = MagicMock()
    hostname_result.exit_status = 0
    hostname_result.stdout = "raspberrypi"

    # nproc command for CPU cores
    nproc_result = MagicMock()
    nproc_result.exit_status = 0
    nproc_result.stdout = "4"

    # CPU model name command (succeeds, so fallback methods won't be called)
    cpu_model_result = MagicMock()
    cpu_model_result.exit_status = 0
    cpu_model_result.stdout = "model name\t: Intel Core i5"

    # Memory command - free -b returns bytes
    mem_result = MagicMock()
    mem_result.exit_status = 0
    mem_result.stdout = """              total        used        free      shared  buff/cache   available
Mem:     8266850304  2254479360  4182536704   128974848  1829834240  5677662208"""

    # Disk command - df -B1 returns bytes
    disk_result = MagicMock()
    disk_result.exit_status = 0
    disk_result.stdout = """Filesystem      1B-blocks        Used    Available Use% Mounted on
/dev/sda1     21474836480  5905580032  14970068992  30% /"""

    # Network command
    net_result = MagicMock()
    net_result.exit_status = 0
    net_result.stdout = json.dumps(
        [
            {
                "ifname": "eth0",
                "operstate": "UP",
                "addr_info": [{"family": "inet", "local": "192.168.1.100"}],
            }
        ]
    )

    # Uptime command
    uptime_result = MagicMock()
    uptime_result.exit_status = 0
    uptime_result.stdout = "up 2 days, 3 hours, 45 minutes"

    # OS command
    os_result = MagicMock()
    os_result.exit_status = 0
    os_result.stdout = 'PRETTY_NAME="Ubuntu 22.04.3 LTS"'

    # Create mock connection
    mock_conn = AsyncMock()
    call_count = 0

    async def mock_run(*args, **kwargs):
        nonlocal call_count
        # Commands in actual order: hostname, nproc, cpu model, free, df, ip, uptime, os-release
        results = [
            hostname_result,
            nproc_result,
            cpu_model_result,
            mem_result,
            disk_result,
            net_result,
            uptime_result,
            os_result,
        ]
        if call_count < len(results):
            result = results[call_count]
            call_count += 1
            return result
        else:
            # Return a default failure result for any extra calls
            default_result = MagicMock()
            default_result.exit_status = 1
            default_result.stdout = ""
            return default_result

    mock_conn.run = mock_run

    # ssh_connect is async, returns a connection usable as async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Execute discovery
    result = await ssh_discover_system(hostname="test-host", username="test-user", password="test-pass")

    # Parse result
    result_data = json.loads(result)

    # Verify structure
    assert result_data["status"] == "success"
    assert result_data["hostname"] == "raspberrypi"  # Actual hostname from remote system
    assert result_data["connection_ip"] == "test-host"  # IP used to connect
    assert "data" in result_data

    # Verify CPU info
    assert "cpu" in result_data["data"]
    assert result_data["data"]["cpu"]["model"] == "Intel Core i5"
    assert result_data["data"]["cpu"]["count"] == 4

    # Verify memory info - free command returns values in bytes when using -b flag
    assert "memory" in result_data["data"]
    # The test mock needs to return bytes, not human-readable format
    assert "total" in result_data["data"]["memory"]
    assert "used" in result_data["data"]["memory"]

    # Verify disk info - df -B1 returns values in bytes
    assert "disk" in result_data["data"]
    assert "total" in result_data["data"]["disk"]
    assert "used" in result_data["data"]["disk"]
    assert "available" in result_data["data"]["disk"]

    # Verify network info
    assert "network" in result_data["data"]
    assert len(result_data["data"]["network"]) == 1
    assert result_data["data"]["network"][0]["name"] == "eth0"
    assert "192.168.1.100" in result_data["data"]["network"][0]["addresses"]

    # Verify uptime and OS
    assert result_data["data"]["uptime"] == "up 2 days, 3 hours, 45 minutes"
    assert result_data["data"]["os"] == "Ubuntu 22.04.3 LTS"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_auth_failure(mock_connect):
    """Test SSH discovery with authentication failure."""
    mock_connect.side_effect = asyncssh.misc.PermissionDenied("Authentication failed")

    result = await ssh_discover_system(hostname="test-host", username="test-user", password="wrong-pass")

    result_data = json.loads(result)
    assert result_data["status"] == "error"
    assert result_data["connection_ip"] == "test-host"
    assert "authentication failed" in result_data["error"].lower()


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_connection_timeout(mock_connect):
    """Test SSH discovery with connection timeout."""

    mock_connect.side_effect = TimeoutError()

    result = await ssh_discover_system(hostname="unreachable-host", username="test-user", password="test-pass")

    result_data = json.loads(result)
    assert result_data["status"] == "error"
    assert result_data["connection_ip"] == "unreachable-host"
    assert "timeout" in result_data["error"].lower()


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.get_database_adapter")
async def test_ssh_discover_no_credentials(mock_get_db):
    """Test SSH discovery without password or key."""
    # Mock database to return no stored credentials
    mock_adapter = MagicMock()
    mock_adapter.get_credential_by_hostname.return_value = None
    mock_get_db.return_value = mock_adapter

    result = await ssh_discover_system(hostname="test-host", username="test-user")

    result_data = json.loads(result)
    assert result_data["status"] == "error"
    # Updated error message since we now use credential resolver
    assert "No credentials" in result_data["error"]


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_with_key_path(mock_connect):
    """Test SSH discovery using key file."""
    # Mock SSH connection
    mock_conn = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Mock minimal command results
    mock_result = MagicMock()
    mock_result.exit_status = 1  # Commands fail
    mock_result.stdout = None
    mock_conn.run.return_value = mock_result

    # Execute discovery with key
    await ssh_discover_system(hostname="test-host", username="test-user", key_path="/path/to/key")

    # Verify ssh_connect was called with key_path parameter
    mock_connect.assert_called_once()
    call_kwargs = mock_connect.call_args.kwargs
    assert call_kwargs["key_path"] == "/path/to/key"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.SSH_KEY_DIR")
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
@patch("src.homelab_mcp.ssh_tools.asyncssh.generate_private_key")
async def test_ensure_mcp_ssh_key_creates_new(mock_generate, mock_get_path, mock_key_dir):
    """Test SSH key generation when keys don't exist."""
    # Setup mock paths
    mock_key_path = MagicMock()
    mock_key_path.exists.return_value = False
    mock_key_path.__str__.return_value = "/home/user/.ssh/mcp/mcp_admin_key"
    mock_get_path.return_value = mock_key_path

    mock_pub_key_path = MagicMock()
    mock_pub_key_path.exists.return_value = False

    # Mock Path() constructor to return our pub key path
    with patch("src.homelab_mcp.ssh_tools.Path") as mock_path_class:
        mock_path_class.return_value = mock_pub_key_path

        # Mock directory
        mock_key_dir.mkdir = MagicMock()

        # Mock key generation
        mock_private_key = MagicMock()
        mock_private_key.export_private_key.return_value = b"private_key_data"
        mock_private_key.export_public_key.return_value = b"public_key_data"
        mock_generate.return_value = mock_private_key

        # Execute
        result = await ensure_mcp_ssh_key()

        # Verify key generation with comment parameter
        mock_generate.assert_called_once_with("ssh-rsa", key_size=2048, comment="mcp_admin@homelab")

        # Verify directory creation
        mock_key_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True, mode=0o700)

        # Verify file writes
        mock_key_path.write_bytes.assert_called_once_with(b"private_key_data")
        mock_key_path.chmod.assert_called_once_with(0o600)
        mock_pub_key_path.write_text.assert_called_once_with("public_key_data")
        mock_pub_key_path.chmod.assert_called_once_with(0o644)

        # Verify result
        assert result == "/home/user/.ssh/mcp/mcp_admin_key"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
async def test_ensure_mcp_ssh_key_uses_existing(mock_get_path):
    """Test that existing SSH keys are reused."""
    # Setup mock paths
    mock_key_path = MagicMock()
    mock_key_path.exists.return_value = True
    mock_key_path.__str__.return_value = "/home/user/.ssh/mcp/mcp_admin_key"
    mock_get_path.return_value = mock_key_path

    with patch("src.homelab_mcp.ssh_tools.Path") as mock_path_class:
        mock_pub_key_path = MagicMock()
        mock_pub_key_path.exists.return_value = True
        mock_path_class.return_value = mock_pub_key_path

        # Execute
        result = await ensure_mcp_ssh_key()

        # Verify result points to existing key
        assert result == "/home/user/.ssh/mcp/mcp_admin_key"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ensure_mcp_ssh_key")
@patch("src.homelab_mcp.ssh_tools.Path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_setup_remote_mcp_admin_user_exists(mock_connect, mock_path, mock_ensure_key):
    """Test remote mcp_admin setup when user already exists."""
    # Mock SSH key
    mock_ensure_key.return_value = "/home/user/.ssh/mcp_admin_rsa"

    # Mock public key path
    mock_pub_key = MagicMock()
    mock_pub_key.read_text.return_value = "ssh-rsa AAAAB3... mcp_admin@host"
    mock_path.return_value = mock_pub_key

    # Mock SSH connection and commands
    mock_conn = AsyncMock()

    # Mock command results - for when user already exists (new SFTP-based sequence)
    user_check = MagicMock()
    user_check.exit_status = 0  # User exists

    sudo_group = MagicMock()
    sudo_group.exit_status = 0

    mktemp_result = MagicMock()
    mktemp_result.exit_status = 0
    mktemp_result.stdout = "/tmp/mcp_key_aBcXyZ.pub\n"

    key_check = MagicMock()
    key_check.exit_status = 1  # Key doesn't exist

    mkdir_home = MagicMock()  # sudo mkdir -p /home/mcp_admin
    mkdir_home.exit_status = 0

    chown_home = MagicMock()  # sudo chown mcp_admin:mcp_admin /home/mcp_admin
    chown_home.exit_status = 0

    mkdir_cmd = MagicMock()  # create .ssh directory
    mkdir_cmd.exit_status = 0

    add_key = MagicMock()
    add_key.exit_status = 0

    cleanup_tmp = MagicMock()  # rm -f /tmp/mcp_key_...
    cleanup_tmp.exit_status = 0

    sudoers_setup = MagicMock()
    sudoers_setup.exit_status = 0

    test_conn = MagicMock()
    test_conn.exit_status = 0

    mock_conn.run.side_effect = [
        user_check,
        sudo_group,
        mktemp_result,
        key_check,
        mkdir_home,
        chown_home,
        mkdir_cmd,
        add_key,
        cleanup_tmp,
        sudoers_setup,
        test_conn,
    ]

    # Mock SFTP context manager
    mock_sftp = AsyncMock()
    mock_sftp.put = AsyncMock()
    mock_sftp_ctx = AsyncMock()
    mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

    # ssh_connect returns a connection usable as async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Execute
    from src.homelab_mcp.ssh_tools import setup_remote_mcp_admin  # noqa: PLC0415
    result = await setup_remote_mcp_admin("test-host", "admin", "password")

    # Parse result
    result_data = json.loads(result)

    # Verify success
    assert result_data["status"] == "success"
    assert result_data["mcp_admin_setup"]["user_creation"] == "User already exists"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_verify_mcp_admin_access_success(mock_connect, mock_key_path):
    """Test successful mcp_admin access verification."""
    # Mock SSH key exists
    mock_key_path.return_value.exists.return_value = True

    # Mock SSH connection and commands
    mock_conn = AsyncMock()

    # Mock command results
    whoami_result = MagicMock()
    whoami_result.exit_status = 0
    whoami_result.stdout = "mcp_admin"

    sudo_result = MagicMock()
    sudo_result.exit_status = 0

    hostname_result = MagicMock()
    hostname_result.exit_status = 0
    hostname_result.stdout = "test-server"

    groups_result = MagicMock()
    groups_result.exit_status = 0
    groups_result.stdout = "mcp_admin : mcp_admin sudo"

    mock_conn.run.side_effect = [
        whoami_result,
        sudo_result,
        hostname_result,
        groups_result,
    ]

    # ssh_connect returns a connection usable as async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Execute
    result = await verify_mcp_admin_access("test-host")

    # Parse result
    result_data = json.loads(result)

    # Verify success
    assert result_data["status"] == "success"
    assert result_data["hostname"] == "test-server"
    assert result_data["connection_ip"] == "test-host"
    assert result_data["mcp_admin"]["ssh_access"] == "Success: Connected with SSH key"
    assert result_data["mcp_admin"]["sudo_access"] == "Success: Passwordless sudo working"
    assert result_data["mcp_admin"]["username"] == "mcp_admin"
    assert result_data["mcp_admin"]["groups"] == ["mcp_admin", "sudo"]
    assert result_data["mcp_admin"]["service_groups"] == []


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
async def test_verify_mcp_admin_access_no_key(mock_key_path):
    """Test verification when SSH key doesn't exist."""
    # Mock SSH key doesn't exist
    mock_key_path.return_value.exists.return_value = False

    # Execute
    result = await verify_mcp_admin_access("test-host")

    # Parse result
    result_data = json.loads(result)

    # Verify error
    assert result_data["status"] == "error"
    assert "SSH key not found" in result_data["error"]


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_verify_mcp_admin_access_auth_failure(mock_connect, mock_key_path):
    """Test verification with authentication failure."""
    # Mock SSH key exists
    mock_key_path.return_value.exists.return_value = True

    # Mock connection failure
    mock_connect.side_effect = asyncssh.misc.PermissionDenied("Authentication failed")

    # Execute
    result = await verify_mcp_admin_access("test-host")

    # Parse result
    result_data = json.loads(result)

    # Verify error
    assert result_data["status"] == "error"
    assert "SSH key authentication failed" in result_data["error"]


# test_ssh_discover_with_mcp_admin_auto_key REMOVED in Phase 33 (D-08/D-17).
# This test exercised the Tier 4 "default mcp_admin key auto-fallback" path in
# resolve_ssh_credentials, which has been intentionally deleted. The replacement
# test is tests/test_ssh_credentials.py::TestResolveSSHCredentials::test_mcp_admin_no_fallback,
# which proves the fallback no longer fires.


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ensure_mcp_ssh_key")
@patch("src.homelab_mcp.ssh_tools.Path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_setup_remote_mcp_admin_force_update_key(mock_connect, mock_path, mock_ensure_key):
    """Test remote mcp_admin setup with force key update."""
    # Mock SSH key
    mock_ensure_key.return_value = "/home/user/.ssh/mcp_admin_rsa"

    # Mock public key path
    mock_pub_key = MagicMock()
    mock_pub_key.read_text.return_value = "ssh-rsa AAAAB3NEW... mcp_admin@host"
    mock_path.return_value = mock_pub_key

    # Mock SSH connection and commands
    mock_conn = AsyncMock()

    # Mock command results - for existing user with force update key (new SFTP-based sequence)
    user_check = MagicMock()
    user_check.exit_status = 0  # User exists

    sudo_group = MagicMock()
    sudo_group.exit_status = 0

    mktemp_result = MagicMock()
    mktemp_result.exit_status = 0
    mktemp_result.stdout = "/tmp/mcp_key_aBcXyZ.pub\n"

    key_check = MagicMock()
    key_check.exit_status = 0  # Key exists (but different)

    mkdir_home = MagicMock()  # sudo mkdir -p /home/mcp_admin
    mkdir_home.exit_status = 0

    chown_home = MagicMock()  # sudo chown mcp_admin:mcp_admin /home/mcp_admin
    chown_home.exit_status = 0

    mkdir_cmd = MagicMock()  # create .ssh directory
    mkdir_cmd.exit_status = 0

    remove_old = MagicMock()  # sed -i '/mcp_admin@/d' (Remove old key)
    remove_old.exit_status = 0

    add_key = MagicMock()
    add_key.exit_status = 0

    cleanup_tmp = MagicMock()  # rm -f /tmp/mcp_key_...
    cleanup_tmp.exit_status = 0

    sudoers_setup = MagicMock()
    sudoers_setup.exit_status = 0

    test_conn = MagicMock()
    test_conn.exit_status = 0

    mock_conn.run.side_effect = [
        user_check,
        sudo_group,
        mktemp_result,
        key_check,
        mkdir_home,
        chown_home,
        mkdir_cmd,
        remove_old,
        add_key,
        cleanup_tmp,
        sudoers_setup,
        test_conn,
    ]

    # Mock SFTP context manager
    mock_sftp = AsyncMock()
    mock_sftp.put = AsyncMock()
    mock_sftp_ctx = AsyncMock()
    mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

    # ssh_connect returns a connection usable as async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Execute with force_update_key=True (default)
    from src.homelab_mcp.ssh_tools import setup_remote_mcp_admin  # noqa: PLC0415
    result = await setup_remote_mcp_admin("test-host", "admin", "password")

    # Parse result
    result_data = json.loads(result)

    # Verify success
    assert result_data["status"] == "success"
    assert result_data["mcp_admin_setup"]["user_creation"] == "User already exists"
    assert result_data["mcp_admin_setup"]["ssh_key"] == "Success: SSH key updated"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ensure_mcp_ssh_key")
@patch("src.homelab_mcp.ssh_tools.Path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_setup_remote_mcp_admin_no_force_update(mock_connect, mock_path, mock_ensure_key):
    """Test remote mcp_admin setup without forcing key update."""
    # Mock SSH key
    mock_ensure_key.return_value = "/home/user/.ssh/mcp_admin_rsa"

    # Mock public key path
    mock_pub_key = MagicMock()
    mock_pub_key.read_text.return_value = "ssh-rsa AAAAB3... mcp_admin@host"
    mock_path.return_value = mock_pub_key

    # Mock SSH connection and commands
    mock_conn = AsyncMock()

    # Mock command results - key already exists, no force update (new SFTP-based sequence)
    user_check = MagicMock()
    user_check.exit_status = 0  # User exists

    sudo_group = MagicMock()
    sudo_group.exit_status = 0

    mktemp_result = MagicMock()
    mktemp_result.exit_status = 0
    mktemp_result.stdout = "/tmp/mcp_key_aBcXyZ.pub\n"

    key_check = MagicMock()
    key_check.exit_status = 0  # Key already exists

    cleanup_tmp = MagicMock()  # rm -f /tmp/mcp_key_...
    cleanup_tmp.exit_status = 0

    sudoers_setup = MagicMock()
    sudoers_setup.exit_status = 0

    test_conn = MagicMock()
    test_conn.exit_status = 0

    mock_conn.run.side_effect = [
        user_check,
        sudo_group,
        mktemp_result,
        key_check,
        cleanup_tmp,
        sudoers_setup,
        test_conn,
    ]

    # Mock SFTP context manager
    mock_sftp = AsyncMock()
    mock_sftp.put = AsyncMock()
    mock_sftp_ctx = AsyncMock()
    mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

    # ssh_connect returns a connection usable as async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Execute with force_update_key=False
    from src.homelab_mcp.ssh_tools import setup_remote_mcp_admin  # noqa: PLC0415
    result = await setup_remote_mcp_admin("test-host", "admin", "password", force_update_key=False)

    # Parse result
    result_data = json.loads(result)

    # Verify success
    assert result_data["status"] == "success"
    assert result_data["mcp_admin_setup"]["ssh_key"] == "SSH key already exists"


# --- Wave 0 RED tests: INJECT-01, INJECT-02, log safety ---


def test_resolve_ssh_credentials_keyring_inject(mocker):
    from homelab_mcp.ssh_tools import resolve_ssh_credentials

    mocker.patch(
        "homelab_mcp.ssh_tools.list_credentials",
        return_value=[{"hostname": "192.168.1.10", "username": "root", "credential_type": "ssh"}],
    )
    mocker.patch("homelab_mcp.ssh_tools.get_credential", return_value="secret")
    creds = resolve_ssh_credentials("192.168.1.10")
    assert creds.password == "secret"
    assert creds.username == "root"


def test_resolve_ssh_credentials_explicit_overrides_keyring(mocker):
    from homelab_mcp.ssh_tools import resolve_ssh_credentials

    mocker.patch(
        "homelab_mcp.ssh_tools.list_credentials",
        return_value=[{"hostname": "192.168.1.10", "username": "root", "credential_type": "ssh"}],
    )
    mocker.patch("homelab_mcp.ssh_tools.get_credential", return_value="keyring-secret")
    creds = resolve_ssh_credentials("192.168.1.10", username="admin", password="explicit")
    assert creds.password == "explicit"
    assert creds.username == "admin"


def test_no_password_in_log_after_ssh_keyring_inject(mocker, caplog):
    import logging

    from homelab_mcp.ssh_tools import resolve_ssh_credentials

    mocker.patch(
        "homelab_mcp.ssh_tools.list_credentials",
        return_value=[{"hostname": "192.168.1.10", "username": "root", "credential_type": "ssh"}],
    )
    mocker.patch("homelab_mcp.ssh_tools.get_credential", return_value="super-secret-pw")
    with caplog.at_level(logging.DEBUG):
        resolve_ssh_credentials("192.168.1.10")
    assert "super-secret-pw" not in caplog.text


# --- SEC-01: Injection-safe key delivery tests ---


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ensure_mcp_ssh_key")
@patch("src.homelab_mcp.ssh_tools.Path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_setup_mcp_admin_uses_grep_ff(mock_connect, mock_path, mock_ensure_key):
    """Key existence check must use grep -Ff with tmpfile path, not -F with key as argument."""
    public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAA mcp_admin@host"

    mock_ensure_key.return_value = "/home/user/.ssh/mcp_admin_rsa"

    mock_pub_key = MagicMock()
    mock_pub_key.read_text.return_value = public_key
    mock_path.return_value = mock_pub_key

    mock_conn = AsyncMock()

    id_result = MagicMock(exit_status=0, stdout="", stderr="")
    mktemp_result = MagicMock(exit_status=0, stdout="/tmp/mcp_key_xYz123.pub\n", stderr="")
    success_result = MagicMock(exit_status=0, stdout="", stderr="")

    call_count = 0
    run_calls: list[str] = []

    async def tracking_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        cmd = args[0] if args else kwargs.get("command", "")
        run_calls.append(str(cmd))
        # Dispatch by command content rather than call index — robust to ordering changes.
        if cmd.startswith("id "):
            return id_result
        if "mktemp" in cmd:
            return mktemp_result
        return success_result

    mock_conn.run = tracking_run

    mock_sftp = AsyncMock()
    mock_sftp.put = AsyncMock()
    mock_sftp_ctx = AsyncMock()
    mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    from src.homelab_mcp.ssh_tools import setup_remote_mcp_admin  # noqa: PLC0415
    try:
        result = await setup_remote_mcp_admin("10.0.0.1", "admin", "password")
        result_data = json.loads(result)
        assert result_data["status"] == "success"
    except Exception:
        pass

    # Find grep calls
    grep_calls = [cmd for cmd in run_calls if "grep" in cmd]
    assert grep_calls, f"Expected at least one grep call. Got calls: {run_calls}"

    grep_cmd = grep_calls[0]
    # Must use file-based grep (-Ff with tmpfile path)
    assert "-Ff" in grep_cmd, f"grep command must use -Ff (file-based): {grep_cmd!r}"
    assert "/tmp/mcp_key_" in grep_cmd, f"grep command must reference the tmpfile path: {grep_cmd!r}"
    # Must NOT use argument-based grep with key content as argument
    assert f'grep -F "{public_key}"' not in grep_cmd, (
        f"grep must not use quoted key argument (injection risk): {grep_cmd!r}"
    )


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ensure_mcp_ssh_key")
@patch("src.homelab_mcp.ssh_tools.Path")
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_setup_mcp_admin_tmpfile_cleanup_on_error(mock_connect, mock_path, mock_ensure_key):
    """Cleanup (rm -f remote tmpfile) runs even when the key append step fails."""
    public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAA mcp_admin@host"

    mock_ensure_key.return_value = "/home/user/.ssh/mcp_admin_rsa"

    mock_pub_key = MagicMock()
    mock_pub_key.read_text.return_value = public_key
    mock_path.return_value = mock_pub_key

    mock_conn = AsyncMock()

    remote_tmp = "/tmp/mcp_key_cLn48Q.pub"
    id_result = MagicMock(exit_status=0, stdout="", stderr="")
    mktemp_result = MagicMock(exit_status=0, stdout=f"{remote_tmp}\n", stderr="")
    # grep returns exit_status=1 so key does not exist → triggers append path
    grep_result = MagicMock(exit_status=1, stdout="", stderr="")
    success_result = MagicMock(exit_status=0, stdout="", stderr="")

    call_count = 0
    run_calls: list[str] = []

    async def tracking_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        cmd = args[0] if args else kwargs.get("command", "")
        run_calls.append(str(cmd))
        # Dispatch by command content rather than call index — robust to ordering changes.
        if cmd.startswith("id "):
            return id_result
        if "mktemp" in cmd:
            return mktemp_result
        if "grep" in cmd:
            return grep_result
        if "cat" in cmd and "authorized_keys" in cmd:
            # Simulate failure on the cat >> authorized_keys step
            raise asyncssh.Error("Simulated append failure")
        return success_result

    mock_conn.run = tracking_run

    mock_sftp = AsyncMock()
    mock_sftp.put = AsyncMock()
    mock_sftp_ctx = AsyncMock()
    mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    from src.homelab_mcp.ssh_tools import setup_remote_mcp_admin  # noqa: PLC0415
    try:
        await setup_remote_mcp_admin("10.0.0.1", "admin", "password", force_update_key=True)
    except Exception:
        pass  # Error expected — we care about cleanup assertions

    # Assert remote tmpfile cleanup ran (rm -f /tmp/mcp_key_...)
    rm_calls = [cmd for cmd in run_calls if "rm -f" in cmd and "mcp_key_" in cmd]
    assert rm_calls, f"Expected rm -f cleanup of remote tmpfile in conn.run calls. Got calls: {run_calls}"


# --- Regression guards (v1.5 / PR #39) ---


@pytest.mark.asyncio
async def test_ssh01_sudo_run_check_raises_in_password_branch():
    """SSH-01 regression: _sudo_run(password=..., check=True) forwards check= to conn.run.

    Before commit 9f752c0 the password branch dropped `check=`, so a non-zero exit from
    `sudo -S <command>` was silently ignored. This test proves the propagation path.

    Revert-proof: reverting commit 9f752c0 (restoring the branch that calls
    `conn.run(full_command)` without `check=check` in the password branch) causes
    conn.run to return a result object rather than raise — the test's
    `pytest.raises(asyncssh.ProcessError)` assertion fails.
    """
    mock_conn = AsyncMock()

    # Raise ProcessError from conn.run (simulates check=True catching non-zero exit).
    # asyncssh.ProcessError kwargs vary by version; use the minimal positional/kwarg
    # combination that instantiates cleanly on the asyncssh pinned in pyproject.toml.
    try:
        err: Exception = asyncssh.ProcessError(
            env=None,
            command="sudo -S ls",
            subsystem=None,
            exit_status=1,
            exit_signal=None,
            returncode=1,
            stdout="",
            stderr="permission denied",
        )
    except TypeError:
        # Fallback: if newer asyncssh changed the constructor, use RuntimeError so
        # the propagation path is still exercised. The exact exception class is not
        # what REG-01 guards — the propagation is. The executor MUST prefer the
        # asyncssh.ProcessError form; this fallback is a version-compat safety net.
        err = RuntimeError("simulated non-zero exit from sudo")

    mock_conn.run.side_effect = err

    with pytest.raises(type(err)):
        await _sudo_run(mock_conn, "ls", password="pw", check=True)

    # Prove check=True was forwarded to conn.run — guards the exact defect
    # in commit 9f752c0's parent (the password branch that dropped check=).
    mock_conn.run.assert_called_once()
    assert mock_conn.run.call_args.kwargs.get("check") is True, (
        f"check=True must be forwarded to conn.run; got kwargs={mock_conn.run.call_args.kwargs!r}"
    )


def test_ssh02_no_disjunctive_always_true_assertions() -> None:
    """SSH-02 meta-guard: no `assert X or <structurally-always-true>` in this file.

    Before commit d25c915 the assertion at test_ssh_discover_no_credentials (currently
    line ~191) read:
        assert "No credentials" in err or "other" in err
    which is equivalent to `True or True` for any non-empty `err` — the test always
    passed and never exercised the "No credentials" precondition it claimed to guard.

    This AST meta-test parses tests/test_ssh_tools.py (itself) and fails if any
    `ast.Assert(test=ast.BoolOp(op=ast.Or(), values=[_, <always_true>]))` pattern
    is present. "Structurally always true" is defined conservatively:
      - ast.Constant with a truthy value
      - nested ast.BoolOp(op=ast.Or) with an always-true branch
      - ast.Compare over two ast.Constant operands

    Revert-proof (captured in this plan's commit message, per CONTEXT.md D-05):
    temporarily mutate line ~191 to `assert "No credentials" in err or "other" in err`
    (where `"other"` is a non-empty string Constant — structurally always true),
    re-run this test, observe FAILED with offender line ~191. Do NOT commit the
    mutation — the commit message captures the diagnostic output.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    def _is_structurally_always_true(node: ast.expr) -> bool:
        """Conservative truthy-constant detector.

        Flags ONLY shapes provably true at parse time. Dynamic expressions
        (Name, Call, Attribute, Compare over non-constants) are NOT flagged,
        with ONE broadened exception for the `in` operator:

        A `Compare` node is treated as structurally always-true when:
        - `node.left` is an `ast.Constant` AND all comparators are `ast.Constant`
          (plain parse-time tautology like `"a" == "a"`), OR
        - `node.left` is an `ast.Constant` AND `node.ops[0]` is `ast.In`
          (a constant literal is `in` SOMETHING — tautological in a disjunctive
          `or` assert where the other branch is the real check).

        The `Constant in X` case is the exact shape of the d25c915 pre-fix defect
        and is special-cased because the comparator may be any expression
        (Subscript, Attribute, Name, Call) and still yield a tautology in context.
        See .planning/phases/32-regression-tests/32-CONTEXT.md decision D-10.
        """
        if isinstance(node, ast.Constant):
            # Non-empty string, non-zero number, True
            return bool(node.value)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return any(_is_structurally_always_true(v) for v in node.values)
        if isinstance(node, ast.Compare):
            # (a) Constant <op> Constant is evaluable at parse time (e.g., `"a" == "a"`).
            if isinstance(node.left, ast.Constant) and all(isinstance(c, ast.Constant) for c in node.comparators):
                return True
            # (b) `<Constant literal> in <anything>` — in the context of a disjunctive
            # `or` assert where the other branch is the real check, a constant string
            # literal being `in` some container is a tautology. This is the exact
            # shape of the d25c915 pre-fix defect:
            #     assert "No credentials" in err or "other" in err["error"]
            # where the RHS is Compare(left=Constant("other"), ops=[In()], comparators=[Subscript(...)])
            # and is always-true whenever `err["error"]` is a non-empty string.
            # See CONTEXT.md decision D-10 for the full rationale.
            if isinstance(node.left, ast.Constant) and node.ops and isinstance(node.ops[0], ast.In):
                return True
        return False

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.BoolOp):
            if isinstance(node.test.op, ast.Or):
                # Flag if any operand beyond the first is structurally always true.
                for operand in node.test.values[1:]:
                    if _is_structurally_always_true(operand):
                        offenders.append(f"line {node.lineno}: {ast.unparse(node)}")
                        break

    assert not offenders, (
        "Found `assert X or <always-true>` anti-pattern(s) in test_ssh_tools.py.\n"
        "Replace with explicit single-check asserts (see SSH-02 fix in commit d25c915):\n" + "\n".join(offenders)
    )


def test_setup_remote_mcp_admin_absent() -> None:
    """D-11: setup_remote_mcp_admin function must be removed from ssh_tools."""
    from src.homelab_mcp import ssh_tools
    assert not hasattr(ssh_tools, "setup_remote_mcp_admin"), (
        "setup_remote_mcp_admin must be deleted from ssh_tools.py (D-11)"
    )
