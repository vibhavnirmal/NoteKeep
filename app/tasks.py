from __future__ import annotations

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


async def refresh_link_title_if_placeholder(link_id: int) -> None:
    """Fetch the latest metadata and update the title if it is still a placeholder."""
    session: Session = SessionLocal()
    try:
        link = get_link(session, link_id)
        if not link or not needs_title_refresh(link):
            return

        metadata = await fetch_link_metadata(link.url)
        new_title = _normalize_value(_coerce_to_str(metadata.get("title"))) if metadata else ""
        if not new_title or new_title == link.title:
            return

        link.title = new_title
        session.add(link)
        session.commit()
    finally:
        session.close()
