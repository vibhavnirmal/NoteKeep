from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..crud import (
    create_link,
    create_note,
    delete_link,
    delete_note,
    # export_all_links,
    get_link,
    get_link_by_url,
    get_note,
    list_collections,
    list_links,
    list_notes,
    list_tags,
    update_link,
    update_note,
)
from ..database import get_db
from ..link_preview import fetch_link_metadata
from ..schemas import LinkCreate, LinkRead, LinkUpdate, NoteCreate, NoteRead, NoteUpdate, PaginatedLinks, PaginatedNotes
from ..tasks import needs_title_refresh, refresh_link_title_if_placeholder

router = APIRouter(prefix="/api", tags=["links"])

SessionDep = Annotated[Session, Depends(get_db)]


@router.post("/links", response_model=LinkRead, status_code=status.HTTP_201_CREATED)
def api_create_link(
    payload: LinkCreate,
    *,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> LinkRead:
    # Check for duplicate URL
    existing_link = get_link_by_url(session, str(payload.url))
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Link already exists",
                "existing_link_id": existing_link.id,
                "existing_link_title": existing_link.title,
                "existing_link_url": existing_link.url
            }
        )

    link = create_link(session, payload)
    session.commit()

    if needs_title_refresh(link):
        background_tasks.add_task(refresh_link_title_if_placeholder, link.id)
    
    return LinkRead.model_validate(link)


@router.get("/links", response_model=PaginatedLinks)
def api_list_links(
    search: str | None = Query(None, description="Search across title, URL, and notes"),
    tag: str | None = Query(None, description="Filter by tag slug"),
    collection: str | None = Query(None, description="Filter by collection slug"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    *,
    session: SessionDep,
) -> PaginatedLinks:
    results, total = list_links(
        session,
        search=search,
        tag=tag,
        collection=collection,
        page=page,
        page_size=page_size,
    )
    return PaginatedLinks(
        items=[LinkRead.model_validate(row) for row in results],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/links/{link_id}", response_model=LinkRead)
def api_get_link(
    link_id: int,
    *,
    session: SessionDep,
) -> LinkRead:
    link = get_link(session, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return LinkRead.model_validate(link)


@router.patch("/links/{link_id}", response_model=LinkRead)
def api_update_link(
    link_id: int,
    payload: LinkUpdate,
    *,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> LinkRead:
    link = get_link(session, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    updated = update_link(session, link, payload)
    session.commit()

    if needs_title_refresh(updated):
        background_tasks.add_task(refresh_link_title_if_placeholder, updated.id)

    return LinkRead.model_validate(updated)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_link(
    link_id: int,
    *,
    session: SessionDep,
) -> None:
    link = get_link(session, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    delete_link(session, link)
    session.commit()


@router.get("/tags")
def api_list_tags(
    *,
    session: SessionDep,
) -> list[dict[str, str | int]]:
    tags = list_tags(session)
    return [{"id": tag.id, "name": tag.name, "slug": tag.slug} for tag in tags]


@router.get("/collections")
def api_list_collections(
    *,
    session: SessionDep,
) -> list[dict[str, str | int]]:
    collections = list_collections(session)
    return [
        {
            "id": collection.id,
            "name": collection.name,
            "slug": collection.slug,
        }
        for collection in collections
    ]


@router.get("/links/export", response_model=list[LinkRead])
def api_export_links(
    *,
    session: SessionDep,
) -> list[LinkRead]:
    # links = export_all_links(session)
    links = list_links(session, page_size=-1)[0]  # Use list_links to get all
    return [LinkRead.model_validate(row) for row in links]


@router.get("/preview")
async def api_fetch_preview(
    url: str = Query(..., description="URL to fetch preview metadata for"),
) -> dict[str, str | int | bool | None]:
    """Fetch preview metadata (title, description, image) for a URL."""
    return await fetch_link_metadata(url)


# ============================================================================
# Notes API Endpoints
# ============================================================================

@router.post("/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def api_create_note(
    payload: NoteCreate,
    *,
    session: SessionDep,
) -> NoteRead:
    """Create a new note."""
    note = create_note(session, payload)
    session.commit()
    session.refresh(note)
    return NoteRead.model_validate(note)


@router.get("/notes", response_model=PaginatedNotes)
def api_list_notes(
    *,
    session: SessionDep,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search in title and content"),
    tags: list[str] | None = Query(None, description="Filter by tag slugs"),
    collections: list[str] | None = Query(None, description="Filter by collection slugs"),
    date_from: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
) -> PaginatedNotes:
    """List notes with filtering and pagination."""
    notes, total = list_notes(
        session,
        page=page,
        page_size=page_size,
        search=search,
        tags=tags,
        collections=collections,
        date_from=date_from,
        date_to=date_to,
    )
    return PaginatedNotes(
        items=[NoteRead.model_validate(note) for note in notes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/notes/{note_id}", response_model=NoteRead)
def api_get_note(
    note_id: int,
    *,
    session: SessionDep,
) -> NoteRead:
    """Get a single note by ID."""
    note = get_note(session, note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    return NoteRead.model_validate(note)


@router.patch("/notes/{note_id}", response_model=NoteRead)
def api_update_note(
    note_id: int,
    payload: NoteUpdate,
    *,
    session: SessionDep,
) -> NoteRead:
    """Update a note."""
    note = get_note(session, note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    note = update_note(session, note, payload)
    session.commit()
    session.refresh(note)
    return NoteRead.model_validate(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_note(
    note_id: int,
    *,
    session: SessionDep,
) -> None:
    """Delete a note."""
    note = get_note(session, note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    delete_note(session, note)
    session.commit()
