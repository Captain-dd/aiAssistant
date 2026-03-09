"""
main.py
Entry point — starts the reminder polling thread, then the Telegram bot.
"""

import logging
from config import TELEGRAM_BOT_TOKEN, YOUR_TELEGRAM_CHAT_ID, REMINDER_POLL_INTERVAL
import reminder_manager as rm
import telegram_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    # Build the Telegram app
    app = telegram_handler.build_app()

    # Start reminder polling thread
    rm.start_reminder_polling(
        bot=app.bot,
        chat_id=YOUR_TELEGRAM_CHAT_ID
    )

    logger.info("🚀 Memory Assistant starting...")
    logger.info(f"⏰ Reminder polling every {REMINDER_POLL_INTERVAL}s")
    logger.info("📱 Telegram bot polling started")

    # Start the bot (blocking)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
