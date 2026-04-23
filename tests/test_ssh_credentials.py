"""Tests for SSH credentials resolution functionality.

Phase 33 rewrite:
- TestSSHCredentialsDatabase DELETED (D-02: no DB credential methods)
- TestUpdateServerCredentials DELETED (D-20: removed MCP tool)
- TestRemoveServer DELETED (D-21: removed MCP tool)
- TestRegisterServer REWRITTEN for verify-only keyring shape (D-03/D-04/D-05/D-07/D-23)
- TestListRegisteredServers REWRITTEN to mock credential_store.list_credentials (D-19)
- New: D-16 positive keyring tests, D-17 negative mcp_admin fallback test
"""

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from src.homelab_mcp.ssh_tools import (
    CredentialNotFoundError,
    SSHCredentials,
    list_registered_servers,
    register_server,
    resolve_ssh_credentials,
)


class TestResolveSSHCredentials:
    """Test SSH credential resolution."""

    def test_explicit_password_takes_priority(self):
        """Test that explicit password overrides stored credentials."""
        creds = resolve_ssh_credentials(
            hostname="192.168.1.100",
            username="admin",
            password="explicit_pass",
        )

        assert isinstance(creds, SSHCredentials)
        assert creds.hostname == "192.168.1.100"
        assert creds.username == "admin"
        assert creds.password == "explicit_pass"
        assert creds.credential_id is None

    def test_explicit_key_path_takes_priority(self):
        """Test that explicit key_path overrides stored credentials."""
        creds = resolve_ssh_credentials(
            hostname="192.168.1.100",
            username="admin",
            key_path="/path/to/key",
        )

        assert creds.key_path == "/path/to/key"
        assert creds.credential_id is None

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    @patch("src.homelab_mcp.ssh_tools.get_credential")
    def test_resolve_keyring_password_auth(self, mock_get_cred, mock_list_creds):
        """D-16: resolve_ssh_credentials returns keyring-backed password credential."""
        mock_list_creds.return_value = [
            {"hostname": "192.168.1.100", "username": "admin", "credential_type": "ssh", "auth_type": "password"}
        ]
        mock_get_cred.return_value = "secret_password"

        creds = resolve_ssh_credentials(hostname="192.168.1.100", username="admin")

        assert isinstance(creds, SSHCredentials)
        assert creds.password == "secret_password"
        assert creds.key_path is None
        assert creds.username == "admin"

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    @patch("src.homelab_mcp.ssh_tools.get_credential")
    def test_resolve_keyring_key_path_auth(self, mock_get_cred, mock_list_creds):
        """D-16/D-09: resolve_ssh_credentials returns key-path credential when auth_type='key'."""
        mock_list_creds.return_value = [
            {"hostname": "192.168.1.100", "username": "admin", "credential_type": "ssh", "auth_type": "key"}
        ]
        mock_get_cred.return_value = "/home/user/.ssh/my_key"

        creds = resolve_ssh_credentials(hostname="192.168.1.100", username="admin")

        assert creds.key_path == "/home/user/.ssh/my_key"
        assert creds.password is None

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_mcp_admin_no_fallback(self, mock_list_creds):
        """D-17: resolve_ssh_credentials raises CredentialNotFoundError for mcp_admin with empty keyring."""
        mock_list_creds.return_value = []
        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_ssh_credentials(hostname="any-host", username="mcp_admin")
        assert "credentials add" in str(exc_info.value)

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_credential_not_found_message(self, mock_list_creds):
        """D-05: CredentialNotFoundError names homelab-mcp credentials add <host> <user>."""
        mock_list_creds.return_value = []
        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_ssh_credentials(hostname="unknown-host", username="some-user")
        msg = str(exc_info.value)
        assert "homelab-mcp credentials add" in msg
        assert "unknown-host" in msg or "<hostname>" in msg

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    @patch("src.homelab_mcp.ssh_tools.get_credential")
    def test_no_raise_when_keyring_has_matching_entry(self, mock_get_cred, mock_list_creds):
        """When keyring has a matching entry with password, returns SSHCredentials."""
        mock_list_creds.return_value = [{"hostname": "host", "username": "alice", "credential_type": "ssh"}]
        mock_get_cred.return_value = "s3cr3t"

        creds = resolve_ssh_credentials("host")
        assert isinstance(creds, SSHCredentials)
        assert creds.password == "s3cr3t"
        assert creds.username == "alice"

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    @patch("src.homelab_mcp.ssh_tools.get_credential")
    def test_desync_warning_logged(self, mock_get_cred, mock_list_creds, caplog):
        """When registry has entry but keyring returns None, a WARNING containing 'desync' is logged."""
        mock_list_creds.return_value = [{"hostname": "desync-host", "username": "alice", "credential_type": "ssh"}]
        mock_get_cred.return_value = None

        with caplog.at_level(logging.WARNING, logger="homelab_mcp.ssh_tools"):
            with pytest.raises(CredentialNotFoundError):
                resolve_ssh_credentials("desync-host")

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING and "desync" in r.message.lower()]
        assert len(warning_records) >= 1, "Expected a WARNING log containing 'desync'"
        assert "desync-host" in warning_records[0].message
        assert "alice" in warning_records[0].message

    # ------------------------------------------------------------------
    # Phase 33.1 Plan 01 — D-04 / D-04a / D-11
    # Registry-scan-by-hostname when username is None, in BOTH tiers.
    # ------------------------------------------------------------------

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    @patch("src.homelab_mcp.ssh_tools.get_credential")
    def test_resolve_with_no_username_single_match(self, mock_get_cred, mock_list_creds):
        """D-04 Tier-2: username=None + single registry match → resolves from registry."""
        mock_list_creds.return_value = [
            {
                "hostname": "h.example.com",
                "username": "alice",
                "credential_type": "ssh",
                "auth_type": "password",
            }
        ]
        mock_get_cred.return_value = "secret"

        creds = resolve_ssh_credentials(hostname="h.example.com", username=None)

        assert isinstance(creds, SSHCredentials)
        assert creds.username == "alice"
        assert creds.password == "secret"
        assert creds.hostname == "h.example.com"

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_resolve_with_no_username_ambiguous_match(self, mock_list_creds):
        """D-04/D-11 Tier-2: username=None + multi registry match → error names users + list tool."""
        mock_list_creds.return_value = [
            {
                "hostname": "h.example.com",
                "username": "alice",
                "credential_type": "ssh",
                "auth_type": "password",
            },
            {
                "hostname": "h.example.com",
                "username": "bob",
                "credential_type": "ssh",
                "auth_type": "password",
            },
        ]

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_ssh_credentials(hostname="h.example.com", username=None)

        msg = str(exc_info.value)
        assert "alice" in msg
        assert "bob" in msg
        # D-04a: must point the agent at a discovery tool so it can self-disambiguate.
        assert ("list_keyring_credentials" in msg) or ("list_registered_servers" in msg)

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_resolve_with_no_username_zero_match(self, mock_list_creds):
        """D-04 Tier-2: username=None + zero registry match → CredentialNotFoundError."""
        mock_list_creds.return_value = []

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_ssh_credentials(hostname="h.example.com", username=None)

        msg = str(exc_info.value)
        assert "homelab-mcp credentials add" in msg
        assert "h.example.com" in msg

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_resolve_tier1_no_username_single_match_injects_username(self, mock_list_creds):
        """D-04 Tier-1: username=None + explicit password → registry username injected, explicit password honored."""
        mock_list_creds.return_value = [
            {
                "hostname": "h.example.com",
                "username": "alice",
                "credential_type": "ssh",
                "auth_type": "password",
            }
        ]

        creds = resolve_ssh_credentials(
            hostname="h.example.com", username=None, password="explicit-pw"
        )

        assert isinstance(creds, SSHCredentials)
        # username comes from the registry (the only registered user for this host)
        assert creds.username == "alice"
        # explicit password wins over any keyring-looked-up value
        assert creds.password == "explicit-pw"
        # no accidental key-path leakage
        assert creds.key_path is None

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_resolve_tier1_no_username_ambiguous_match_raises(self, mock_list_creds):
        """D-04 Tier-1: username=None + explicit password + multi registry → ambiguous error."""
        mock_list_creds.return_value = [
            {
                "hostname": "h.example.com",
                "username": "alice",
                "credential_type": "ssh",
                "auth_type": "password",
            },
            {
                "hostname": "h.example.com",
                "username": "bob",
                "credential_type": "ssh",
                "auth_type": "password",
            },
        ]

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_ssh_credentials(
                hostname="h.example.com", username=None, password="p"
            )

        msg = str(exc_info.value)
        assert "alice" in msg
        assert "bob" in msg
        assert ("list_keyring_credentials" in msg) or ("list_registered_servers" in msg)

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_resolve_tier1_no_username_zero_match_raises(self, mock_list_creds):
        """BLOCKER 1: Tier-1 branch with username=None + zero registry match MUST raise.

        Previously line 63 silently substituted 'mcp_admin' — this test proves the
        fallback is removed. The call now scans the registry and raises when empty.
        """
        mock_list_creds.return_value = []

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_ssh_credentials(
                hostname="h.example.com", username=None, password="p"
            )

        msg = str(exc_info.value)
        assert "homelab-mcp credentials add" in msg
        assert "h.example.com" in msg
        # Regression guard: the removed fallback username MUST NOT appear anywhere
        # in a successful credential — if this test ever starts passing with an
        # SSHCredentials return, the silent fallback was reintroduced.


class TestCredentialNotFoundError:
    """Test that CredentialNotFoundError is raised when all credential tiers miss."""

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_raises_when_no_credentials_exist(self, mock_list_creds):
        """When no keyring entry exists, raises CredentialNotFoundError with CLI pointer."""
        mock_list_creds.return_value = []

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_ssh_credentials("unknown-host")

        error_msg = str(exc_info.value)
        assert "credentials add" in error_msg


class TestRegisterServer:
    """Test register_server verify-only behavior (D-03/D-04/D-05/D-07/D-23)."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.ssh_tools.resolve_ssh_credentials")
    @patch("src.homelab_mcp.ssh_tools.asyncssh.connect")
    async def test_register_verify_success(self, mock_ssh_connect, mock_resolve):
        """register_server returns verified=true when keyring resolves and SSH connects."""
        mock_resolve.return_value = SSHCredentials(
            hostname="192.168.1.100", username="admin", port=22, password="pw"
        )
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = AsyncMock()
        mock_ctx.__aexit__.return_value = None
        mock_ssh_connect.return_value = mock_ctx

        result = await register_server(hostname="192.168.1.100", username="admin")
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["verified"] is True
        assert result_dict["hostname"] == "192.168.1.100"
        assert result_dict["username"] == "admin"

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.ssh_tools.resolve_ssh_credentials")
    async def test_register_missing_keyring_error(self, mock_resolve):
        """register_server returns actionable error when keyring has no entry (D-05)."""
        mock_resolve.side_effect = CredentialNotFoundError(
            "No credentials found for 192.168.1.100. "
            "Run `homelab-mcp credentials add 192.168.1.100 admin`"
        )
        result = await register_server(hostname="192.168.1.100", username="admin")
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert result_dict["verified"] is False
        assert "credentials add" in result_dict["error"]

    def test_register_server_schema_no_write_params(self):
        """D-03: register_server signature accepts no password or key_path."""
        import inspect
        sig = inspect.signature(register_server)
        assert "password" not in sig.parameters
        assert "key_path" not in sig.parameters

    def test_register_no_verify_connection_flag(self):
        """D-07: register_server has no verify_connection parameter."""
        import inspect
        sig = inspect.signature(register_server)
        assert "verify_connection" not in sig.parameters

    def test_register_username_required(self):
        """D-23: register_server username parameter is required (no default)."""
        import inspect
        sig = inspect.signature(register_server)
        username_param = sig.parameters.get("username")
        assert username_param is not None
        assert username_param.default is inspect.Parameter.empty, (
            "username must be required parameter (D-23) — no default like 'mcp_admin'"
        )

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    @patch("src.homelab_mcp.ssh_tools.resolve_ssh_credentials")
    @patch("src.homelab_mcp.ssh_tools.asyncssh.connect")
    async def test_register_does_not_write_db(self, mock_ssh_connect, mock_resolve, mock_db_adapter):
        """D-03/D-04: register_server must NOT touch the database."""
        mock_resolve.return_value = SSHCredentials(
            hostname="192.168.1.100", username="admin", port=22, password="pw"
        )
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = AsyncMock()
        mock_ctx.__aexit__.return_value = None
        mock_ssh_connect.return_value = mock_ctx

        await register_server(hostname="192.168.1.100", username="admin")
        mock_db_adapter.assert_not_called()


class TestListRegisteredServers:
    """Test list_registered_servers reads keyring registry (D-19)."""

    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_list_returns_keyring_entries(self, mock_list_creds):
        """list_registered_servers reads from credential_store.list_credentials, not DB."""
        mock_list_creds.return_value = [
            {"hostname": "host1.local", "username": "admin", "credential_type": "ssh"},
            {"hostname": "host2.local", "username": "root", "credential_type": "ssh"},
        ]
        result = list_registered_servers()
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["count"] == 2
        hostnames = [s["hostname"] for s in data["servers"]]
        assert "host1.local" in hostnames
        assert "host2.local" in hostnames

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    @patch("src.homelab_mcp.ssh_tools.list_credentials")
    def test_list_does_not_read_db(self, mock_list_creds, mock_db_adapter):
        """D-19: list_registered_servers must not touch the database."""
        mock_list_creds.return_value = []
        list_registered_servers()
        mock_db_adapter.assert_not_called()
