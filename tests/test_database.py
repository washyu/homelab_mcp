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
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='devices'"
        )
        assert cursor.fetchone() is not None

        # Check discovery_history table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='discovery_history'"
        )
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
            "network_interfaces": json.dumps(
                [{"name": "eth0", "addresses": ["192.168.1.10"]}]
            ),
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

        device_id = adapter.store_device(device_data)

        # Verify INSERT was called with JSONB data
        assert mock_cursor.execute.call_count >= 2  # SELECT + INSERT
        mock_conn.commit.assert_called()


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
