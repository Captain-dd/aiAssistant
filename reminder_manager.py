"""
reminder_manager.py
Reminders stored in reminders.json.
Background thread polls every 30 seconds.
Fires via Twilio call + Telegram message when due.
"""

import json
import os
import threading
import time
import requests
from datetime import datetime, timedelta

from config import (
    REMINDERS_FILE, REMINDER_POLL_INTERVAL, TELEGRAM_BOT_TOKEN,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER, YOUR_PHONE_NUMBER,
    YOUR_TELEGRAM_CHAT_ID
)


# ── JSON helpers ───────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(REMINDERS_FILE):
        return {"reminders": []}
    with open(REMINDERS_FILE, "r") as f:
        return json.load(f)

def _save(data: dict):
    with open(REMINDERS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def _next_id(reminders: list) -> int:
    return max((r["id"] for r in reminders), default=0) + 1


# ── reminder CRUD ──────────────────────────────────────────────────────────────

def add_reminder(reminder_text: str, due_datetime: datetime) -> dict:
    data = _load()
    reminder = {
        "id": _next_id(data["reminders"]),
        "text": reminder_text,
        "due": due_datetime.isoformat(),
        "created_at": datetime.now().isoformat(),
        "fired": False
    }
    data["reminders"].append(reminder)
    _save(data)
    return reminder

def list_reminders(include_fired: bool = False) -> list[dict]:
    data = _load()
    reminders = data["reminders"]
    if not include_fired:
        reminders = [r for r in reminders if not r["fired"]]
    return reminders

def delete_reminder(reminder_id: int) -> dict:
    data = _load()
    before = len(data["reminders"])
    data["reminders"] = [r for r in data["reminders"] if r["id"] != reminder_id]
    if len(data["reminders"]) == before:
        return {"status": "not_found", "id": reminder_id}
    _save(data)
    return {"status": "deleted", "id": reminder_id}

def edit_reminder(reminder_id: int, new_due: datetime) -> dict:
    """Update the due datetime of an existing reminder."""
    data = _load()
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            r["due"] = new_due.isoformat()
            r["edited_at"] = datetime.now().isoformat()
            _save(data)
            return {"status": "updated", "reminder": r}
    return {"status": "not_found", "id": reminder_id}


def _mark_fired(reminder_id: int):
    data = _load()
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            r["fired"] = True
            r["fired_at"] = datetime.now().isoformat()
    _save(data)

def add_recurring_reminder(reminder_text, interval_minutes, start_time, end_time, active_days):
    data = _load()
    now = datetime.now()
    start_h, start_m = map(int, start_time.split(":"))
    
    first_fire = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)

    # If start time already passed, find next interval within today's window
    if first_fire <= now:
        end_h, end_m = map(int, end_time.split(":"))
        end_today = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        
        # Keep adding intervals until we find one in the future
        while first_fire <= now:
            first_fire += timedelta(minutes=interval_minutes)
        
        # If next interval is past end time, schedule for tomorrow at start
        if first_fire > end_today:
            first_fire = (now + timedelta(days=1)).replace(
                hour=start_h, minute=start_m, second=0, microsecond=0
            )
    reminder = {
        "id": _next_id(data["reminders"]),
        "type": "recurring",
        "text": reminder_text,
        "interval_minutes": interval_minutes,
        "start_time": start_time,
        "end_time": end_time,
        "active_days": active_days,
        "next_fire": first_fire.isoformat(),
        "created_at": now.isoformat(),
        "fired": False,
        "paused": False,
        "paused_until": None,
        "last_fired_at": None
    }
    data["reminders"].append(reminder)
    _save(data)
    return reminder

def pause_reminder(reminder_id):
    data = _load()
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            r["paused"] = True
            r["paused_until"] = None
            _save(data)
            return {"status": "paused", "reminder": r}
    return {"status": "not_found"}

def resume_reminder(reminder_id):
    data = _load()
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            r["paused"] = False
            r["paused_until"] = None
            _save(data)
            return {"status": "resumed", "reminder": r}
    return {"status": "not_found"}

def _update_next_fire(reminder_id, next_fire):
    data = _load()
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            r["next_fire"] = next_fire.isoformat()
            r["last_fired_at"] = datetime.now().isoformat()
    _save(data)

def _calculate_next_fire(reminder, from_time):
    interval = timedelta(minutes=reminder["interval_minutes"])
    end_h, end_m = map(int, reminder["end_time"].split(":"))
    start_h, start_m = map(int, reminder["start_time"].split(":"))
    candidate = from_time + interval
    end_today = candidate.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if candidate > end_today:
        candidate = candidate.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        candidate += timedelta(days=1)
    return candidate

def _is_within_window(reminder, now):
    start_h, start_m = map(int, reminder["start_time"].split(":"))
    end_h, end_m = map(int, reminder["end_time"].split(":"))
    current = now.hour * 60 + now.minute
    return (start_h * 60 + start_m) <= current <= (end_h * 60 + end_m)


# ── Twilio call ────────────────────────────────────────────────────────────────

def _make_twilio_call(reminder_text: str):
    """Make a Twilio voice call with a fixed TTS message."""
    try:
        from twilio.rest import Client
        from twilio.twiml.voice_response import VoiceResponse

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        twiml = VoiceResponse()
        twiml.say(
            "Hello! You have a reminder from your personal assistant. "
            "Please check your Telegram for the full details.",
            voice="alice",
            language="en-IN"
        )

        call = client.calls.create(
            to=YOUR_PHONE_NUMBER,
            from_=TWILIO_FROM_NUMBER,
            twiml=str(twiml)
        )
        print(f"[Twilio] Call initiated: {call.sid}")
        return True
    except Exception as e:
        print(f"[Twilio] Call failed: {e}")
        return False


# ── Telegram notification ──────────────────────────────────────────────────────

def _send_telegram_reminder(reminder: dict):
    """Send reminder via Telegram Bot HTTP API directly — no async needed."""
    try:
        r_type = reminder.get("type", "one_shot")

        if r_type == "recurring":
            msg = (
                f"⏰ *REMINDER*\n\n"
                f"📝 {reminder['text']}\n\n"
                f"🔁 Every {reminder['interval_minutes']} min "
                f"({reminder['start_time']} – {reminder['end_time']})"
            )
        else:
            due_str = datetime.fromisoformat(reminder["due"]).strftime("%d %b %Y %I:%M %p")
            msg = (
                f"⏰ *REMINDER FIRED!*\n\n"
                f"📝 {reminder['text']}\n\n"
                f"🕐 Was due at: {due_str}"
            )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": YOUR_TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[Telegram] Reminder sent successfully")
        else:
            print(f"[Telegram] Failed: {response.status_code} — {response.text}")
    except Exception as e:
        print(f"[Telegram] Reminder notification failed: {e}")

# ── Polling thread ─────────────────────────────────────────────────────────────

def start_reminder_polling(bot=None, chat_id: str = None):
    """Start background thread that checks reminders every 30 seconds."""

    def poll():
        print(f"[Reminder] Polling started (every {REMINDER_POLL_INTERVAL}s)")
        while True:
            time.sleep(REMINDER_POLL_INTERVAL)
            try:
                now = datetime.now()
                data = _load()
                for reminder in data["reminders"]:
                    r_type = reminder.get("type", "one_shot")

                    if r_type == "one_shot":
                        if reminder["fired"]:
                            continue
                        due = datetime.fromisoformat(reminder["due"])
                        if now >= due:
                            print(f"[Reminder] FIRING one-shot: {reminder['text']}")
                            _make_twilio_call(reminder["text"])
                            _send_telegram_reminder(reminder)
                            _mark_fired(reminder["id"])

                    elif r_type == "recurring":
                        if reminder.get("paused"):
                            continue
                        if not _is_within_window(reminder, now):
                            continue
                        next_fire = datetime.fromisoformat(reminder["next_fire"])
                        if now >= next_fire:
                            print(f"[Reminder] FIRING recurring: {reminder['text']}")
                            _make_twilio_call(reminder["text"])
                            _send_telegram_reminder(reminder)
                            new_next = _calculate_next_fire(reminder, now)
                            _update_next_fire(reminder["id"], new_next)

            except Exception as e:
                print(f"[Reminder] Poll error: {e}")

    thread = threading.Thread(target=poll, daemon=True, name="ReminderPoller")
    thread.start()
    return thread
