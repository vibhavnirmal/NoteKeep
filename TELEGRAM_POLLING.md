# Telegram Bot - Polling Mode

## Overview

This Telegram bot integration uses **polling**, which means:
- ✅ Your NAS doesn't need to be exposed to the internet
- ✅ No port forwarding required
- ✅ No public URL needed
- ✅ Works behind firewalls
- ✅ Your NoteKeep app reaches out to Telegram (outbound only)

The bot periodically checks Telegram for new messages and processes them locally.

## How It Works

```
You → Telegram Bot → Telegram Servers
                          ↑
                          | (polling every 30s)
                          |
                     Your NAS (NoteKeep)
```

1. You send a link to your Telegram bot
2. Message sits on Telegram servers
3. Your NAS polls Telegram every ~30 seconds
4. NAS fetches new messages
5. Links are saved to your inbox
6. Bot sends confirmation back to you

## Setup (Simple!)

### 1. Environment Variable Already Set

Your `.env` already has the bot token:
```bash
TELEGRAM_BOT_TOKEN=8309725036:AAGTJyatx0BpMEkGEFKi4_Qxv5Sob6tKkjE
```

### 2. Two Ways to Run

#### Option A: Automatic (Built into App)

The poller starts automatically when you run your app:

```bash
uvicorn app.main:app --reload
```

You'll see:
```
🤖 Telegram polling started...
Waiting for messages...
```

That's it! Send a message to your bot on Telegram.

#### Option B: Separate Process (Recommended for Production)

Run the poller as a separate service:

```bash
# Terminal 1: Run your web app
uvicorn app.main:app

# Terminal 2: Run the Telegram poller
python -m app.run_telegram_poller
```

This approach is better because:
- Poller runs independently of web app
- Can restart one without affecting the other
- Easier to monitor logs separately

## Testing

### 1. Start the Service

**Built-in mode:**
```bash
uvicorn app.main:app
```

**Separate mode:**
```bash
python -m app.run_telegram_poller
```

### 2. Send a Test Message

1. Open Telegram
2. Find your bot (search by username)
3. Send: `/start`
4. You should see: "👋 Welcome to NoteKeep Bot!"

### 3. Send a Link

Send any URL:
```
https://github.com/microsoft/vscode
```

Within ~30 seconds, you should see:
- ✅ Confirmation message in Telegram
- 📨 Log in your terminal showing the message was processed
- 🔗 Link appears in your NoteKeep inbox

## Features

### Commands
- `/start` - Welcome message

### Link Saving
- Send any message with a URL
- **Automatically fetches page title** from the URL
- **Automatically extracts tags** (domain + keywords from page metadata)
- Multiple URLs in one message supported
- Optional custom title (your text will override auto-fetched title)

### Examples

**Single link (auto-fetch title and tags):**
```
https://github.com/microsoft/vscode
```
→ Fetches title: "Visual Studio Code - Code Editing. Redefined"
→ Adds tags: github.com, vscode, editor

**Single link with custom title:**
```
Check this awesome project! https://github.com/torvalds/linux
```
→ Uses your title: "Check this awesome project!"
→ Still adds tags: github.com, linux, kernel

**Multiple links:**
```
https://github.com
https://stackoverflow.com
https://dev.to
```
→ Saves all three links with auto-fetched titles and tags

**No URL:**
```
Hello
```
→ Bot responds: "❌ No valid URL found"

## Production Deployment

### Using systemd (Linux/NAS)

Create `/etc/systemd/system/notekeep-telegram.service`:

```ini
[Unit]
Description=NoteKeep Telegram Bot Poller
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/NoteKeep
Environment="TELEGRAM_BOT_TOKEN=8309725036:AAGTJyatx0BpMEkGEFKi4_Qxv5Sob6tKkjE"
Environment="DATABASE_URL=sqlite:///./notekeep.db"
ExecStart=/path/to/python -m app.run_telegram_poller
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable notekeep-telegram
sudo systemctl start notekeep-telegram
sudo systemctl status notekeep-telegram
```

View logs:
```bash
sudo journalctl -u notekeep-telegram -f
```

### Using Docker

If you're running NoteKeep in Docker, the poller is already included in the app startup (Option A).

No additional configuration needed!

### Using Docker Compose (Separate Container)

Add to your `docker-compose.yml`:

```yaml
services:
  notekeep-web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./notekeep.db:/app/notekeep.db
    environment:
      - DATABASE_URL=sqlite:///./notekeep.db

  notekeep-telegram:
    build: .
    command: python -m app.run_telegram_poller
    volumes:
      - ./notekeep.db:/app/notekeep.db
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DATABASE_URL=sqlite:///./notekeep.db
    restart: unless-stopped
```

## Advantages of Polling

| Feature | Polling |
|---------|---------|
| Internet exposure | ❌ Not needed |
| Port forwarding | ❌ Not needed |
| Public URL | ❌ Not needed |
| HTTPS cert | ❌ Not needed |
| Works on NAS | ✅ Yes |
| Message delay | ~30 seconds |
| Setup complexity | ✅ Simple |

## Monitoring

### Check if Poller is Running

**Built-in mode:**
Check your uvicorn logs for:
```
🤖 Telegram polling started...
```

**Separate mode:**
The terminal running `run_telegram_poller.py` shows:
```
NoteKeep Telegram Bot Poller
============================
Waiting for messages...
```

### When a Message Arrives

You'll see:
```
📨 New message from John
✅ Link saved to inbox
```

### Troubleshooting

**No messages being received:**
1. Check bot token is correct in `.env`
2. Verify internet connection (outbound to api.telegram.org)
3. Check logs for errors
4. Send `/start` to verify bot is working

**Polling stops:**
- Check for error messages in logs
- Verify database is accessible
- Restart the service

**Slow to receive messages:**
- Normal! Polling checks every ~30 seconds
- This is a trade-off for not exposing your NAS
- Still much better than manual checking!

## FAQ

**Q: Do I need to open any ports?**
A: No! Your NAS only makes outbound connections to Telegram.

**Q: Is this secure?**
A: Yes! Your NAS never accepts incoming connections. The bot token should still be kept secret.

**Q: How often does it check for messages?**
A: Every ~30 seconds using long polling (efficient, doesn't spam requests).

**Q: Does this use a lot of bandwidth?**
A: No! Long polling keeps one connection open and only receives data when there are new messages.

**Q: Can multiple people use the same bot?**
A: Yes! Each user's messages are processed independently and saved to the same inbox.

**Q: What if my NAS restarts?**
A: The poller will resume from the last processed message. No messages are lost.

## Comparison: Built-in vs Separate Process

### Built-in (Option A)
**Pros:**
- Simple - one command to start everything
- Good for development and testing
- Automatic startup

**Cons:**
- If web app crashes, poller stops too
- Shared logs (harder to debug)

### Separate (Option B)
**Pros:**
- Independent services
- Can restart one without affecting the other
- Separate logs (easier to monitor)
- Better for production

**Cons:**
- Need to manage two processes
- Slightly more complex setup

## Security Notes

- Keep `TELEGRAM_BOT_TOKEN` secret
- Don't commit `.env` to git
- Bot only saves links from users who message it
- Consider adding user whitelisting for production
- Database should have appropriate file permissions

## Next Steps

1. Start the poller (choose Option A or B)
2. Send `/start` to your bot
3. Send a test link
4. Check your inbox!

That's it - simple and secure! 🎉
