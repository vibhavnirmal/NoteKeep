"""
Standalone Telegram Poller

Run this script separately from your main app to poll Telegram for messages.
This is useful if you want to run the poller as a separate service.

Usage:
    python -m app.run_telegram_poller
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.telegram_poller import start_polling

if __name__ == "__main__":
    print("=" * 60)
    print("NoteKeep Telegram Bot Poller")
    print("=" * 60)
    print()
    print("This service will check Telegram for new messages")
    print("and save links to your NoteKeep inbox.")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    try:
        asyncio.run(start_polling())
    except KeyboardInterrupt:
        print("\n\n👋 Telegram poller stopped")
        print("Goodbye!")
