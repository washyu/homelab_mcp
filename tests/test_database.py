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


class TestDriftBaselines:
    """Tests for DRFT-04: SQLiteAdapter drift baseline CRUD methods.

    These tests will fail with AttributeError until Plan 02 implements
    upsert_drift_baseline, get_drift_baseline, and get_all_drift_baselines
    on SQLiteAdapter — that is the expected RED state.
    """

    @pytest.fixture
    def adapter(self):
        """Create an in-memory SQLite adapter with schema initialized."""
        db = SQLiteAdapter(":memory:")
        db.init_schema()
        return db

    def test_upsert_and_get_baseline(self, adapter):
        """upsert_drift_baseline stores config; get_drift_baseline retrieves it."""
        baseline_config = {"cores": 2, "memory": 2048, "net0": "virtio,bridge=vmbr0"}

        adapter.upsert_drift_baseline(
            node="pve",
            vmid=100,
            vm_type="qemu",
            baseline_config=baseline_config,
            recorded_by="test_tool",
        )

        result = adapter.get_drift_baseline(node="pve", vmid=100, vm_type="qemu")

        assert result is not None
        assert result["node"] == "pve"
        assert result["vmid"] == 100
        assert result["vm_type"] == "qemu"
        assert result["baseline_config"] == baseline_config

    def test_upsert_replaces_existing(self, adapter):
        """Second upsert for same (node, vmid, vm_type) replaces the previous baseline."""
        adapter.upsert_drift_baseline(
            node="pve",
            vmid=100,
            vm_type="qemu",
            baseline_config={"cores": 2},
            recorded_by="initial_tool",
        )
        adapter.upsert_drift_baseline(
            node="pve",
            vmid=100,
            vm_type="qemu",
            baseline_config={"cores": 4, "memory": 4096},
            recorded_by="resize_vm",
        )

        result = adapter.get_drift_baseline(node="pve", vmid=100, vm_type="qemu")

        assert result is not None
        assert result["baseline_config"]["cores"] == 4
        assert result["baseline_config"].get("memory") == 4096

        # Verify only one baseline exists for this VM
        all_baselines = adapter.get_all_drift_baselines()
        pve_100 = [b for b in all_baselines if b["node"] == "pve" and b["vmid"] == 100]
        assert len(pve_100) == 1

    def test_get_returns_none_when_absent(self, adapter):
        """get_drift_baseline returns None for an unknown vmid."""
        result = adapter.get_drift_baseline(node="pve", vmid=9999, vm_type="qemu")

        assert result is None

    def test_get_all_drift_baselines(self, adapter):
        """get_all_drift_baselines returns a list containing all stored baselines."""
        adapter.upsert_drift_baseline(
            node="pve",
            vmid=100,
            vm_type="qemu",
            baseline_config={"cores": 2},
            recorded_by="tool_a",
        )
        adapter.upsert_drift_baseline(
            node="pve",
            vmid=101,
            vm_type="lxc",
            baseline_config={"cores": 1},
            recorded_by="tool_b",
        )

        all_baselines = adapter.get_all_drift_baselines()

        assert isinstance(all_baselines, list)
        assert len(all_baselines) >= 2
        vmids = [b["vmid"] for b in all_baselines]
        assert 100 in vmids
        assert 101 in vmids

    def test_baseline_config_is_full_dict(self, adapter):
        """Retrieved baseline_config is a dict (deserialized from JSON), not a raw string."""
        config = {"cores": 4, "memory": 8192, "net0": "virtio,bridge=vmbr0"}

        adapter.upsert_drift_baseline(
            node="pve",
            vmid=200,
            vm_type="qemu",
            baseline_config=config,
            recorded_by="some_tool",
        )

        result = adapter.get_drift_baseline(node="pve", vmid=200, vm_type="qemu")

        assert result is not None
        assert isinstance(result["baseline_config"], dict)
        assert result["baseline_config"]["cores"] == 4
        assert result["baseline_config"]["net0"] == "virtio,bridge=vmbr0"


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
    from unittest.mock import Mock

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

    monkeypatch.setattr(
        "src.homelab_mcp.database.psycopg2.connect",
        lambda *a, **kw: mock_conn,
        raising=False,
    )

    from src.homelab_mcp.database import PostgreSQLAdapter

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
