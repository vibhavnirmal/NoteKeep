from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.orm import Session

from .crud import get_link
from .database import SessionLocal
from .link_preview import fetch_link_metadata


def _normalize_value(value: str | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _coerce_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def needs_title_refresh(link: Any) -> bool:
    """Return True when the link still uses the URL as its title."""
    title = _normalize_value(getattr(link, "title", None))
    url = _normalize_value(getattr(link, "url", None))
    if not url:
        return False
    if not title:
        return True
    return title == url


def _fetch_title_sync(url: str) -> str:
    try:
        metadata = asyncio.run(fetch_link_metadata(url))
    except RuntimeError:
        # Already inside an event loop; fall back to creating a new loop manually
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            metadata = loop.run_until_complete(fetch_link_metadata(url))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    if not metadata:
        return ""
    return _normalize_value(_coerce_to_str(metadata.get("title")))


def refresh_link_title_if_placeholder(link_id: int) -> None:
    """Fetch the latest metadata and update the title if it is still a placeholder."""
    session: Session = SessionLocal()
    try:
        link = get_link(session, link_id)
        if not link or not needs_title_refresh(link):
            return

        new_title = _fetch_title_sync(link.url)
        if not new_title or new_title == link.title:
            return

        link.title = new_title
        session.add(link)
        session.commit()
    finally:
        session.close()
