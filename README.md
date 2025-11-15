# NoteKeep

Self-hosted FastAPI app for capturing links quickly and organising them later. Designed for NAS deployment with Docker, offline-friendly quick add, and simple categorisation workflows.

## Features

- Quick add flow with offline-capable web UI backed by service worker + IndexedDB queue.
- **Telegram Bot Integration** - Save links from your phone via Telegram using polling mode (no internet exposure needed - perfect for NAS!). Automatically fetches page titles and extracts tags. See [TELEGRAM_POLLING.md](TELEGRAM_POLLING.md).
- **Duplicate Detection** - Automatically detects and prevents duplicate links. URLs with different UTM tracking parameters (utm_source, utm_medium, etc.) are treated as duplicates.
- **Bulk import** from text (multiple URLs) or CSV file upload for mass link migration.
- REST API (`/api`) for integrations and shortcuts.
- Inbox view for uncategorised links and full library view with search and filters.
- Tag and collection management directly from the UI.
- Automatic domain tagging for quick categorization.
- Export endpoint (`GET /api/links/export`) for JSON backups.
- SQLite storage by default; can be pointed at Postgres by changing `DATABASE_URL`.

## Getting Started

### Configuration

Create a `.env` file in the project root if you need custom settings:

```bash
DATABASE_URL=sqlite:///./notekeep.db

# Optional: Telegram Bot Integration (Polling Mode - No Port Forwarding!)
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

No authentication required - the app is designed for personal/trusted network use.

**Telegram Bot Setup:** The bot uses polling mode, so you don't need to expose your NAS to the internet. Just set the token and start the app! See [TELEGRAM_POLLING.md](TELEGRAM_POLLING.md) for details.

### Local Development

Install dependencies and run the dev server:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .[dev]
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/inbox` to get started.

### Docker

Build and run with Compose:

```bash
docker compose up --build
```

The app listens on port `8000`. SQLite database persists to `notekeep.db` in the project root.

## Offline Capture Workflow

1. Bookmark or install the `/add` page on your phone (through "Add to Home Screen").
2. Share URLs to `https://your-host/add?url=...`.
3. If offline, the page queues submissions locally and syncs when reconnected.

### Bulk Import from Textarea

You can import multiple links at once by pasting them into the textarea on the Add page. All imported links are added to your inbox.

## Link Health & Image Management

NoteKeep automatically fetches preview images AND checks link health when links are added. For existing links, you can run the maintenance script:

```bash
# Initial migration: Check links missing images (run once)
python3 check_link_images.py --mode missing --batch-size 100

# Periodic maintenance: Check for broken/outdated links and images (recommended: weekly)
python3 check_link_images.py --mode missing --batch-size 50 --max-age-days 90

# Retry failed image fetches
python3 check_link_images.py --mode broken --batch-size 50

# Run all checks
python3 check_link_images.py --mode all

# List all broken/deleted links found
python3 check_link_images.py --mode list-broken
```

### Automated Maintenance (Recommended)

Set up a weekly cron job to check for broken links, missing images, and verify existing ones:

```bash
# Add to crontab (crontab -e)
# Run every Sunday at 2 AM - checks 50 links older than 90 days
0 2 * * 0 cd /path/to/notekeep && python3 check_link_images.py --mode missing --batch-size 50 --max-age-days 90
```

### How It Works

**Link Health Tracking:**
- **New links**: Health checked immediately when added
- **Status tracking**: `active`, `broken` (404/410), `unreachable`, or `error`
- **HTTP codes**: Stores status codes (404, 500, etc.) for debugging
- **Re-verification**: Links re-checked every 90 days to catch newly broken ones

**Image Management:**
- **New links**: Images fetched immediately when added
- **Old links without images**: Checked once, then marked to avoid redundant requests
- **Links with images**: Re-verified every 90 days alongside health checks
- **Failed fetches**: Retry with backoff (won't spam failed URLs)

The system tracks `last_checked_at`, `link_status`, `http_status_code`, `image_checked_at`, and `image_check_status` to prevent recursive checking while keeping your database fresh and alerting you to broken links.

## Testing

Run the test suite:

```bash
pytest
```

## Replacing Icons

Update the PWA icon at `app/static/icons/icon.svg` with your own artwork. Provide PNG assets if you need iOS home-screen icons.
