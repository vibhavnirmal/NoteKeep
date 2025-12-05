"""Link preview metadata fetcher using HTML parsing."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


def _extract_instagram_caption(soup: BeautifulSoup) -> str | None:
    # Instagram renders post text in caption containers; class list may change over time.
    caption_nodes = soup.find_all(class_="_ap3a _aaco _aacu _aacx _aad7 _aade")
    if not caption_nodes:
        return None
    parts = [node.get_text(" ", strip=True) for node in caption_nodes if node.get_text(strip=True)]
    caption = " ".join([p for p in parts if p]).strip()
    if not caption:
        return None
    match = re.search(r'"([^"]+)"', caption)
    if match:
        return match.group(1).strip() or None
    return None


async def fetch_link_metadata(url: str, timeout: int = 10) -> dict[str, str | int | bool | None]:
    """Fetch metadata from a URL including title, description, image, and status."""
    status_code = None
    is_accessible = False

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=headers, timeout=timeout, follow_redirects=True
            )
            status_code = response.status_code
            response.raise_for_status()
            is_accessible = True

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to get title from various sources
            title = None
            og_title = soup.find("meta", property="og:title")
            if og_title:
                content = og_title.get("content")
                if content:
                    title = str(content).strip()
            if not title and soup.title and soup.title.string:
                title = soup.title.string.strip()

            # Try to get description
            description = None
            og_desc = soup.find("meta", property="og:description")
            if og_desc:
                content = og_desc.get("content")
                if content:
                    description = str(content).strip()
            if not description:
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    content = meta_desc.get("content")
                    if content:
                        description = str(content).strip()

            # Instagram-specific caption scraping (class may change over time)
            try:
                host = urlparse(url).netloc.lower()
            except Exception:
                host = ""
            if "instagram.com" in host:
                caption = _extract_instagram_caption(soup)
                if caption:
                    description = caption
                    print(f"Extracted Instagram caption: {caption}")

            # Try to get image
            image = None
            og_image = soup.find("meta", property="og:image")
            if og_image:
                content = og_image.get("content")
                if content:
                    image = str(content).strip()
                    # Make absolute URL if relative
                    if image and not image.startswith(("http://", "https://")):
                        image = urljoin(url, image)

            return {
                "title": title,
                "description": description,
                "image": image,
                "error": None,
                "status_code": status_code,
                "is_accessible": is_accessible,
            }
    except httpx.HTTPStatusError as e:
        return {
            "title": None,
            "description": None,
            "image": None,
            "error": f"HTTP {e.response.status_code}: {str(e)}",
            "status_code": e.response.status_code,
            "is_accessible": False,
        }
    except httpx.HTTPError as e:
        return {
            "title": None,
            "description": None,
            "image": None,
            "error": f"Failed to fetch: {str(e)}",
            "status_code": None,
            "is_accessible": False,
        }
    except Exception as e:
        return {
            "title": None,
            "description": None,
            "image": None,
            "error": f"Error: {str(e)}",
            "status_code": None,
            "is_accessible": False,
        }
