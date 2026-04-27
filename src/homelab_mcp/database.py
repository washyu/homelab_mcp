"""Database abstraction layer for network sitemap functionality."""

import hashlib
import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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
    def update_device_fingerprint(self, hostname: str, fingerprint: dict[str, Any]) -> dict[str, Any]:
        """Phase 38 D-05/D-11: deep-merge fingerprint dict into the device row.

        Returns the merged fingerprint dict. Raises ValueError if hostname is
        not found in the sitemap (with a hint pointing to discover_and_map).
        """
        pass

    @abstractmethod
    def set_device_credential_binding(
        self,
        device_id: int,
        credential_type: str,
        credential_id: str | None,
    ) -> None:
        """Phase 38.1 R3/R4/R8/R9: write the credential_id binding column.

        Args:
            device_id: ``devices.id`` primary key.
            credential_type: ``"ssh"`` or ``"proxmox"`` — selects which
                column (``ssh_credential_id`` or ``proxmox_credential_id``).
                Closed set; ValueError on any other value (defense-in-depth
                even though argparse and CLI handlers already constrain).
            credential_id: UUID string from
                ``credential_store.register_credential()``, or ``None`` to
                null the binding (used by R9 rotation cleanup and ``unlink``).
        """
        pass

    @abstractmethod
    def find_devices_by_hostname_or_ip(self, hostname: str) -> list[dict[str, Any]]:
        """Phase 38.1 R4/R8 (Blocker B2): find sitemap rows where
        ``hostname == arg`` OR ``connection_ip == arg``.

        Encapsulates SQLite ``?`` vs Postgres ``%s`` placeholder differences
        so adapter-agnostic callers (server.py auto-bind, link, unlink) never
        need to construct raw SQL.

        Args:
            hostname: identifier to match against either column. May be a
                hostname (short or FQDN) or an IP address string.

        Returns:
            List of dicts each containing at minimum keys: ``id``,
            ``hostname``, ``connection_ip``, ``ssh_credential_id``,
            ``proxmox_credential_id``. Empty list when no row matches.
        """
        pass

    @abstractmethod
    def bulk_null_credential_binding(
        self,
        credential_ids: list[str],
        credential_type: str,
    ) -> list[str]:
        """Phase 38.1 R9 (Blocker B2): null the ``<type>_credential_id`` column
        on every devices row whose binding is in the given UUID list.

        Used by the rotation-cleanup path in ``credentials remove``.
        Encapsulates the placeholder differences (``IN (?,?,...)`` for SQLite
        vs ``= ANY(%s)`` for Postgres) so the caller passes only plain Python
        values.

        Args:
            credential_ids: UUID list to match against the binding column.
                Empty list → no-op, returns ``[]``.
            credential_type: ``"ssh"`` or ``"proxmox"`` — selects which
                column to null. Closed set; ValueError on any other value.

        Returns:
            List of hostnames whose binding was nulled (for D-26 stderr
            feedback). Empty list when no row matched.
        """
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

    @abstractmethod
    def purge_failed_devices(self, dry_run: bool = False) -> list[dict[str, Any]]:
        """Remove devices where discovery failed.

        Failed = ``status='error'`` OR ``hostname`` is empty/null/'unknown'.
        Returns the list of removed rows (preview only when ``dry_run=True``).
        Also deletes the corresponding ``discovery_history`` rows to avoid
        orphan foreign keys.
        """
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
                usb_devices TEXT,
                pci_devices TEXT,
                block_devices TEXT,
                fingerprint TEXT,
                ssh_credential_id TEXT,
                proxmox_credential_id TEXT,
                uptime TEXT,
                os_info TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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

        # Create indexes
        # Phase 35 D-01: hostname is the natural key for upsert; composite
        # (hostname, connection_ip) index dropped in favor of a non-unique
        # hostname-alone index for the new match clause.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_hostname
            ON devices (hostname)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_device_id
            ON discovery_history (device_id)
        """)

        self.connection.commit()

        # Phase 33/35 migrations: CREATE TABLE IF NOT EXISTS is a no-op on
        # pre-existing DBs, so ALTER-TABLE migrations (Phase 35 usb/pci/block
        # columns, stale UNIQUE drop, zombie-row dedup, Phase 33 ssh_credentials
        # drop) must run separately. Pass our live connection so ``:memory:``
        # databases (which are per-connection) stay on the same DB.
        from .migration import run_sqlite_migrations  # noqa: PLC0415

        run_sqlite_migrations(_connection=self.connection)

    def store_device(self, device_data: dict[str, Any]) -> int:
        """Store or update a device in SQLite."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor()

        # Check if device exists
        # Phase 35 D-01: hostname is the natural key. D-01a: fall back to
        # (hostname, connection_ip) when hostname is degenerate ('', 'unknown', None)
        # so distinct error rows (Phase 33 behavior) are preserved.
        hostname_key = device_data["hostname"]
        if hostname_key in (None, "", "unknown"):
            cursor.execute(
                "SELECT id FROM devices WHERE hostname = ? AND connection_ip = ?",
                (hostname_key, device_data["connection_ip"]),
            )
        else:
            cursor.execute(
                "SELECT id FROM devices WHERE hostname = ?",
                (hostname_key,),
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
                    usb_devices = ?, pci_devices = ?, block_devices = ?,
                    fingerprint = ?,
                    uptime = ?, os_info = ?, error_message = ?, updated_at = ?,
                    connection_ip = ?
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
                    device_data.get("usb_devices"),
                    device_data.get("pci_devices"),
                    device_data.get("block_devices"),
                    device_data.get("fingerprint"),
                    device_data.get("uptime"),
                    device_data.get("os_info"),
                    device_data.get("error_message"),
                    datetime.now().isoformat(),
                    device_data["connection_ip"],
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
                    usb_devices, pci_devices, block_devices,
                    fingerprint,
                    uptime, os_info, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    device_data.get("usb_devices"),
                    device_data.get("pci_devices"),
                    device_data.get("block_devices"),
                    device_data.get("fingerprint"),
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

    def update_device_fingerprint(self, hostname: str, fingerprint: dict[str, Any]) -> dict[str, Any]:
        """Phase 38 D-05/D-11 SQLite: read-merge-write fingerprint."""
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()

        # Hostname-natural-key lookup (Phase 35 D-01 — AST guard tests/test_ast_regression.py:392).
        if hostname in (None, "", "unknown"):
            raise ValueError(
                f"Cannot fingerprint degenerate hostname: {hostname!r}. "
                "Run discover_and_map for this hostname first to populate a real hostname."
            )
        cursor.execute(
            "SELECT fingerprint FROM devices WHERE hostname = ?",
            (hostname,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(
                f"Hostname not in sitemap: {hostname!r}. "
                "Run discover_and_map for this hostname first to add the device."
            )

        stored: dict[str, Any] = json.loads(row[0]) if row[0] else {}
        merged = merge_fingerprint(stored, fingerprint)
        now_iso = datetime.now().isoformat()
        # Phase 38 WR-03: do NOT bump ``last_seen`` here — fingerprint merge is
        # NOT a discovery event. ``last_seen`` should reflect "we last heard
        # from the device" (set by store_device); ``updated_at`` already covers
        # "this row was touched". Bumping last_seen on every fingerprint call
        # would confuse Phase 39 drift detection that reads last_seen.
        cursor.execute(
            "UPDATE devices SET fingerprint = ?, updated_at = ? WHERE hostname = ?",
            (json.dumps(merged), now_iso, hostname),
        )
        self.connection.commit()
        return merged

    def set_device_credential_binding(self, device_id: int, credential_type: str, credential_id: str | None) -> None:
        """Phase 38.1 R3/R4/R8/R9 — see DatabaseAdapter.set_device_credential_binding."""
        if credential_type not in ("ssh", "proxmox"):
            raise ValueError(f"credential_type must be 'ssh' or 'proxmox', got {credential_type!r}")
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        # Closed set ({"ssh", "proxmox"}) — safe to interpolate column name.
        column = f"{credential_type}_credential_id"
        cursor.execute(
            f"UPDATE devices SET {column} = ?, updated_at = ? WHERE id = ?",  # noqa: S608
            (credential_id, datetime.now().isoformat(), device_id),
        )
        self.connection.commit()

    def find_devices_by_hostname_or_ip(self, hostname: str) -> list[dict[str, Any]]:
        """SQLite implementation. See DatabaseAdapter.find_devices_by_hostname_or_ip."""
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id, hostname, connection_ip, "
            "ssh_credential_id, proxmox_credential_id "
            "FROM devices WHERE hostname = ? OR connection_ip = ?",
            (hostname, hostname),
        )
        return [dict(row) for row in cursor.fetchall()]

    def bulk_null_credential_binding(
        self,
        credential_ids: list[str],
        credential_type: str,
    ) -> list[str]:
        """SQLite implementation. See DatabaseAdapter.bulk_null_credential_binding."""
        if credential_type not in ("ssh", "proxmox"):
            raise ValueError(f"credential_type must be 'ssh' or 'proxmox', got {credential_type!r}")
        if not credential_ids:
            return []  # no-op on empty input
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        column = f"{credential_type}_credential_id"  # closed set

        # WR-02 (Phase 38.1 review): chunk to stay safely under SQLite's
        # SQLITE_MAX_VARIABLE_NUMBER limit (default 999 on older builds,
        # 32766 on newer). 500 is a conservative cap that works on all
        # supported SQLite versions and leaves headroom for the trailing
        # updated_at parameter on the UPDATE.
        chunk_size = 500
        affected_hostnames: list[str] = []
        now_iso = datetime.now().isoformat()
        for start in range(0, len(credential_ids), chunk_size):
            chunk = credential_ids[start : start + chunk_size]
            # SQLite-side placeholder construction stays internal to the adapter —
            # never leaks to server.py (Blocker B2 mitigation).
            placeholders = ",".join("?" * len(chunk))
            # Step 1: capture affected hostnames BEFORE the UPDATE
            cursor.execute(
                f"SELECT hostname FROM devices WHERE {column} IN ({placeholders})",  # noqa: S608
                tuple(chunk),
            )
            chunk_hostnames = [row["hostname"] for row in cursor.fetchall()]
            if not chunk_hostnames:
                continue
            # Step 2: null the binding
            cursor.execute(
                f"UPDATE devices SET {column} = NULL, updated_at = ? "  # noqa: S608
                f"WHERE {column} IN ({placeholders})",
                (now_iso, *chunk),
            )
            affected_hostnames.extend(chunk_hostnames)
        if not affected_hostnames:
            return []
        self.connection.commit()
        return affected_hostnames

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

            # Phase 35 D-09b: parse usb_devices / pci_devices / block_devices JSON
            for _json_col in ("usb_devices", "pci_devices", "block_devices"):
                if device_dict.get(_json_col):
                    try:
                        device_dict[_json_col] = json.loads(device_dict[_json_col])
                    except json.JSONDecodeError:
                        device_dict[_json_col] = []

            # Phase 38 D-10: parse fingerprint JSON (dict default, not list)
            if device_dict.get("fingerprint"):
                try:
                    device_dict["fingerprint"] = json.loads(device_dict["fingerprint"])
                except json.JSONDecodeError:
                    device_dict["fingerprint"] = {}

            # Phase 38.1 R7 / D-10: per-row eligibility derived from binding columns.
            # Pure binding-state (NOT cluster-walk-aware — D-09 ratifies this for the
            # sitemap-row read path; cluster-served rows still report eligibility=false
            # for the proxmox column even though drift's resolver Tier-2 walk resolves
            # them at scan time).
            device_dict["eligibility"] = {
                "ssh": device_dict.get("ssh_credential_id") is not None,
                "proxmox": device_dict.get("proxmox_credential_id") is not None,
            }

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
                logger.debug(
                    "Failed to parse discovery history JSON for record at %s", row[1] if len(row) > 1 else "unknown"
                )

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

    def purge_failed_devices(self, dry_run: bool = False) -> list[dict[str, Any]]:
        """SQLite implementation. See ``DatabaseAdapter.purge_failed_devices``."""
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT id, hostname, connection_ip, status, error_message, last_seen
            FROM devices
            WHERE status = 'error'
               OR hostname IS NULL
               OR hostname = ''
               OR hostname = 'unknown'
            ORDER BY id
            """
        )
        candidates = [dict(row) for row in cursor.fetchall()]
        if dry_run or not candidates:
            return candidates
        ids = [row["id"] for row in candidates]
        placeholders = ",".join("?" * len(ids))
        # Delete history first (no ON DELETE CASCADE); then devices.
        cursor.execute(
            f"DELETE FROM discovery_history WHERE device_id IN ({placeholders})",  # noqa: S608
            ids,
        )
        cursor.execute(
            f"DELETE FROM devices WHERE id IN ({placeholders})",  # noqa: S608
            ids,
        )
        self.connection.commit()
        return candidates


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
        # Phase 35 D-01: composite UNIQUE dropped — hostname alone is the natural
        # upsert key (migration.py drops the stale composite for pre-existing DBs).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                hostname VARCHAR(255) NOT NULL,
                connection_ip INET NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                status VARCHAR(50) NOT NULL,
                system_info JSONB DEFAULT '{}',
                network_interfaces JSONB DEFAULT '[]',
                ssh_credential_id TEXT,
                proxmox_credential_id TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
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

        # Create indexes including JSONB indexes
        # Phase 35 D-01: composite (hostname, connection_ip) index dropped in
        # favor of a non-unique hostname-alone index for the new match clause.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_hostname
            ON devices (hostname)
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

        self.connection.commit()

        # Phase 33/35 migrations on pre-existing Postgres DBs: drop legacy
        # ssh_credentials table, dedup zombie hostname rows, drop stale UNIQUE
        # (hostname, connection_ip). Pass our live connection to reuse it.
        from .migration import run_postgres_migrations  # noqa: PLC0415

        run_postgres_migrations(_connection=self.connection)

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
            # Phase 35 D-09b: usb/pci/block device inventories land inside the
            # existing system_info JSONB column (no schema change on Postgres).
            "usb_devices": _maybe_json_load(device_data.get("usb_devices")),
            "pci_devices": _maybe_json_load(device_data.get("pci_devices")),
            "block_devices": _maybe_json_load(device_data.get("block_devices")),
            # Phase 38 D-09a: fingerprint sub-dict lands inside system_info JSONB
            # (no DDL change). _maybe_json_load handles JSON-string from
            # parse_discovery_output AND already-decoded dict from update_device_fingerprint.
            "fingerprint": _maybe_json_load(device_data.get("fingerprint")),
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
        # Phase 35 D-01: hostname is the natural key. D-01a: fall back to
        # (hostname, connection_ip) when hostname is degenerate.
        hostname_key = device_data["hostname"]
        if hostname_key in (None, "", "unknown"):
            cursor.execute(
                "SELECT id FROM devices WHERE hostname = %s AND connection_ip = %s",
                (hostname_key, device_data["connection_ip"]),
            )
        else:
            cursor.execute(
                "SELECT id FROM devices WHERE hostname = %s",
                (hostname_key,),
            )

        existing = cursor.fetchone()

        if existing:
            # Update existing device
            # Phase 35 D-01: connection_ip becomes an UPDATE field (was part of
            # the match clause pre-Phase-35) so re-discovery with a new IP
            # rewrites the row instead of creating a zombie.
            device_id: int = existing[0]
            cursor.execute(
                """
                UPDATE devices SET
                    last_seen = %s, status = %s, system_info = %s,
                    network_interfaces = %s, error_message = %s, connection_ip = %s,
                    updated_at = NOW()
                WHERE id = %s
            """,
                (
                    device_data["last_seen"],
                    device_data["status"],
                    json.dumps(system_info),
                    json.dumps(network_interfaces),
                    device_data.get("error_message"),
                    device_data["connection_ip"],
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

    def update_device_fingerprint(self, hostname: str, fingerprint: dict[str, Any]) -> dict[str, Any]:
        """Phase 38 D-05/D-11 Postgres: read-merge-write for path parity with SQLite.

        Pitfall 4 (RESEARCH.md): does NOT use jsonb_set / || — merge happens in
        Python so that SQLite and Postgres adapters produce identical results.

        Phase 38 WR-04: the SELECT + Python merge + UPDATE sequence is wrapped
        in an explicit transaction with ``SELECT ... FOR UPDATE`` to row-lock
        the device during the merge window. Without the lock, a concurrent
        ``store_device`` writer landing between the SELECT and the UPDATE
        would have its mutations to other ``system_info`` sub-keys (cpu,
        memory, disk, etc.) silently overwritten by this method's write-back
        of the full blob. The connection is configured with ``autocommit =
        False`` (see ``connect``), so the explicit ``BEGIN`` is redundant but
        kept for clarity. On any error the transaction is rolled back to
        avoid leaving an open lock on the row.
        """
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()

        if hostname in (None, "", "unknown"):
            raise ValueError(
                f"Cannot fingerprint degenerate hostname: {hostname!r}. "
                "Run discover_and_map for this hostname first to populate a real hostname."
            )

        try:
            cursor.execute("BEGIN")
            cursor.execute(
                "SELECT system_info FROM devices WHERE hostname = %s FOR UPDATE",
                (hostname,),
            )
            row = cursor.fetchone()
            if row is None:
                # No row to lock; release the empty transaction before raising.
                self.connection.rollback()
                raise ValueError(
                    f"Hostname not in sitemap: {hostname!r}. "
                    "Run discover_and_map for this hostname first to add the device."
                )

            system_info = row[0] if row[0] else {}
            if isinstance(system_info, str):
                system_info = json.loads(system_info)
            stored_fp = system_info.get("fingerprint") or {}
            merged = merge_fingerprint(stored_fp, fingerprint)
            system_info["fingerprint"] = merged

            # Phase 38 WR-03: do NOT bump ``last_seen`` here — fingerprint merge is
            # NOT a discovery event. ``last_seen`` should reflect "we last heard
            # from the device" (set by store_device); ``updated_at`` already covers
            # "this row was touched".
            cursor.execute(
                "UPDATE devices SET system_info = %s, updated_at = NOW() WHERE hostname = %s",
                (json.dumps(system_info), hostname),
            )
            self.connection.commit()
            return merged
        except ValueError:
            # ValueError already rolled back above; re-raise for the caller.
            raise
        except Exception:
            # Any DB or merge error: release the row lock before propagating.
            self.connection.rollback()
            raise

    def set_device_credential_binding(self, device_id: int, credential_type: str, credential_id: str | None) -> None:
        """Phase 38.1 R3/R4/R8/R9 — see DatabaseAdapter.set_device_credential_binding."""
        if credential_type not in ("ssh", "proxmox"):
            raise ValueError(f"credential_type must be 'ssh' or 'proxmox', got {credential_type!r}")
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        column = f"{credential_type}_credential_id"  # closed set
        try:
            cursor.execute("BEGIN")
            cursor.execute(
                "SELECT id FROM devices WHERE id = %s FOR UPDATE",
                (device_id,),
            )
            if cursor.fetchone() is None:
                self.connection.rollback()
                raise ValueError(f"device_id {device_id} not found in devices table")
            cursor.execute(
                f"UPDATE devices SET {column} = %s, updated_at = NOW() WHERE id = %s",  # noqa: S608
                (credential_id, device_id),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def find_devices_by_hostname_or_ip(self, hostname: str) -> list[dict[str, Any]]:
        """PostgreSQL implementation. See DatabaseAdapter.find_devices_by_hostname_or_ip."""
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # WR-05 (Phase 38.1 review): compare against host(connection_ip) so a
        # row inserted with a CIDR-suffixed INET ('192.168.1.5/24') still
        # matches when caller passes a bare IP. ::text would preserve the
        # netmask suffix and silently miss the row, falling into the silent
        # no-op D-01 path. host() strips any netmask. The SELECT clause keeps
        # ::text for output stability (consumers expect plain-string IPs).
        cursor.execute(
            "SELECT id, hostname, connection_ip::text AS connection_ip, "
            "ssh_credential_id, proxmox_credential_id "
            "FROM devices WHERE hostname = %s OR host(connection_ip) = %s",
            (hostname, hostname),
        )
        return [dict(row) for row in cursor.fetchall()]

    def bulk_null_credential_binding(
        self,
        credential_ids: list[str],
        credential_type: str,
    ) -> list[str]:
        """PostgreSQL implementation. See DatabaseAdapter.bulk_null_credential_binding."""
        if credential_type not in ("ssh", "proxmox"):
            raise ValueError(f"credential_type must be 'ssh' or 'proxmox', got {credential_type!r}")
        if not credential_ids:
            return []
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        column = f"{credential_type}_credential_id"  # closed set
        try:
            cursor.execute("BEGIN")
            # Capture affected hostnames first (under the same transaction so a
            # concurrent rebind doesn't sneak in between SELECT and UPDATE).
            cursor.execute(
                f"SELECT id, hostname FROM devices "  # noqa: S608
                f"WHERE {column} = ANY(%s) FOR UPDATE",
                (credential_ids,),
            )
            rows = cursor.fetchall()
            affected_hostnames = [row["hostname"] for row in rows]
            if not affected_hostnames:
                self.connection.rollback()
                return []
            cursor.execute(
                f"UPDATE devices SET {column} = NULL, updated_at = NOW() "  # noqa: S608
                f"WHERE {column} = ANY(%s)",
                (credential_ids,),
            )
            self.connection.commit()
            return affected_hostnames
        except Exception:
            self.connection.rollback()
            raise

    def get_all_devices(self) -> list[dict[str, Any]]:
        """Get all devices from PostgreSQL."""
        if not self.connection:
            self.connect()

        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT
                id, hostname, connection_ip::text as connection_ip, last_seen, status,
                system_info, network_interfaces, error_message, created_at, updated_at,
                ssh_credential_id, proxmox_credential_id
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
                        # Phase 35 D-09b: flatten usb/pci/block device inventories
                        # so downstream consumers see the same top-level keys as
                        # the SQLite path.
                        "usb_devices": system_info.get("usb_devices"),
                        "pci_devices": system_info.get("pci_devices"),
                        "block_devices": system_info.get("block_devices"),
                        # Phase 38 D-10: flatten fingerprint sub-dict to top-level
                        # for SQLite parity (Phase 35 D-09b convention).
                        "fingerprint": system_info.get("fingerprint"),
                    }
                )

            # Phase 38.1 R7 / D-10: per-row eligibility (parity with SQLite path).
            device_dict["eligibility"] = {
                "ssh": device_dict.get("ssh_credential_id") is not None,
                "proxmox": device_dict.get("proxmox_credential_id") is not None,
            }

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

    def purge_failed_devices(self, dry_run: bool = False) -> list[dict[str, Any]]:
        """PostgreSQL implementation. See ``DatabaseAdapter.purge_failed_devices``."""
        if not self.connection:
            self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT id, hostname, connection_ip::text AS connection_ip,
                   status, error_message, last_seen::text AS last_seen
            FROM devices
            WHERE status = 'error'
               OR hostname IS NULL
               OR hostname = ''
               OR hostname = 'unknown'
            ORDER BY id
            """
        )
        candidates = [dict(row) for row in cursor.fetchall()]
        if dry_run or not candidates:
            return candidates
        ids = [row["id"] for row in candidates]
        cursor.execute("DELETE FROM discovery_history WHERE device_id = ANY(%s)", (ids,))
        cursor.execute("DELETE FROM devices WHERE id = ANY(%s)", (ids,))
        self.connection.commit()
        return candidates


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


def _maybe_json_load(value: Any) -> Any:
    """Decode a JSON-string into native Python if it looks like one; else pass through.

    Phase 35 D-09b helper — ``NetworkDevice.usb_devices`` / ``pci_devices`` /
    ``block_devices`` are JSON-encoded strings per the sitemap dataclass
    contract; the Postgres JSONB path prefers structured values, so we
    round-trip the string through ``json.loads`` before dumping the enclosing
    ``system_info`` dict. Passes ``None``, empty string, decode error, or
    non-string values through as ``None`` (except non-string which pass through
    unchanged).
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def merge_fingerprint(stored: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Phase 38 D-05 merge contract: top-level overwrite, capabilities deep-merge.

    ``stored`` is the existing fingerprint dict (parsed from DB).
    ``incoming`` is the dict from update_device_fingerprint (already filtered
    to recognized keys). Returns the merged dict to write back. Pure function —
    no side effects.

    - Top-level keys (kernel/os/package_*) overwrite (last-write-wins).
    - ``capabilities`` sub-dict deep-merges: incoming sub-keys overwrite,
      missing sub-keys preserved.
    """
    merged: dict[str, Any] = dict(stored)
    for key, value in incoming.items():
        if key == "capabilities" and isinstance(value, dict):
            existing_caps = dict(merged.get("capabilities", {}))
            existing_caps.update(value)  # incoming sub-keys overwrite, others preserved
            merged["capabilities"] = existing_caps
        else:
            merged[key] = value  # top-level keys overwrite (D-05 step 3a)
    return merged
