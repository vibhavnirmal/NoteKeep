"""Telegram bot polling service for NoteKeep - no internet exposure required"""
import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .config import get_settings
from .crud import create_link, create_note, get_link_by_url
from .database import SessionLocal
from .schemas import LinkCreate, NoteCreate

settings = get_settings()
TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None

# Store the last update_id we processed
last_update_id = 0


def extract_urls(text: str) -> list[str]:
    """Extract URLs from text"""
    url_pattern = r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)"
    return re.findall(url_pattern, text)


async def fetch_url_metadata(url: str) -> dict[str, Any]:
    """Fetch title and metadata from URL"""
    try:
        # Validate URL format and scheme
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Invalid URL scheme")

        # Prevent SSRF attacks - block private IPs and localhost
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid hostname")

        # Block localhost and private IP ranges
        blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
        if hostname.lower() in blocked_hosts:
            raise ValueError("Blocked hostname")

        # Block private IP ranges (10.x, 172.16-31.x, 192.168.x)
        if (hostname.startswith("10.") or 
            hostname.startswith("192.168.") or
            any(hostname.startswith(f"172.{i}.") for i in range(16, 32))):
            raise ValueError("Private IP address blocked")

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            max_redirects=3,
            limits=httpx.Limits(max_connections=5)
        ) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()

            # Limit response size to prevent memory issues (5MB max)
            if len(response.content) > 5 * 1024 * 1024:
                raise ValueError("Response too large")

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to get title from various sources
            title = None

            # Try Open Graph title
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                content = og_title["content"]
                # Sanitize: limit length and strip dangerous chars
                if isinstance(content, str):
                    title = content[:500].strip()

            # Try regular title tag
            if not title:
                title_tag = soup.find("title")
                if title_tag and title_tag.string:
                    title = str(title_tag.string)[:500].strip()

            # Extract domain as a potential tag
            domain = parsed.netloc.replace("www.", "")
            # Sanitize domain - only alphanumeric, dots, and hyphens
            domain = re.sub(r'[^a-zA-Z0-9\.\-]', '', domain)[:100]

            # Try to get image
            image = None
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                content = og_image["content"]
                if isinstance(content, str):
                    image = content.strip()[:1000]  # Limit length
                    # Make absolute URL if relative
                    if image and not image.startswith(("http://", "https://")):
                        from urllib.parse import urljoin
                        image = urljoin(url, image)

            return {
                "title": title,
                "domain": domain,
                "image": image
            }

    except Exception as e:
        print(f"Error fetching metadata for {url}: {e}")
        # Return domain as fallback
        try:
            domain = urlparse(url).netloc.replace("www.", "")
            return {"title": None, "domain": domain, "image": None}
        except Exception:
            return {"title": None, "domain": None, "image": None}


async def send_telegram_message(chat_id: int, text: str) -> None:
    """Send a message via Telegram bot"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Error sending Telegram message: {e}")


async def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict[str, Any]]:
    """Get updates from Telegram using long polling"""
    if not TELEGRAM_BOT_TOKEN:
        return []

    params = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset

    async with httpx.AsyncClient(timeout=timeout + 5) as client:
        try:
            response = await client.get(f"{TELEGRAM_API_URL}/getUpdates", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("result", []) if data.get("ok") else []
        except Exception as e:
            print(f"Error getting updates: {e}")
            return []


async def process_message(message: dict[str, Any]) -> None:
    """Process a single message"""
    if "text" not in message:
        return

    chat_id = message["chat"]["id"]
    text = message["text"]
    
    # Validate text input - limit length to prevent abuse
    if len(text) > 4000:
        await send_telegram_message(
            chat_id, "❌ Message too long. Please keep it under 4000 characters."
        )
        return

    # Handle /start command
    if text.startswith("/start"):
        welcome_message = (
            "👋 <b>Welcome to NoteKeep Bot!</b>\n\n"
            "Send me a link and I'll:\n"
            "• 📄 Automatically fetch the page title\n"
            "• 🏷️ Extract relevant tags\n"
            "• 💾 Save it to your inbox\n\n"
            "Send me any text and I'll:\n"
            "• 📝 Create a note titled 'FromTelegram'\n"
            "• 💾 Save your message for later\n\n"
            "Just send a URL or text and I'll take care of the rest! �"
        )
        await send_telegram_message(chat_id, welcome_message)
        return

    # Extract URLs from message
    urls = extract_urls(text)

    if not urls:
        # No URLs found - create a note instead
        session = SessionLocal()
        try:
            # Sanitize text
            sanitized_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text).strip()
            
            # Create note with title "FromTelegram"
            note_payload = NoteCreate(
                title="FromTelegram",
                content=sanitized_text,
                tags=[],
                collection=None,
                image_url=None,
            )
            
            create_note(session=session, note_data=note_payload)
            session.commit()
            
            await send_telegram_message(
                chat_id, "✅ Note saved! 📝"
            )
        except Exception as e:
            session.rollback()
            print(f"Error saving note: {e}")
            await send_telegram_message(
                chat_id, "❌ Sorry, there was an error saving your note. Please try again."
            )
        finally:
            session.close()
        return

    # Limit number of URLs to prevent abuse
    if len(urls) > 10:
        await send_telegram_message(
            chat_id, "❌ Too many URLs. Please send maximum 10 links at a time."
        )
        return

    # Validate all URLs before processing
    valid_urls = []
    for url in urls:
        try:
            parsed = urlparse(url)
            # Must have http or https scheme
            if parsed.scheme not in ("http", "https"):
                continue
            # Must have a valid domain
            if not parsed.netloc or len(parsed.netloc) < 3:
                continue
            # Limit URL length
            if len(url) > 2048:
                continue
            valid_urls.append(url)
        except Exception:
            continue

    if not valid_urls:
        await send_telegram_message(
            chat_id, "❌ No valid URLs found. URLs must start with http:// or https://"
        )
        return

    # Save links to database
    session = SessionLocal()
    saved_count = 0
    duplicate_count = 0
    saved_links = []
    duplicate_links = []

    try:
        for url in valid_urls:
            # Check if URL already exists
            existing_link = get_link_by_url(session, url)
            if existing_link:
                duplicate_count += 1
                duplicate_links.append({
                    "url": url,
                    "title": existing_link.title or url,
                    "id": existing_link.id
                })
                print(f"⚠️  Duplicate URL skipped: {url}")
                continue

            # Fetch metadata from URL
            print(f"🔍 Fetching metadata for: {url}")
            metadata = await fetch_url_metadata(url)

            # Determine title
            # Priority: user-provided text > fetched title > None
            user_text = text.replace(url, "").strip() if len(valid_urls) == 1 else None

            # Sanitize user-provided text
            if user_text:
                # Remove any control characters and limit length
                user_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', user_text)
                user_text = user_text[:500].strip()
                # If empty after sanitization, set to None
                if not user_text:
                    user_text = None

            title = user_text if user_text else metadata.get("title")

            # Collect tags: keywords only (no auto domain tagging)
            tags = []

            # Final sanitization: ensure tags are clean
            tags = [tag for tag in tags if tag and len(tag) > 0][:5]  # Max 5 tags

            # Create link payload
            link_payload = LinkCreate(
                url=url,  # type: ignore[arg-type]
                title=title,
                notes=None,
                tags=tags,
                collection=None,
                image_url=metadata.get("image"),
            )

            # Create link in database
            create_link(session=session, payload=link_payload)
            saved_count += 1
            saved_links.append({
                "url": url,
                "title": title or url,
                "tags": tags
            })

        session.commit()

        # Send confirmation with details (sanitize output for Telegram HTML)
        if saved_count == 0 and duplicate_count > 0:
            # All links were duplicates
            if duplicate_count == 1:
                dup = duplicate_links[0]
                safe_url = dup['url'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                response_text = (
                    f"⚠️ <b>Link already exists!</b>\n\n"
                    f"🔗 {safe_url}\n"
                    f"📄 {dup['title']}\n\n"
                    f"💡 This link is already in your collection."
                )
            else:
                response_text = (
                    f"⚠️ <b>All {duplicate_count} links already exist!</b>\n\n"
                    f"💡 These links are already in your collection."
                )
        elif saved_count > 0 and duplicate_count == 0:
            # All links were saved
            if saved_count == 1:
                link_info = saved_links[0]
                # Escape HTML special chars for Telegram
                safe_url = (link_info['url']
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;'))
                response_text = (
                    f"✅ <b>Link saved to your inbox!</b>\n\n"
                    f"🔗 {safe_url}\n"
                )
                if link_info['title'] and link_info['title'] != link_info['url']:
                    # Escape title for HTML
                    safe_title = (link_info['title']
                        .replace('&', '&amp;')
                        .replace('<', '&lt;')
                        .replace('>', '&gt;'))[:200]  # Limit display length
                    response_text += f"📄 {safe_title}\n"
                if link_info['tags']:
                    # Join tags safely
                    safe_tags = ', '.join([
                        tag.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        for tag in link_info['tags'][:5]
                    ])
                    response_text += f"🏷️ {safe_tags}"
            else:
                response_text = f"✅ {saved_count} links saved to your inbox!"
        else:
            # Mixed: some saved, some duplicates
            response_text = f"✅ {saved_count} new link(s) saved!\n"
            if duplicate_count > 0:
                response_text += f"⚠️ {duplicate_count} duplicate(s) skipped."

        await send_telegram_message(chat_id, response_text)

    except Exception as e:
        session.rollback()
        print(f"Error saving link: {e}")
        await send_telegram_message(
            chat_id, "❌ Sorry, there was an error saving your link. Please try again."
        )
    finally:
        session.close()


async def poll_telegram() -> None:
    """Main polling loop - checks Telegram for new messages"""
    global last_update_id

    print("🤖 Telegram polling started...")
    print("Waiting for messages...")

    while True:
        try:
            # Get updates with long polling (30 second timeout)
            updates = await get_updates(offset=last_update_id + 1 if last_update_id else None)

            for update in updates:
                update_id = update.get("update_id", 0)
                message = update.get("message")

                if message:
                    print(f"📨 New message from {message.get('chat', {}).get('first_name', 'Unknown')}")
                    await process_message(message)

                # Update the last_update_id to mark this update as processed
                if update_id > last_update_id:
                    last_update_id = update_id

        except Exception as e:
            print(f"Error in polling loop: {e}")
            await asyncio.sleep(5)  # Wait 5 seconds before retrying on error


async def start_polling() -> None:
    """Start the polling service"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️  TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Telegram polling disabled")
        return

    print("Starting Telegram bot polling service...")
    await poll_telegram()


if __name__ == "__main__":
    # Can be run standalone for testing
    asyncio.run(start_polling())
