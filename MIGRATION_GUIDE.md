# Database Migration Guide - Personal Notes Feature

## Overview
This migration adds support for **Personal Notes** - standalone notes without requiring a URL/link.

## What's Being Added
- `notes` table - Stores personal notes with title, content, and timestamps
- `note_tags` table - Association table for many-to-many relationship between notes and tags
- New relationships in existing `collections` and `tags` tables

## Database Schema Changes

### New Table: `notes`
```sql
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    collection_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL
);
```

### New Table: `note_tags`
```sql
CREATE TABLE note_tags (
    note_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
```

## Migration Steps

### Option 1: Automatic Migration (Recommended)
Run the migration script which will automatically create the new tables:

```bash
python migrate_db.py
```

This will:
- ✅ Create the `notes` table
- ✅ Create the `note_tags` association table
- ✅ Leave existing data intact
- ✅ Add new relationships to collections and tags

### Option 2: Manual SQL Migration
If you prefer to review the exact SQL, you can run these commands manually:

```bash
# Backup your database first!
cp notekeep.db notekeep.db.backup

# Then apply the migration using SQLite
sqlite3 notekeep.db < migration.sql
```

Where `migration.sql` contains:
```sql
-- Create notes table
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    collection_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY(collection_id) REFERENCES collections (id) ON DELETE SET NULL
);

-- Create note_tags association table
CREATE TABLE IF NOT EXISTS note_tags (
    note_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY(note_id) REFERENCES notes (id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS ix_notes_collection_id ON notes(collection_id);
CREATE INDEX IF NOT EXISTS ix_notes_created_at ON notes(created_at);
CREATE INDEX IF NOT EXISTS ix_note_tags_note_id ON note_tags(note_id);
CREATE INDEX IF NOT EXISTS ix_note_tags_tag_id ON note_tags(tag_id);
```

## Verification

After running the migration, verify the tables were created:

```bash
sqlite3 notekeep.db ".tables"
```

You should see `notes` and `note_tags` in the output.

Check the schema:
```bash
sqlite3 notekeep.db ".schema notes"
sqlite3 notekeep.db ".schema note_tags"
```

## Rollback (if needed)

If you need to rollback this migration:

```bash
# Restore from backup
cp notekeep.db.backup notekeep.db

# Or drop the tables manually
sqlite3 notekeep.db "DROP TABLE IF EXISTS note_tags; DROP TABLE IF EXISTS notes;"
```

## Next Steps

After successful migration:
1. ✅ Database schema updated
2. ⏳ API endpoints (Phase 2) - Ready to implement
3. ⏳ Web interface (Phase 2) - Ready to implement
4. ⏳ Navigation updates - Ready to implement

## Troubleshooting

**Error: "table notes already exists"**
- The migration is idempotent - this is safe to ignore
- The existing table will be preserved

**Error: "database is locked"**
- Stop the FastAPI server before running migration
- Close any SQLite browser connections

**Foreign key constraint failed**
- Ensure you're using SQLite 3.6.19 or later
- Check that foreign key support is enabled: `PRAGMA foreign_keys = ON;`

## Testing the Migration

After migration, you can test by creating a note using Python:

```python
from app.database import SessionLocal
from app.crud import create_note
from app.schemas import NoteCreate

db = SessionLocal()
note_data = NoteCreate(
    title="My First Note",
    content="This is a test note!",
    tags=["test"],
    collection="Personal"
)
note = create_note(db, note_data, user_id=1)
print(f"Created note: {note.title} (ID: {note.id})")
db.close()
```
