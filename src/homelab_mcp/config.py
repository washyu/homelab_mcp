"""Configuration management for the homelab MCP server."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .sitemap import NetworkSiteMap


class DatabaseConfig:
    """Database configuration settings."""

    def __init__(self) -> None:
        self.db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()

        # SQLite configuration
        self.sqlite_path = os.getenv("SQLITE_PATH")
        if not self.sqlite_path:
            try:
                home_dir = Path.home()
                mcp_dir = home_dir / ".mcp"
                mcp_dir.mkdir(exist_ok=True)
                self.sqlite_path = str(mcp_dir / "sitemap.db")
            except (RuntimeError, OSError):
                # Fallback to current directory if home directory cannot be determined
                current_dir = Path.cwd()
                mcp_dir = current_dir / ".mcp"
                mcp_dir.mkdir(exist_ok=True)
                self.sqlite_path = str(mcp_dir / "sitemap.db")

        # PostgreSQL configuration
        self.postgres_config = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "homelab_mcp"),
            "user": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", "password"),
        }

    def get_database_params(self) -> dict[str, Any]:
        """Get database parameters for the current configuration."""
        if self.db_type == "postgresql":
            return {"db_type": "postgresql", "connection_params": self.postgres_config}
        else:  # Default to SQLite
            return {"db_type": "sqlite", "db_path": self.sqlite_path}

    def is_postgresql_configured(self) -> bool:
        """Check if PostgreSQL is properly configured."""
        if self.db_type != "postgresql":
            return False

        # Check if required environment variables are set
        required_vars = [
            "POSTGRES_HOST",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        ]
        return all(os.getenv(var) for var in required_vars)


class MCPConfig:
    """Main MCP server configuration."""

    def __init__(self) -> None:
        self.database = DatabaseConfig()

        # Server configuration
        self.debug = os.getenv("MCP_DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()

        # SSH configuration
        self.ssh_timeout = int(os.getenv("SSH_TIMEOUT", "10"))
        self.ssh_retries = int(os.getenv("SSH_RETRIES", "3"))

        # Discovery configuration
        self.discovery_batch_size = int(os.getenv("DISCOVERY_BATCH_SIZE", "10"))
        self.discovery_timeout = int(os.getenv("DISCOVERY_TIMEOUT", "300"))  # 5 minutes

        # Feature flags
        self.enable_postgresql = (
            os.getenv("ENABLE_POSTGRESQL", "false").lower() == "true"
        )
        self.enable_resource_pools = (
            os.getenv("ENABLE_RESOURCE_POOLS", "false").lower() == "true"
        )

    def validate(self) -> list[str]:
        """Validate configuration and return any errors."""
        errors = []

        # Database validation
        if self.database.db_type == "postgresql":
            if not self.database.is_postgresql_configured():
                errors.append(
                    "PostgreSQL is selected but not properly configured. "
                    "Required: POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD"
                )

            try:
                import importlib.util

                if importlib.util.find_spec("psycopg2") is None:
                    raise ImportError("psycopg2 not found")
            except ImportError:
                errors.append(
                    "PostgreSQL selected but psycopg2 is not installed. "
                    "Install with: pip install psycopg2-binary"
                )

        # Timeout validation
        if self.ssh_timeout <= 0:
            errors.append("SSH_TIMEOUT must be greater than 0")

        if self.discovery_timeout <= 0:
            errors.append("DISCOVERY_TIMEOUT must be greater than 0")

        return errors


def get_config() -> MCPConfig:
    """Get the current MCP configuration."""
    return MCPConfig()


def create_database_from_config(config: MCPConfig | None = None) -> "NetworkSiteMap":
    """Create a NetworkSiteMap instance from configuration."""
    if config is None:
        config = get_config()

    from .sitemap import NetworkSiteMap

    db_params = config.database.get_database_params()
    return NetworkSiteMap(**db_params)


def print_config_info(config: MCPConfig | None = None) -> None:
    """Print current configuration information."""
    if config is None:
        config = get_config()

    print("=== Homelab MCP Configuration ===")
    print(f"Database Type: {config.database.db_type}")

    if config.database.db_type == "postgresql":
        pg_config = config.database.postgres_config
        print(f"PostgreSQL Host: {pg_config['host']}:{pg_config['port']}")
        print(f"PostgreSQL Database: {pg_config['database']}")
        print(f"PostgreSQL User: {pg_config['user']}")
        print(
            "PostgreSQL Password: [CONFIGURED]"
            if pg_config["password"]
            else "PostgreSQL Password: [NOT SET]"
        )
    else:
        print(f"SQLite Path: {config.database.sqlite_path}")

    print(f"Debug Mode: {config.debug}")
    print(f"Log Level: {config.log_level}")
    print(f"SSH Timeout: {config.ssh_timeout}s")
    print(f"Discovery Batch Size: {config.discovery_batch_size}")

    # Validate configuration
    errors = config.validate()
    if errors:
        print("\n=== Configuration Errors ===")
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("\n✓ Configuration is valid")

    print("=" * 35)
