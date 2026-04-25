"""Database migration utilities for moving from SQLite to PostgreSQL."""

import json
import logging
import sys
from datetime import datetime
from typing import Any

from .config import get_config
from .database import PostgreSQLAdapter, SQLiteAdapter, calculate_data_hash

logger = logging.getLogger(__name__)


def run_sqlite_migrations(db_path: str | None = None, *, _connection: Any = None) -> list[str]:
    """Run pending migrations on SQLite database.

    Pass ``_connection`` to migrate on an existing open connection (used by
    ``SQLiteAdapter.init_schema`` to avoid the close/reopen dance that breaks
    ``:memory:`` databases). Without it, opens/closes its own connection.
    """
    own_connection = _connection is None
    adapter: SQLiteAdapter | None = None
    if own_connection:
        config = get_config()
        if db_path is None:
            db_path = config.database.sqlite_path
        adapter = SQLiteAdapter(db_path)
        adapter.connect()
        assert adapter.connection is not None
        conn = adapter.connection
    else:
        conn = _connection

    applied_migrations: list[str] = []

    # D-01: Drop legacy ssh_credentials table if it still exists (v1.6 cleanup).
    # Keyring is now the single source of truth for remote credentials (CRED-04).
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='ssh_credentials'
        """
    )
    if cursor.fetchone():
        cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_hostname")
        cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_device_id")
        cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
        conn.commit()
        applied_migrations.append("drop_ssh_credentials_table")
        import sys  # noqa: PLC0415

        print(
            "Dropped legacy ssh_credentials table (v1.6: keyring is now the sole credential store)",
            file=sys.stderr,
        )
        print(
            "NOTE: Any credentials previously stored in the database have been removed.\n"
            "Re-add them with: homelab-mcp credentials add <hostname> <username>",
            file=sys.stderr,
        )

    # ─────────────────────────────────────────────────────────────────
    # Phase 35 D-09c: ADD COLUMN for usb_devices / pci_devices / block_devices.
    # Legacy rows get NULL defaults; get_all_devices returns None for these on
    # pre-existing devices until re-discovered.
    # ─────────────────────────────────────────────────────────────────
    cursor.execute("PRAGMA table_info(devices)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    newly_added: list[str] = []
    for new_col in ("usb_devices", "pci_devices", "block_devices"):
        if new_col not in existing_columns:
            cursor.execute(f"ALTER TABLE devices ADD COLUMN {new_col} TEXT")  # noqa: S608
            newly_added.append(new_col)
    if newly_added:
        conn.commit()
        for col in newly_added:
            applied_migrations.append(f"add_column_{col}")

    # ─────────────────────────────────────────────────────────────────
    # Phase 35 D-02: Collapse duplicate hostnames into a single row. Keep row
    # with greatest last_seen; merge non-null values from siblings (non-null
    # wins); delete siblings. Skip degenerate hostnames ('', 'unknown', NULL)
    # — those are Phase-33-pre-existing distinct-error rows and must not
    # collapse.
    # ─────────────────────────────────────────────────────────────────
    cursor.execute(
        """
        SELECT hostname, COUNT(*) AS n
        FROM devices
        WHERE hostname NOT IN ('', 'unknown') AND hostname IS NOT NULL
        GROUP BY hostname
        HAVING n > 1
        """
    )
    duplicate_hostnames = [row[0] for row in cursor.fetchall()]
    if duplicate_hostnames:
        cursor.execute("PRAGMA table_info(devices)")
        all_cols = [row[1] for row in cursor.fetchall()]
        merge_cols = [c for c in all_cols if c not in ("id", "hostname", "created_at")]

        for hostname in duplicate_hostnames:
            cursor.execute(
                "SELECT * FROM devices WHERE hostname = ? ORDER BY last_seen DESC",
                (hostname,),
            )
            rows = cursor.fetchall()
            keeper = dict(zip(all_cols, rows[0], strict=True))
            siblings = [dict(zip(all_cols, r, strict=True)) for r in rows[1:]]

            for sibling in siblings:
                for col in merge_cols:
                    if keeper.get(col) is None and sibling.get(col) is not None:
                        keeper[col] = sibling[col]

            set_fragments = ", ".join(f"{c} = ?" for c in merge_cols)
            cursor.execute(
                f"UPDATE devices SET {set_fragments} WHERE id = ?",  # noqa: S608
                [keeper[c] for c in merge_cols] + [keeper["id"]],
            )

            sibling_ids = [s["id"] for s in siblings]
            if sibling_ids:
                placeholders = ",".join("?" * len(sibling_ids))
                cursor.execute(
                    f"DELETE FROM devices WHERE id IN ({placeholders})",  # noqa: S608
                    sibling_ids,
                )

        conn.commit()
        applied_migrations.append("dedupe_zombie_device_rows")

    # ─────────────────────────────────────────────────────────────────
    # Phase 35 stale-constraint addendum: drop composite UNIQUE + composite
    # index (both incompatible with hostname-only upsert). SQLite cannot
    # ALTER TABLE DROP CONSTRAINT; idiomatic path is table rebuild. Guard on
    # sqlite_master SQL text so re-run is a no-op.
    # ─────────────────────────────────────────────────────────────────
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='devices'")
    row = cursor.fetchone()
    current_sql = row[0] if row else ""
    if "UNIQUE(hostname, connection_ip)" in current_sql or "UNIQUE (hostname, connection_ip)" in current_sql:
        cursor.execute("DROP INDEX IF EXISTS idx_devices_hostname_ip")
        # Phase 35 I8: idempotent recovery from a prior partial-failure run
        # that may have left an orphan `devices_new` table — without this,
        # the subsequent CREATE would raise "table devices_new already exists".
        cursor.execute("DROP TABLE IF EXISTS devices_new")
        cursor.execute("""
            CREATE TABLE devices_new (
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
                uptime TEXT,
                os_info TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Dynamic column copy: older pre-Phase-35 schemas may be missing some
        # columns (e.g., the three new JSON columns added just above, or columns
        # from older baseline schemas). Select NULL for any target column
        # missing on the source table so the INSERT never fails.
        cursor.execute("PRAGMA table_info(devices)")
        source_cols = {row[1] for row in cursor.fetchall()}
        target_cols = [
            "id",
            "hostname",
            "connection_ip",
            "last_seen",
            "status",
            "cpu_model",
            "cpu_cores",
            "memory_total",
            "memory_used",
            "memory_free",
            "memory_available",
            "disk_filesystem",
            "disk_size",
            "disk_used",
            "disk_available",
            "disk_use_percent",
            "disk_mount",
            "network_interfaces",
            "usb_devices",
            "pci_devices",
            "block_devices",
            "uptime",
            "os_info",
            "error_message",
            "created_at",
            "updated_at",
        ]
        insert_col_list = ", ".join(target_cols)
        select_fragments = ", ".join(c if c in source_cols else f"NULL AS {c}" for c in target_cols)
        cursor.execute(
            f"INSERT INTO devices_new ({insert_col_list}) SELECT {select_fragments} FROM devices"  # noqa: S608
        )
        cursor.execute("DROP TABLE devices")
        cursor.execute("ALTER TABLE devices_new RENAME TO devices")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_hostname ON devices (hostname)")
        conn.commit()
        applied_migrations.append("drop_stale_hostname_ip_unique")

    # Phase 36 D-05: Drop legacy drift_baselines table if it still exists (v1.7 cleanup).
    # Sitemap is now the single source of truth for drift detection (DRFT-11).
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='drift_baselines'
        """
    )
    if cursor.fetchone():
        cursor.execute("DROP INDEX IF EXISTS idx_drift_baselines_node_vmid")
        cursor.execute("DROP TABLE IF EXISTS drift_baselines")
        conn.commit()
        applied_migrations.append("drop_drift_baselines_table")
        import sys  # noqa: PLC0415

        print(
            "Dropped legacy drift_baselines table (v1.7: sitemap is now the single source of truth for drift)",
            file=sys.stderr,
        )
        print(
            "NOTE: Pre-existing baseline rows are not preserved (per DRFT-21 architectural decision).\n"
            "      Drift now reports against the live sitemap; no manual baseline registration is needed.",
            file=sys.stderr,
        )

    if own_connection:
        assert adapter is not None
        adapter.close()
    return applied_migrations


def run_postgres_migrations(postgres_params: dict[str, Any] | None = None, *, _connection: Any = None) -> list[str]:
    """Run pending migrations on PostgreSQL database.

    Pass ``_connection`` to migrate on an existing open connection (used by
    ``PostgreSQLAdapter.init_schema`` to avoid the close/reopen dance).
    Without it, opens/closes its own connection.
    """
    own_connection = _connection is None
    adapter: PostgreSQLAdapter | None = None
    if own_connection:
        config = get_config()
        if postgres_params is None:
            postgres_params = config.database.postgres_config
        adapter = PostgreSQLAdapter(postgres_params)
        adapter.connect()
        assert adapter.connection is not None
        conn = adapter.connection
    else:
        conn = _connection

    applied_migrations: list[str] = []

    cursor = conn.cursor()

    # D-01: Drop legacy ssh_credentials table if it still exists (v1.6 cleanup — Postgres path).
    # Keyring is now the single source of truth for remote credentials (CRED-04).
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'ssh_credentials'
        )
        """
    )
    if cursor.fetchone()[0]:
        cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_hostname")
        cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_device_id")
        cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
        conn.commit()
        applied_migrations.append("drop_ssh_credentials_table")
        import sys  # noqa: PLC0415

        print(
            "Dropped legacy ssh_credentials table from Postgres (v1.6: keyring is now the sole credential store)",
            file=sys.stderr,
        )
        print(
            "NOTE: Any credentials previously stored in the database have been removed.\n"
            "Re-add them with: homelab-mcp credentials add <hostname> <username>",
            file=sys.stderr,
        )

    # ─────────────────────────────────────────────────────────────────
    # Phase 35 D-02 (Postgres): Collapse duplicate hostnames. Same
    # keep-greatest-last_seen + non-null-sibling-merge semantics as SQLite.
    # ─────────────────────────────────────────────────────────────────
    cursor.execute(
        """
        SELECT hostname, COUNT(*) AS n
        FROM devices
        WHERE hostname NOT IN ('', 'unknown') AND hostname IS NOT NULL
        GROUP BY hostname
        HAVING COUNT(*) > 1
        """
    )
    duplicate_hostnames_pg = [row[0] for row in cursor.fetchall()]
    if duplicate_hostnames_pg:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'devices'
            """
        )
        all_cols_pg = [row[0] for row in cursor.fetchall()]
        merge_cols_pg = [c for c in all_cols_pg if c not in ("id", "hostname", "created_at")]

        for hostname in duplicate_hostnames_pg:
            cursor.execute(
                f"SELECT {', '.join(all_cols_pg)} FROM devices WHERE hostname = %s ORDER BY last_seen DESC",  # noqa: S608
                (hostname,),
            )
            rows_pg = cursor.fetchall()
            keeper_pg = dict(zip(all_cols_pg, rows_pg[0], strict=True))
            siblings_pg = [dict(zip(all_cols_pg, r, strict=True)) for r in rows_pg[1:]]

            for sibling in siblings_pg:
                for col in merge_cols_pg:
                    if keeper_pg.get(col) is None and sibling.get(col) is not None:
                        keeper_pg[col] = sibling[col]

            set_fragments_pg = ", ".join(f"{c} = %s" for c in merge_cols_pg)
            cursor.execute(
                f"UPDATE devices SET {set_fragments_pg} WHERE id = %s",  # noqa: S608
                [keeper_pg[c] for c in merge_cols_pg] + [keeper_pg["id"]],
            )

            sibling_ids_pg = [s["id"] for s in siblings_pg]
            if sibling_ids_pg:
                cursor.execute(
                    "DELETE FROM devices WHERE id = ANY(%s)",
                    (sibling_ids_pg,),
                )

        conn.commit()
        applied_migrations.append("dedupe_zombie_device_rows")

    # ─────────────────────────────────────────────────────────────────
    # Phase 35 stale-constraint addendum (Postgres): drop composite UNIQUE
    # and composite index; create replacement hostname-alone index.
    # ─────────────────────────────────────────────────────────────────
    cursor.execute(
        """
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'devices'::regclass
        AND contype = 'u'
        AND pg_get_constraintdef(oid) = 'UNIQUE (hostname, connection_ip)'
        """
    )
    stale_unique = cursor.fetchone()
    if stale_unique:
        cursor.execute(f"ALTER TABLE devices DROP CONSTRAINT {stale_unique[0]}")  # noqa: S608
        conn.commit()
        applied_migrations.append("drop_stale_hostname_ip_unique")

    cursor.execute(
        """
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'devices' AND indexname = 'idx_devices_hostname_ip'
        """
    )
    if cursor.fetchone():
        cursor.execute("DROP INDEX idx_devices_hostname_ip")
        conn.commit()
        applied_migrations.append("drop_stale_hostname_ip_index")

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_devices_hostname ON devices (hostname)
        """
    )
    conn.commit()

    if own_connection:
        assert adapter is not None
        adapter.close()
    return applied_migrations


class DatabaseMigrator:
    """Handles migration between different database backends."""

    def __init__(self, source_adapter: Any, target_adapter: Any) -> None:
        self.source = source_adapter
        self.target = target_adapter

    def migrate_devices(self) -> tuple[int, int]:
        """Migrate device records from source to target database."""
        print("Migrating device records...")

        # Get all devices from source
        devices = self.source.get_all_devices()

        migrated_count = 0
        error_count = 0

        for device in devices:
            try:
                # Convert timestamps to proper format for PostgreSQL
                if "last_seen" in device and isinstance(device["last_seen"], str):
                    # Convert ISO string to datetime if needed
                    try:
                        datetime.fromisoformat(device["last_seen"].replace("Z", "+00:00"))
                    except ValueError:
                        # If parsing fails, use current time
                        device["last_seen"] = datetime.now().isoformat()

                # Store in target database
                device_id = self.target.store_device(device)

                # Migrate discovery history for this device
                if "id" in device:
                    self._migrate_device_history(device["id"], device_id)

                migrated_count += 1

                if migrated_count % 10 == 0:
                    print(f"  Migrated {migrated_count} devices...")

            except Exception as e:
                print(f"  ERROR migrating device {device.get('hostname', 'unknown')}: {e}")
                error_count += 1

        print(f"Device migration complete: {migrated_count} migrated, {error_count} errors")
        return migrated_count, error_count

    def _migrate_device_history(self, source_device_id: int, target_device_id: int) -> None:
        """Migrate discovery history for a specific device."""
        try:
            changes = self.source.get_device_changes(source_device_id, limit=1000)

            for change in changes:
                # Convert change data to JSON string if needed
                if isinstance(change["data"], dict):
                    discovery_data = json.dumps(change["data"])
                else:
                    discovery_data = str(change["data"])

                # Calculate hash for the data
                data_hash = calculate_data_hash(discovery_data)

                # Store in target database
                self.target.store_discovery_history(target_device_id, discovery_data, data_hash)

        except Exception as e:
            print(f"    Warning: Could not migrate history for device {source_device_id}: {e}")

    def verify_migration(self) -> bool:
        """Verify that migration was successful."""
        print("Verifying migration...")

        source_devices = self.source.get_all_devices()
        target_devices = self.target.get_all_devices()

        print(f"Source devices: {len(source_devices)}")
        print(f"Target devices: {len(target_devices)}")

        if len(source_devices) != len(target_devices):
            print("ERROR: Device count mismatch!")
            return False

        # Verify a few random devices
        import random

        sample_size = min(5, len(source_devices))
        sample_devices = random.sample(source_devices, sample_size)

        for source_device in sample_devices:
            # Find corresponding device in target
            target_device = None
            for td in target_devices:
                if (
                    td["hostname"] == source_device["hostname"]
                    and td["connection_ip"] == source_device["connection_ip"]
                ):
                    target_device = td
                    break

            if not target_device:
                print(f"ERROR: Device {source_device['hostname']} not found in target!")
                return False

            # Compare key fields
            key_fields = ["hostname", "connection_ip", "status", "cpu_model", "os_info"]
            for field in key_fields:
                if source_device.get(field) != target_device.get(field):
                    print(f"ERROR: Field mismatch for {source_device['hostname']}.{field}")
                    return False

        print("✓ Migration verification successful")
        return True


def migrate_sqlite_to_postgresql(
    sqlite_path: str | None = None,
    postgres_params: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> bool:
    """Migrate data from SQLite to PostgreSQL."""

    print("=== SQLite to PostgreSQL Migration ===")

    # Get configuration
    config = get_config()

    # Setup source (SQLite)
    if sqlite_path is None:
        sqlite_path = config.database.sqlite_path

    print(f"Source SQLite: {sqlite_path}")

    source = SQLiteAdapter(sqlite_path)

    # Setup target (PostgreSQL)
    if postgres_params is None:
        postgres_params = config.database.postgres_config

    print(f"Target PostgreSQL: {postgres_params['host']}:{postgres_params['port']}/{postgres_params['database']}")

    if dry_run:
        print("DRY RUN MODE - No changes will be made to target database")

    try:
        # Test connections
        print("Testing source connection...")
        source.connect()
        source_devices = source.get_all_devices()
        print(f"Found {len(source_devices)} devices in source database")

        if len(source_devices) == 0:
            print("No devices found in source database - nothing to migrate")
            return True

        if not dry_run:
            print("Testing target connection...")
            target = PostgreSQLAdapter(postgres_params)
            target.connect()
            target.init_schema()
            print("Target database connection successful")

            # Perform migration
            migrator = DatabaseMigrator(source, target)
            migrated_count, error_count = migrator.migrate_devices()

            if error_count == 0:
                # Verify migration
                if migrator.verify_migration():
                    print("✓ Migration completed successfully!")
                    return True
                else:
                    print("✗ Migration verification failed")
                    return False
            else:
                print(f"✗ Migration completed with {error_count} errors")
                return False

        else:
            print("✓ Dry run completed - source database is accessible")
            return True

    except ImportError:
        print("ERROR: psycopg2 is required for PostgreSQL migration")
        print("Install with: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        return False
    finally:
        try:
            source.close()
            if not dry_run and "target" in locals():
                target.close()
        except Exception:
            logger.debug("Error closing database connection during migration cleanup")


def setup_postgresql_database(postgres_params: dict[str, Any] | None = None) -> bool:
    """Setup and initialize PostgreSQL database."""

    print("=== PostgreSQL Database Setup ===")

    if postgres_params is None:
        config = get_config()
        postgres_params = config.database.postgres_config

    try:
        print(f"Connecting to PostgreSQL at {postgres_params['host']}:{postgres_params['port']}")

        adapter = PostgreSQLAdapter(postgres_params)
        adapter.connect()
        adapter.init_schema()

        print("✓ PostgreSQL database initialized successfully")
        print("Schema created with JSONB support for enhanced querying")

        adapter.close()
        return True

    except ImportError:
        print("ERROR: psycopg2 is required for PostgreSQL support")
        print("Install with: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"ERROR: PostgreSQL setup failed: {e}")
        print("Check your connection parameters and ensure PostgreSQL is running")
        return False


def create_postgres_config_template() -> str:
    """Create a template for PostgreSQL environment configuration."""

    template = """# PostgreSQL Configuration for Homelab MCP
# Copy these to your environment or .env file

# Database type selection
DATABASE_TYPE=postgresql

# PostgreSQL connection parameters
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=homelab_mcp
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here

# Optional: Enable PostgreSQL features
ENABLE_POSTGRESQL=true

# Example Docker Compose for PostgreSQL:
#
# services:
#   postgres:
#     image: postgres:15
#     environment:
#       POSTGRES_DB: homelab_mcp
#       POSTGRES_USER: postgres
#       POSTGRES_PASSWORD: your_password_here
#     ports:
#       - "5432:5432"
#     volumes:
#       - postgres_data:/var/lib/postgresql/data
#
# volumes:
#   postgres_data:
"""
    return template


def main() -> None:
    """Command-line interface for migration utilities."""
    import argparse

    parser = argparse.ArgumentParser(description="Database migration utilities for Homelab MCP")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Setup PostgreSQL database")
    setup_parser.add_argument("--host", default="localhost", help="PostgreSQL host")
    setup_parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port")
    setup_parser.add_argument("--database", default="homelab_mcp", help="Database name")
    setup_parser.add_argument("--user", default="postgres", help="Database user")
    setup_parser.add_argument("--password", required=True, help="Database password")

    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate from SQLite to PostgreSQL")
    migrate_parser.add_argument("--sqlite-path", help="Path to SQLite database")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Test migration without making changes")
    migrate_parser.add_argument("--host", default="localhost", help="PostgreSQL host")
    migrate_parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port")
    migrate_parser.add_argument("--database", default="homelab_mcp", help="Database name")
    migrate_parser.add_argument("--user", default="postgres", help="Database user")
    migrate_parser.add_argument("--password", required=True, help="Database password")

    # Config command
    subparsers.add_parser("config", help="Generate PostgreSQL configuration template")

    args = parser.parse_args()

    if args.command == "setup":
        postgres_params = {
            "host": args.host,
            "port": args.port,
            "database": args.database,
            "user": args.user,
            "password": args.password,
        }

        success = setup_postgresql_database(postgres_params)
        sys.exit(0 if success else 1)

    elif args.command == "migrate":
        postgres_params = {
            "host": args.host,
            "port": args.port,
            "database": args.database,
            "user": args.user,
            "password": args.password,
        }

        success = migrate_sqlite_to_postgresql(
            sqlite_path=args.sqlite_path,
            postgres_params=postgres_params,
            dry_run=args.dry_run,
        )
        sys.exit(0 if success else 1)

    elif args.command == "config":
        print(create_postgres_config_template())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
