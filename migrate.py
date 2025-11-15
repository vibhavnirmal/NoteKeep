#!/usr/bin/env python3
"""
Database Migration Manager for NoteKeep

This script ensures backward-compatible database migrations using Alembic.
Run this script before starting the application to apply any pending migrations.

Usage:
    python migrate.py              # Apply all pending migrations
    python migrate.py --create "description"  # Create a new migration
    python migrate.py --history    # Show migration history
    python migrate.py --current    # Show current revision
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))

from alembic import command
from alembic.config import Config


def get_alembic_config():
    """Get Alembic configuration."""
    alembic_cfg = Config("alembic.ini")
    return alembic_cfg


def upgrade_database():
    """Apply all pending migrations."""
    alembic_cfg = get_alembic_config()
    
    try:
        command.upgrade(alembic_cfg, "head")
        print("✅ Database up to date")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


def create_migration(message: str):
    """Create a new migration with autogenerate."""
    print(f"📝 Creating new migration: {message}")
    alembic_cfg = get_alembic_config()
    
    try:
        command.revision(alembic_cfg, message=message, autogenerate=True)
        print("✅ Migration created successfully!")
        print("⚠️  Please review the generated migration file before applying it.")
        return True
    except Exception as e:
        print(f"❌ Failed to create migration: {e}")
        return False


def show_history():
    """Show migration history."""
    print("📜 Migration History:")
    alembic_cfg = get_alembic_config()
    
    try:
        command.history(alembic_cfg, verbose=True)
        return True
    except Exception as e:
        print(f"❌ Failed to show history: {e}")
        return False


def show_current():
    """Show current revision."""
    print("📍 Current Database Revision:")
    alembic_cfg = get_alembic_config()
    
    try:
        command.current(alembic_cfg, verbose=True)
        return True
    except Exception as e:
        print(f"❌ Failed to show current revision: {e}")
        return False


def downgrade(revision: str = "-1"):
    """Downgrade database to a specific revision."""
    print(f"⬇️  Downgrading database to: {revision}")
    alembic_cfg = get_alembic_config()
    
    try:
        command.downgrade(alembic_cfg, revision)
        print("✅ Database downgraded successfully!")
        return True
    except Exception as e:
        print(f"❌ Downgrade failed: {e}")
        return False


def stamp_database(revision: str = "head"):
    """Stamp the database with a specific revision without running migrations."""
    print(f"🏷️  Stamping database with revision: {revision}")
    alembic_cfg = get_alembic_config()
    
    try:
        command.stamp(alembic_cfg, revision)
        print("✅ Database stamped successfully!")
        return True
    except Exception as e:
        print(f"❌ Stamping failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Database Migration Manager for NoteKeep",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--create",
        metavar="MESSAGE",
        help="Create a new migration with the given message",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show migration history",
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Show current database revision",
    )
    parser.add_argument(
        "--downgrade",
        metavar="REVISION",
        nargs="?",
        const="-1",
        help="Downgrade to a specific revision (default: previous revision)",
    )
    parser.add_argument(
        "--stamp",
        metavar="REVISION",
        nargs="?",
        const="head",
        help="Stamp the database with a revision without running migrations (default: head)",
    )
    
    args = parser.parse_args()
    
    # If no arguments provided, run upgrade
    if len(sys.argv) == 1:
        success = upgrade_database()
        sys.exit(0 if success else 1)
    
    # Handle specific commands
    if args.create:
        success = create_migration(args.create)
        sys.exit(0 if success else 1)
    
    if args.history:
        success = show_history()
        sys.exit(0 if success else 1)
    
    if args.current:
        success = show_current()
        sys.exit(0 if success else 1)
    
    if args.downgrade is not None:
        success = downgrade(args.downgrade)
        sys.exit(0 if success else 1)
    
    if args.stamp is not None:
        success = stamp_database(args.stamp)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
