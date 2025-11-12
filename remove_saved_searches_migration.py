"""Remove saved_searches table migration"""
import sqlite3
import os

DB_PATH = "notekeep.db"

def migrate():
    """Drop the saved_searches table"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file {DB_PATH} not found")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='saved_searches'
        """)
        
        if cursor.fetchone():
            # Drop the table
            cursor.execute("DROP TABLE saved_searches")
            conn.commit()
            print("✓ saved_searches table dropped successfully")
        else:
            print("ℹ saved_searches table does not exist, skipping")
            
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
