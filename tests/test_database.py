"""Tests for database abstraction layer."""

import json
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.homelab_mcp.config import DatabaseConfig
from src.homelab_mcp.database import (
    POSTGRESQL_AVAILABLE,
    PostgreSQLAdapter,
    SQLiteAdapter,
    calculate_data_hash,
    get_database_adapter,
)


class TestSQLiteAdapter:
    """Test SQLite database adapter."""

    @pytest.fixture
    def temp_db(self):
        """Create an in-memory database."""
        yield ":memory:"

    @pytest.fixture
    def adapter(self, temp_db):
        """Create a SQLite adapter instance."""
        adapter = SQLiteAdapter(temp_db)
        adapter.init_schema()
        return adapter

    def test_init_schema(self, temp_db):
        """Test schema initialization."""
        adapter = SQLiteAdapter(temp_db)
        adapter.init_schema()

        # Test that tables exist (connection already established by init_schema)
        cursor = adapter.connection.cursor()

        # Check devices table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        assert cursor.fetchone() is not None

        # Check discovery_history table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='discovery_history'")
        assert cursor.fetchone() is not None

        adapter.close()

    def test_store_and_retrieve_device(self, adapter):
        """Test storing and retrieving devices."""
        device_data = {
            "hostname": "test-server",
            "connection_ip": "192.168.1.10",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "cpu_model": "Intel Core i7",
            "cpu_cores": 8,
            "memory_total": "16G",
            "os_info": "Ubuntu 22.04",
            "network_interfaces": json.dumps([{"name": "eth0", "addresses": ["192.168.1.10"]}]),
        }

        # Store device
        device_id = adapter.store_device(device_data)
        assert isinstance(device_id, int)
        assert device_id > 0

        # Retrieve devices
        devices = adapter.get_all_devices()
        assert len(devices) == 1

        device = devices[0]
        assert device["hostname"] == "test-server"
        assert device["connection_ip"] == "192.168.1.10"
        assert device["status"] == "success"
        assert device["cpu_cores"] == 8
        assert isinstance(device["network_interfaces"], list)

    def test_store_device_update(self, adapter):
        """Test updating existing device."""
        device_data = {
            "hostname": "test-server",
            "connection_ip": "192.168.1.10",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "cpu_cores": 4,
        }

        # Store initial device
        device_id1 = adapter.store_device(device_data)

        # Update device
        device_data["cpu_cores"] = 8
        device_data["last_seen"] = datetime.now().isoformat()
        device_id2 = adapter.store_device(device_data)

        # Should be same device ID
        assert device_id1 == device_id2

        # Verify only one device exists with updated data
        devices = adapter.get_all_devices()
        assert len(devices) == 1
        assert devices[0]["cpu_cores"] == 8

    def test_discovery_history(self, adapter):
        """Test discovery history functionality."""
        # Store a device first
        device_data = {
            "hostname": "test-server",
            "connection_ip": "192.168.1.10",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
        }
        device_id = adapter.store_device(device_data)

        # Store discovery history
        discovery_data = json.dumps({"test": "data"})
        data_hash = calculate_data_hash(discovery_data)
        adapter.store_discovery_history(device_id, discovery_data, data_hash)

        # Retrieve history
        changes = adapter.get_device_changes(device_id)
        assert len(changes) == 1
        assert changes[0]["data"]["test"] == "data"

        # Store same data again - should not create duplicate
        adapter.store_discovery_history(device_id, discovery_data, data_hash)
        changes = adapter.get_device_changes(device_id)
        assert len(changes) == 1

    def test_store_and_retrieve_fingerprint_phase38_sqlite(self, adapter):
        """Phase 38 D-09: SQLite store_device round-trips fingerprint as JSON-string + flatten-on-read."""
        fp_dict = {
            "kernel_name": "Linux",
            "kernel_version": "6.5.13-1-pve",
            "os_name": "Proxmox VE 8.2.4",
            "os_version": "8.2.4",
            "package_fingerprint": "sha256:abc123",
            "capabilities": {"vulkan": {"available": True, "loader_version": "1.3.275"}},
        }
        device_data = {
            "hostname": "test-pve",
            "connection_ip": "10.0.0.5",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "fingerprint": json.dumps(fp_dict),
        }
        adapter.store_device(device_data)
        devices = adapter.get_all_devices()
        assert len(devices) == 1
        fp_back = devices[0]["fingerprint"]
        assert isinstance(fp_back, dict), f"fingerprint should be decoded to dict, got {type(fp_back)}"
        assert fp_back["kernel_name"] == "Linux"
        assert fp_back["kernel_version"] == "6.5.13-1-pve"
        assert fp_back["capabilities"]["vulkan"]["available"] is True

    def test_store_device_update_branch_writes_fingerprint_phase38_sqlite(self, adapter):
        """Phase 38 D-09: UPDATE branch (re-storing same hostname) writes fingerprint."""
        base = {
            "hostname": "test-host",
            "connection_ip": "10.0.0.6",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
        }
        # First store: no fingerprint
        adapter.store_device(dict(base))
        # Second store: same hostname (UPDATE branch) with fingerprint
        fp_dict = {"kernel_name": "Linux", "kernel_version": "6.0.0"}
        adapter.store_device({**base, "fingerprint": json.dumps(fp_dict)})
        devices = adapter.get_all_devices()
        assert len(devices) == 1
        assert devices[0]["fingerprint"]["kernel_version"] == "6.0.0"

    def test_update_device_fingerprint_deep_merge_capabilities_phase38_sqlite(self, adapter):
        """Phase 38 D-05: capabilities sub-dict deep-merges (existing keys preserved)."""
        base = {
            "hostname": "merge-host",
            "connection_ip": "10.0.0.10",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "fingerprint": json.dumps(
                {
                    "kernel_version": "6.0.0",
                    "capabilities": {"vulkan": {"available": True, "loader_version": "1.3.275"}},
                }
            ),
        }
        adapter.store_device(base)
        merged = adapter.update_device_fingerprint(
            "merge-host",
            {"capabilities": {"cuda": {"driver_version": "535.183.06"}}},
        )
        assert "vulkan" in merged["capabilities"], "Original capability should survive deep-merge"
        assert merged["capabilities"]["vulkan"]["available"] is True
        assert "cuda" in merged["capabilities"]
        assert merged["capabilities"]["cuda"]["driver_version"] == "535.183.06"
        # And the persisted state matches.
        devices = adapter.get_all_devices()
        target = next(d for d in devices if d["hostname"] == "merge-host")
        assert "vulkan" in target["fingerprint"]["capabilities"]
        assert "cuda" in target["fingerprint"]["capabilities"]

    def test_update_device_fingerprint_overwrites_top_level_phase38_sqlite(self, adapter):
        """Phase 38 D-05: top-level keys (kernel/os/package) overwrite, capabilities preserved."""
        base = {
            "hostname": "overwrite-host",
            "connection_ip": "10.0.0.11",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "fingerprint": json.dumps(
                {
                    "kernel_version": "6.0.0",
                    "capabilities": {"vulkan": {"available": True}},
                }
            ),
        }
        adapter.store_device(base)
        merged = adapter.update_device_fingerprint(
            "overwrite-host",
            {"kernel_version": "6.5.13-1-pve"},
        )
        assert merged["kernel_version"] == "6.5.13-1-pve"
        assert merged["capabilities"]["vulkan"]["available"] is True

    def test_update_device_fingerprint_missing_hostname_raises_phase38_sqlite(self, adapter):
        """Phase 38 D-05: missing hostname raises ValueError with discover_and_map hint."""
        with pytest.raises(ValueError, match="discover_and_map"):
            adapter.update_device_fingerprint("nonexistent.local", {"kernel_name": "Linux"})


@pytest.mark.skipif(not POSTGRESQL_AVAILABLE, reason="psycopg2 not available")
class TestPostgreSQLAdapter:
    """Test PostgreSQL database adapter."""

    @pytest.fixture
    def mock_connection(self):
        """Mock PostgreSQL connection."""
        with patch("src.homelab_mcp.database.psycopg2") as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.extras.RealDictCursor = MagicMock

            yield mock_conn, mock_cursor

    def test_init_schema(self, mock_connection):
        """Test PostgreSQL schema initialization."""
        mock_conn, mock_cursor = mock_connection

        adapter = PostgreSQLAdapter(
            {
                "host": "localhost",
                "database": "test_db",
                "user": "test_user",
                "password": "test_pass",
            }
        )
        adapter.connection = mock_conn
        adapter.init_schema()

        # Verify that schema creation queries were executed
        assert mock_cursor.execute.call_count >= 4  # Should create tables and indexes
        mock_conn.commit.assert_called()

    def test_store_device_jsonb(self, mock_connection):
        """Test storing device with JSONB format."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchone.return_value = None  # No existing device
        mock_cursor.fetchone.return_value = [1]  # Return device ID

        adapter = PostgreSQLAdapter()
        adapter.connection = mock_conn

        device_data = {
            "hostname": "test-server",
            "connection_ip": "192.168.1.10",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "cpu_model": "Intel Core i7",
            "cpu_cores": 8,
            "memory_total": "16G",
            "network_interfaces": json.dumps([{"name": "eth0"}]),
        }

        adapter.store_device(device_data)

        # Verify INSERT was called with JSONB data
        assert mock_cursor.execute.call_count >= 2  # SELECT + INSERT
        mock_conn.commit.assert_called()

    def test_store_device_jsonb_includes_fingerprint_phase38(self, mock_connection):
        """Phase 38 D-09a: Postgres store_device places fingerprint inside system_info JSONB.

        Mirrors test_store_device_jsonb above — asserts on mock_cursor.execute, not on round-trip.
        The codebase has no live-Postgres fixture; mock-cursor assertion is the established pattern.
        """
        mock_conn, mock_cursor = mock_connection
        # SELECT (existence check) returns None, then INSERT RETURNING returns [1]
        mock_cursor.fetchone.side_effect = [None, [1]]

        adapter = PostgreSQLAdapter()
        adapter.connection = mock_conn

        fp_dict = {
            "kernel_name": "Linux",
            "kernel_version": "6.5.13-1-pve",
            "package_fingerprint": "sha256:def456",
            "capabilities": {"cuda": {"driver_version": "535.183.06"}},
        }
        device_data = {
            "hostname": "test-pg",
            "connection_ip": "10.0.0.7",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "fingerprint": json.dumps(fp_dict),
        }
        adapter.store_device(device_data)

        # Find the INSERT call (after the SELECT for existence check).
        # The system_info JSON-string is positional arg index 4 in the INSERT VALUES tuple
        # (hostname, connection_ip, last_seen, status, system_info, network_interfaces, error_message).
        insert_call = None
        for call in mock_cursor.execute.call_args_list:
            sql = call.args[0]
            if "INSERT INTO devices" in sql:
                insert_call = call
                break
        assert insert_call is not None, "Expected INSERT INTO devices call"
        params = insert_call.args[1]
        system_info_json = params[4]  # 5th positional in VALUES tuple
        parsed = json.loads(system_info_json)
        assert "fingerprint" in parsed, (
            f"system_info JSONB must include 'fingerprint' sub-key, got keys: {list(parsed.keys())}"
        )
        assert parsed["fingerprint"]["kernel_name"] == "Linux"
        assert parsed["fingerprint"]["kernel_version"] == "6.5.13-1-pve"
        assert parsed["fingerprint"]["capabilities"]["cuda"]["driver_version"] == "535.183.06"

    def test_store_device_update_branch_includes_fingerprint_phase38_postgres(self, mock_connection):
        """Phase 38 D-09a: Postgres UPDATE branch (existing device) carries fingerprint inside system_info JSONB."""
        mock_conn, mock_cursor = mock_connection
        # Existing device: SELECT returns [1] (device id)
        mock_cursor.fetchone.return_value = [1]

        adapter = PostgreSQLAdapter()
        adapter.connection = mock_conn

        fp_dict = {"kernel_name": "Linux", "kernel_version": "6.0.0"}
        device_data = {
            "hostname": "test-pg-update",
            "connection_ip": "10.0.0.8",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
            "fingerprint": json.dumps(fp_dict),
        }
        adapter.store_device(device_data)

        # Find the UPDATE call. system_info JSON-string is positional arg index 2 in the UPDATE
        # tuple (last_seen, status, system_info, network_interfaces, error_message, connection_ip, id).
        update_call = None
        for call in mock_cursor.execute.call_args_list:
            sql = call.args[0]
            if "UPDATE devices SET" in sql:
                update_call = call
                break
        assert update_call is not None, "Expected UPDATE devices SET call"
        params = update_call.args[1]
        system_info_json = params[2]
        parsed = json.loads(system_info_json)
        assert "fingerprint" in parsed
        assert parsed["fingerprint"]["kernel_version"] == "6.0.0"

    def test_get_all_devices_flattens_fingerprint_phase38_postgres(self, mock_connection):
        """Phase 38 D-10: Postgres get_all_devices lifts system_info['fingerprint'] to top-level row key."""
        mock_conn, mock_cursor = mock_connection

        # Prime the read path: cursor.fetchall returns row dicts (RealDictCursor shape).
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "hostname": "test-pg-read",
                "connection_ip": "10.0.0.9",
                "last_seen": datetime.now().isoformat(),
                "status": "success",
                "system_info": {
                    "cpu": {"model": "Intel", "cores": 4},
                    "memory": {"total": "16G"},
                    "disk": {},
                    "uptime": "1h",
                    "os": "Linux",
                    "usb_devices": [],
                    "pci_devices": [],
                    "block_devices": [],
                    "fingerprint": {
                        "kernel_name": "Linux",
                        "kernel_version": "6.5.13-1-pve",
                        "capabilities": {"cuda": {"driver_version": "535.183.06"}},
                    },
                },
                "network_interfaces": [],
                "error_message": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        ]

        adapter = PostgreSQLAdapter()
        adapter.connection = mock_conn

        devices = adapter.get_all_devices()
        assert len(devices) == 1
        assert "fingerprint" in devices[0], (
            "get_all_devices must flatten system_info['fingerprint'] to top-level row key"
        )
        assert devices[0]["fingerprint"]["kernel_name"] == "Linux"
        assert devices[0]["fingerprint"]["capabilities"]["cuda"]["driver_version"] == "535.183.06"

    def test_update_device_fingerprint_deep_merge_capabilities_phase38_postgres(self, mock_connection):
        """Phase 38 D-05/D-11: Postgres deep-merge proven via mock_cursor.execute on SELECT-then-UPDATE.

        Mirrors test_store_device_jsonb at line 171 — asserts on mock_cursor.execute, not real round-trip.
        Postgres "round-trip" in this codebase = "adapter produced the right SQL with the right JSON args".
        """
        mock_conn, mock_cursor = mock_connection

        # Prime the SELECT-system_info-from-devices-where-hostname read.
        existing_system_info = {
            "cpu": {"model": "Intel"},
            "memory": {"total": "16G"},
            "disk": {},
            "uptime": "1h",
            "os": "Linux",
            "usb_devices": [],
            "pci_devices": [],
            "block_devices": [],
            "fingerprint": {
                "kernel_version": "6.0.0",
                "capabilities": {"vulkan": {"available": True, "loader_version": "1.3.275"}},
            },
        }
        mock_cursor.fetchone.return_value = [existing_system_info]

        adapter = PostgreSQLAdapter()
        adapter.connection = mock_conn

        merged = adapter.update_device_fingerprint(
            "merge-host",
            {"capabilities": {"cuda": {"driver_version": "535.183.06"}}},
        )

        # Return value is the merged fingerprint dict.
        assert "vulkan" in merged["capabilities"], "Original capability survives deep-merge"
        assert "cuda" in merged["capabilities"]
        assert merged["capabilities"]["cuda"]["driver_version"] == "535.183.06"

        # Verify SELECT-then-UPDATE sequence on mock cursor.
        select_call = None
        update_call = None
        for call in mock_cursor.execute.call_args_list:
            sql = call.args[0]
            if "SELECT system_info FROM devices" in sql:
                select_call = call
            elif "UPDATE devices SET" in sql:
                update_call = call
        assert select_call is not None, "Expected SELECT system_info FROM devices call"
        assert update_call is not None, "Expected UPDATE devices SET call"

        # SELECT should be parameterized on hostname.
        assert "hostname" in select_call.args[0]
        assert select_call.args[1] == ("merge-host",)

        # UPDATE's system_info JSON arg should contain the merged fingerprint.
        update_params = update_call.args[1]
        # Find the JSON-string param (system_info is a json.dumps result).
        system_info_json = next(p for p in update_params if isinstance(p, str) and p.startswith("{"))
        parsed = json.loads(system_info_json)
        assert "vulkan" in parsed["fingerprint"]["capabilities"]
        assert "cuda" in parsed["fingerprint"]["capabilities"]

    def test_update_device_fingerprint_overwrites_top_level_phase38_postgres(self, mock_connection):
        """Phase 38 D-05/D-11: top-level overwrite proven via mock_cursor.execute UPDATE inspection."""
        mock_conn, mock_cursor = mock_connection

        existing_system_info = {
            "cpu": {},
            "memory": {},
            "disk": {},
            "uptime": "",
            "os": "",
            "usb_devices": [],
            "pci_devices": [],
            "block_devices": [],
            "fingerprint": {
                "kernel_version": "6.0.0",
                "capabilities": {"vulkan": {"available": True}},
            },
        }
        mock_cursor.fetchone.return_value = [existing_system_info]

        adapter = PostgreSQLAdapter()
        adapter.connection = mock_conn

        merged = adapter.update_device_fingerprint(
            "overwrite-host",
            {"kernel_version": "6.5.13-1-pve"},
        )

        assert merged["kernel_version"] == "6.5.13-1-pve"
        assert merged["capabilities"]["vulkan"]["available"] is True

        update_call = next(
            (c for c in mock_cursor.execute.call_args_list if "UPDATE devices SET" in c.args[0]),
            None,
        )
        assert update_call is not None
        update_params = update_call.args[1]
        system_info_json = next(p for p in update_params if isinstance(p, str) and p.startswith("{"))
        parsed = json.loads(system_info_json)
        assert parsed["fingerprint"]["kernel_version"] == "6.5.13-1-pve"
        assert parsed["fingerprint"]["capabilities"]["vulkan"]["available"] is True

    def test_update_device_fingerprint_missing_hostname_raises_phase38_postgres(self, mock_connection):
        """Phase 38 D-05: Postgres missing-hostname path raises ValueError with discover_and_map hint."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchone.return_value = None  # No row found for hostname.

        adapter = PostgreSQLAdapter()
        adapter.connection = mock_conn

        with pytest.raises(ValueError, match="discover_and_map"):
            adapter.update_device_fingerprint("nonexistent.local", {"kernel_name": "Linux"})


class TestDatabaseFactory:
    """Test database adapter factory function."""

    def test_get_sqlite_adapter(self):
        """Test getting SQLite adapter."""
        adapter = get_database_adapter("sqlite", db_path=":memory:")
        assert isinstance(adapter, SQLiteAdapter)

    @pytest.mark.skipif(not POSTGRESQL_AVAILABLE, reason="psycopg2 not available")
    def test_get_postgresql_adapter(self):
        """Test getting PostgreSQL adapter."""
        adapter = get_database_adapter(
            "postgresql",
            connection_params={
                "host": "localhost",
                "database": "test",
                "user": "test",
                "password": "test",
            },
        )
        assert isinstance(adapter, PostgreSQLAdapter)

    def test_get_adapter_auto_detect(self):
        """Test auto-detection of adapter type."""
        with patch.dict(os.environ, {"DATABASE_TYPE": "sqlite"}):
            adapter = get_database_adapter()
            assert isinstance(adapter, SQLiteAdapter)

    def test_unsupported_database_type(self):
        """Test error for unsupported database type."""
        with pytest.raises(ValueError, match="Unsupported database type"):
            get_database_adapter("mysql")


class TestDatabaseConfig:
    """Test database configuration."""

    def test_default_sqlite_config(self):
        """Test default SQLite configuration."""
        with patch.dict(os.environ, {}, clear=True):
            config = DatabaseConfig()
            assert config.db_type == "sqlite"
            assert config.sqlite_path.endswith("sitemap.db")

    def test_postgresql_config_from_env(self):
        """Test PostgreSQL configuration from environment."""
        env_vars = {
            "DATABASE_TYPE": "postgresql",
            "POSTGRES_HOST": "pg-host",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "my_db",
            "POSTGRES_USER": "my_user",
            "POSTGRES_PASSWORD": "my_pass",
        }

        with patch.dict(os.environ, env_vars):
            config = DatabaseConfig()
            assert config.db_type == "postgresql"
            assert config.postgres_config["host"] == "pg-host"
            assert config.postgres_config["port"] == 5433
            assert config.postgres_config["database"] == "my_db"
            assert config.postgres_config["user"] == "my_user"
            assert config.postgres_config["password"] == "my_pass"

    def test_get_database_params_sqlite(self):
        """Test getting SQLite database parameters."""
        config = DatabaseConfig()
        config.db_type = "sqlite"
        config.sqlite_path = "/test/path.db"

        params = config.get_database_params()
        assert params["db_type"] == "sqlite"
        assert params["db_path"] == "/test/path.db"

    def test_get_database_params_postgresql(self):
        """Test getting PostgreSQL database parameters."""
        config = DatabaseConfig()
        config.db_type = "postgresql"

        params = config.get_database_params()
        assert params["db_type"] == "postgresql"
        assert "connection_params" in params

    def test_is_postgresql_configured(self):
        """Test PostgreSQL configuration validation."""
        config = DatabaseConfig()
        config.db_type = "sqlite"
        assert not config.is_postgresql_configured()

        config.db_type = "postgresql"
        # Without environment variables, should be False
        assert not config.is_postgresql_configured()

        # With environment variables, should be True
        env_vars = {
            "POSTGRES_HOST": "localhost",
            "POSTGRES_DB": "test",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "test",
        }

        with patch.dict(os.environ, env_vars):
            config = DatabaseConfig()
            config.db_type = "postgresql"
            assert config.is_postgresql_configured()


class TestUtilityFunctions:
    """Test utility functions."""

    def test_calculate_data_hash(self):
        """Test data hash calculation."""
        data1 = "test data"
        data2 = "test data"
        data3 = "different data"

        hash1 = calculate_data_hash(data1)
        hash2 = calculate_data_hash(data2)
        hash3 = calculate_data_hash(data3)

        assert hash1 == hash2  # Same data should have same hash
        assert hash1 != hash3  # Different data should have different hash
        assert len(hash1) == 64  # SHA256 produces 64-character hex string


class TestCredentialDBRemoval:
    """CRED-04: ssh_credentials table and CRUD methods must not exist after v1.6 migration."""

    @pytest.fixture
    def temp_db(self):
        """Create an in-memory database."""
        yield ":memory:"

    def test_ssh_credentials_table_dropped(self, temp_db):
        """CRED-04 D-01: ssh_credentials table must not exist after init_schema (v1.6)."""
        adapter = SQLiteAdapter(temp_db)
        adapter.init_schema()
        cursor = adapter.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ssh_credentials'")
        assert cursor.fetchone() is None, (
            "ssh_credentials table must not be created by init_schema after v1.6 migration"
        )
        adapter.close()

    def test_no_credential_methods_on_adapter(self, temp_db):
        """CRED-04 D-02: SQLiteAdapter must not expose credential CRUD methods after Phase 33."""
        adapter = SQLiteAdapter(temp_db)
        for method_name in (
            "add_credential",
            "get_credential_by_hostname",
            "update_credential",
            "delete_credential",
            "update_last_verified",
        ):
            assert not hasattr(adapter, method_name), (
                f"SQLiteAdapter must not have {method_name!r} after Phase 33 credential DB removal"
            )


# Phase 33 regression tests — RED until implementation plans land


def test_ssh_credentials_table_dropped():
    """CRED-04 / D-01: ssh_credentials table must not exist after init_schema (v1.6)."""
    from src.homelab_mcp.database import SQLiteAdapter

    adapter = SQLiteAdapter(":memory:")
    adapter.connect()
    adapter.init_schema()
    cursor = adapter.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ssh_credentials'")
    assert cursor.fetchone() is None, "ssh_credentials table must not exist after v1.6 migration (CRED-04)"
    adapter.close()


def test_no_credential_methods_on_adapter():
    """CRED-04 / D-02: SQLiteAdapter must not expose credential CRUD methods after Phase 33."""
    from src.homelab_mcp.database import SQLiteAdapter

    adapter = SQLiteAdapter(":memory:")
    for method_name in (
        "add_credential",
        "get_credential",
        "get_credential_by_hostname",
        "get_credential_by_id",
        "update_credential",
        "delete_credential",
        "list_credentials",
        "update_last_verified",
    ):
        assert not hasattr(adapter, method_name), (
            f"SQLiteAdapter must not have {method_name!r} after Phase 33 credential DB removal (D-02)"
        )


def test_ssh_credentials_table_dropped_postgres(monkeypatch):
    """CRED-04 / D-01: Postgres migration path executes DROP TABLE IF EXISTS ssh_credentials.

    Uses unittest.mock to stub psycopg2.connect — no live Postgres server required.
    The Postgres migration (run_postgres_migrations / init_schema, whichever Plan 33-02 wires)
    must issue a DROP TABLE statement against the cursor.
    """
    pytest.importorskip("psycopg2")

    from unittest.mock import Mock

    from src.homelab_mcp import database as db_module
    from src.homelab_mcp.database import PostgreSQLAdapter

    executed: list[str] = []
    mock_cursor = Mock()
    mock_cursor.execute.side_effect = lambda sql, *a, **kw: executed.append(sql)
    # Return a truthy row for the existence check so the DROP branch fires
    mock_cursor.fetchone.return_value = (True,)

    mock_conn = Mock()
    # Support both `with conn.cursor() as cur:` and `cur = conn.cursor()` patterns
    cursor_ctx = Mock()
    cursor_ctx.__enter__ = Mock(return_value=mock_cursor)
    cursor_ctx.__exit__ = Mock(return_value=None)
    mock_conn.cursor.return_value = cursor_ctx
    # Fallback: if adapter uses non-context cursor(), returning the ctx also works via attribute access,
    # but if it accesses mock_cursor methods directly, expose them on the ctx via __getattr__ fallback:
    cursor_ctx.execute = mock_cursor.execute
    cursor_ctx.fetchone = mock_cursor.fetchone
    mock_conn.commit = Mock()

    # Object-form monkeypatch — the dotted-string form would attempt to import
    # `src.homelab_mcp.database.psycopg2` as a submodule, but `database` is a
    # single-file module that lazy-imports psycopg2 as an attribute.
    monkeypatch.setattr(db_module.psycopg2, "connect", lambda *a, **kw: mock_conn)

    adapter = PostgreSQLAdapter(
        connection_params={"host": "fake", "database": "fake", "user": "fake", "password": "fake"}
    )
    adapter.connect()
    # init_schema invokes run_postgres_migrations per Plan 33-02 wiring
    adapter.init_schema()

    dropped = [s for s in executed if "DROP TABLE IF EXISTS SSH_CREDENTIALS" in s.upper().replace("  ", " ")]
    assert dropped, f"Expected DROP TABLE IF EXISTS ssh_credentials in Postgres migration; got executed SQL: {executed}"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 35 functional regression tests (D-17a + D-01a + D-17b)
# ─────────────────────────────────────────────────────────────────────────────


def test_store_device_updates_in_place_on_ip_change_phase35(tmp_path):
    """Phase 35 D-17a: same hostname re-discovered with a different
    connection_ip MUST update the existing row in place (same id), with
    connection_ip overwritten — no zombie second row is produced.
    """
    from src.homelab_mcp.database import SQLiteAdapter

    db_path = str(tmp_path / "phase35_d17a.db")
    adapter = SQLiteAdapter(db_path)
    adapter.connect()
    adapter.init_schema()

    try:
        id1 = adapter.store_device(
            {
                "hostname": "pve1",
                "connection_ip": "10.0.0.10",
                "last_seen": "2026-01-01T00:00:00",
                "status": "success",
                "cpu_cores": 4,
            }
        )
        id2 = adapter.store_device(
            {
                "hostname": "pve1",
                "connection_ip": "10.0.0.99",
                "last_seen": "2026-01-02T00:00:00",
                "status": "success",
                "cpu_cores": 4,
            }
        )
        assert id1 == id2, (
            f"Phase 35 D-17a regression: hostname-only upsert failed "
            f"(id1={id1}, id2={id2}) — check store_device match clause"
        )
        devices = adapter.get_all_devices()
        assert len(devices) == 1, f"Phase 35 D-17a: expected 1 row, got {len(devices)} (zombie-row regression)"
        assert devices[0]["connection_ip"] == "10.0.0.99", (
            f"Phase 35 D-17a: expected IP overwrite to '10.0.0.99', got {devices[0]['connection_ip']!r}"
        )
    finally:
        adapter.close()


def test_store_device_preserves_degenerate_hostnames_phase35(tmp_path):
    """Phase 35 D-01a: degenerate-hostname rows ('', 'unknown', None) MUST
    fall back to (hostname, connection_ip) match so distinct error rows do
    not collapse into one poisoned bucket.
    """
    from src.homelab_mcp.database import SQLiteAdapter

    db_path = str(tmp_path / "phase35_d01a.db")
    adapter = SQLiteAdapter(db_path)
    adapter.connect()
    adapter.init_schema()

    try:
        id1 = adapter.store_device(
            {
                "hostname": "unknown",
                "connection_ip": "10.0.0.10",
                "last_seen": "2026-01-01T00:00:00",
                "status": "error",
                "error_message": "ssh timeout",
            }
        )
        id2 = adapter.store_device(
            {
                "hostname": "unknown",
                "connection_ip": "10.0.0.11",
                "last_seen": "2026-01-01T00:00:00",
                "status": "error",
                "error_message": "ssh timeout",
            }
        )
        assert id1 != id2, "Phase 35 D-01a regression: degenerate-hostname fallback collapsed distinct error rows"
        devices = adapter.get_all_devices()
        assert len(devices) == 2
    finally:
        adapter.close()


def test_migration_dedup_collapses_duplicates_and_is_idempotent_phase35(tmp_path):
    """Phase 35 D-17b: seeded pre-migration DB with two rows sharing a hostname
    but different IPs — first migration run collapses them into one (merging
    non-null sibling fields); second run is a no-op. Degenerate-hostname rows
    preserved distinct.
    """
    import sqlite3

    from src.homelab_mcp.migration import run_sqlite_migrations

    db_path = str(tmp_path / "phase35_d17b.db")

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL,
            connection_ip TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            status TEXT NOT NULL,
            cpu_model TEXT,
            cpu_cores INTEGER,
            memory_total TEXT,
            network_interfaces TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(hostname, connection_ip)
        )
        """
    )
    conn.execute("CREATE INDEX idx_devices_hostname_ip ON devices (hostname, connection_ip)")
    conn.execute(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status, cpu_cores) VALUES (?, ?, ?, ?, ?)",
        ("pve1", "10.0.0.10", "2026-01-01T00:00:00", "success", 4),
    )
    conn.execute(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status, memory_total) VALUES (?, ?, ?, ?, ?)",
        ("pve1", "10.0.0.11", "2026-01-02T00:00:00", "success", "16Gi"),
    )
    conn.execute(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status, error_message) VALUES (?, ?, ?, ?, ?)",
        ("unknown", "10.0.0.20", "2026-01-01T00:00:00", "error", "ssh timeout"),
    )
    conn.execute(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status, error_message) VALUES (?, ?, ?, ?, ?)",
        ("unknown", "10.0.0.21", "2026-01-01T00:00:00", "error", "ssh timeout"),
    )
    conn.commit()
    conn.close()

    applied1 = run_sqlite_migrations(db_path=db_path)
    assert "dedupe_zombie_device_rows" in applied1, applied1
    assert any(a.startswith("add_column_") for a in applied1), applied1
    assert "drop_stale_hostname_ip_unique" in applied1, applied1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT hostname, connection_ip, cpu_cores, memory_total FROM devices WHERE hostname = 'pve1'"
        ).fetchall()
    ]
    assert len(rows) == 1, f"Phase 35 D-17b: expected 1 pve1 row after dedup, got {len(rows)}: {rows}"
    keeper = rows[0]
    assert keeper["connection_ip"] == "10.0.0.11", (
        f"Phase 35 D-17b: keeper should be the row with greatest last_seen; "
        f"got connection_ip={keeper['connection_ip']!r}"
    )
    assert keeper["cpu_cores"] == 4, (
        f"Phase 35 D-17b: non-null-wins merge should have pulled cpu_cores=4 from sibling; got {keeper['cpu_cores']!r}"
    )
    assert keeper["memory_total"] == "16Gi"

    unknown_rows = conn.execute("SELECT connection_ip FROM devices WHERE hostname = 'unknown'").fetchall()
    assert len(unknown_rows) == 2, (
        f"Phase 35 D-02a regression: degenerate-hostname rows collapsed ({len(unknown_rows)} remaining)"
    )
    conn.close()

    applied2 = run_sqlite_migrations(db_path=db_path)
    assert "dedupe_zombie_device_rows" not in applied2, applied2
    assert not any(a.startswith("add_column_") for a in applied2), applied2
    assert "drop_stale_hostname_ip_unique" not in applied2, applied2


def test_init_schema_triggers_phase35_migrations_on_legacy_db(tmp_path):
    """Regression: ``SQLiteAdapter.init_schema`` must run Phase 33/35 migrations
    on pre-existing databases.

    Without this wiring, ``CREATE TABLE IF NOT EXISTS devices`` is a no-op on
    a legacy DB, so the new ``usb_devices`` / ``pci_devices`` / ``block_devices``
    columns are never added — causing ``store_device`` to fail with
    ``no such column: usb_devices``. The zombie-row dedup and stale UNIQUE drop
    similarly skip. This test simulates a pre-Phase-35 DB and verifies that
    instantiating ``NetworkSiteMap`` alone triggers all three migrations.
    """
    import sqlite3

    from src.homelab_mcp.sitemap import NetworkSiteMap

    db_path = str(tmp_path / "legacy_pre_phase35.db")

    # Pre-Phase-35 schema: no usb/pci/block columns, with stale UNIQUE
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL,
            connection_ip TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            status TEXT NOT NULL,
            cpu_cores INTEGER,
            UNIQUE(hostname, connection_ip)
        )
        """
    )
    # Two rows with same hostname — Phase 35 dedup target
    conn.execute(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status, cpu_cores) "
        "VALUES ('pve1', '10.0.0.1', '2026-01-01', 'success', 4)"
    )
    conn.execute(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status, cpu_cores) "
        "VALUES ('pve1', '10.0.0.2', '2026-01-02', 'success', 4)"
    )
    conn.commit()
    conn.close()

    # Instantiating NetworkSiteMap must be sufficient to run migrations
    NetworkSiteMap(db_path=db_path, db_type="sqlite")

    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
        assert "usb_devices" in cols, "Phase 35 usb_devices column not added by init_schema migrations"
        assert "pci_devices" in cols, "Phase 35 pci_devices column not added by init_schema migrations"
        assert "block_devices" in cols, "Phase 35 block_devices column not added by init_schema migrations"

        rows = conn.execute("SELECT hostname, connection_ip FROM devices").fetchall()
        assert len(rows) == 1, f"Zombie row dedup did not run on init_schema; got {rows}"
        assert rows[0] == ("pve1", "10.0.0.2"), f"Keeper should have latest last_seen; got {rows[0]}"

        table_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='devices'").fetchone()[0]
        assert "UNIQUE(hostname, connection_ip)" not in table_sql, "Stale composite UNIQUE not dropped on init_schema"
        assert "UNIQUE (hostname, connection_ip)" not in table_sql, "Stale composite UNIQUE not dropped on init_schema"
    finally:
        conn.close()


def test_run_sqlite_migrations_adds_fingerprint_column_idempotently_phase38(tmp_path):
    """Phase 38 D-08 / SC-3: ADD COLUMN fingerprint is idempotent and non-destructive."""
    import sqlite3

    from src.homelab_mcp.migration import run_sqlite_migrations

    db_path = str(tmp_path / "legacy.db")
    # Build a pre-Phase-38 schema (with usb/pci/block but no fingerprint).
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL,
            connection_ip TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            status TEXT NOT NULL,
            usb_devices TEXT,
            pci_devices TEXT,
            block_devices TEXT
        )
        """
    )
    # Insert a legacy row to confirm it survives the migration with NULL fingerprint
    conn.execute(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status) VALUES (?, ?, ?, ?)",
        ("legacy.local", "10.0.0.1", "2026-04-01T00:00:00", "success"),
    )
    conn.commit()
    conn.close()

    applied1 = run_sqlite_migrations(db_path=db_path)
    assert "add_column_fingerprint" in applied1, applied1

    # Verify column exists, legacy row still present, fingerprint is NULL.
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
    assert "fingerprint" in cols, cols
    row = conn.execute(
        "SELECT hostname, fingerprint FROM devices WHERE hostname = ?",
        ("legacy.local",),
    ).fetchone()
    assert row is not None
    assert row[0] == "legacy.local"
    assert row[1] is None  # NULL on legacy rows — re-discovery populates
    conn.close()

    # Re-run is idempotent — no add_column_fingerprint on second call.
    applied2 = run_sqlite_migrations(db_path=db_path)
    assert "add_column_fingerprint" not in applied2, applied2


# ---------------------------------------------------------------------------
# Phase 38.1 — Wave 0 RED tests: credential binding columns + eligibility (R2, R7)
# ---------------------------------------------------------------------------


def test_devices_has_credential_id_columns_phase381_sqlite(tmp_path) -> None:
    """devices table MUST have ssh_credential_id and proxmox_credential_id columns (R2 — SQLite)."""
    import sqlite3  # noqa: PLC0415

    db_path = str(tmp_path / "sitemap_381.db")
    adapter = SQLiteAdapter(db_path)
    adapter.init_schema()
    adapter.close()

    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
    conn.close()

    assert "ssh_credential_id" in cols, (
        f"Phase 38.1 R2: devices table missing ssh_credential_id column. Present columns: {sorted(cols)}"
    )
    assert "proxmox_credential_id" in cols, (
        f"Phase 38.1 R2: devices table missing proxmox_credential_id column. Present columns: {sorted(cols)}"
    )


@pytest.mark.integration
def test_devices_has_credential_id_columns_phase381_postgres(tmp_path) -> None:
    """devices table MUST have ssh_credential_id and proxmox_credential_id columns (R2 — Postgres)."""
    import os  # noqa: PLC0415

    pg_url = os.environ.get("TEST_POSTGRES_URL", "")
    if not pg_url:
        pytest.skip("TEST_POSTGRES_URL not set — Postgres integration test skipped")

    # Phase 38.1: verify both columns exist in Postgres devices table
    # This test will FAIL until the Postgres schema migration lands in Plan 02.
    adapter = PostgreSQLAdapter(pg_url)
    adapter.connect()
    cursor = adapter.connection.cursor()  # type: ignore[union-attr]
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'devices' AND column_name IN ('ssh_credential_id', 'proxmox_credential_id')"
    )
    found_cols = {row[0] for row in cursor.fetchall()}
    adapter.close()

    assert "ssh_credential_id" in found_cols, (
        f"Phase 38.1 R2: Postgres devices missing ssh_credential_id. Found: {found_cols}"
    )
    assert "proxmox_credential_id" in found_cols, (
        f"Phase 38.1 R2: Postgres devices missing proxmox_credential_id. Found: {found_cols}"
    )


def test_set_device_credential_binding_writes_column_sqlite_phase381(tmp_path) -> None:
    """set_device_credential_binding writes UUID to the correct column (R2 + R3/R4 path)."""
    import sqlite3  # noqa: PLC0415
    from datetime import datetime  # noqa: PLC0415

    db_path = str(tmp_path / "sitemap_bind.db")
    adapter = SQLiteAdapter(db_path)
    adapter.init_schema()

    # Store a device so we have a row to bind
    device_data = {
        "hostname": "pve1",
        "connection_ip": "10.0.0.10",
        "last_seen": datetime.now().isoformat(),
        "status": "success",
    }
    adapter.store_device(device_data)

    # Phase 38.1 R2: abstract method set_device_credential_binding must exist
    test_uuid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    adapter.set_device_credential_binding(
        hostname="pve1",
        credential_type="proxmox",
        credential_id=test_uuid,
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT proxmox_credential_id FROM devices WHERE hostname = ?", ("pve1",)
    ).fetchone()
    conn.close()
    adapter.close()

    assert row is not None, "Phase 38.1 R2: no device row found for 'pve1'"
    assert row[0] == test_uuid, (
        f"Phase 38.1 R2: expected proxmox_credential_id={test_uuid!r}, got {row[0]!r}"
    )


def test_get_all_devices_includes_eligibility_field_sqlite_phase381(tmp_path) -> None:
    """get_all_devices rows include eligibility field with ssh+proxmox bool pair (R7)."""
    from datetime import datetime  # noqa: PLC0415

    db_path = str(tmp_path / "sitemap_elig.db")
    adapter = SQLiteAdapter(db_path)
    adapter.init_schema()

    device_data = {
        "hostname": "pve2",
        "connection_ip": "10.0.0.20",
        "last_seen": datetime.now().isoformat(),
        "status": "success",
    }
    adapter.store_device(device_data)

    devices = adapter.get_all_devices()
    assert len(devices) == 1
    device = devices[0]

    # Phase 38.1 R7: each row must contain an eligibility field
    assert "eligibility" in device, (
        f"Phase 38.1 R7: get_all_devices row missing 'eligibility' field. Keys: {sorted(device.keys())}"
    )
    eligibility = device["eligibility"]
    assert isinstance(eligibility, dict), (
        f"Phase 38.1 R7: eligibility must be a dict, got {type(eligibility).__name__!r}"
    )
    assert "ssh" in eligibility, f"Phase 38.1 R7: eligibility missing 'ssh' key: {eligibility}"
    assert "proxmox" in eligibility, f"Phase 38.1 R7: eligibility missing 'proxmox' key: {eligibility}"
    assert isinstance(eligibility["ssh"], bool), (
        f"Phase 38.1 R7: eligibility.ssh must be bool, got {type(eligibility['ssh']).__name__!r}"
    )
    assert isinstance(eligibility["proxmox"], bool), (
        f"Phase 38.1 R7: eligibility.proxmox must be bool, got {type(eligibility['proxmox']).__name__!r}"
    )
    # New device has no credentials bound — both must be False
    assert eligibility["ssh"] is False, (
        "Phase 38.1 R7: unbound device should have eligibility.ssh == False"
    )
    assert eligibility["proxmox"] is False, (
        "Phase 38.1 R7: unbound device should have eligibility.proxmox == False"
    )
    adapter.close()
