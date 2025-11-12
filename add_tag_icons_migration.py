#!/usr/bin/env python3
"""Migration script to add icon and color columns to tags table."""

import sqlite3
import sys
from pathlib import Path

# Default database path
DB_PATH = Path(__file__).parent / "notekeep.db"


def migrate_database(db_path: str = None):
    """Add icon and color columns to tags table."""
    if db_path is None:
        db_path = str(DB_PATH)
    
    print(f"Migrating database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(tags)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'icon' not in columns:
            print("Adding 'icon' column to tags table...")
            cursor.execute("ALTER TABLE tags ADD COLUMN icon VARCHAR(50)")
            print("✓ Added 'icon' column")
        else:
            print("✓ 'icon' column already exists")
        
        if 'color' not in columns:
            print("Adding 'color' column to tags table...")
            cursor.execute("ALTER TABLE tags ADD COLUMN color VARCHAR(20)")
            print("✓ Added 'color' column")
        else:
            print("✓ 'color' column already exists")
        
        # Set default icons for common tags if they exist
        default_icons = {
            'youtube': ('play-circle', 'red'),
            'instagram': ('camera', 'pink'),
            'reddit': ('message-circle', 'orange'),
            'github': ('code', 'gray'),
            'recipe': ('utensils', 'green'),
            'home': ('home', 'blue'),
            'money': ('dollar-sign', 'emerald'),
            'work': ('briefcase', 'indigo'),
            'shopping': ('shopping-cart', 'purple'),
            'travel': ('plane', 'sky'),
            'health': ('heart', 'rose'),
            'education': ('book', 'amber'),
        }
        
        for tag_name, (icon, color) in default_icons.items():
            cursor.execute(
                "UPDATE tags SET icon = ?, color = ? WHERE LOWER(name) = ? AND icon IS NULL",
                (icon, color, tag_name.lower())
            )
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"\n✗ Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    migrate_database(db_path)
