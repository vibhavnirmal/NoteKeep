#!/usr/bin/env python3
"""Reset the SQLite database schema while preserving existing data.

This script exports all current data, drops every table, recreates the schema
from the latest SQLAlchemy models, and then re-inserts the exported data.
It is useful when the models gain new columns and you need the underlying
SQLite file to match the new structure without losing information.

Usage:
    python scripts/reset_database.py

Optional flags:
    --no-backup       Skip creating a timestamped backup of the SQLite file.
    --backup-dir DIR  Directory where the backup copy will be written.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import Collection, Link, Tag, link_tag_table


def _determine_db_path() -> Path | None:
    """Return the filesystem path for the configured SQLite database."""
    settings = get_settings()
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        return None
    return Path(url.database)


def _backup_database(db_path: Path, backup_dir: Path) -> Path:
    """Create a timestamped copy of the database for safekeeping."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{db_path.name}.{timestamp}.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _export_data() -> dict[str, list[dict[str, Any]]]:
    """Fetch all ORM objects and association rows into plain dictionaries."""
    data: dict[str, list[dict[str, Any]]] = {
        "collections": [],
        "tags": [],
        "links": [],
        "link_tags": [],
    }

    with SessionLocal() as session:
        collections = session.execute(select(Collection)).scalars().all()
        tags = session.execute(select(Tag)).scalars().all()
        links = session.execute(select(Link)).scalars().all()
        link_tags = session.execute(
            select(link_tag_table.c.link_id, link_tag_table.c.tag_id)
        ).all()

        data["collections"] = [
            {
                "id": coll.id,
                "name": coll.name,
                "slug": coll.slug,
                "created_at": coll.created_at,
                "updated_at": coll.updated_at,
            }
            for coll in collections
        ]

        data["tags"] = [
            {
                "id": tag.id,
                "name": tag.name,
                "slug": tag.slug,
                "icon": getattr(tag, "icon", None),
                "color": getattr(tag, "color", None),
                "created_at": tag.created_at,
                "updated_at": tag.updated_at,
            }
            for tag in tags
        ]

        data["links"] = [
            {
                "id": link.id,
                "url": link.url,
                "title": link.title,
                "notes": link.notes,
                "collection_id": link.collection_id,
                "created_at": link.created_at,
                "updated_at": link.updated_at,
            }
            for link in links
        ]

        data["link_tags"] = [
            {"link_id": row.link_id, "tag_id": row.tag_id}
            for row in link_tags
        ]

    return data


def _restore_data(data: dict[str, list[dict[str, Any]]]) -> None:
    """Insert the exported data into the newly created schema."""
    with SessionLocal() as session:
        if data["collections"]:
            session.execute(insert(Collection), data["collections"])
        if data["tags"]:
            session.execute(insert(Tag), data["tags"])
        if data["links"]:
            session.execute(insert(Link), data["links"])
        if data["link_tags"]:
            session.execute(link_tag_table.insert(), data["link_tags"])
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creation of a timestamped backup before resetting the database",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("backups"),
        help="Directory to store the backup copy (default: ./backups)",
    )
    args = parser.parse_args()

    db_path = _determine_db_path()
    if db_path is None:
        raise SystemExit("Database reset only supports sqlite URLs in the current configuration.")

    if not db_path.exists():
        print(f"ℹ Database file {db_path} does not exist. Creating fresh schema…")
        data = {"collections": [], "tags": [], "links": [], "link_tags": []}
    else:
        if args.no_backup:
            print("⚠ Skipping database backup as requested via --no-backup")
        else:
            backup_path = _backup_database(db_path, args.backup_dir)
            print(f"✓ Database backup created at {backup_path}")

        data = _export_data()
        print(
            "✓ Exported data: "
            f"{len(data['collections'])} collections, "
            f"{len(data['tags'])} tags, "
            f"{len(data['links'])} links"
        )

    print("➤ Dropping existing tables…")
    Base.metadata.drop_all(bind=engine)

    print("➤ Recreating tables from current models…")
    Base.metadata.create_all(bind=engine)

    if any(data.values()):
        print("➤ Restoring data into new schema…")
        _restore_data(data)
        print("✓ Restore complete!")
    else:
        print("ℹ No data to restore; schema initialized empty.")

    print("All done.")


if __name__ == "__main__":
    main()
