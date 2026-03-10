import os
from dotenv import load_dotenv
import os

# Use /app/data on Railway, local folder on Mac
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None

MEMORIES_DIR       = "/app/data/memories" if IS_RAILWAY else "memories"
REMINDERS_FILE     = "/app/data/reminders.json" if IS_RAILWAY else "reminders.json"
DAILY_SUMMARY_FILE = "/app/data/daily_summary.json" if IS_RAILWAY else "daily_summary.json"

load_dotenv()

TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER   = os.getenv("TWILIO_FROM_NUMBER")
YOUR_PHONE_NUMBER    = os.getenv("YOUR_PHONE_NUMBER")
YOUR_TELEGRAM_CHAT_ID = os.getenv("YOUR_TELEGRAM_CHAT_ID")

# Use /app/data on Railway, local folder on Mac
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None

import os

# Try volume path first, fall back to local
_base = "/app/data" if os.path.exists("/app/data") else "."

MEMORIES_DIR       = os.path.join(_base, "memories")
REMINDERS_FILE     = os.path.join(_base, "reminders.json")
DAILY_SUMMARY_FILE = os.path.join(_base, "daily_summary.json")

MEMORIES_DIR   = "memories"
REMINDERS_FILE = "reminders.json"

CATEGORIZER_MODEL = "claude-haiku-4-5-20251001"   # fast + cheap for classification
BRAIN_MODEL       = "claude-sonnet-4-20250514"     # smart for answering/storing

REMINDER_POLL_INTERVAL = 30   # seconds
