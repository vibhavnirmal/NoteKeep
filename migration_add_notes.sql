-- ================================================================
-- Migration: Add Personal Notes Feature
-- Date: 2025-11-17
-- Description: Creates tables for standalone notes (notes without URLs)
-- ================================================================

-- Enable foreign key support
PRAGMA foreign_keys = ON;

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

-- Create note_tags association table (many-to-many)
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

-- Verify tables were created
SELECT 'Migration completed successfully!' as status;
SELECT name FROM sqlite_master WHERE type='table' AND name IN ('notes', 'note_tags');
