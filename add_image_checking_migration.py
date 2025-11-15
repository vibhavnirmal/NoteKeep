#!/usr/bin/env python3
"""Migration script to add image checking columns to links table."""

import sqlite3
import sys
from pathlib import Path

# Default database path
DB_PATH = Path(__file__).parent / "notekeep.db"


def migrate_database(db_path: str | None = None):
    """Add image_checked_at and image_check_status columns to links table."""
    if db_path is None:
        db_path = str(DB_PATH)

    print(f"Migrating database at: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if columns already exist
        cursor.execute("PRAGMA table_info(links)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'image_checked_at' not in columns:
            print("Adding 'image_checked_at' column to links table...")
            cursor.execute("ALTER TABLE links ADD COLUMN image_checked_at DATETIME")
            print("✓ Added 'image_checked_at' column")
        else:
            print("✓ 'image_checked_at' column already exists")

        if 'image_check_status' not in columns:
            print("Adding 'image_check_status' column to links table...")
            cursor.execute("ALTER TABLE links ADD COLUMN image_check_status VARCHAR(20)")
            print("✓ Added 'image_check_status' column")
        else:
            print("✓ 'image_check_status' column already exists")

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