"""Database migration utilities for moving from SQLite to PostgreSQL."""

import json
import sys
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .database import SQLiteAdapter, PostgreSQLAdapter, calculate_data_hash
from .config import DatabaseConfig, get_config


class DatabaseMigrator:
    """Handles migration between different database backends."""
    
    def __init__(self, source_adapter, target_adapter):
        self.source = source_adapter
        self.target = target_adapter
    
    def migrate_devices(self) -> Tuple[int, int]:
        """Migrate device records from source to target database."""
        print("Migrating device records...")
        
        # Get all devices from source
        devices = self.source.get_all_devices()
        
        migrated_count = 0
        error_count = 0
        
        for device in devices:
            try:
                # Convert timestamps to proper format for PostgreSQL
                if 'last_seen' in device and isinstance(device['last_seen'], str):
                    # Convert ISO string to datetime if needed
                    try:
                        datetime.fromisoformat(device['last_seen'].replace('Z', '+00:00'))
                    except ValueError:
                        # If parsing fails, use current time
                        device['last_seen'] = datetime.now().isoformat()
                
                # Store in target database
                device_id = self.target.store_device(device)
                
                # Migrate discovery history for this device
                if 'id' in device:
                    self._migrate_device_history(device['id'], device_id)
                
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
                if isinstance(change['data'], dict):
                    discovery_data = json.dumps(change['data'])
                else:
                    discovery_data = str(change['data'])
                
                # Calculate hash for the data
                from .database import calculate_data_hash
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
                if (td['hostname'] == source_device['hostname'] and 
                    td['connection_ip'] == source_device['connection_ip']):
                    target_device = td
                    break
            
            if not target_device:
                print(f"ERROR: Device {source_device['hostname']} not found in target!")
                return False
            
            # Compare key fields
            key_fields = ['hostname', 'connection_ip', 'status', 'cpu_model', 'os_info']
            for field in key_fields:
                if source_device.get(field) != target_device.get(field):
                    print(f"ERROR: Field mismatch for {source_device['hostname']}.{field}")
                    return False
        
        print("✓ Migration verification successful")
        return True


def migrate_sqlite_to_postgresql(
    sqlite_path: Optional[str] = None,
    postgres_params: Optional[Dict[str, Any]] = None,
    dry_run: bool = False
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
            if not dry_run and 'target' in locals():
                target.close()
        except:
            pass


def setup_postgresql_database(postgres_params: Optional[Dict[str, Any]] = None) -> bool:
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


def main():
    """Command-line interface for migration utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration utilities for Homelab MCP")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup PostgreSQL database')
    setup_parser.add_argument('--host', default='localhost', help='PostgreSQL host')
    setup_parser.add_argument('--port', type=int, default=5432, help='PostgreSQL port')
    setup_parser.add_argument('--database', default='homelab_mcp', help='Database name')
    setup_parser.add_argument('--user', default='postgres', help='Database user')
    setup_parser.add_argument('--password', required=True, help='Database password')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Migrate from SQLite to PostgreSQL')
    migrate_parser.add_argument('--sqlite-path', help='Path to SQLite database')
    migrate_parser.add_argument('--dry-run', action='store_true', help='Test migration without making changes')
    migrate_parser.add_argument('--host', default='localhost', help='PostgreSQL host')
    migrate_parser.add_argument('--port', type=int, default=5432, help='PostgreSQL port')
    migrate_parser.add_argument('--database', default='homelab_mcp', help='Database name')
    migrate_parser.add_argument('--user', default='postgres', help='Database user')
    migrate_parser.add_argument('--password', required=True, help='Database password')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Generate PostgreSQL configuration template')
    
    args = parser.parse_args()
    
    if args.command == 'setup':
        postgres_params = {
            'host': args.host,
            'port': args.port,
            'database': args.database,
            'user': args.user,
            'password': args.password
        }
        
        success = setup_postgresql_database(postgres_params)
        sys.exit(0 if success else 1)
        
    elif args.command == 'migrate':
        postgres_params = {
            'host': args.host,
            'port': args.port,
            'database': args.database,
            'user': args.user,
            'password': args.password
        }
        
        success = migrate_sqlite_to_postgresql(
            sqlite_path=args.sqlite_path,
            postgres_params=postgres_params,
            dry_run=args.dry_run
        )
        sys.exit(0 if success else 1)
        
    elif args.command == 'config':
        print(create_postgres_config_template())
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main()