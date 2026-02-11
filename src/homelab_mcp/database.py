"""Database abstraction layer for network sitemap functionality."""

import hashlib
import json
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import psycopg2
    import psycopg2.extras

    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""

    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def init_schema(self) -> None:
        """Initialize database schema."""
        pass

    @abstractmethod
    def store_device(self, device_data: dict[str, Any]) -> int:
        """Store or update a device record."""
        pass

    @abstractmethod
    def get_all_devices(self) -> list[dict[str, Any]]:
        """Get all devices from the database."""
        pass

    @abstractmethod
    def store_discovery_history(self, device_id: int, discovery_data: str, data_hash: str) -> None:
        """Store discovery history record."""
        pass

    @abstractmethod
    def get_device_changes(self, device_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get change history for a device."""
        pass

    @abstractmethod
    def execute_query(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query and return results."""
        pass

    # SSH Credentials CRUD methods
    @abstractmethod
    def add_credential(
        self,
        hostname: str,
        username: str = "mcp_admin",
        key_path: str | None = None,
        port: int = 22,
        display_name: str | None = None,
        device_id: int | None = None,
    ) -> int:
        """Add a new SSH credential record."""
        pass

    @abstractmethod
    def get_credential(self, credential_id: int) -> dict[str, Any] | None:
        """Get a credential by its ID."""
        pass

    @abstractmethod
    def get_credential_by_hostname(self, hostname: str, username: str | None = None) -> dict[str, Any] | None:
        """Get credential by hostname and optionally username."""
        pass

    @abstractmethod
    def update_credential(self, credential_id: int, **kwargs: Any) -> bool:
        """Update a credential record."""
        pass

    @abstractmethod
    def delete_credential(self, credential_id: int) -> bool:
        """Delete a credential record."""
        pass

    @abstractmethod
    def list_credentials(self, active_only: bool = True) -> list[dict[str, Any]]:
        """List all credentials."""
        pass

    @abstractmethod
    def update_last_verified(self, credential_id: int) -> bool:
        """Update the last_verified timestamp for a credential."""
        pass


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            # Default to ~/.mcp/sitemap.db
            try:
                home_dir = Path.home()
                mcp_dir = home_dir / ".mcp"
                mcp_dir.mkdir(exist_ok=True)
                db_path = str(mcp_dir / "sitemap.db")
            except (RuntimeError, OSError):
                # Fallback to current directory if home directory cannot be determined
                current_dir = Path.cwd()
                mcp_dir = current_dir / ".mcp"
                mcp_dir.mkdir(exist_ok=True)
                db_path = str(mcp_dir / "sitemap.db")

        self.db_path = db_path
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Establish SQLite connection."""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close SQLite connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def init_schema(self) -> None:
        """Initialize SQLite schema."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        # Create devices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname TEXT NOT NULL,
                connection_ip TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                status TEXT NOT NULL,
                cpu_model TEXT,
                cpu_cores INTEGER,
                memory_total TEXT,
                memory_used TEXT,
                memory_free TEXT,
                memory_available TEXT,
                disk_filesystem TEXT,
                disk_size TEXT,
                disk_used TEXT,
                disk_available TEXT,
                disk_use_percent TEXT,
                disk_mount TEXT,
                network_interfaces TEXT,
                uptime TEXT,
                os_info TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(hostname, connection_ip)
            )
        """)

        # Create discovery history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                discovery_data TEXT,
                data_hash TEXT,
                discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices (id)
            )
        """)

        # Create ssh_credentials table for persistent credential storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ssh_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                hostname TEXT NOT NULL,
                username TEXT NOT NULL DEFAULT 'mcp_admin',
                key_path TEXT,
                port INTEGER DEFAULT 22,
                display_name TEXT,
                is_active INTEGER DEFAULT 1,
                last_verified TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(hostname, username),
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_hostname_ip
            ON devices (hostname, connection_ip)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_device_id
            ON discovery_history (device_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ssh_credentials_hostname
            ON ssh_credentials (hostname)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ssh_credentials_device_id
            ON ssh_credentials (device_id)
        """)

        self.connection.commit()

    def store_device(self, device_data: dict[str, Any]) -> int:
        """Store or update a device in SQLite."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        # Check if device exists
        cursor.execute(
            """
            SELECT id FROM devices
            WHERE hostname = ? AND connection_ip = ?
        """,
            (device_data["hostname"], device_data["connection_ip"]),
        )

        existing = cursor.fetchone()

        if existing:
            # Update existing device
            device_id: int = existing[0]
            cursor.execute(
                """
                UPDATE devices SET
                    last_seen = ?, status = ?, cpu_model = ?, cpu_cores = ?,
                    memory_total = ?, memory_used = ?, memory_free = ?, memory_available = ?,
                    disk_filesystem = ?, disk_size = ?, disk_used = ?, disk_available = ?,
                    disk_use_percent = ?, disk_mount = ?, network_interfaces = ?,
                    uptime = ?, os_info = ?, error_message = ?, updated_at = ?
                WHERE id = ?
            """,
                (
                    device_data["last_seen"],
                    device_data["status"],
                    device_data.get("cpu_model"),
                    device_data.get("cpu_cores"),
                    device_data.get("memory_total"),
                    device_data.get("memory_used"),
                    device_data.get("memory_free"),
                    device_data.get("memory_available"),
                    device_data.get("disk_filesystem"),
                    device_data.get("disk_size"),
                    device_data.get("disk_used"),
                    device_data.get("disk_available"),
                    device_data.get("disk_use_percent"),
                    device_data.get("disk_mount"),
                    device_data.get("network_interfaces"),
                    device_data.get("uptime"),
                    device_data.get("os_info"),
                    device_data.get("error_message"),
                    datetime.now().isoformat(),
                    device_id,
                ),
            )
        else:
            # Insert new device
            cursor.execute(
                """
                INSERT INTO devices (
                    hostname, connection_ip, last_seen, status, cpu_model, cpu_cores,
                    memory_total, memory_used, memory_free, memory_available,
                    disk_filesystem, disk_size, disk_used, disk_available,
                    disk_use_percent, disk_mount, network_interfaces,
                    uptime, os_info, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    device_data["hostname"],
                    device_data["connection_ip"],
                    device_data["last_seen"],
                    device_data["status"],
                    device_data.get("cpu_model"),
                    device_data.get("cpu_cores"),
                    device_data.get("memory_total"),
                    device_data.get("memory_used"),
                    device_data.get("memory_free"),
                    device_data.get("memory_available"),
                    device_data.get("disk_filesystem"),
                    device_data.get("disk_size"),
                    device_data.get("disk_used"),
                    device_data.get("disk_available"),
                    device_data.get("disk_use_percent"),
                    device_data.get("disk_mount"),
                    device_data.get("network_interfaces"),
                    device_data.get("uptime"),
                    device_data.get("os_info"),
                    device_data.get("error_message"),
                ),
            )
            lastrowid = cursor.lastrowid
            assert lastrowid is not None
            device_id = lastrowid

        self.connection.commit()
        return device_id

    def get_all_devices(self) -> list[dict[str, Any]]:
        """Get all devices from SQLite."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM devices ORDER BY hostname, connection_ip")

        devices = []
        for row in cursor.fetchall():
            device_dict = dict(row)
            # Parse network interfaces JSON
            if device_dict.get("network_interfaces"):
                try:
                    device_dict["network_interfaces"] = json.loads(device_dict["network_interfaces"])
                except json.JSONDecodeError:
                    device_dict["network_interfaces"] = []

            devices.append(device_dict)

        return devices

    def store_discovery_history(self, device_id: int, discovery_data: str, data_hash: str) -> None:
        """Store discovery history in SQLite."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        # Check if this exact data was already stored recently
        cursor.execute(
            """
            SELECT id FROM discovery_history
            WHERE device_id = ? AND data_hash = ?
            ORDER BY discovered_at DESC LIMIT 1
        """,
            (device_id, data_hash),
        )

        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO discovery_history (device_id, discovery_data, data_hash)
                VALUES (?, ?, ?)
            """,
                (device_id, discovery_data, data_hash),
            )
            self.connection.commit()

    def get_device_changes(self, device_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get device change history from SQLite."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT discovery_data, discovered_at FROM discovery_history
            WHERE device_id = ?
            ORDER BY discovered_at DESC LIMIT ?
        """,
            (device_id, limit),
        )

        changes = []
        for row in cursor.fetchall():
            try:
                data = json.loads(row[0])
                changes.append({"data": data, "discovered_at": row[1]})
            except json.JSONDecodeError:
                pass

        return changes

    def execute_query(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query and return results."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        return [dict(row) for row in cursor.fetchall()]

    # SSH Credentials CRUD methods
    def add_credential(
        self,
        hostname: str,
        username: str = "mcp_admin",
        key_path: str | None = None,
        port: int = 22,
        display_name: str | None = None,
        device_id: int | None = None,
    ) -> int:
        """Add a new SSH credential record."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO ssh_credentials
            (hostname, username, key_path, port, display_name, device_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (hostname, username, key_path, port, display_name, device_id),
        )

        self.connection.commit()
        lastrowid = cursor.lastrowid
        assert lastrowid is not None
        return lastrowid

    def get_credential(self, credential_id: int) -> dict[str, Any] | None:
        """Get a credential by its ID."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM ssh_credentials WHERE id = ?",
            (credential_id,),
        )

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_credential_by_hostname(self, hostname: str, username: str | None = None) -> dict[str, Any] | None:
        """Get credential by hostname and optionally username."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        if username:
            cursor.execute(
                """
                SELECT * FROM ssh_credentials
                WHERE hostname = ? AND username = ? AND is_active = 1
            """,
                (hostname, username),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM ssh_credentials
                WHERE hostname = ? AND is_active = 1
                ORDER BY id DESC LIMIT 1
            """,
                (hostname,),
            )

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def update_credential(self, credential_id: int, **kwargs: Any) -> bool:
        """Update a credential record."""
        if not self.connection:
            self.connect()

        assert self.connection is not None

        # Build update query dynamically based on provided kwargs
        allowed_fields = {
            "hostname",
            "username",
            "key_path",
            "port",
            "display_name",
            "device_id",
            "is_active",
        }
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not update_fields:
            return False

        # Add updated_at timestamp
        set_clause = ", ".join(f"{k} = ?" for k in update_fields)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(update_fields.values()) + [credential_id]

        cursor = self.connection.cursor()
        cursor.execute(
            f"UPDATE ssh_credentials SET {set_clause} WHERE id = ?",
            values,
        )

        self.connection.commit()
        return cursor.rowcount > 0

    def delete_credential(self, credential_id: int) -> bool:
        """Delete a credential record."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            "DELETE FROM ssh_credentials WHERE id = ?",
            (credential_id,),
        )

        self.connection.commit()
        return cursor.rowcount > 0

    def list_credentials(self, active_only: bool = True) -> list[dict[str, Any]]:
        """List all credentials."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        if active_only:
            cursor.execute("SELECT * FROM ssh_credentials WHERE is_active = 1 ORDER BY hostname")
        else:
            cursor.execute("SELECT * FROM ssh_credentials ORDER BY hostname")

        return [dict(row) for row in cursor.fetchall()]

    def update_last_verified(self, credential_id: int) -> bool:
        """Update the last_verified timestamp for a credential."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE ssh_credentials
            SET last_verified = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (credential_id,),
        )

        self.connection.commit()
        return cursor.rowcount > 0


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter with JSONB support."""

    def __init__(self, connection_params: dict[str, Any] | None = None):
        if not POSTGRESQL_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgreSQL support")

        if connection_params is None:
            # Default connection parameters from environment
            connection_params = {
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "port": int(os.getenv("POSTGRES_PORT", "5432")),
                "database": os.getenv("POSTGRES_DB", "homelab_mcp"),
                "user": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", "password"),
            }

        self.connection_params = connection_params
        self.connection: Any | None = None  # psycopg2 connection type

    def connect(self) -> None:
        """Establish PostgreSQL connection."""
        self.connection = psycopg2.connect(**self.connection_params)
        self.connection.autocommit = False

    def close(self) -> None:
        """Close PostgreSQL connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def init_schema(self) -> None:
        """Initialize PostgreSQL schema with JSONB support."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        # Create devices table with JSONB columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                hostname VARCHAR(255) NOT NULL,
                connection_ip INET NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                status VARCHAR(50) NOT NULL,
                system_info JSONB DEFAULT '{}',
                network_interfaces JSONB DEFAULT '[]',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(hostname, connection_ip)
            )
        """)

        # Create discovery history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_history (
                id SERIAL PRIMARY KEY,
                device_id INTEGER REFERENCES devices(id),
                discovery_data JSONB NOT NULL,
                data_hash VARCHAR(64) NOT NULL,
                discovered_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create ssh_credentials table for persistent credential storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ssh_credentials (
                id SERIAL PRIMARY KEY,
                device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL,
                hostname VARCHAR(255) NOT NULL,
                username VARCHAR(255) NOT NULL DEFAULT 'mcp_admin',
                key_path TEXT,
                port INTEGER DEFAULT 22,
                display_name VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                last_verified TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(hostname, username)
            )
        """)

        # Create indexes including JSONB indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_hostname_ip
            ON devices (hostname, connection_ip)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_status
            ON devices (status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_system_info_gin
            ON devices USING GIN (system_info)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_network_gin
            ON devices USING GIN (network_interfaces)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_device_id
            ON discovery_history (device_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_data_gin
            ON discovery_history USING GIN (discovery_data)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ssh_credentials_hostname
            ON ssh_credentials (hostname)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ssh_credentials_device_id
            ON ssh_credentials (device_id)
        """)

        self.connection.commit()

    def store_device(self, device_data: dict[str, Any]) -> int:
        """Store or update a device in PostgreSQL with JSONB."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        # Prepare system info JSONB
        system_info = {
            "cpu": {
                "model": device_data.get("cpu_model"),
                "cores": device_data.get("cpu_cores"),
            },
            "memory": {
                "total": device_data.get("memory_total"),
                "used": device_data.get("memory_used"),
                "free": device_data.get("memory_free"),
                "available": device_data.get("memory_available"),
            },
            "disk": {
                "filesystem": device_data.get("disk_filesystem"),
                "size": device_data.get("disk_size"),
                "used": device_data.get("disk_used"),
                "available": device_data.get("disk_available"),
                "use_percent": device_data.get("disk_use_percent"),
                "mount": device_data.get("disk_mount"),
            },
            "uptime": device_data.get("uptime"),
            "os": device_data.get("os_info"),
        }

        # Parse network interfaces
        network_interfaces = []
        if device_data.get("network_interfaces"):
            if isinstance(device_data["network_interfaces"], str):
                try:
                    network_interfaces = json.loads(device_data["network_interfaces"])
                except json.JSONDecodeError:
                    network_interfaces = []
            elif isinstance(device_data["network_interfaces"], list):
                network_interfaces = device_data["network_interfaces"]

        # Check if device exists
        cursor.execute(
            """
            SELECT id FROM devices
            WHERE hostname = %s AND connection_ip = %s
        """,
            (device_data["hostname"], device_data["connection_ip"]),
        )

        existing = cursor.fetchone()

        if existing:
            # Update existing device
            device_id: int = existing[0]
            cursor.execute(
                """
                UPDATE devices SET
                    last_seen = %s, status = %s, system_info = %s,
                    network_interfaces = %s, error_message = %s, updated_at = NOW()
                WHERE id = %s
            """,
                (
                    device_data["last_seen"],
                    device_data["status"],
                    json.dumps(system_info),
                    json.dumps(network_interfaces),
                    device_data.get("error_message"),
                    device_id,
                ),
            )
        else:
            # Insert new device
            cursor.execute(
                """
                INSERT INTO devices (
                    hostname, connection_ip, last_seen, status,
                    system_info, network_interfaces, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    device_data["hostname"],
                    device_data["connection_ip"],
                    device_data["last_seen"],
                    device_data["status"],
                    json.dumps(system_info),
                    json.dumps(network_interfaces),
                    device_data.get("error_message"),
                ),
            )
            result = cursor.fetchone()
            assert result is not None
            device_id = result[0]

        self.connection.commit()
        return device_id

    def get_all_devices(self) -> list[dict[str, Any]]:
        """Get all devices from PostgreSQL."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT
                id, hostname, connection_ip::text as connection_ip, last_seen, status,
                system_info, network_interfaces, error_message, created_at, updated_at
            FROM devices
            ORDER BY hostname, connection_ip
        """)

        devices = []
        for row in cursor.fetchall():
            device_dict = dict(row)

            # Flatten system_info for backward compatibility
            if device_dict.get("system_info"):
                system_info = device_dict["system_info"]
                device_dict.update(
                    {
                        "cpu_model": system_info.get("cpu", {}).get("model"),
                        "cpu_cores": system_info.get("cpu", {}).get("cores"),
                        "memory_total": system_info.get("memory", {}).get("total"),
                        "memory_used": system_info.get("memory", {}).get("used"),
                        "memory_free": system_info.get("memory", {}).get("free"),
                        "memory_available": system_info.get("memory", {}).get("available"),
                        "disk_filesystem": system_info.get("disk", {}).get("filesystem"),
                        "disk_size": system_info.get("disk", {}).get("size"),
                        "disk_used": system_info.get("disk", {}).get("used"),
                        "disk_available": system_info.get("disk", {}).get("available"),
                        "disk_use_percent": system_info.get("disk", {}).get("use_percent"),
                        "disk_mount": system_info.get("disk", {}).get("mount"),
                        "uptime": system_info.get("uptime"),
                        "os_info": system_info.get("os"),
                    }
                )

            devices.append(device_dict)

        return devices

    def store_discovery_history(self, device_id: int, discovery_data: str, data_hash: str) -> None:
        """Store discovery history in PostgreSQL."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        # Parse discovery data to JSONB
        try:
            discovery_json = json.loads(discovery_data)
        except json.JSONDecodeError:
            discovery_json = {"raw_data": discovery_data}

        # Check if this exact data was already stored recently
        cursor.execute(
            """
            SELECT id FROM discovery_history
            WHERE device_id = %s AND data_hash = %s
            ORDER BY discovered_at DESC LIMIT 1
        """,
            (device_id, data_hash),
        )

        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO discovery_history (device_id, discovery_data, data_hash)
                VALUES (%s, %s, %s)
            """,
                (device_id, json.dumps(discovery_json), data_hash),
            )
            self.connection.commit()

    def get_device_changes(self, device_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get device change history from PostgreSQL."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT discovery_data, discovered_at FROM discovery_history
            WHERE device_id = %s
            ORDER BY discovered_at DESC LIMIT %s
        """,
            (device_id, limit),
        )

        changes = []
        for row in cursor.fetchall():
            changes.append(
                {
                    "data": row["discovery_data"],
                    "discovered_at": row["discovered_at"].isoformat(),
                }
            )

        return changes

    def execute_query(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query and return results."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        return [dict(row) for row in cursor.fetchall()]

    # SSH Credentials CRUD methods
    def add_credential(
        self,
        hostname: str,
        username: str = "mcp_admin",
        key_path: str | None = None,
        port: int = 22,
        display_name: str | None = None,
        device_id: int | None = None,
    ) -> int:
        """Add a new SSH credential record."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO ssh_credentials
            (hostname, username, key_path, port, display_name, device_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """,
            (hostname, username, key_path, port, display_name, device_id),
        )

        result = cursor.fetchone()
        assert result is not None
        self.connection.commit()
        credential_id_result: int = result[0]
        return credential_id_result

    def get_credential(self, credential_id: int) -> dict[str, Any] | None:
        """Get a credential by its ID."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM ssh_credentials WHERE id = %s",
            (credential_id,),
        )

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_credential_by_hostname(self, hostname: str, username: str | None = None) -> dict[str, Any] | None:
        """Get credential by hostname and optionally username."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if username:
            cursor.execute(
                """
                SELECT * FROM ssh_credentials
                WHERE hostname = %s AND username = %s AND is_active = TRUE
            """,
                (hostname, username),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM ssh_credentials
                WHERE hostname = %s AND is_active = TRUE
                ORDER BY id DESC LIMIT 1
            """,
                (hostname,),
            )

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def update_credential(self, credential_id: int, **kwargs: Any) -> bool:
        """Update a credential record."""
        if not self.connection:
            self.connect()

        assert self.connection is not None

        # Build update query dynamically based on provided kwargs
        allowed_fields = {
            "hostname",
            "username",
            "key_path",
            "port",
            "display_name",
            "device_id",
            "is_active",
        }
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not update_fields:
            return False

        # Add updated_at timestamp
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        set_clause += ", updated_at = NOW()"
        values = list(update_fields.values()) + [credential_id]

        cursor = self.connection.cursor()
        cursor.execute(
            f"UPDATE ssh_credentials SET {set_clause} WHERE id = %s",
            values,
        )

        self.connection.commit()
        rowcount: int = cursor.rowcount
        return rowcount > 0

    def delete_credential(self, credential_id: int) -> bool:
        """Delete a credential record."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            "DELETE FROM ssh_credentials WHERE id = %s",
            (credential_id,),
        )

        self.connection.commit()
        rowcount: int = cursor.rowcount
        return rowcount > 0

    def list_credentials(self, active_only: bool = True) -> list[dict[str, Any]]:
        """List all credentials."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if active_only:
            cursor.execute("SELECT * FROM ssh_credentials WHERE is_active = TRUE ORDER BY hostname")
        else:
            cursor.execute("SELECT * FROM ssh_credentials ORDER BY hostname")

        return [dict(row) for row in cursor.fetchall()]

    def update_last_verified(self, credential_id: int) -> bool:
        """Update the last_verified timestamp for a credential."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE ssh_credentials
            SET last_verified = NOW(), updated_at = NOW()
            WHERE id = %s
        """,
            (credential_id,),
        )

        self.connection.commit()
        rowcount: int = cursor.rowcount
        return rowcount > 0


def get_database_adapter(db_type: str | None = None, **kwargs: Any) -> DatabaseAdapter:
    """Factory function to get the appropriate database adapter."""
    if db_type is None:
        # Auto-detect based on environment
        db_type = os.getenv("DATABASE_TYPE", "sqlite")

    if db_type.lower() == "postgresql":
        if not POSTGRESQL_AVAILABLE:
            raise ImportError("PostgreSQL support requires psycopg2. Install it with: pip install psycopg2-binary")
        return PostgreSQLAdapter(kwargs.get("connection_params"))
    elif db_type.lower() == "sqlite":
        return SQLiteAdapter(kwargs.get("db_path"))
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def calculate_data_hash(discovery_data: str) -> str:
    """Calculate hash of discovery data for change detection."""
    return hashlib.sha256(discovery_data.encode()).hexdigest()
