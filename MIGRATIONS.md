# Database Migrations Guide

## Quick Reference

```bash
# Apply migrations
python migrate.py

# Create new migration
python migrate.py --create "description"

# Show current version
python migrate.py --current

# Show history
python migrate.py --history

# Rollback one version
python migrate.py --downgrade -1
```

## For Developers

When you modify `app/models.py`:

1. **Create migration:**
   ```bash
   python migrate.py --create "Add field to table"
   ```

2. **Review generated file** in `migrations/versions/`

3. **Apply migration:**
   ```bash
   python migrate.py
   ```

4. **Test rollback** (recommended):
   ```bash
   python migrate.py --downgrade -1  # rollback
   python migrate.py                  # re-apply
   ```

## Best Practices

### ✅ DO:
- Add new columns as nullable or with defaults
- Test both upgrade and downgrade
- Review auto-generated migrations
- Keep migrations small and focused

### ❌ DON'T:
- Add NOT NULL columns without defaults
- Modify old migration files
- Skip testing migrations

## Examples

### Adding Nullable Column
```python
def upgrade() -> None:
    with op.batch_alter_table('links') as batch_op:
        batch_op.add_column(sa.Column('new_field', sa.String(100), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table('links') as batch_op:
        batch_op.drop_column('new_field')
```

### Adding Column with Default
```python
def upgrade() -> None:
    with op.batch_alter_table('links') as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(20), server_default='active'))

def downgrade() -> None:
    with op.batch_alter_table('links') as batch_op:
        batch_op.drop_column('status')
```

## Setup for Existing Database

If you already have a database without Alembic:

```bash
# Create initial migration
python init_alembic.py

# Mark database as current (don't run migration)
python migrate.py --stamp head
```

## Docker

Migrations run automatically via the entrypoint script. No manual intervention needed.

## Troubleshooting

**"Table already exists"**
```bash
python migrate.py --stamp head
```

**"Can't locate revision"**
```bash
python migrate.py --current  # Check version
python migrate.py --history  # Check available migrations
```

