"""Tests for configuration management."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from src.homelab_mcp.config import (
    DatabaseConfig,
    MCPConfig,
    create_database_from_config,
    get_config,
    print_config_info,
)


class TestDatabaseConfig:
    """Test DatabaseConfig class."""

    def setup_method(self):
        """Set up test method."""
        # Store original environment to restore later
        self.original_env = dict(os.environ)

    def teardown_method(self):
        """Clean up test method."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_default_sqlite_config(self):
        """Test default SQLite configuration."""
        # Clear relevant environment variables
        for key in ["DATABASE_TYPE", "SQLITE_PATH"]:
            os.environ.pop(key, None)

        config = DatabaseConfig()

        assert config.db_type == "sqlite"
        assert config.sqlite_path is not None
        assert ".mcp" in config.sqlite_path
        assert config.sqlite_path.endswith("sitemap.db")

    def test_custom_sqlite_path(self):
        """Test custom SQLite path from environment."""
        custom_path = "/custom/path/test.db"
        os.environ["SQLITE_PATH"] = custom_path

        config = DatabaseConfig()

        assert config.db_type == "sqlite"
        assert config.sqlite_path == custom_path

    def test_postgresql_config_from_env(self):
        """Test PostgreSQL configuration from environment variables."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "test-host"
        os.environ["POSTGRES_PORT"] = "5433"
        os.environ["POSTGRES_DB"] = "test-db"
        os.environ["POSTGRES_USER"] = "test-user"
        os.environ["POSTGRES_PASSWORD"] = "test-pass"

        config = DatabaseConfig()

        assert config.db_type == "postgresql"
        assert config.postgres_config["host"] == "test-host"
        assert config.postgres_config["port"] == 5433
        assert config.postgres_config["database"] == "test-db"
        assert config.postgres_config["user"] == "test-user"
        assert config.postgres_config["password"] == "test-pass"

    def test_postgresql_default_values(self):
        """Test PostgreSQL configuration with default values."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        # Don't set specific postgres env vars to test defaults
        for key in [
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        ]:
            os.environ.pop(key, None)

        config = DatabaseConfig()

        assert config.postgres_config["host"] == "localhost"
        assert config.postgres_config["port"] == 5432
        assert config.postgres_config["database"] == "homelab_mcp"
        assert config.postgres_config["user"] == "postgres"
        assert config.postgres_config["password"] == "password"

    def test_get_database_params_sqlite(self):
        """Test getting database parameters for SQLite."""
        os.environ["DATABASE_TYPE"] = "sqlite"
        os.environ["SQLITE_PATH"] = "/test/path.db"

        config = DatabaseConfig()
        params = config.get_database_params()

        assert params["db_type"] == "sqlite"
        assert params["db_path"] == "/test/path.db"
        assert "connection_params" not in params

    def test_get_database_params_postgresql(self):
        """Test getting database parameters for PostgreSQL."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "pg-host"

        config = DatabaseConfig()
        params = config.get_database_params()

        assert params["db_type"] == "postgresql"
        assert "connection_params" in params
        assert params["connection_params"]["host"] == "pg-host"
        assert "db_path" not in params

    def test_is_postgresql_configured_true(self):
        """Test PostgreSQL configuration validation when properly configured."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "localhost"
        os.environ["POSTGRES_DB"] = "test"
        os.environ["POSTGRES_USER"] = "user"
        os.environ["POSTGRES_PASSWORD"] = "pass"

        config = DatabaseConfig()

        assert config.is_postgresql_configured() is True

    def test_is_postgresql_configured_false_missing_vars(self):
        """Test PostgreSQL configuration validation with missing variables."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "localhost"
        # Missing other required vars
        for key in ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]:
            os.environ.pop(key, None)

        config = DatabaseConfig()

        assert config.is_postgresql_configured() is False

    def test_is_postgresql_configured_false_sqlite(self):
        """Test PostgreSQL configuration validation when using SQLite."""
        os.environ["DATABASE_TYPE"] = "sqlite"

        config = DatabaseConfig()

        assert config.is_postgresql_configured() is False

    @patch("src.homelab_mcp.config.Path.home")
    def test_sqlite_path_home_directory_failure(self, mock_home):
        """Test SQLite path fallback when home directory access fails."""
        # Mock Path.home() to raise RuntimeError
        mock_home.side_effect = RuntimeError("Home directory not accessible")

        # Clear SQLITE_PATH to force home directory usage
        os.environ.pop("SQLITE_PATH", None)

        with patch("src.homelab_mcp.config.Path.cwd") as mock_cwd:
            # Create proper mock Path objects
            mock_current_dir = MagicMock()
            mock_mcp_dir = MagicMock()
            mock_db_path = MagicMock()

            # Set up path operations
            mock_current_dir.__truediv__.return_value = mock_mcp_dir
            mock_mcp_dir.__truediv__.return_value = mock_db_path
            mock_mcp_dir.mkdir = MagicMock()

            # Return string when converting to str
            mock_db_path.__str__ = MagicMock(
                return_value="/current/dir/.mcp/sitemap.db"
            )

            mock_cwd.return_value = mock_current_dir

            config = DatabaseConfig()

            # Should fallback to current directory
            mock_cwd.assert_called_once()
            mock_mcp_dir.mkdir.assert_called_once_with(exist_ok=True)
            assert config.sqlite_path == "/current/dir/.mcp/sitemap.db"


class TestMCPConfig:
    """Test MCPConfig class."""

    def setup_method(self):
        """Set up test method."""
        # Store original environment to restore later
        self.original_env = dict(os.environ)

    def teardown_method(self):
        """Clean up test method."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_default_config(self):
        """Test default MCP configuration."""
        # Clear all relevant environment variables
        env_vars = [
            "MCP_DEBUG",
            "MCP_LOG_LEVEL",
            "SSH_TIMEOUT",
            "SSH_RETRIES",
            "DISCOVERY_BATCH_SIZE",
            "DISCOVERY_TIMEOUT",
            "ENABLE_POSTGRESQL",
            "ENABLE_RESOURCE_POOLS",
        ]
        for var in env_vars:
            os.environ.pop(var, None)

        config = MCPConfig()

        assert config.debug is False
        assert config.log_level == "INFO"
        assert config.ssh_timeout == 10
        assert config.ssh_retries == 3
        assert config.discovery_batch_size == 10
        assert config.discovery_timeout == 300
        assert config.enable_postgresql is False
        assert config.enable_resource_pools is False
        assert isinstance(config.database, DatabaseConfig)

    def test_config_from_environment(self):
        """Test MCP configuration from environment variables."""
        os.environ["MCP_DEBUG"] = "true"
        os.environ["MCP_LOG_LEVEL"] = "DEBUG"
        os.environ["SSH_TIMEOUT"] = "30"
        os.environ["SSH_RETRIES"] = "5"
        os.environ["DISCOVERY_BATCH_SIZE"] = "20"
        os.environ["DISCOVERY_TIMEOUT"] = "600"
        os.environ["ENABLE_POSTGRESQL"] = "true"
        os.environ["ENABLE_RESOURCE_POOLS"] = "true"

        config = MCPConfig()

        assert config.debug is True
        assert config.log_level == "DEBUG"
        assert config.ssh_timeout == 30
        assert config.ssh_retries == 5
        assert config.discovery_batch_size == 20
        assert config.discovery_timeout == 600
        assert config.enable_postgresql is True
        assert config.enable_resource_pools is True

    def test_boolean_parsing_variations(self):
        """Test boolean parsing with different string variations."""
        # Test debug flag with different values
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("1", False),  # Only 'true' should be True
            ("yes", False),
            ("", False),
        ]

        for env_value, expected in test_cases:
            os.environ["MCP_DEBUG"] = env_value
            config = MCPConfig()
            assert (
                config.debug is expected
            ), f"Failed for '{env_value}', expected {expected}, got {config.debug}"

    def test_validate_success(self):
        """Test successful configuration validation."""
        os.environ["DATABASE_TYPE"] = "sqlite"
        os.environ["SSH_TIMEOUT"] = "10"
        os.environ["DISCOVERY_TIMEOUT"] = "300"

        config = MCPConfig()
        errors = config.validate()

        assert len(errors) == 0

    def test_validate_postgresql_not_configured(self):
        """Test validation error for unconfigured PostgreSQL."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        # Don't set PostgreSQL environment variables
        for key in [
            "POSTGRES_HOST",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        ]:
            os.environ.pop(key, None)

        config = MCPConfig()
        errors = config.validate()

        assert len(errors) >= 1
        assert any(
            "PostgreSQL is selected but not properly configured" in error
            for error in errors
        )

    def test_validate_invalid_timeouts(self):
        """Test validation errors for invalid timeout values."""
        os.environ["SSH_TIMEOUT"] = "0"
        os.environ["DISCOVERY_TIMEOUT"] = "-10"

        config = MCPConfig()
        errors = config.validate()

        assert len(errors) >= 2
        assert any("SSH_TIMEOUT must be greater than 0" in error for error in errors)
        assert any(
            "DISCOVERY_TIMEOUT must be greater than 0" in error for error in errors
        )

    def test_validate_postgresql_missing_psycopg2(self):
        """Test validation error when psycopg2 is not installed."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "localhost"
        os.environ["POSTGRES_DB"] = "test"
        os.environ["POSTGRES_USER"] = "user"
        os.environ["POSTGRES_PASSWORD"] = "pass"

        config = MCPConfig()

        # Patch the import inside validate method
        with patch(
            "builtins.__import__", side_effect=ImportError("No module named 'psycopg2'")
        ):
            errors = config.validate()

        assert len(errors) >= 1
        assert any("psycopg2 is not installed" in error for error in errors)


class TestConfigHelperFunctions:
    """Test configuration helper functions."""

    def setup_method(self):
        """Set up test method."""
        self.original_env = dict(os.environ)

    def teardown_method(self):
        """Clean up test method."""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_get_config(self):
        """Test get_config function."""
        config = get_config()

        assert isinstance(config, MCPConfig)
        assert isinstance(config.database, DatabaseConfig)

    @patch("src.homelab_mcp.sitemap.NetworkSiteMap")
    def test_create_database_from_config_default(self, mock_sitemap):
        """Test creating database from default config."""
        mock_sitemap_instance = MagicMock()
        mock_sitemap.return_value = mock_sitemap_instance

        result = create_database_from_config()

        assert result == mock_sitemap_instance
        mock_sitemap.assert_called_once()
        # Check that database parameters were passed
        call_args = mock_sitemap.call_args
        assert "db_type" in call_args.kwargs or len(call_args.args) > 0

    @patch("src.homelab_mcp.sitemap.NetworkSiteMap")
    def test_create_database_from_config_custom(self, mock_sitemap):
        """Test creating database from custom config."""
        mock_sitemap_instance = MagicMock()
        mock_sitemap.return_value = mock_sitemap_instance

        # Create custom config
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "custom-host"
        custom_config = MCPConfig()

        result = create_database_from_config(custom_config)

        assert result == mock_sitemap_instance
        mock_sitemap.assert_called_once()

        # Verify PostgreSQL parameters were used
        call_args = mock_sitemap.call_args
        if call_args.kwargs:
            assert call_args.kwargs.get("db_type") == "postgresql"

    @patch("builtins.print")
    def test_print_config_info_sqlite(self, mock_print):
        """Test printing SQLite configuration info."""
        os.environ["DATABASE_TYPE"] = "sqlite"
        os.environ["SQLITE_PATH"] = "/test/path.db"
        os.environ["MCP_DEBUG"] = "true"

        print_config_info()

        # Check that print was called with config information
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        printed_text = "\n".join(print_calls)

        assert "Homelab MCP Configuration" in printed_text
        assert "Database Type: sqlite" in printed_text
        assert "SQLite Path: /test/path.db" in printed_text
        assert "Debug Mode: True" in printed_text

    @patch("builtins.print")
    def test_print_config_info_postgresql(self, mock_print):
        """Test printing PostgreSQL configuration info."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "pg-host"
        os.environ["POSTGRES_PORT"] = "5433"
        os.environ["POSTGRES_DB"] = "pg-db"
        os.environ["POSTGRES_USER"] = "pg-user"
        os.environ["POSTGRES_PASSWORD"] = "pg-pass"

        print_config_info()

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        printed_text = "\n".join(print_calls)

        assert "Database Type: postgresql" in printed_text
        assert "PostgreSQL Host: pg-host:5433" in printed_text
        assert "PostgreSQL Database: pg-db" in printed_text
        assert "PostgreSQL User: pg-user" in printed_text
        assert "[CONFIGURED]" in printed_text  # Password should be masked
        assert "pg-pass" not in printed_text  # Password should not be visible

    @patch("builtins.print")
    def test_print_config_info_with_errors(self, mock_print):
        """Test printing configuration info with validation errors."""
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["SSH_TIMEOUT"] = "0"  # Invalid value
        # Don't set PostgreSQL vars to cause validation error
        for key in [
            "POSTGRES_HOST",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        ]:
            os.environ.pop(key, None)

        print_config_info()

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        printed_text = "\n".join(print_calls)

        assert "Configuration Errors" in printed_text
        assert "ERROR:" in printed_text
        assert "PostgreSQL is selected but not properly configured" in printed_text

    @patch("builtins.print")
    def test_print_config_info_valid_config(self, mock_print):
        """Test printing valid configuration info."""
        os.environ["DATABASE_TYPE"] = "sqlite"
        os.environ["SSH_TIMEOUT"] = "10"
        os.environ["DISCOVERY_TIMEOUT"] = "300"

        print_config_info()

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        printed_text = "\n".join(print_calls)

        assert "✓ Configuration is valid" in printed_text


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def setup_method(self):
        """Set up test method."""
        self.original_env = dict(os.environ)
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test method."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_sqlite_config_workflow(self):
        """Test complete SQLite configuration workflow."""
        # Set up SQLite configuration
        sqlite_path = os.path.join(self.temp_dir, "test.db")
        os.environ["DATABASE_TYPE"] = "sqlite"
        os.environ["SQLITE_PATH"] = sqlite_path
        os.environ["MCP_DEBUG"] = "true"
        os.environ["SSH_TIMEOUT"] = "15"

        # Get configuration
        config = get_config()

        # Validate configuration structure
        assert isinstance(config, MCPConfig)
        assert config.database.db_type == "sqlite"
        assert config.database.sqlite_path == sqlite_path
        assert config.debug is True
        assert config.ssh_timeout == 15

        # Validate database parameters
        db_params = config.database.get_database_params()
        assert db_params["db_type"] == "sqlite"
        assert db_params["db_path"] == sqlite_path

        # Validate configuration
        errors = config.validate()
        assert len(errors) == 0

        # Test that PostgreSQL is not configured
        assert not config.database.is_postgresql_configured()

    def test_full_postgresql_config_workflow(self):
        """Test complete PostgreSQL configuration workflow."""
        # Set up PostgreSQL configuration
        os.environ["DATABASE_TYPE"] = "postgresql"
        os.environ["POSTGRES_HOST"] = "test-host"
        os.environ["POSTGRES_PORT"] = "5433"
        os.environ["POSTGRES_DB"] = "test-db"
        os.environ["POSTGRES_USER"] = "test-user"
        os.environ["POSTGRES_PASSWORD"] = "test-pass"
        os.environ["ENABLE_POSTGRESQL"] = "true"

        # Get configuration
        config = get_config()

        # Validate configuration structure
        assert isinstance(config, MCPConfig)
        assert config.database.db_type == "postgresql"
        assert config.enable_postgresql is True

        # Validate database parameters
        db_params = config.database.get_database_params()
        assert db_params["db_type"] == "postgresql"
        assert db_params["connection_params"]["host"] == "test-host"
        assert db_params["connection_params"]["port"] == 5433
        assert db_params["connection_params"]["database"] == "test-db"
        assert db_params["connection_params"]["user"] == "test-user"
        assert db_params["connection_params"]["password"] == "test-pass"

        # Test that PostgreSQL is configured
        assert config.database.is_postgresql_configured()
