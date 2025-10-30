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

## Bulk Import

Import multiple links at once using the Bulk Import tab on the Add page:

### Text Input
Paste multiple URLs, one per line. Optionally add titles using the pipe separator:
```
https://example.com/article1
https://example.com/article2 | My Article Title
```

### CSV Upload
Upload a CSV file with the following columns:
- `url` (required) - The link URL
- `title` (optional) - Custom title for the link
- `notes` (optional) - Additional notes
- `tags` (optional) - Comma-separated tags

See `sample_import.csv` for an example format.

All imported links are added to your inbox as unread/new items.

## Testing

Run the test suite:

```bash
pytest
```

## Replacing Icons

Update the PWA icon at `app/static/icons/icon.svg` with your own artwork. Provide PNG assets if you need iOS home-screen icons.
