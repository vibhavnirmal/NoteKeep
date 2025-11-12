#!/usr/bin/env python3
"""
Migration script to remove the in_inbox column from the links table.
This migration is part of removing the inbox functionality from NoteKeep.
"""

import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "notekeep.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the column exists
        cursor.execute("PRAGMA table_info(links)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'in_inbox' not in columns:
            print("Column 'in_inbox' does not exist. Migration not needed.")
            conn.close()
            return
        
        print("Starting migration: Removing in_inbox column from links table...")
        
        # SQLite doesn't support DROP COLUMN directly in older versions
        # We need to: 1) Create new table, 2) Copy data, 3) Drop old, 4) Rename new
        
        # Create new table without in_inbox column
        cursor.execute("""
            CREATE TABLE links_new (
                id INTEGER NOT NULL,
                url TEXT NOT NULL,
                title VARCHAR(255),
                notes TEXT,
                collection_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                FOREIGN KEY(collection_id) REFERENCES collections (id)
            )
        """)
        
        # Copy data from old table to new table (excluding in_inbox)
        cursor.execute("""
            INSERT INTO links_new 
            (id, url, title, notes, collection_id, created_at, updated_at)
            SELECT id, url, title, notes, collection_id, created_at, updated_at
            FROM links
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE links")
        
        # Rename new table to links
        cursor.execute("ALTER TABLE links_new RENAME TO links")
        
        conn.commit()
        print("✓ Successfully removed in_inbox column from links table")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
