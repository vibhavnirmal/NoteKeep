#!/usr/bin/env python3
"""Add image_url column to notes table."""

import sqlite3
import sys

def add_image_column():
    """Add image_url column to notes table."""
    db_path = "notekeep.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'image_url' in columns:
            print("✓ Column 'image_url' already exists in notes table")
            return
        
        # Add the column
        cursor.execute("""
            ALTER TABLE notes 
            ADD COLUMN image_url VARCHAR(500)
        """)
        
        conn.commit()
        print("✓ Successfully added 'image_url' column to notes table")
        
    except sqlite3.Error as e:
        print(f"✗ Database error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_image_column()
