from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..crud import (
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


def group_links_by_date(links):
    """Group links by date categories: Today, Yesterday, This Week, etc."""
    from datetime import timedelta
    from collections import defaultdict
    
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())  # Monday
    last_week_start = week_start - timedelta(days=7)
    month_start = today.replace(day=1)
    
    groups = defaultdict(list)
    
    for link in links:
        link_date = link.created_at.date()
        
        if link_date == today:
            groups['Today'].append(link)
        elif link_date == yesterday:
            groups['Yesterday'].append(link)
        elif link_date >= week_start:
            groups['This Week'].append(link)
        elif link_date >= last_week_start:
            groups['Last Week'].append(link)
        elif link_date >= month_start:
            groups['This Month'].append(link)
        else:
            # Group by month and year for older links
            month_year = link_date.strftime('%B %Y')
            groups[month_year].append(link)
    
    # Return in order
    ordered_groups = []
    for key in ['Today', 'Yesterday', 'This Week', 'Last Week', 'This Month']:
        if key in groups:
            ordered_groups.append((key, groups[key]))
    
    # Add older months in reverse chronological order
    other_keys = sorted(
        [k for k in groups.keys() if k not in ['Today', 'Yesterday', 'This Week', 'Last Week', 'This Month']], 
        key=lambda x: datetime.strptime(x, '%B %Y'), 
        reverse=True
    )
    for key in other_keys:
        ordered_groups.append((key, groups[key]))
    
    return ordered_groups


templates.env.filters["format_date"] = format_date
templates.env.filters["relative_time"] = relative_time


@router.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/links", status_code=status.HTTP_302_FOUND)


@router.get("/links/{link_id}")
def link_detail_view(request: Request, link_id: int):
    """View a single link with all details"""
    session = _get_session()
    try:
        link = get_link(session, link_id)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        collections = list_collections(session)
        return templates.TemplateResponse(
            "link_detail.html",
            {
                "request": request,
                "link": link,
                "collections": collections,
            },
        )
    finally:
        session.close()


@router.get("/links")
def list_links_view(
    request: Request,
    search: str | None = Query(None),
    tag: str | None = Query(None),
    collection: str | None = Query(None),
    has_notes: bool | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    updated: int = Query(0),
):
    session = _get_session()
    try:
        links, total = list_links(
            session,
            search=search,
            tag=tag,
            collection=collection,
            has_notes=has_notes,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        tags = list_tags(session)
        collections = list_collections(session)
        collection_summaries = list_collections_with_counts(session)
        top_collection_summaries = sorted(
            collection_summaries,
            key=lambda item: item[1],
            reverse=True,
        )[:6]
        
        # Group links by date
        grouped_links = group_links_by_date(links)
    finally:
        session.close()
    return templates.TemplateResponse(
        "links.html",
        {
            "request": request,
            "links": links,
            "grouped_links": grouped_links,
            "total": total,
            "page": page,
            "page_size": page_size,
            "tags": tags,
            "collections": collections,
            "collection_summaries": collection_summaries,
            "top_collection_summaries": top_collection_summaries,
            "search": search,
            "filter_tag": tag,
            "filter_collection": collection,
            "has_notes": has_notes,
            "date_from": date_from,
            "date_to": date_to,
            "success_message": "Link updated successfully!" if updated else None,
        },
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
        )
        update_link(session, link, payload)
        session.commit()
    finally:
        session.close()
    referer = request.headers.get("referer") or "/links"
    separator = "&" if "?" in referer else "?"
    redirect_url = f"{referer}{separator}updated=1"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)




@router.post("/links/{link_id}/update")



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
    referer = request.headers.get("referer") or "/links"
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
                )
                create_link(session, link_data)
                imported_count += 1
            except Exception as e:
                skipped_count += 1
                errors.append(f"Error importing {url[:50]}: {str(e)}")
        
        session.commit()
        
        # Build success/error messages
        if imported_count > 0:
            success_msg = f"Successfully imported {imported_count} link(s)!"
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
    from app.icons import ICON_LIBRARY, COLOR_OPTIONS
    
    session = _get_session()
    try:
        tags_with_counts = list_tags_with_counts(session)
        collections_with_counts = list_collections_with_counts(session)
        
        # Convert to list of dicts with link_count, icon, and color attributes
        tags = [{"id": tag.id, "name": tag.name, "icon": tag.icon, "color": tag.color, "link_count": count} for tag, count in tags_with_counts]
        collections = [{"id": coll.id, "name": coll.name, "link_count": count} for coll, count in collections_with_counts]
    finally:
        session.close()
    
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "tags": tags,
            "collections": collections,
            "icon_library": ICON_LIBRARY,
            "color_options": COLOR_OPTIONS,
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
def update_tag_route(
    request: Request,
    tag_id: int,
    name: str = Form(...),
    icon: str | None = Form(None),
    color: str | None = Form(None),
):
    session = _get_session()
    try:
        tag = get_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        update_tag(session, tag, name, icon=icon, color=color)
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
