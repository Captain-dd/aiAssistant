"""
telegram_handler.py
Connects the Telegram bot to the categorizer + brain pipeline.
"""

import logging
from urllib import response
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes, CallbackContext

from config import TELEGRAM_BOT_TOKEN, YOUR_TELEGRAM_CHAT_ID
import categorizer
import brain

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler — every text message passes through here."""
    user_message = update.message.text
    chat_id = str(update.effective_chat.id)

    # Security: only respond to the owner
    if YOUR_TELEGRAM_CHAT_ID and chat_id != YOUR_TELEGRAM_CHAT_ID:
        await update.message.reply_text("⛔ Unauthorized.")
        return

    await update.message.reply_text("🤔 Processing...")

    try:
        # Model 1: Categorize
        classification = categorizer.categorize(user_message)

        # Model 2: Act
        response = brain.process(classification, user_message)

        try:
            await update.message.reply_text(response, parse_mode="Markdown")
        except Exception:
            # Fallback: send without markdown if parsing fails
            await update.message.reply_text(response, parse_mode=None)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text(
                f"❌ Something went wrong:\n{str(e)}",
                parse_mode=None
            )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Personal Memory Assistant is active!*\n\n"
        "Just talk to me naturally:\n"
        "• Tell me things to remember\n"
        "• Ask me questions\n"
        "• Add/manage tasks\n"
        "• Set reminders\n\n"
        "I'll figure out what to do. 🧠",
        parse_mode="Markdown"
    )


async def cmd_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick command to list all memories."""
    import memory_manager as mm
    mems = mm.list_memories()
    if not mems:
        await update.message.reply_text("🗂️ No memories yet.")
        return
    lines = ["🗂️ *Your Memories:*\n"]
    for name in mems:
        data = mm.get_memory(name)
        lines.append(f"  • `{name}` — {len(data.get('entries',[]))} entries, {len(data.get('tasks',[]))} tasks")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick command to list all reminders."""
    import reminder_manager as rm
    reminders = rm.list_reminders()
    if not reminders:
        await update.message.reply_text("⏰ No upcoming reminders.")
        return
    from datetime import datetime
    lines = ["⏰ *Upcoming Reminders:*\n"]
    for r in reminders:
        due = datetime.fromisoformat(r["due"]).strftime("%d %b %Y %I:%M %p")
        lines.append(f"  [{r['id']}] {r['text']} — {due}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def build_app():
    """Build and return the Telegram Application."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("memories", cmd_memories))
    app.add_handler(CommandHandler("reminders", cmd_reminders))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
