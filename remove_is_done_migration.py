"""Migration script to remove is_done column from links table."""

import sqlite3
import sys
from pathlib import Path

def migrate_database(db_path: str = "notekeep.db"):
    """Remove is_done column from links table."""
    print(f"Starting migration for database: {db_path}")
    
    # Check if database exists
    if not Path(db_path).exists():
        print(f"Error: Database file {db_path} not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if is_done column exists
        cursor.execute("PRAGMA table_info(links)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'is_done' not in column_names:
            print("Column 'is_done' does not exist in links table. Migration not needed.")
            conn.close()
            return True
        
        print("Found 'is_done' column. Removing it...")
        
        # SQLite doesn't support DROP COLUMN directly in older versions
        # We need to recreate the table without the is_done column
        
        # 1. Create a backup of the original table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links_backup AS 
            SELECT * FROM links
        """)
        
        # 2. Get all column names except is_done
        columns_to_keep = [col[1] for col in columns if col[1] != 'is_done']
        columns_str = ', '.join(columns_to_keep)
        
        # 3. Create new table without is_done
        cursor.execute("""
            CREATE TABLE links_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title VARCHAR(255),
                notes TEXT,
                in_inbox BOOLEAN DEFAULT 1 NOT NULL,
                collection_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY(collection_id) REFERENCES collections (id)
            )
        """)
        
        # 4. Copy data from old table to new table
        cursor.execute(f"""
            INSERT INTO links_new ({columns_str})
            SELECT {columns_str} FROM links
        """)
        
        # 5. Drop old table
        cursor.execute("DROP TABLE links")
        
        # 6. Rename new table to original name
        cursor.execute("ALTER TABLE links_new RENAME TO links")
        
        # 7. Recreate indexes if they existed
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_links_id ON links (id)
        """)
        
        conn.commit()
        print("✓ Successfully removed 'is_done' column from links table")
        
        # Verify the change
        cursor.execute("PRAGMA table_info(links)")
        new_columns = cursor.fetchall()
        new_column_names = [col[1] for col in new_columns]
        
        if 'is_done' in new_column_names:
            print("Warning: 'is_done' column still exists!")
            conn.close()
            return False
        
        print(f"✓ Verified: Current columns in links table: {', '.join(new_column_names)}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "notekeep.db"
    success = migrate_database(db_path)
    sys.exit(0 if success else 1)
