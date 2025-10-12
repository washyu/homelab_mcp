"""Tests for database migration functionality."""

import json
import os
import tempfile
from unittest.mock import MagicMock, call, patch

import pytest

from src.homelab_mcp.migration import (
    DatabaseMigrator,
    create_postgres_config_template,
    main,
    migrate_sqlite_to_postgresql,
    setup_postgresql_database,
)


class MockDevice:
    """Mock device data for testing."""

    @staticmethod
    def create_sample_device(device_id=1, hostname="test-server"):
        return {
            "id": device_id,
            "hostname": hostname,
            "connection_ip": "192.168.1.100",
            "last_seen": "2024-01-01T12:00:00Z",
            "status": "success",
            "cpu_model": "Intel Core i7",
            "cpu_cores": 8,
            "memory_total": "16G",
            "memory_used": "8G",
            "disk_size": "1T",
            "disk_use_percent": "45%",
            "os_info": "Ubuntu 22.04.3 LTS",
            "uptime": "up 5 days, 2 hours",
            "network_interfaces": json.dumps(
                [{"name": "eth0", "addresses": ["192.168.1.100"]}]
            ),
        }

    @staticmethod
    def create_sample_history(device_id=1):
        return {
            "id": 1,
            "device_id": device_id,
            "timestamp": "2024-01-01T12:00:00Z",
            "data": {
                "hostname": "test-server",
                "status": "success",
                "cpu": {"model": "Intel Core i7", "cores": "8"},
                "memory": {"total": "16G", "used": "8G"},
            },
        }


class TestDatabaseMigrator:
    """Test DatabaseMigrator class."""

    def setup_method(self):
        """Set up test method."""
        self.mock_source = MagicMock()
        self.mock_target = MagicMock()
        self.migrator = DatabaseMigrator(self.mock_source, self.mock_target)

    def test_migrate_devices_success(self):
        """Test successful device migration."""
        # Setup mock devices
        devices = [
            MockDevice.create_sample_device(1, "server-1"),
            MockDevice.create_sample_device(2, "server-2"),
        ]

        self.mock_source.get_all_devices.return_value = devices
        self.mock_target.store_device.side_effect = [10, 20]  # New device IDs

        # Mock history migration
        with patch.object(
            self.migrator, "_migrate_device_history"
        ) as mock_migrate_history:
            migrated_count, error_count = self.migrator.migrate_devices()

        # Verify results
        assert migrated_count == 2
        assert error_count == 0

        # Verify source was queried
        self.mock_source.get_all_devices.assert_called_once()

        # Verify devices were stored in target
        assert self.mock_target.store_device.call_count == 2
        self.mock_target.store_device.assert_has_calls(
            [call(devices[0]), call(devices[1])]
        )

        # Verify history migration was called
        assert mock_migrate_history.call_count == 2
        mock_migrate_history.assert_has_calls([call(1, 10), call(2, 20)])

    def test_migrate_devices_with_timestamp_conversion(self):
        """Test device migration with timestamp format conversion."""
        device = MockDevice.create_sample_device(1, "test-server")
        device["last_seen"] = "2024-01-01T12:00:00Z"  # ISO format with Z

        self.mock_source.get_all_devices.return_value = [device]
        self.mock_target.store_device.return_value = 10

        with patch.object(self.migrator, "_migrate_device_history"):
            migrated_count, error_count = self.migrator.migrate_devices()

        assert migrated_count == 1
        assert error_count == 0

        # Check that timestamp was processed
        stored_device = self.mock_target.store_device.call_args[0][0]
        assert "last_seen" in stored_device

    def test_migrate_devices_with_invalid_timestamp(self):
        """Test device migration with invalid timestamp that gets replaced."""
        device = MockDevice.create_sample_device(1, "test-server")
        device["last_seen"] = "invalid-timestamp"

        self.mock_source.get_all_devices.return_value = [device]
        self.mock_target.store_device.return_value = 10

        with patch.object(self.migrator, "_migrate_device_history"):
            with patch("src.homelab_mcp.migration.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2024-01-02T00:00:00"
                )
                mock_datetime.fromisoformat.side_effect = ValueError(
                    "Invalid timestamp"
                )

                migrated_count, error_count = self.migrator.migrate_devices()

        assert migrated_count == 1
        assert error_count == 0

        # Check that invalid timestamp was replaced
        stored_device = self.mock_target.store_device.call_args[0][0]
        assert stored_device["last_seen"] == "2024-01-02T00:00:00"

    def test_migrate_devices_with_errors(self):
        """Test device migration with some failures."""
        devices = [
            MockDevice.create_sample_device(1, "server-1"),
            MockDevice.create_sample_device(2, "server-2"),
            MockDevice.create_sample_device(3, "server-3"),
        ]

        self.mock_source.get_all_devices.return_value = devices

        # First device succeeds, second fails, third succeeds
        self.mock_target.store_device.side_effect = [
            10,  # Success
            Exception("Database error"),  # Failure
            30,  # Success
        ]

        with patch.object(self.migrator, "_migrate_device_history"):
            with patch("builtins.print"):  # Suppress error printing
                migrated_count, error_count = self.migrator.migrate_devices()

        assert migrated_count == 2
        assert error_count == 1

    def test_migrate_device_history_success(self):
        """Test successful device history migration."""
        source_device_id = 1
        target_device_id = 10

        changes = [MockDevice.create_sample_history(source_device_id)]

        self.mock_source.get_device_changes.return_value = changes

        with patch("src.homelab_mcp.migration.calculate_data_hash") as mock_hash:
            mock_hash.return_value = "test-hash"

            self.migrator._migrate_device_history(source_device_id, target_device_id)

        # Verify source was queried
        self.mock_source.get_device_changes.assert_called_once_with(
            source_device_id, limit=1000
        )

        # Verify history was stored in target
        self.mock_target.store_discovery_history.assert_called_once()
        call_args = self.mock_target.store_discovery_history.call_args
        assert call_args[0][0] == target_device_id  # device_id
        assert '"hostname": "test-server"' in call_args[0][1]  # JSON data
        assert call_args[0][2] == "test-hash"  # hash

    def test_migrate_device_history_with_dict_data(self):
        """Test device history migration when data is dict instead of JSON string."""
        source_device_id = 1
        target_device_id = 10

        history_item = MockDevice.create_sample_history(source_device_id)
        # Data is already a dict, not a JSON string
        changes = [history_item]

        self.mock_source.get_device_changes.return_value = changes

        with patch("src.homelab_mcp.migration.calculate_data_hash") as mock_hash:
            mock_hash.return_value = "test-hash"

            self.migrator._migrate_device_history(source_device_id, target_device_id)

        # Verify data was converted to JSON
        call_args = self.mock_target.store_discovery_history.call_args
        stored_data = call_args[0][1]
        assert isinstance(stored_data, str)
        parsed_data = json.loads(stored_data)
        assert parsed_data["hostname"] == "test-server"

    def test_migrate_device_history_error_handling(self):
        """Test device history migration error handling."""
        source_device_id = 1
        target_device_id = 10

        # Mock source to raise exception
        self.mock_source.get_device_changes.side_effect = Exception(
            "Source database error"
        )

        with patch("builtins.print"):  # Suppress warning printing
            # Should not raise exception, just log warning
            self.migrator._migrate_device_history(source_device_id, target_device_id)

        # Verify target was not called
        self.mock_target.store_discovery_history.assert_not_called()

    def test_verify_migration_success(self):
        """Test successful migration verification."""
        source_devices = [
            MockDevice.create_sample_device(1, "server-1"),
            MockDevice.create_sample_device(2, "server-2"),
        ]
        target_devices = [
            MockDevice.create_sample_device(10, "server-1"),
            MockDevice.create_sample_device(20, "server-2"),
        ]

        self.mock_source.get_all_devices.return_value = source_devices
        self.mock_target.get_all_devices.return_value = target_devices

        with patch("builtins.print"):  # Suppress output
            with patch(
                "random.sample", return_value=source_devices[:1]
            ):  # Sample first device
                result = self.migrator.verify_migration()

        assert result is True

    def test_verify_migration_count_mismatch(self):
        """Test migration verification with device count mismatch."""
        self.mock_source.get_all_devices.return_value = [
            MockDevice.create_sample_device(1)
        ]
        self.mock_target.get_all_devices.return_value = []  # Empty target

        with patch("builtins.print"):  # Suppress output
            result = self.migrator.verify_migration()

        assert result is False

    def test_verify_migration_missing_device(self):
        """Test migration verification with missing device in target."""
        source_devices = [MockDevice.create_sample_device(1, "server-1")]
        target_devices = [MockDevice.create_sample_device(10, "different-server")]

        self.mock_source.get_all_devices.return_value = source_devices
        self.mock_target.get_all_devices.return_value = target_devices

        with patch("builtins.print"):  # Suppress output
            with patch("random.sample", return_value=source_devices):
                result = self.migrator.verify_migration()

        assert result is False

    def test_verify_migration_field_mismatch(self):
        """Test migration verification with field value mismatch."""
        source_device = MockDevice.create_sample_device(1, "server-1")
        target_device = MockDevice.create_sample_device(10, "server-1")
        target_device["cpu_model"] = "Different CPU"  # Mismatch

        self.mock_source.get_all_devices.return_value = [source_device]
        self.mock_target.get_all_devices.return_value = [target_device]

        with patch("builtins.print"):  # Suppress output
            with patch("random.sample", return_value=[source_device]):
                result = self.migrator.verify_migration()

        assert result is False


class TestMigrationFunctions:
    """Test migration helper functions."""

    def setup_method(self):
        """Set up test method."""
        self.original_env = dict(os.environ)
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test method."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.homelab_mcp.migration.SQLiteAdapter")
    @patch("src.homelab_mcp.migration.PostgreSQLAdapter")
    @patch("src.homelab_mcp.migration.DatabaseMigrator")
    def test_migrate_sqlite_to_postgresql_success(
        self, mock_migrator_class, mock_pg_adapter, mock_sqlite_adapter
    ):
        """Test successful SQLite to PostgreSQL migration."""
        # Setup mocks
        mock_sqlite = MagicMock()
        mock_sqlite.get_all_devices.return_value = [MockDevice.create_sample_device()]
        mock_sqlite_adapter.return_value = mock_sqlite

        mock_pg = MagicMock()
        mock_pg_adapter.return_value = mock_pg

        mock_migrator = MagicMock()
        mock_migrator.migrate_devices.return_value = (1, 0)  # 1 migrated, 0 errors
        mock_migrator.verify_migration.return_value = True
        mock_migrator_class.return_value = mock_migrator

        sqlite_path = os.path.join(self.temp_dir, "test.db")
        postgres_params = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "user": "test",
            "password": "test",
        }

        with patch("builtins.print"):  # Suppress output
            result = migrate_sqlite_to_postgresql(
                sqlite_path, postgres_params, dry_run=False
            )

        assert result is True

        # Verify adapters were created
        mock_sqlite_adapter.assert_called_once_with(sqlite_path)
        mock_pg_adapter.assert_called_once_with(postgres_params)

        # Verify connections were established
        mock_sqlite.connect.assert_called_once()
        mock_pg.connect.assert_called_once()
        mock_pg.init_schema.assert_called_once()

        # Verify migration was performed
        mock_migrator_class.assert_called_once_with(mock_sqlite, mock_pg)
        mock_migrator.migrate_devices.assert_called_once()
        mock_migrator.verify_migration.assert_called_once()

        # Verify connections were closed
        mock_sqlite.close.assert_called_once()
        mock_pg.close.assert_called_once()

    @patch("src.homelab_mcp.migration.SQLiteAdapter")
    def test_migrate_sqlite_to_postgresql_no_devices(self, mock_sqlite_adapter):
        """Test migration when source database is empty."""
        mock_sqlite = MagicMock()
        mock_sqlite.get_all_devices.return_value = []
        mock_sqlite_adapter.return_value = mock_sqlite

        sqlite_path = os.path.join(self.temp_dir, "empty.db")

        with patch("builtins.print"):  # Suppress output
            result = migrate_sqlite_to_postgresql(sqlite_path, dry_run=False)

        assert result is True
        mock_sqlite.connect.assert_called_once()
        mock_sqlite.close.assert_called_once()

    @patch("src.homelab_mcp.migration.SQLiteAdapter")
    def test_migrate_sqlite_to_postgresql_dry_run(self, mock_sqlite_adapter):
        """Test dry run migration."""
        mock_sqlite = MagicMock()
        mock_sqlite.get_all_devices.return_value = [MockDevice.create_sample_device()]
        mock_sqlite_adapter.return_value = mock_sqlite

        sqlite_path = os.path.join(self.temp_dir, "test.db")

        with patch("builtins.print"):  # Suppress output
            result = migrate_sqlite_to_postgresql(sqlite_path, dry_run=True)

        assert result is True
        mock_sqlite.connect.assert_called_once()
        mock_sqlite.close.assert_called_once()
        # No PostgreSQL operations should be performed in dry run

    def test_migrate_sqlite_to_postgresql_missing_psycopg2(self):
        """Test migration failure when psycopg2 is not available."""
        with patch("builtins.print"):  # Suppress output
            with patch(
                "src.homelab_mcp.migration.PostgreSQLAdapter",
                side_effect=ImportError("No module named 'psycopg2'"),
            ):
                result = migrate_sqlite_to_postgresql("/test/path.db", dry_run=False)

        assert result is False

    @patch("src.homelab_mcp.migration.SQLiteAdapter")
    def test_migrate_sqlite_to_postgresql_connection_error(self, mock_sqlite_adapter):
        """Test migration failure due to connection error."""
        mock_sqlite = MagicMock()
        mock_sqlite.connect.side_effect = Exception("Connection failed")
        mock_sqlite_adapter.return_value = mock_sqlite

        with patch("builtins.print"):  # Suppress output
            result = migrate_sqlite_to_postgresql("/test/path.db", dry_run=False)

        assert result is False

    @patch("src.homelab_mcp.migration.PostgreSQLAdapter")
    def test_setup_postgresql_database_success(self, mock_pg_adapter):
        """Test successful PostgreSQL database setup."""
        mock_pg = MagicMock()
        mock_pg_adapter.return_value = mock_pg

        postgres_params = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "user": "test",
            "password": "test",
        }

        with patch("builtins.print"):  # Suppress output
            result = setup_postgresql_database(postgres_params)

        assert result is True
        mock_pg_adapter.assert_called_once_with(postgres_params)
        mock_pg.connect.assert_called_once()
        mock_pg.init_schema.assert_called_once()
        mock_pg.close.assert_called_once()

    def test_setup_postgresql_database_missing_psycopg2(self):
        """Test PostgreSQL setup failure when psycopg2 is not available."""
        with patch("builtins.print"):  # Suppress output
            with patch(
                "src.homelab_mcp.migration.PostgreSQLAdapter",
                side_effect=ImportError("No module named 'psycopg2'"),
            ):
                result = setup_postgresql_database()

        assert result is False

    @patch("src.homelab_mcp.migration.PostgreSQLAdapter")
    def test_setup_postgresql_database_connection_error(self, mock_pg_adapter):
        """Test PostgreSQL setup failure due to connection error."""
        mock_pg = MagicMock()
        mock_pg.connect.side_effect = Exception("Connection refused")
        mock_pg_adapter.return_value = mock_pg

        with patch("builtins.print"):  # Suppress output
            result = setup_postgresql_database()

        assert result is False

    def test_create_postgres_config_template(self):
        """Test PostgreSQL configuration template creation."""
        template = create_postgres_config_template()

        assert isinstance(template, str)
        assert "DATABASE_TYPE=postgresql" in template
        assert "POSTGRES_HOST=" in template
        assert "POSTGRES_PORT=" in template
        assert "POSTGRES_DB=" in template
        assert "POSTGRES_USER=" in template
        assert "POSTGRES_PASSWORD=" in template
        assert "docker compose" in template.lower()  # Should include docker example


class TestMigrationCLI:
    """Test migration command-line interface."""

    @patch("src.homelab_mcp.migration.setup_postgresql_database")
    @patch("sys.argv", ["migration.py", "setup", "--password", "testpass"])
    def test_main_setup_command(self, mock_setup):
        """Test CLI setup command."""
        mock_setup.return_value = True

        with patch("sys.exit") as mock_exit:
            main()

        mock_setup.assert_called_once()
        setup_args = mock_setup.call_args[0][0]
        assert setup_args["host"] == "localhost"
        assert setup_args["port"] == 5432
        assert setup_args["database"] == "homelab_mcp"
        assert setup_args["user"] == "postgres"
        assert setup_args["password"] == "testpass"

        mock_exit.assert_called_once_with(0)

    @patch("src.homelab_mcp.migration.setup_postgresql_database")
    @patch(
        "sys.argv",
        [
            "migration.py",
            "setup",
            "--password",
            "testpass",
            "--host",
            "custom-host",
            "--port",
            "5433",
        ],
    )
    def test_main_setup_command_custom_params(self, mock_setup):
        """Test CLI setup command with custom parameters."""
        mock_setup.return_value = True

        with patch("sys.exit") as mock_exit:
            main()

        setup_args = mock_setup.call_args[0][0]
        assert setup_args["host"] == "custom-host"
        assert setup_args["port"] == 5433
        assert setup_args["password"] == "testpass"

        mock_exit.assert_called_once_with(0)

    @patch("src.homelab_mcp.migration.migrate_sqlite_to_postgresql")
    @patch("sys.argv", ["migration.py", "migrate", "--password", "testpass"])
    def test_main_migrate_command(self, mock_migrate):
        """Test CLI migrate command."""
        mock_migrate.return_value = True

        with patch("sys.exit") as mock_exit:
            main()

        mock_migrate.assert_called_once()
        call_args = mock_migrate.call_args

        # Check that postgres_params were passed correctly
        postgres_params = call_args[1]["postgres_params"]
        assert postgres_params["host"] == "localhost"
        assert postgres_params["password"] == "testpass"
        assert call_args[1]["dry_run"] is False

        mock_exit.assert_called_once_with(0)

    @patch("src.homelab_mcp.migration.migrate_sqlite_to_postgresql")
    @patch(
        "sys.argv",
        [
            "migration.py",
            "migrate",
            "--password",
            "testpass",
            "--dry-run",
            "--sqlite-path",
            "/custom/path.db",
        ],
    )
    def test_main_migrate_command_dry_run(self, mock_migrate):
        """Test CLI migrate command with dry run and custom path."""
        mock_migrate.return_value = True

        with patch("sys.exit") as mock_exit:
            main()

        call_args = mock_migrate.call_args
        assert call_args[1]["sqlite_path"] == "/custom/path.db"
        assert call_args[1]["dry_run"] is True

        mock_exit.assert_called_once_with(0)

    @patch("src.homelab_mcp.migration.create_postgres_config_template")
    @patch("sys.argv", ["migration.py", "config"])
    def test_main_config_command(self, mock_template):
        """Test CLI config command."""
        mock_template.return_value = "# Test template"

        with patch("builtins.print") as mock_print:
            main()

        mock_template.assert_called_once()
        mock_print.assert_called_once_with("# Test template")

    @patch("sys.argv", ["migration.py", "invalid"])
    def test_main_invalid_command(self):
        """Test CLI with invalid command."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2

    @patch("sys.argv", ["migration.py"])
    def test_main_no_command(self):
        """Test CLI with no command."""
        with patch("argparse.ArgumentParser.print_help") as mock_help:
            main()

        mock_help.assert_called_once()

    @patch("src.homelab_mcp.migration.setup_postgresql_database")
    @patch("sys.argv", ["migration.py", "setup", "--password", "testpass"])
    def test_main_setup_failure(self, mock_setup):
        """Test CLI setup command failure."""
        mock_setup.return_value = False

        with patch("sys.exit") as mock_exit:
            main()

        mock_exit.assert_called_once_with(1)

    @patch("src.homelab_mcp.migration.migrate_sqlite_to_postgresql")
    @patch("sys.argv", ["migration.py", "migrate", "--password", "testpass"])
    def test_main_migrate_failure(self, mock_migrate):
        """Test CLI migrate command failure."""
        mock_migrate.return_value = False

        with patch("sys.exit") as mock_exit:
            main()

        mock_exit.assert_called_once_with(1)


class TestMigrationIntegration:
    """Integration tests for migration functionality."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test method."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_migration_workflow_with_mocks(self):
        """Test complete migration workflow with mocked database adapters."""
        # Create mock source and target adapters
        mock_source = MagicMock()
        mock_target = MagicMock()

        # Setup sample data
        devices = [
            MockDevice.create_sample_device(1, "server-1"),
            MockDevice.create_sample_device(2, "server-2"),
        ]
        history = [MockDevice.create_sample_history(1)]

        mock_source.get_all_devices.return_value = devices
        mock_source.get_device_changes.return_value = history
        mock_target.store_device.side_effect = [10, 20]

        # Setup target devices for verification (same devices with different IDs)
        target_devices = [
            MockDevice.create_sample_device(10, "server-1"),
            MockDevice.create_sample_device(20, "server-2"),
        ]
        mock_target.get_all_devices.return_value = target_devices

        # Create migrator and run migration
        migrator = DatabaseMigrator(mock_source, mock_target)

        with patch(
            "src.homelab_mcp.migration.calculate_data_hash", return_value="test-hash"
        ):
            with patch("builtins.print"):  # Suppress output
                # Migrate devices
                migrated_count, error_count = migrator.migrate_devices()

                # Verify migration
                verification_result = migrator.verify_migration()

        # Verify results
        assert migrated_count == 2
        assert error_count == 0
        assert verification_result is True

        # Verify all expected calls were made
        mock_source.get_all_devices.assert_called()
        assert mock_target.store_device.call_count == 2
        assert mock_target.store_discovery_history.call_count == 2
