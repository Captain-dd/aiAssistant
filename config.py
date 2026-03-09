import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER   = os.getenv("TWILIO_FROM_NUMBER")
YOUR_PHONE_NUMBER    = os.getenv("YOUR_PHONE_NUMBER")
YOUR_TELEGRAM_CHAT_ID = os.getenv("YOUR_TELEGRAM_CHAT_ID")

MEMORIES_DIR   = "memories"
REMINDERS_FILE = "reminders.json"

CATEGORIZER_MODEL = "claude-haiku-4-5-20251001"   # fast + cheap for classification
BRAIN_MODEL       = "claude-sonnet-4-20250514"     # smart for answering/storing

REMINDER_POLL_INTERVAL = 30   # seconds
