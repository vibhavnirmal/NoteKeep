from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..crud import (
    count_unread_inbox,
    create_collection,
    create_tag,
    delete_collection,
    delete_link,
    delete_tag,
    get_collection,
    get_link,
    get_tag,
    get_top_tags,
    list_collections,
    list_collections_with_counts,
    list_links,
    list_tags,
    list_tags_with_counts,
    update_collection,
    update_link,
    update_tag,
)
from ..database import SessionLocal
from ..schemas import LinkUpdate

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _get_session() -> Session:
    return SessionLocal()


def _add_global_context(context: dict, request: Request) -> dict:
    """Add global context variables like unread_inbox_count to all templates."""
    session = _get_session()
    try:
        unread_count = count_unread_inbox(session)
    finally:
        session.close()
    
    context["request"] = request
    context["unread_inbox_count"] = unread_count
    return context


def format_date(dt: datetime) -> str:
    """Format datetime as MM/DD/YYYY"""
    return dt.strftime("%m/%d/%Y")


def relative_time(dt: datetime) -> str:
    """Return relative time string like '1 year ago', '3 months ago', etc."""
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 2592000:  # 30 days
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 31536000:  # 365 days
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = int(seconds / 31536000)
        return f"{years} year{'s' if years != 1 else ''} ago"


templates.env.filters["format_date"] = format_date
templates.env.filters["relative_time"] = relative_time


@router.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/inbox", status_code=status.HTTP_302_FOUND)


@router.get("/inbox")
def inbox(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    updated: int = Query(0),
):
    session = _get_session()
    try:
        links, total = list_links(
            session,
            include_done=False,
            only_inbox=True,
            page=page,
            page_size=page_size,
        )
        tags = list_tags(session)
        top_tags = get_top_tags(session, limit=5)
        collections = list_collections(session)
    finally:
        session.close()
    return templates.TemplateResponse(
        "inbox.html",
        _add_global_context({
            "links": links,
            "total": total,
            "page": page,
            "page_size": page_size,
            "tags": tags,
            "top_tags": top_tags,
            "collections": collections,
            "success_message": "Link updated successfully!" if updated else None,
        }, request),
    )


@router.get("/links")
def list_links_view(
    request: Request,
    search: str | None = Query(None),
    tag: str | None = Query(None),
    collection: str | None = Query(None),
    has_notes: bool | None = Query(None),
    is_unread: bool | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    quick_filter: str | None = Query(None),
    saved_search_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    updated: int = Query(0),
):
    from datetime import datetime, timedelta
    
    session = _get_session()
    try:
        # Handle quick filters
        if quick_filter:
            today = datetime.now().date()
            if quick_filter == "today":
                date_from = today.strftime("%Y-%m-%d")
                date_to = today.strftime("%Y-%m-%d")
            elif quick_filter == "this_week":
                # Start of week (Monday)
                start_of_week = today - timedelta(days=today.weekday())
                date_from = start_of_week.strftime("%Y-%m-%d")
                date_to = today.strftime("%Y-%m-%d")
            elif quick_filter == "unread":
                is_unread = True
            elif quick_filter == "has_notes":
                has_notes = True

        # Handle saved searches
        if saved_search_id:
            from ..crud import get_saved_search
            saved_search = get_saved_search(session, saved_search_id)
            if saved_search:
                search = saved_search.search_query or search
                tag = saved_search.tag_slug or tag
                collection = saved_search.collection_slug or collection
                has_notes = saved_search.has_notes if saved_search.has_notes is not None else has_notes
                is_unread = saved_search.is_unread if saved_search.is_unread is not None else is_unread
                date_from = saved_search.date_from or date_from
                date_to = saved_search.date_to or date_to

        links, total = list_links(
            session,
            search=search,
            tag=tag,
            collection=collection,
            has_notes=has_notes,
            is_unread=is_unread,
            date_from=date_from,
            date_to=date_to,
            include_done=True,
            exclude_inbox=True,
            page=page,
            page_size=page_size,
        )
        tags = list_tags(session)
        collections = list_collections(session)
        from ..crud import list_saved_searches
        saved_searches = list_saved_searches(session)
    finally:
        session.close()
    return templates.TemplateResponse(
        "links.html",
        _add_global_context({
            "links": links,
            "total": total,
            "page": page,
            "page_size": page_size,
            "tags": tags,
            "collections": collections,
            "saved_searches": saved_searches,
            "search": search,
            "filter_tag": tag,
            "filter_collection": collection,
            "has_notes": has_notes,
            "is_unread": is_unread,
            "date_from": date_from,
            "date_to": date_to,
            "quick_filter": quick_filter,
            "success_message": "Link updated successfully!" if updated else None,
        }, request),
    )


@router.post("/links/{link_id}/update")
def update_link_view(
    request: Request,
    link_id: int,
    title: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    collection: str | None = Form(default=None),
):
    title = title.strip() if title is not None else None
    notes = notes.strip() if notes is not None else None
    collection = collection.strip() if collection is not None else None

    session = _get_session()
    try:
        link = get_link(session, link_id)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        tags_list = [tag.strip() for tag in (tags or "").split(",") if tag.strip()]
        payload = LinkUpdate(
            title=title if title is not None else link.title,
            notes=notes if notes is not None else link.notes,
            tags=tags_list if tags is not None else None,
            collection=collection if collection else None,
            in_inbox=False,  # Move out of inbox when user clicks Save
        )
        update_link(session, link, payload)
        session.commit()
    finally:
        session.close()
    referer = request.headers.get("referer") or "/inbox"
    separator = "&" if "?" in referer else "?"
    redirect_url = f"{referer}{separator}updated=1"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/links/{link_id}/mark-done")
def mark_done_link_view(request: Request, link_id: int, is_done: str | None = Form(default=None)):
    session = _get_session()
    try:
        link = get_link(session, link_id)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        
        # Toggle the is_done status based on checkbox
        new_done_status = is_done is not None and is_done.lower() in {"on", "true", "1"}
        payload = LinkUpdate(is_done=new_done_status)
        update_link(session, link, payload)
        session.commit()
    finally:
        session.close()
    
    referer = request.headers.get("referer") or "/inbox"
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/links/{link_id}/delete")
def delete_link_view(request: Request, link_id: int):
    session = _get_session()
    try:
        link = get_link(session, link_id)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        delete_link(session, link)
        session.commit()
    finally:
        session.close()
    referer = request.headers.get("referer") or "/inbox"
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/add")
def add_page(
    request: Request,
    url: str | None = Query(None),
    title: str | None = Query(None),
    notes: str | None = Query(None),
    bulk_success: str | None = Query(None),
    bulk_error: str | None = Query(None),
):
    return templates.TemplateResponse(
        "add.html",
        {
            "request": request,
            "prefill": {
                "url": url or "",
                "title": title or "",
            },
            "bulk_success_message": bulk_success,
            "bulk_error_message": bulk_error,
        },
    )


@router.post("/bulk-import")
def bulk_import_links(request: Request, urls: str = Form(...)):
    """Import multiple links from a textarea input"""
    from ..routers.api import extract_domain_name
    from ..schemas import LinkCreate
    from ..crud import create_link, get_link_by_url
    
    lines = urls.strip().split('\n')
    imported_count = 0
    skipped_count = 0
    duplicate_count = 0
    errors = []
    
    session = _get_session()
    try:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse line - support "URL | Title" format or just "URL"
            url = None
            title = None
            
            if '|' in line:
                parts = line.split('|', 1)
                url = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else None
            else:
                url = line
            
            # Validate URL
            if not url or not (url.startswith('http://') or url.startswith('https://')):
                skipped_count += 1
                errors.append(f"Invalid URL: {line[:50]}")
                continue
            
            # Check for duplicate
            existing_link = get_link_by_url(session, url)
            if existing_link:
                duplicate_count += 1
                errors.append(f"Duplicate: {url[:50]} (already exists)")
                continue
            
            try:
                # Auto-tag with domain name
                tags = [extract_domain_name(url)]
                
                link_data = LinkCreate(
                    url=url,
                    title=title or url,
                    tags=tags,
                    in_inbox=True,  # All bulk imports go to inbox
                    is_done=False,  # Mark as new/unread
                )
                create_link(session, link_data)
                imported_count += 1
            except Exception as e:
                skipped_count += 1
                errors.append(f"Error importing {url[:50]}: {str(e)}")
        
        session.commit()
        
        # Build success/error messages
        if imported_count > 0:
            success_msg = f"Successfully imported {imported_count} link(s) to your inbox!"
            if duplicate_count > 0:
                success_msg += f" {duplicate_count} duplicate(s) skipped."
            if skipped_count > 0:
                success_msg += f" {skipped_count} invalid link(s) skipped."
            return RedirectResponse(
                url=f"/add?bulk_success={success_msg}#bulk",
                status_code=status.HTTP_303_SEE_OTHER
            )
        else:
            error_msg = f"No links were imported."
            if duplicate_count > 0:
                error_msg += f" {duplicate_count} duplicate(s) skipped."
            if skipped_count > 0:
                error_msg += f" {skipped_count} invalid link(s) skipped."
            if errors:
                error_msg += f" Details: {'; '.join(errors[:3])}"
            return RedirectResponse(
                url=f"/add?bulk_error={error_msg}#bulk",
                status_code=status.HTTP_303_SEE_OTHER
            )
    except Exception as e:
        session.rollback()
        return RedirectResponse(
            url=f"/add?bulk_error=Error during import: {str(e)}#bulk",
            status_code=status.HTTP_303_SEE_OTHER
        )
    finally:
        session.close()


@router.post("/bulk-import-csv")
async def bulk_import_csv(request: Request, file: UploadFile):
    """Import multiple links from a CSV file"""
    import csv
    import io
    from ..routers.api import extract_domain_name
    from ..schemas import LinkCreate
    from ..crud import create_link
    
    imported_count = 0
    skipped_count = 0
    errors = []
    
    session = _get_session()
    try:
        # Read CSV file
        content = await file.read()
        decoded_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded_content))
        
        # Check for required column
        if 'url' not in csv_reader.fieldnames:
            return RedirectResponse(
                url="/add?bulk_error=CSV must have a 'url' column#bulk",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        for row in csv_reader:
            url = row.get('url', '').strip()
            if not url:
                continue
            
            # Validate URL
            if not (url.startswith('http://') or url.startswith('https://')):
                skipped_count += 1
                errors.append(f"Invalid URL: {url[:50]}")
                continue
            
            try:
                # Get optional fields from CSV
                title = row.get('title', '').strip() or url
                notes = row.get('notes', '').strip() or None
                
                # Handle tags - CSV can have comma-separated tags or single tag
                tags_str = row.get('tags', '').strip()
                if tags_str:
                    # Split by comma if multiple tags
                    tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                else:
                    # Auto-tag with domain name if no tags provided
                    tags = [extract_domain_name(url)]
                
                link_data = LinkCreate(
                    url=url,
                    title=title,
                    notes=notes,
                    tags=tags,
                    in_inbox=True,  # All bulk imports go to inbox
                    is_done=False,  # Mark as new/unread
                )
                create_link(session, link_data)
                imported_count += 1
            except Exception as e:
                skipped_count += 1
                errors.append(f"Error importing {url[:50]}: {str(e)}")
        
        session.commit()
        
        # Build success/error messages
        if imported_count > 0:
            success_msg = f"Successfully imported {imported_count} link(s) from CSV to your inbox!"
            if skipped_count > 0:
                success_msg += f" {skipped_count} link(s) were skipped."
            return RedirectResponse(
                url=f"/add?bulk_success={success_msg}#bulk",
                status_code=status.HTTP_303_SEE_OTHER
            )
        else:
            error_msg = f"No links were imported from CSV. {skipped_count} link(s) were skipped."
            if errors:
                error_msg += f" Errors: {'; '.join(errors[:3])}"
            return RedirectResponse(
                url=f"/add?bulk_error={error_msg}#bulk",
                status_code=status.HTTP_303_SEE_OTHER
            )
    except Exception as e:
        session.rollback()
        return RedirectResponse(
            url=f"/add?bulk_error=Error processing CSV: {str(e)}#bulk",
            status_code=status.HTTP_303_SEE_OTHER
        )
    finally:
        session.close()


@router.get("/settings")
def settings_page(
    request: Request,
    success: str | None = Query(None),
    error: str | None = Query(None),
):
    session = _get_session()
    try:
        tags_with_counts = list_tags_with_counts(session)
        collections_with_counts = list_collections_with_counts(session)
        
        # Convert to list of dicts with link_count attribute
        tags = [{"id": tag.id, "name": tag.name, "link_count": count} for tag, count in tags_with_counts]
        collections = [{"id": coll.id, "name": coll.name, "link_count": count} for coll, count in collections_with_counts]
    finally:
        session.close()
    
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "tags": tags,
            "collections": collections,
            "success_message": success,
            "error_message": error,
        },
    )


# Tag management routes
@router.post("/settings/tags/create")
def create_tag_route(request: Request, name: str = Form(...)):
    session = _get_session()
    try:
        create_tag(session, name)
        session.commit()
        return RedirectResponse(url="/settings?success=Tag+created+successfully", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        session.rollback()
        return RedirectResponse(url=f"/settings?error={str(e)}", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        session.close()


@router.post("/settings/tags/{tag_id}/update")
def update_tag_route(request: Request, tag_id: int, name: str = Form(...)):
    session = _get_session()
    try:
        tag = get_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        update_tag(session, tag, name)
        session.commit()
        return RedirectResponse(url="/settings?success=Tag+updated+successfully", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        session.rollback()
        return RedirectResponse(url=f"/settings?error={str(e)}", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        session.close()


@router.post("/settings/tags/{tag_id}/delete")
def delete_tag_route(request: Request, tag_id: int):
    session = _get_session()
    try:
        tag = get_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        delete_tag(session, tag)
        session.commit()
        return RedirectResponse(url="/settings?success=Tag+deleted+successfully", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        session.close()


# Collection management routes
@router.post("/settings/collections/create")
def create_collection_route(request: Request, name: str = Form(...)):
    session = _get_session()
    try:
        create_collection(session, name)
        session.commit()
        return RedirectResponse(url="/settings?success=Collection+created+successfully#collections", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        session.rollback()
        return RedirectResponse(url=f"/settings?error={str(e)}#collections", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        session.close()


@router.post("/settings/collections/{collection_id}/update")
def update_collection_route(request: Request, collection_id: int, name: str = Form(...)):
    session = _get_session()
    try:
        collection = get_collection(session, collection_id)
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        update_collection(session, collection, name)
        session.commit()
        return RedirectResponse(url="/settings?success=Collection+updated+successfully#collections", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        session.rollback()
        return RedirectResponse(url=f"/settings?error={str(e)}#collections", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        session.close()


@router.post("/settings/collections/{collection_id}/delete")
def delete_collection_route(request: Request, collection_id: int):
    session = _get_session()
    try:
        collection = get_collection(session, collection_id)
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        delete_collection(session, collection)
        session.commit()
        return RedirectResponse(url="/settings?success=Collection+deleted+successfully#collections", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        session.close()


# Saved Search routes
@router.post("/saved-searches/create")
def create_saved_search_route(
    request: Request,
    name: str = Form(...),
    search_query: str | None = Form(None),
    tag_slug: str | None = Form(None),
    collection_slug: str | None = Form(None),
    has_notes: bool | None = Form(None),
    is_unread: bool | None = Form(None),
    date_from: str | None = Form(None),
    date_to: str | None = Form(None),
):
    from ..crud import create_saved_search
    session = _get_session()
    try:
        create_saved_search(
            session,
            name=name,
            search_query=search_query if search_query else None,
            tag_slug=tag_slug if tag_slug else None,
            collection_slug=collection_slug if collection_slug else None,
            has_notes=has_notes,
            is_unread=is_unread,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
        )
        session.commit()
        return RedirectResponse(
            url="/links?success=Search+saved+successfully",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        session.rollback()
        return RedirectResponse(
            url=f"/links?error={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER
        )
    finally:
        session.close()


@router.post("/saved-searches/{search_id}/delete")
def delete_saved_search_route(request: Request, search_id: int):
    from ..crud import get_saved_search, delete_saved_search
    session = _get_session()
    try:
        saved_search = get_saved_search(session, search_id)
        if not saved_search:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )
        delete_saved_search(session, saved_search)
        session.commit()
        return RedirectResponse(
            url="/links?success=Saved+search+deleted",
            status_code=status.HTTP_303_SEE_OTHER
        )
    finally:
        session.close()
