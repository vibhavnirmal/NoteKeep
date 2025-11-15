#!/usr/bin/env python3
"""Migration script to add link health checking columns to links table."""

import sqlite3
import sys
from pathlib import Path

# Default database path
DB_PATH = Path(__file__).parent / "notekeep.db"


def migrate_database(db_path: str | None = None):
    """Add link_status, last_checked_at, and http_status_code columns to links table."""
    if db_path is None:
        db_path = str(DB_PATH)

    print(f"Migrating database at: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if columns already exist
        cursor.execute("PRAGMA table_info(links)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'link_status' not in columns:
            print("Adding 'link_status' column to links table...")
            cursor.execute("ALTER TABLE links ADD COLUMN link_status VARCHAR(20)")
            print("✓ Added 'link_status' column")
        else:
            print("✓ 'link_status' column already exists")

        if 'last_checked_at' not in columns:
            print("Adding 'last_checked_at' column to links table...")
            cursor.execute("ALTER TABLE links ADD COLUMN last_checked_at DATETIME")
            print("✓ Added 'last_checked_at' column")
        else:
            print("✓ 'last_checked_at' column already exists")

        if 'http_status_code' not in columns:
            print("Adding 'http_status_code' column to links table...")
            cursor.execute("ALTER TABLE links ADD COLUMN http_status_code INTEGER")
            print("✓ Added 'http_status_code' column")
        else:
            print("✓ 'http_status_code' column already exists")

        conn.commit()
        print("✓ Migration completed successfully")

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = None

    migrate_database(db_path)
