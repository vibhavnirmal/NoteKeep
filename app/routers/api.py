from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..crud import (
    create_link,
    delete_link,
    export_all_links,
    get_link,
    get_link_by_url,
    list_collections,
    list_links,
    list_tags,
    update_link,
)
from ..database import get_db
from ..link_preview import fetch_link_metadata
from ..schemas import LinkCreate, LinkRead, LinkUpdate, PaginatedLinks
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
) -> LinkRead:
    link = get_link(session, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    updated = update_link(session, link, payload)
    session.commit()
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
    links = export_all_links(session)
    return [LinkRead.model_validate(row) for row in links]


@router.get("/preview")
async def api_fetch_preview(
    url: str = Query(..., description="URL to fetch preview metadata for"),
) -> dict[str, str | int | bool | None]:
    """Fetch preview metadata (title, description, image) for a URL."""
    return await fetch_link_metadata(url)
