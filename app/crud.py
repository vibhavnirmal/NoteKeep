from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .models import Collection, Link, Tag, link_tag_table
from .schemas import LinkCreate, LinkUpdate

DEFAULT_PAGE_SIZE = 25

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
    return normalized


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
    link = Link(
        url=str(payload.url),
        title=payload.title,
        notes=payload.notes,
        collection=collection,
        tags=tags,
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
    collection: str | None = None,
    has_notes: bool | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
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

    if tag:
        lowered_tag = tag.lower()
        query = query.join(Link.tags)
        count_query = count_query.join(Link.tags)
        filters.append(func.lower(Tag.slug) == lowered_tag)

    if collection:
        lowered_collection = collection.lower()
        query = query.join(Link.collection)
        count_query = count_query.join(Link.collection)
        filters.append(func.lower(Collection.slug) == lowered_collection)

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


def list_tags(session: Session) -> list[Tag]:
    return list(session.execute(select(Tag).order_by(Tag.name)).scalars())


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


def list_collections(session: Session) -> list[Collection]:
    return list(session.execute(select(Collection).order_by(Collection.name)).scalars())


def export_all_links(session: Session) -> list[Link]:
    return list(
        session.execute(
            select(Link)
            .options(joinedload(Link.tags), joinedload(Link.collection))
            .order_by(Link.created_at.desc())
        )
        .unique()
        .scalars()
    )


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


def list_tags_with_counts(session: Session) -> list[tuple[Tag, int]]:
    """List all tags with their link counts"""
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


def list_collections_with_counts(session: Session) -> list[tuple[Collection, int]]:
    """List all collections with their link counts"""
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
