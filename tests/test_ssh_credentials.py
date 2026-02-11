"""Tests for SSH credentials storage and resolution functionality."""

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.homelab_mcp.database import SQLiteAdapter
from src.homelab_mcp.ssh_tools import (
    SSHCredentials,
    list_registered_servers,
    register_server,
    remove_server,
    resolve_ssh_credentials,
    update_server_credentials,
)


class TestSSHCredentialsDatabase:
    """Test SSH credentials database operations."""

    @pytest.fixture
    def adapter(self):
        """Create a SQLite adapter with in-memory database."""
        adapter = SQLiteAdapter(":memory:")
        adapter.init_schema()
        return adapter

    def test_ssh_credentials_table_created(self, adapter):
        """Test that ssh_credentials table is created during init_schema."""
        cursor = adapter.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ssh_credentials'")
        assert cursor.fetchone() is not None

    def test_add_credential(self, adapter):
        """Test adding a new credential."""
        cred_id = adapter.add_credential(
            hostname="192.168.1.100",
            username="mcp_admin",
            key_path="/home/user/.ssh/id_rsa",
            port=22,
            display_name="Test Server",
        )

        assert isinstance(cred_id, int)
        assert cred_id > 0

    def test_get_credential_by_id(self, adapter):
        """Test retrieving credential by ID."""
        cred_id = adapter.add_credential(
            hostname="192.168.1.100",
            username="mcp_admin",
            port=22,
        )

        cred = adapter.get_credential(cred_id)
        assert cred is not None
        assert cred["hostname"] == "192.168.1.100"
        assert cred["username"] == "mcp_admin"
        assert cred["port"] == 22

    def test_get_credential_not_found(self, adapter):
        """Test retrieving non-existent credential."""
        cred = adapter.get_credential(999)
        assert cred is None

    def test_get_credential_by_hostname(self, adapter):
        """Test retrieving credential by hostname."""
        adapter.add_credential(
            hostname="192.168.1.100",
            username="mcp_admin",
            port=22,
        )

        cred = adapter.get_credential_by_hostname("192.168.1.100")
        assert cred is not None
        assert cred["hostname"] == "192.168.1.100"

    def test_get_credential_by_hostname_and_username(self, adapter):
        """Test retrieving credential by hostname and specific username."""
        adapter.add_credential(
            hostname="192.168.1.100",
            username="admin1",
            port=22,
        )
        adapter.add_credential(
            hostname="192.168.1.100",
            username="admin2",
            port=22,
        )

        cred = adapter.get_credential_by_hostname("192.168.1.100", "admin2")
        assert cred is not None
        assert cred["username"] == "admin2"

    def test_update_credential(self, adapter):
        """Test updating a credential."""
        cred_id = adapter.add_credential(
            hostname="192.168.1.100",
            username="mcp_admin",
            port=22,
            display_name="Old Name",
        )

        success = adapter.update_credential(
            cred_id,
            display_name="New Name",
            port=2222,
        )
        assert success is True

        cred = adapter.get_credential(cred_id)
        assert cred["display_name"] == "New Name"
        assert cred["port"] == 2222

    def test_update_credential_no_fields(self, adapter):
        """Test updating with no valid fields returns False."""
        cred_id = adapter.add_credential(
            hostname="192.168.1.100",
            username="mcp_admin",
        )

        success = adapter.update_credential(cred_id, invalid_field="value")
        assert success is False

    def test_delete_credential(self, adapter):
        """Test deleting a credential."""
        cred_id = adapter.add_credential(
            hostname="192.168.1.100",
            username="mcp_admin",
        )

        success = adapter.delete_credential(cred_id)
        assert success is True

        cred = adapter.get_credential(cred_id)
        assert cred is None

    def test_delete_nonexistent_credential(self, adapter):
        """Test deleting non-existent credential returns False."""
        success = adapter.delete_credential(999)
        assert success is False

    def test_list_credentials(self, adapter):
        """Test listing all credentials."""
        adapter.add_credential(hostname="192.168.1.100", username="admin1")
        adapter.add_credential(hostname="192.168.1.101", username="admin2")

        credentials = adapter.list_credentials()
        assert len(credentials) == 2

    def test_list_credentials_active_only(self, adapter):
        """Test listing only active credentials."""
        cred1_id = adapter.add_credential(hostname="192.168.1.100", username="admin1")
        adapter.add_credential(hostname="192.168.1.101", username="admin2")

        # Deactivate first credential
        adapter.update_credential(cred1_id, is_active=False)

        active_creds = adapter.list_credentials(active_only=True)
        assert len(active_creds) == 1
        assert active_creds[0]["hostname"] == "192.168.1.101"

        all_creds = adapter.list_credentials(active_only=False)
        assert len(all_creds) == 2

    def test_update_last_verified(self, adapter):
        """Test updating last_verified timestamp."""
        cred_id = adapter.add_credential(
            hostname="192.168.1.100",
            username="mcp_admin",
        )

        success = adapter.update_last_verified(cred_id)
        assert success is True

        cred = adapter.get_credential(cred_id)
        assert cred["last_verified"] is not None

    def test_unique_constraint_hostname_username(self, adapter):
        """Test that hostname+username combination must be unique."""
        adapter.add_credential(hostname="192.168.1.100", username="admin")

        with pytest.raises(sqlite3.IntegrityError):
            adapter.add_credential(hostname="192.168.1.100", username="admin")


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

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_stored_credentials_used(self, mock_get_db):
        """Test that stored credentials are used when no explicit ones provided."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential_by_hostname.return_value = {
            "id": 1,
            "hostname": "192.168.1.100",
            "username": "stored_user",
            "key_path": "/stored/key",
            "port": 2222,
        }
        mock_get_db.return_value = mock_adapter

        creds = resolve_ssh_credentials(
            hostname="192.168.1.100",
        )

        assert creds.hostname == "192.168.1.100"
        assert creds.username == "stored_user"
        assert creds.key_path == "/stored/key"
        assert creds.port == 2222
        assert creds.credential_id == 1

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    @patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
    def test_mcp_admin_uses_default_key(self, mock_key_path, mock_get_db):
        """Test that mcp_admin username uses default MCP key if available."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential_by_hostname.return_value = None
        mock_get_db.return_value = mock_adapter

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_key_path.return_value = mock_path

        creds = resolve_ssh_credentials(
            hostname="192.168.1.100",
            username="mcp_admin",
        )

        assert creds.username == "mcp_admin"
        assert creds.key_path is not None


class TestRegisterServer:
    """Test server registration functionality."""

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    async def test_register_server_success(self, mock_get_db):
        """Test successful server registration."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential_by_hostname.return_value = None
        mock_adapter.add_credential.return_value = 1
        mock_get_db.return_value = mock_adapter

        result = await register_server(
            hostname="192.168.1.100",
            username="mcp_admin",
            verify_connection=False,
        )

        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["credential_id"] == 1
        assert result_dict["hostname"] == "192.168.1.100"

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    async def test_register_server_already_exists(self, mock_get_db):
        """Test registration when server already exists."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential_by_hostname.return_value = {
            "id": 1,
            "hostname": "192.168.1.100",
        }
        mock_get_db.return_value = mock_adapter

        result = await register_server(
            hostname="192.168.1.100",
            username="mcp_admin",
        )

        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "already registered" in result_dict["error"]


class TestListRegisteredServers:
    """Test listing registered servers."""

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_list_servers(self, mock_get_db):
        """Test listing registered servers."""
        mock_adapter = MagicMock()
        mock_adapter.list_credentials.return_value = [
            {
                "id": 1,
                "hostname": "192.168.1.100",
                "username": "admin",
                "port": 22,
                "display_name": "Server 1",
                "is_active": 1,
                "last_verified": "2024-01-01T00:00:00",
                "key_path": "/path/to/key",
                "device_id": None,
            },
            {
                "id": 2,
                "hostname": "192.168.1.101",
                "username": "admin",
                "port": 22,
                "display_name": None,
                "is_active": 1,
                "last_verified": None,
                "key_path": None,
                "device_id": 5,
            },
        ]
        mock_get_db.return_value = mock_adapter

        result = list_registered_servers()
        result_dict = json.loads(result)

        assert result_dict["status"] == "success"
        assert result_dict["total_servers"] == 2
        assert len(result_dict["servers"]) == 2

        server1 = result_dict["servers"][0]
        assert server1["hostname"] == "192.168.1.100"
        assert server1["has_key"] is True

        server2 = result_dict["servers"][1]
        assert server2["has_key"] is False


class TestUpdateServerCredentials:
    """Test updating server credentials."""

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_update_by_id(self, mock_get_db):
        """Test updating credentials by ID."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential.return_value = {
            "id": 1,
            "hostname": "192.168.1.100",
        }
        mock_adapter.update_credential.return_value = True
        mock_get_db.return_value = mock_adapter

        result = update_server_credentials(
            credential_id=1,
            display_name="New Name",
        )

        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        mock_adapter.update_credential.assert_called_once()

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_update_by_hostname(self, mock_get_db):
        """Test updating credentials by hostname."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential_by_hostname.return_value = {
            "id": 1,
            "hostname": "192.168.1.100",
        }
        mock_adapter.update_credential.return_value = True
        mock_get_db.return_value = mock_adapter

        result = update_server_credentials(
            hostname="192.168.1.100",
            port=2222,
        )

        result_dict = json.loads(result)
        assert result_dict["status"] == "success"

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_update_not_found(self, mock_get_db):
        """Test updating non-existent credential."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential.return_value = None
        mock_get_db.return_value = mock_adapter

        result = update_server_credentials(credential_id=999)

        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "not found" in result_dict["error"]

    def test_update_no_identifier(self):
        """Test updating without ID or hostname."""
        result = update_server_credentials()

        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "Must provide either" in result_dict["error"]


class TestRemoveServer:
    """Test removing registered servers."""

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_remove_by_id(self, mock_get_db):
        """Test removing server by ID."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential.return_value = {
            "id": 1,
            "hostname": "192.168.1.100",
            "username": "admin",
        }
        mock_adapter.delete_credential.return_value = True
        mock_get_db.return_value = mock_adapter

        result = remove_server(credential_id=1)

        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["hostname"] == "192.168.1.100"
        mock_adapter.delete_credential.assert_called_once_with(1)

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_remove_by_hostname(self, mock_get_db):
        """Test removing server by hostname."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential_by_hostname.return_value = {
            "id": 1,
            "hostname": "192.168.1.100",
            "username": "admin",
        }
        mock_adapter.delete_credential.return_value = True
        mock_get_db.return_value = mock_adapter

        result = remove_server(hostname="192.168.1.100")

        result_dict = json.loads(result)
        assert result_dict["status"] == "success"

    @patch("src.homelab_mcp.ssh_tools.get_database_adapter")
    def test_remove_not_found(self, mock_get_db):
        """Test removing non-existent server."""
        mock_adapter = MagicMock()
        mock_adapter.get_credential.return_value = None
        mock_get_db.return_value = mock_adapter

        result = remove_server(credential_id=999)

        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "not found" in result_dict["error"]

    def test_remove_no_identifier(self):
        """Test removing without ID or hostname."""
        result = remove_server()

        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "Must provide either" in result_dict["error"]
