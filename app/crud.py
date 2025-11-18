from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .models import Collection, Link, Tag, link_tag_table, Note
from .schemas import LinkCreate, LinkUpdate, NoteCreate, NoteUpdate

DEFAULT_PAGE_SIZE = 25


class DefaultTagBase(TypedDict):
    name: str
    slug: str


class DefaultTag(DefaultTagBase, total=False):
    icon: str | None
    color: str | None
    aliases: list[str]


DEFAULT_TAGS: list[DefaultTag] = [
    {"name": "YouTube", "slug": "youtube", "icon": "youtube", "color": "#ef4444"},
    {"name": "Instagram", "slug": "instagram", "icon": "instagram", "color": "#db2777"},
    {"name": "Reddit", "slug": "reddit", "icon": None, "color": "#f97316"},
    {"name": "GitHub", "slug": "github", "icon": "github", "color": "#111827"},
    {"name": "Twitter", "slug": "twitter", "icon": None, "color": "#0f172a"},
    {"name": "LinkedIn", "slug": "linkedin", "icon": "linkedin", "color": "#2563eb"},
    {"name": "Tutorial", "slug": "tutorial", "icon": "graduation-cap", "color": "#7c3aed"},
    {"name": "Idea", "slug": "idea", "icon": "lightbulb", "color": "#16a34a"},
    {"name": "Article", "slug": "article", "icon": "file-text", "color": "#6366f1"},
    {"name": "Shopping", "slug": "shopping", "icon": "shopping-cart", "color": "#facc15"},
    {"name": "Food", "slug": "food", "icon": "utensils-crossed", "color": "#fb923c"},
]

DEFAULT_TAG_ALIASES: dict[str, str] = {
    alias.lower(): tag["slug"]
    for tag in DEFAULT_TAGS
    for alias in (tag.get("aliases") or [])
}
DEFAULT_TAG_SLUGS = [tag["slug"] for tag in DEFAULT_TAGS]
DEFAULT_TAG_SLUG_SET = {tag["slug"] for tag in DEFAULT_TAGS}

# UTM parameters to strip when checking for duplicates
UTM_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic'
}


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing UTM tracking parameters.
    This ensures URLs with different UTM parameters are treated as duplicates.
    """
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url

        # Parse query parameters
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Remove UTM parameters
        filtered_params = {k: v for k, v in params.items() if k not in UTM_PARAMS}

        # Rebuild query string
        new_query = urlencode(filtered_params, doseq=True) if filtered_params else ''

        # Rebuild URL
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

        return normalized
    except Exception:
        # If normalization fails, return original URL
        return url


def _normalize_tag(tag: str) -> str:
    normalized = tag.strip().lower()
    if normalized.startswith("youtu"):
        return "youtube"
    alias_target = DEFAULT_TAG_ALIASES.get(normalized)
    if alias_target:
        return alias_target
    if normalized in DEFAULT_TAG_SLUG_SET:
        return normalized
    return normalized


def ensure_default_tags(session: Session) -> None:
    """Ensure the core default tags exist with consistent metadata."""
    existing_tags = session.execute(select(Tag)).scalars().all()
    if not existing_tags:
        existing_tags = []

    def _find_matching_tag(candidate: dict[str, str | list[str] | None]) -> Tag | None:
        target_slug = candidate["slug"].lower()
        target_name = candidate["name"].lower()
        aliases = {alias.lower() for alias in (candidate.get("aliases") or [])}
        for tag in existing_tags:
            slug = (tag.slug or "").lower()
            name = (tag.name or "").lower()
            if slug == target_slug or name == target_name:
                return tag
            if slug in aliases or name in aliases:
                return tag
        return None

    for tag_def in DEFAULT_TAGS:
        match = _find_matching_tag(tag_def)
        if match:
            updated = False
            if match.name != tag_def["name"]:
                match.name = tag_def["name"]
                updated = True
            if tag_def.get("icon") is not None and match.icon != tag_def.get("icon"):
                match.icon = tag_def.get("icon")
                updated = True
            if tag_def.get("color") is not None and match.color != tag_def.get("color"):
                match.color = tag_def.get("color")
                updated = True
            if updated:
                session.add(match)
        else:
            new_tag = Tag(
                name=tag_def["name"],
                slug="",
                icon=tag_def.get("icon"),
                color=tag_def.get("color"),
            )
            session.add(new_tag)
            existing_tags.append(new_tag)

    session.flush()


def get_default_tags(session: Session, limit: int = 5) -> list[Tag]:
    """Return the default tags in their defined order, limited to the provided size."""
    if limit <= 0:
        return []
    tags = session.execute(select(Tag)).scalars().all()
    if not tags:
        ensure_default_tags(session)
        tags = session.execute(select(Tag)).scalars().all()
    tags_by_slug = {(tag.slug or "").lower(): tag for tag in tags}
    ordered: list[Tag] = []
    for tag_def in DEFAULT_TAGS:
        slug = tag_def["slug"]
        match = tags_by_slug.get(slug)
        if match:
            ordered.append(match)
        if len(ordered) >= limit:
            break
    return ordered


def get_or_create_collection(session: Session, name: str | None) -> Collection | None:
    if not name:
        return None
    normalized = name.strip()
    if not normalized:
        return None
    existing = session.execute(
        select(Collection).where(func.lower(Collection.name) == func.lower(normalized))
    ).scalar_one_or_none()
    if existing:
        return existing
    collection = Collection(name=normalized, slug="")
    session.add(collection)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return session.execute(
            select(Collection).where(func.lower(Collection.name) == func.lower(normalized))
        ).scalar_one()
    return collection


def get_or_create_tags(session: Session, tag_names: Iterable[str]) -> list[Tag]:
    tags: list[Tag] = []
    cleaned = {_normalize_tag(tag) for tag in tag_names if tag and tag.strip()}
    if not cleaned:
        return tags

    # Limit to maximum 4 tags
    if len(cleaned) > 4:
        cleaned = set(list(cleaned)[:4])

    existing = session.execute(select(Tag).where(func.lower(Tag.name).in_(cleaned))).scalars().all()
    tags.extend(existing)
    for tag in cleaned:
        if not any(existing_tag.name.lower() == tag for existing_tag in tags if existing_tag.name):
            new_tag = Tag(name=tag, slug="")
            session.add(new_tag)
            tags.append(new_tag)
    return tags


def get_link_by_url(session: Session, url: str) -> Link | None:
    """
    Check if a link with this URL already exists.
    URLs are normalized (UTM parameters removed) before comparison.
    """
    from .models import Link
    normalized_url = normalize_url(url)

    # Check all links and compare normalized URLs
    all_links = session.query(Link).all()
    for link in all_links:
        if normalize_url(link.url) == normalized_url:
            return link

    return None


def create_link(session: Session, payload: LinkCreate) -> Link:
    collection = get_or_create_collection(session, payload.collection)
    tags = get_or_create_tags(session, payload.tags)

    # Fetch metadata including image if not provided
    image_url = payload.image_url
    if not image_url:
        from .link_preview import fetch_link_metadata
        import asyncio
        try:
            metadata = asyncio.run(fetch_link_metadata(str(payload.url), timeout=5))
            if metadata and metadata.get("image"):
                image_url = metadata["image"]
        except Exception:
            # If fetching fails, continue without image
            pass

    # Set initial title to URL if not provided, will be updated by background task
    title = payload.title or str(payload.url)

    link = Link(
        url=str(payload.url),
        title=title,
        notes=payload.notes,
        image_url=image_url,
        collection=collection,
        tags=tags,
        image_check_status="success" if image_url else "pending",
        image_checked_at=datetime.now() if image_url else None,
        link_status="active",  # Assume active until proven otherwise
        last_checked_at=datetime.now(),
    )
    session.add(link)
    session.flush()
    session.refresh(link)
    return link


def get_link(session: Session, link_id: int) -> Link | None:
    return session.get(
        Link,
        link_id,
        options=[joinedload(Link.collection), joinedload(Link.tags)],
    )


def update_link(session: Session, link: Link, payload: LinkUpdate) -> Link:
    if payload.title is not None:
        link.title = payload.title
    if payload.notes is not None:
        link.notes = payload.notes
    if payload.image_url is not None:
        link.image_url = payload.image_url
    if payload.collection is not None:
        link.collection = get_or_create_collection(session, payload.collection)
    if payload.tags is not None:
        link.tags = get_or_create_tags(session, payload.tags)
    session.add(link)
    session.flush()
    session.refresh(link)
    return link


def delete_link(session: Session, link: Link) -> None:
    session.delete(link)
    session.flush()


def list_links(
    session: Session,
    *,
    search: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = None,
    collection: str | None = None,
    collections: list[str] | None = None,
    has_notes: bool | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    broken: bool | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[Sequence[Link], int]:
    query = (
        select(Link)
        .options(joinedload(Link.tags), joinedload(Link.collection))
        .order_by(Link.created_at.desc())
    )
    count_query = select(func.count(func.distinct(Link.id))).select_from(Link)

    filters = []

    if search:
        search_term = search.strip()
        if search_term:
            base_pattern = f"%{search_term.lower()}%"
            search_expression = (
                func.lower(Link.title).like(base_pattern)
                | func.lower(Link.url).like(base_pattern)
                | func.lower(Link.notes).like(base_pattern)
            )

            tag_term = search_term.lstrip("#").strip()
            if tag_term:
                tag_pattern = f"%{tag_term.lower()}%"
                search_expression = (
                    search_expression
                    | Link.tags.any(func.lower(Tag.name).like(tag_pattern))
                    | Link.tags.any(func.lower(Tag.slug).like(tag_pattern))
                )

            filters.append(search_expression)

    # Support both single tag and multiple tags for backward compatibility
    if tag:
        lowered_tag = tag.lower()
        query = query.join(Link.tags)
        count_query = count_query.join(Link.tags)
        filters.append(func.lower(Tag.slug) == lowered_tag)
    elif tags and len(tags) > 0:
        # Filter links that have ALL selected tags (AND logic)
        query = query.join(Link.tags)
        count_query = count_query.join(Link.tags)
        lowered_tags = [t.lower() for t in tags]
        filters.append(func.lower(Tag.slug).in_(lowered_tags))
        # Group by link ID and ensure it has all selected tags
        query = query.group_by(Link.id).having(
            func.count(func.distinct(Tag.id)) >= len(lowered_tags)
        )

    # Support both single collection and multiple collections for backward compatibility
    if collection:
        lowered_collection = collection.lower()
        query = query.join(Link.collection)
        count_query = count_query.join(Link.collection)
        filters.append(func.lower(Collection.slug) == lowered_collection)
    elif collections and len(collections) > 0:
        # Filter links that belong to any of the selected collections (OR logic)
        query = query.join(Link.collection)
        count_query = count_query.join(Link.collection)
        lowered_collections = [c.lower() for c in collections]
        filters.append(func.lower(Collection.slug).in_(lowered_collections))

    # Advanced filters
    if has_notes is not None:
        if has_notes:
            filters.append(Link.notes.isnot(None))
            filters.append(Link.notes != "")
        else:
            filters.append((Link.notes.is_(None)) | (Link.notes == ""))

    # Date range filters
    if date_from:
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_from, "%Y-%m-%d")
            filters.append(Link.created_at >= date_obj)
        except ValueError:
            pass  # Ignore invalid date format

    if date_to:
        try:
            from datetime import datetime, timedelta
            date_obj = datetime.strptime(date_to, "%Y-%m-%d")
            # Include the entire day by adding 1 day
            end_of_day = date_obj + timedelta(days=1)
            filters.append(Link.created_at < end_of_day)
        except ValueError:
            pass  # Ignore invalid date format

    # Broken links filter
    if broken:
        filters.append(Link.link_status.in_(["broken", "unreachable", "error"]))

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = session.execute(count_query).scalar_one()

    offset = max(page - 1, 0) * page_size
    results = (
        session.execute(query.limit(page_size).offset(offset))
        .unique()
        .scalars()
        .all()
    )
    return results, total


def has_broken_links(session: Session) -> bool:
    """Check if there are any broken links in the database."""
    count = session.execute(
        select(func.count(Link.id))
        .where(Link.link_status.in_(["broken", "unreachable", "error"]))
    ).scalar_one()
    return count > 0


def list_tags(session: Session) -> Sequence[Tag]:
    """Return a list of all tags that are associated with at least one link."""
    return (
        session.query(Tag)
        .join(link_tag_table)
        .group_by(Tag.id)
        .order_by(func.lower(Tag.name))
        .all()
    )


def list_all_tags(session: Session) -> Sequence[Tag]:
    """Return a list of all tags, regardless of whether they are used."""
    return session.query(Tag).order_by(func.lower(Tag.name)).all()


def get_top_tags(session: Session, limit: int = 5) -> list[Tag]:
    """Get most frequently used tags, ordered by usage count."""
    from sqlalchemy import desc

    tag_counts = (
        session.execute(
            select(Tag, func.count(link_tag_table.c.link_id).label('usage_count'))
            .join(link_tag_table, Tag.id == link_tag_table.c.tag_id)
            .group_by(Tag.id)
            .order_by(desc('usage_count'), Tag.name)
            .limit(limit)
        )
        .all()
    )
    return [tag for tag, count in tag_counts]


def list_collections(session: Session) -> Sequence[Collection]:
    """Return a list of all collections that are associated with at least one link."""
    return (
        session.query(Collection)
        .join(Link)
        .group_by(Collection.id)
        .order_by(func.lower(Collection.name))
        .all()
    )


def list_all_collections(session: Session) -> Sequence[Collection]:
    """Return a list of all collections."""
    return session.query(Collection).order_by(func.lower(Collection.name)).all()


def list_collections_with_counts(session: Session) -> Sequence[tuple[Collection, int]]:
    """Return a list of all collections with their link counts."""
    collection_counts = (
        session.execute(
            select(Collection, func.count(Link.id).label("count"))
            .outerjoin(Link, Collection.id == Link.collection_id)
            .group_by(Collection.id)
            .order_by(Collection.name)
        )
        .all()
    )
    return [(collection, count) for collection, count in collection_counts]


# Tag management functions
def get_tag(session: Session, tag_id: int) -> Tag | None:
    return session.execute(select(Tag).where(Tag.id == tag_id)).scalar_one_or_none()


def create_tag(session: Session, name: str) -> Tag:
    normalized = _normalize_tag(name)
    if not normalized:
        raise ValueError("Tag name cannot be empty")

    # Check if tag already exists
    existing = session.execute(
        select(Tag).where(func.lower(Tag.name) == func.lower(normalized))
    ).scalar_one_or_none()
    if existing:
        raise ValueError(f"Tag '{normalized}' already exists")

    tag = Tag(name=normalized, slug="")
    session.add(tag)
    session.flush()
    return tag


def update_tag(session: Session, tag: Tag, new_name: str, icon: str | None = None, color: str | None = None) -> Tag:
    normalized = _normalize_tag(new_name)
    if not normalized:
        raise ValueError("Tag name cannot be empty")

    # Check if another tag with the same name exists
    existing = session.execute(
        select(Tag).where(func.lower(Tag.name) == func.lower(normalized), Tag.id != tag.id)
    ).scalar_one_or_none()
    if existing:
        raise ValueError(f"Tag '{normalized}' already exists")

    tag.name = normalized
    if icon is not None:
        tag.icon = icon if icon.strip() else None
    if color is not None:
        tag.color = color if color.strip() else None
    session.flush()
    return tag


def delete_tag(session: Session, tag: Tag) -> None:
    session.delete(tag)
    session.flush()


def list_tags_with_counts(session: Session) -> Sequence[tuple[Tag, int]]:
    """Return a list of all tags with their link counts."""
    tag_counts = (
        session.execute(
            select(Tag, func.count(link_tag_table.c.link_id).label("count"))
            .outerjoin(link_tag_table, Tag.id == link_tag_table.c.tag_id)
            .group_by(Tag.id)
            .order_by(Tag.name)
        )
        .all()
    )
    return [(tag, count) for tag, count in tag_counts]


# Collection management functions
def get_collection(session: Session, collection_id: int) -> Collection | None:
    return session.execute(select(Collection).where(Collection.id == collection_id)).scalar_one_or_none()


def create_collection(session: Session, name: str) -> Collection:
    normalized = name.strip()
    if not normalized:
        raise ValueError("Collection name cannot be empty")

    # Check if collection already exists
    existing = session.execute(
        select(Collection).where(func.lower(Collection.name) == func.lower(normalized))
    ).scalar_one_or_none()
    if existing:
        raise ValueError(f"Collection '{normalized}' already exists")

    collection = Collection(name=normalized, slug="")
    session.add(collection)
    session.flush()
    return collection


def update_collection(session: Session, collection: Collection, new_name: str) -> Collection:
    normalized = new_name.strip()
    if not normalized:
        raise ValueError("Collection name cannot be empty")

    # Check if another collection with the same name exists
    existing = session.execute(
        select(Collection).where(func.lower(Collection.name) == func.lower(normalized), Collection.id != collection.id)
    ).scalar_one_or_none()
    if existing:
        raise ValueError(f"Collection '{normalized}' already exists")

    collection.name = normalized
    session.flush()
    return collection


def delete_collection(session: Session, collection: Collection) -> None:
    # First, set collection_id to NULL for all links using this collection
    session.execute(
        select(Link)
        .where(Link.collection_id == collection.id)
    )
    for link in session.execute(select(Link).where(Link.collection_id == collection.id)).scalars():
        link.collection_id = None
    session.flush()
    
    # Now delete the collection
    session.delete(collection)
    session.flush()


# Note CRUD functions
def create_note(session: Session, note_data: NoteCreate) -> Note:
    """Create a new note with tags and collection"""
    # Create note
    note = Note(
        title=note_data.title,
        content=note_data.content,
        image_url=note_data.image_url,
    )

    # Handle collection
    if note_data.collection:
        collection_name = note_data.collection.strip()
        if collection_name:
            collection = session.execute(
                select(Collection).where(func.lower(Collection.name) == func.lower(collection_name))
            ).scalar_one_or_none()
            if not collection:
                collection = Collection(name=collection_name, slug="")
                session.add(collection)
                session.flush()
            note.collection = collection

    # Handle tags
    if note_data.tags:
        for tag_name in note_data.tags:
            normalized = _normalize_tag(tag_name)
            if not normalized:
                continue
            tag = session.execute(
                select(Tag).where(func.lower(Tag.name) == func.lower(normalized))
            ).scalar_one_or_none()
            if not tag:
                tag = Tag(name=normalized, slug="", icon=None, color=None)
                session.add(tag)
                session.flush()
            note.tags.append(tag)

    session.add(note)
    session.flush()
    return note


def get_note(session: Session, note_id: int) -> Note | None:
    """Get a single note by ID"""
    return session.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()


def list_notes(
    session: Session,
    search: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = None,
    collection: str | None = None,
    collections: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[Sequence[Note], int]:
    """List notes with filtering and pagination"""
    query = select(Note).options(joinedload(Note.tags), joinedload(Note.collection))

    # Search filter
    if search:
        query = query.where(
            (Note.title.ilike(f"%{search}%")) | (Note.content.ilike(f"%{search}%"))
        )

    # Tag filters
    if tag:
        query = query.join(Note.tags).where(Tag.slug == tag)
    if tags:
        for tag_slug in tags:
            query = query.join(Note.tags).where(Tag.slug == tag_slug)

    # Collection filters
    if collection:
        query = query.join(Note.collection).where(Collection.slug == collection)
    if collections:
        query = query.join(Note.collection).where(Collection.slug.in_(collections))

    # Date range filters
    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(Note.created_at >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to)
            query = query.where(Note.created_at <= to_date)
        except ValueError:
            pass

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = session.execute(count_query).scalar() or 0

    # Apply pagination
    query = query.order_by(Note.created_at.desc())
    if page_size > 0:
        query = query.limit(page_size).offset((page - 1) * page_size)

    notes = session.execute(query).scalars().unique().all()
    return notes, total


def update_note(session: Session, note: Note, note_data: NoteUpdate) -> Note:
    """Update an existing note"""
    # Update basic fields
    if note_data.title is not None:
        note.title = note_data.title
    if note_data.content is not None:
        note.content = note_data.content
    if note_data.image_url is not None:
        note.image_url = note_data.image_url

    # Update collection
    if note_data.collection is not None:
        if note_data.collection.strip():
            collection_name = note_data.collection.strip()
            collection = session.execute(
                select(Collection).where(func.lower(Collection.name) == func.lower(collection_name))
            ).scalar_one_or_none()
            if not collection:
                collection = Collection(name=collection_name, slug="")
                session.add(collection)
                session.flush()
            note.collection = collection
        else:
            note.collection = None

    # Update tags
    if note_data.tags is not None:
        note.tags.clear()
        for tag_name in note_data.tags:
            normalized = _normalize_tag(tag_name)
            if not normalized:
                continue
            tag = session.execute(
                select(Tag).where(func.lower(Tag.name) == func.lower(normalized))
            ).scalar_one_or_none()
            if not tag:
                tag = Tag(name=normalized, slug="", icon=None, color=None)
                session.add(tag)
                session.flush()
            note.tags.append(tag)

    session.flush()
    return note


def delete_note(session: Session, note: Note) -> None:
    """Delete a note"""
    session.delete(note)
    session.flush()

