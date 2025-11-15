#!/usr/bin/env python3
"""
One-time migration script to set up Alembic for an existing database.

This script should be run once to initialize Alembic for databases
that were created with the old create_all() method.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alembic import command
from alembic.config import Config


def initialize_alembic():
    """Initialize Alembic for existing database."""
    print("🔧 Initializing Alembic for existing database...")
    
    alembic_cfg = Config("alembic.ini")
    
    try:
        # Create initial migration from current models
        print("📝 Creating initial migration...")
        command.revision(
            alembic_cfg,
            message="Initial schema",
            autogenerate=True
        )
        
        print("✅ Initial migration created!")
        print("\n📋 Next steps:")
        print("1. Review the migration file in migrations/versions/")
        print("2. If your database already has this schema, run:")
        print("   python migrate.py --stamp head")
        print("3. Otherwise, run:")
        print("   python migrate.py")
        
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Alembic: {e}")
        return False


if __name__ == "__main__":
    success = initialize_alembic()
    sys.exit(0 if success else 1)
