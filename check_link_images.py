#!/usr/bin/env python3
"""Background task to check and update missing images for existing links."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.link_preview import fetch_link_metadata
from app.models import Link


async def check_link_image(link: Link, session: Session) -> bool:
    """Check and update image AND link health for a single link. Returns True if updated.
    
    Smart logic:
    - Check if link is accessible (not broken/deleted)
    - If link has no image: Try to fetch one
    - If link has image: Verify it's still valid (update timestamp)
    - Skip links marked as 'not_found' unless they're very old
    """
    try:
        print(f"🔍 Checking link: {link.url[:50]}...")

        # Skip if already marked as 'not_found' and checked recently
        if (link.image_check_status == "not_found" and
            link.image_checked_at and
            (datetime.now() - link.image_checked_at).days < 180):
            print("  ⏭️  Skipping - already marked as no image available")
            return False

        # Fetch metadata (this also checks if link is accessible)
        metadata = await fetch_link_metadata(link.url, timeout=10)

        # Update link health status
        link.last_checked_at = datetime.now()
        status_code = metadata.get("status_code")
        if isinstance(status_code, int):
            link.http_status_code = status_code

        if metadata.get("is_accessible"):
            link.link_status = "active"
            print("  ✓ Link is accessible")
        else:
            if metadata.get("status_code") in [404, 410]:
                link.link_status = "broken"
                print(f"  ❌ Link is broken (HTTP {metadata.get('status_code')})")
            elif metadata.get("status_code"):
                link.link_status = "error"
                print(f"  ⚠️  Link error (HTTP {metadata.get('status_code')})")
            else:
                link.link_status = "unreachable"
                print("  ⚠️  Link is unreachable")

        # Update the image if found
        updated = False
        image_url = metadata.get("image")
        if image_url and isinstance(image_url, str) and not link.image_url:
            link.image_url = image_url
            print(f"  ✓ Added image: {image_url[:50]}...")
            updated = True

        # Update checking metadata
        link.image_checked_at = datetime.now()
        link.image_check_status = "success" if metadata.get("image") else "not_found"

        session.commit()
        return updated

    except Exception as e:
        print(f"  ✗ Failed to check {link.url[:50]}...: {e}")
        link.image_checked_at = datetime.now()
        link.image_check_status = "failed"
        link.link_status = "error"
        link.last_checked_at = datetime.now()
        session.commit()
        return False


async def check_missing_images(batch_size: int = 50, max_age_days: int = 90):
    """Check links that don't have images or haven't been checked recently.
    
    Args:
        batch_size: Maximum number of links to check in one run
        max_age_days: Re-check images older than this (default 90 days)
                     Only applies to links WITH images (to catch broken ones)
    """
    session = SessionLocal()

    try:
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        links_to_check = session.query(Link).filter(
            # Priority 1: Links without images that haven't been checked yet
            ((Link.image_url.is_(None)) & (Link.image_checked_at.is_(None))) |
            # Priority 2: Links without images that failed before (retry with backoff)
            ((Link.image_url.is_(None)) &
             (Link.image_check_status == "failed") &
             (Link.image_checked_at < cutoff_date)) |
            # Priority 3: Links WITH images but old check (verify still valid)
            ((Link.image_url.is_not(None)) &
             ((Link.image_checked_at.is_(None)) |
              (Link.image_checked_at < cutoff_date)))
        ).limit(batch_size).all()

        if not links_to_check:
            print("✓ No links need image checking")
            return

        print(f"📋 Found {len(links_to_check)} links to check")

        updated_count = 0
        broken_count = 0
        for link in links_to_check:
            if await check_link_image(link, session):
                updated_count += 1
            if link.link_status == "broken":
                broken_count += 1

        print(f"✅ Completed! Updated {updated_count} links with images")
        if broken_count > 0:
            print(f"⚠️  Found {broken_count} broken/deleted links")

    except Exception as e:
        print(f"❌ Error during image checking: {e}")
        session.rollback()
    finally:
        session.close()


async def check_broken_images(batch_size: int = 20):
    """Check links that have images but might be broken (status = failed)."""
    session = SessionLocal()

    try:
        # Find links with failed image checks that we should retry
        links_to_check = session.query(Link).filter(
            Link.image_check_status == "failed"
        ).limit(batch_size).all()

        if not links_to_check:
            print("✓ No broken images to retry")
            return

        print(f"🔄 Retrying {len(links_to_check)} broken images")

        fixed_count = 0
        for link in links_to_check:
            # Clear the old image and try again
            old_image = link.image_url
            link.image_url = None

            if await check_link_image(link, session):
                fixed_count += 1
                print(f"  ✓ Fixed broken image for: {link.url[:50]}...")
            else:
                # Restore old image if we couldn't find a new one
                link.image_url = old_image
                session.commit()

        print(f"✅ Fixed {fixed_count} broken images")

    except Exception as e:
        print(f"❌ Error during broken image checking: {e}")
        session.rollback()
    finally:
        session.close()


async def list_broken_links():
    """List all broken/unreachable links found during checking."""
    session = SessionLocal()

    try:
        broken_links = session.query(Link).filter(
            Link.link_status.in_(["broken", "unreachable", "error"])
        ).all()

        if not broken_links:
            print("✓ No broken links found!")
            return

        print(f"\n🔴 Found {len(broken_links)} broken/problematic links:\n")

        for link in broken_links:
            status = link.link_status or "unknown"
            status_emoji = {
                "broken": "❌",
                "unreachable": "⚠️",
                "error": "⚠️"
            }.get(status, "?")

            print(f"{status_emoji} [{status.upper()}] {link.title or 'No title'}")
            print(f"   URL: {link.url}")
            if link.http_status_code:
                print(f"   HTTP Status: {link.http_status_code}")
            if link.last_checked_at:
                print(f"   Last checked: {link.last_checked_at.strftime('%Y-%m-%d %H:%M')}")
            print()

    except Exception as e:
        print(f"❌ Error listing broken links: {e}")
    finally:
        session.close()


async def main():
    """Main function to run image checking tasks."""
    import argparse

    parser = argparse.ArgumentParser(description="Check and update link images and health")
    parser.add_argument(
        "--mode",
        choices=["missing", "broken", "all", "list-broken"],
        default="missing",
        help="What to check: missing images, broken images, all, or list broken links"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of links to check per run"
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=90,
        help="Re-check images older than this many days (default: 90)"
    )

    args = parser.parse_args()

    if args.mode == "list-broken":
        await list_broken_links()
        return

    print(f"🖼️  Starting link health & image check (mode: {args.mode})")
    print(f"📊 Settings: batch_size={args.batch_size}, max_age={args.max_age_days} days")

    if args.mode in ["missing", "all"]:
        await check_missing_images(args.batch_size, args.max_age_days)

    if args.mode in ["broken", "all"]:
        await check_broken_images(args.batch_size)

    print("🎉 Link checking completed!")


if __name__ == "__main__":
    asyncio.run(main())
