#!/usr/bin/env python3
"""Database management utility for Homelab MCP."""

import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from homelab_mcp.config import (
    create_database_from_config,
    get_config,
    print_config_info,
)
from homelab_mcp.migration import (
    create_postgres_config_template,
    migrate_sqlite_to_postgresql,
    setup_postgresql_database,
)


def main():
    """Main CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Database management utility for Homelab MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python db_manager.py info                    # Show current configuration
  python db_manager.py test                    # Test database connection
  python db_manager.py setup-postgres          # Setup PostgreSQL database
  python db_manager.py migrate --dry-run       # Test SQLite to PostgreSQL migration
  python db_manager.py migrate                 # Perform migration
  python db_manager.py config-template         # Generate .env template
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Info command
    subparsers.add_parser("info", help="Show current database configuration")

    # Test command
    subparsers.add_parser("test", help="Test database connection")

    # Setup PostgreSQL command
    subparsers.add_parser("setup-postgres", help="Setup PostgreSQL database")

    # Migration command
    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate from SQLite to PostgreSQL"
    )
    migrate_parser.add_argument(
        "--dry-run", action="store_true", help="Test migration without making changes"
    )

    # Config template command
    subparsers.add_parser(
        "config-template", help="Generate PostgreSQL configuration template"
    )

    args = parser.parse_args()

    if args.command == "info":
        config = get_config()
        print_config_info(config)

    elif args.command == "test":
        print("Testing database connection...")
        try:
            config = get_config()
            sitemap = create_database_from_config(config)

            # Try to get device count
            devices = sitemap.get_all_devices()
            print("✓ Database connection successful")
            print(f"  Found {len(devices)} devices in database")
            print(f"  Database type: {config.database.db_type}")

            if config.database.db_type == "postgresql":
                print("  Using PostgreSQL with JSONB support")
            else:
                print("  Using SQLite")

        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)

    elif args.command == "setup-postgres":
        config = get_config()
        if config.database.db_type != "postgresql":
            print("ERROR: DATABASE_TYPE must be set to 'postgresql'")
            print("Set environment variable: DATABASE_TYPE=postgresql")
            sys.exit(1)

        success = setup_postgresql_database()
        sys.exit(0 if success else 1)

    elif args.command == "migrate":
        config = get_config()

        if config.database.db_type != "postgresql":
            print("ERROR: Target database type must be PostgreSQL")
            print("Set environment variable: DATABASE_TYPE=postgresql")
            sys.exit(1)

        print("Migrating from SQLite to PostgreSQL...")
        success = migrate_sqlite_to_postgresql(dry_run=args.dry_run)

        if success and not args.dry_run:
            print("\nMigration completed successfully!")
            print("You can now update your configuration to use PostgreSQL:")
            print("  DATABASE_TYPE=postgresql")

        sys.exit(0 if success else 1)

    elif args.command == "config-template":
        print("PostgreSQL Configuration Template:")
        print("=" * 40)
        print(create_postgres_config_template())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
