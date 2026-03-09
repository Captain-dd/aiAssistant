"""
brain.py  ── Model 2
Processes the categorizer output and performs the actual action.
Uses Claude Sonnet (smart) for nuanced answering and intelligent storage.
"""

import json
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY, BRAIN_MODEL
import memory_manager as mm
import task_manager as tm
import reminder_manager as rm

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── helpers ────────────────────────────────────────────────────────────────────

def _llm(system: str, user: str, max_tokens: int = 1024) -> str:
    resp = client.messages.create(
        model=BRAIN_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return resp.content[0].text.strip()


def _fmt_entries(entries: list) -> str:
    if not entries:
        return "No entries found."
    lines = []
    for e in entries:
        lines.append(f"  [{e['id']}] {e['created_at']}: {e['content']}")
    return "\n".join(lines)


def _fmt_tasks(tasks: list) -> str:
    if not tasks:
        return "No tasks found."
    status_icons = {
        "pending": "🔵", "in_progress": "🟡",
        "complete": "✅", "cancelled": "❌"
    }
    lines = []
    for t in tasks:
        icon = status_icons.get(t["status"], "•")
        due = f"\n     Due: {t['due']}" if t.get("due") else ""
        moved = f"\n     Moved from: {t['moved_from']}" if t.get("moved_from") else ""
        lines.append(
            f"{icon} ID:{t['id']} — {t['description']}\n"
            f"     Status: {t['status']}{due}{moved}"
        )
    return "\n".join(lines)


# ── dispatch ───────────────────────────────────────────────────────────────────

def process(classification: dict, raw_message: str) -> str:
    """Main dispatcher — routes to the right handler based on type."""
    t = classification.get("type")

    if t == "storage":
        return _handle_storage(classification, raw_message)
    elif t == "question":
        return _handle_question(classification, raw_message)
    elif t == "task":
        return _handle_task(classification, raw_message)
    elif t == "reminder":
        return _handle_reminder(classification, raw_message)
    elif t == "management":
        return _handle_management(classification, raw_message)
    else:
        return "❓ I couldn't understand that. Please try rephrasing."


# ── storage ────────────────────────────────────────────────────────────────────

def _handle_storage(c: dict, raw: str) -> str:
    memory_name = c.get("memory", "personal")
    content = c.get("content", raw)

    # Let the brain clean/summarise what to store
    cleaned = _llm(
        system=(
            "You are a memory storage assistant. The user wants to store a piece of information. "
            "Return only the cleaned, concise version of what should be stored. "
            "Keep all key facts. Remove filler words. Keep it under 200 words. "
            "Do NOT add any explanation — just the text to store."
        ),
        user=content
    )

    entry = mm.add_entry(memory_name, cleaned)
    created = c.get("create_new_memory", False)
    new_tag = " *(new memory created)*" if created else ""

    return (
        f"✅ *Stored in `{memory_name}` memory*{new_tag}\n\n"
        f"📝 Entry #{entry['id']}: {cleaned}\n"
        f"🕐 {entry['created_at']}"
    )


# ── question ───────────────────────────────────────────────────────────────────

def _handle_question(c: dict, raw: str) -> str:
    search_in = c.get("memories_to_search", ["all"])
    query = c.get("query", raw)

    if "all" in search_in:
        all_data = mm.get_all_entries_across_memories()
    else:
        all_data = {}
        for name in search_in:
            mem = mm.get_memory(name)
            all_data[name] = {
                "entries": mem.get("entries", []),
                "tasks": mem.get("tasks", [])
            }

    if not all_data:
        return "🔍 No memories found yet. Start by telling me things to remember!"

    # Build context for Model 2
    context_parts = []
    for mem_name, mem_data in all_data.items():
        entries_text = _fmt_entries(mem_data.get("entries", []))
        tasks_text = _fmt_tasks(mem_data.get("tasks", []))
        context_parts.append(
            f"=== MEMORY: {mem_name.upper()} ===\n"
            f"ENTRIES:\n{entries_text}\n\n"
            f"TASKS:\n{tasks_text}"
        )

    context = "\n\n".join(context_parts)

    answer = _llm(
        system=(
            "You are a personal memory assistant. Answer the user's question using ONLY "
            "the memory context provided below. Be concise and friendly. "
            "If the answer is not in the context, say so honestly. "
            "Format the response nicely for Telegram (use emojis sparingly).\n\n"
            f"MEMORY CONTEXT:\n{context}"
        ),
        user=query,
        max_tokens=1024
    )

    return f"🧠 *From your memories:*\n\n{answer}"


# ── task ───────────────────────────────────────────────────────────────────────

def _handle_task(c: dict, raw: str) -> str:
    action = c.get("action", "list")
    memory = c.get("memory", "personal")
    task_id = c.get("task_id")
    description = c.get("description", "")
    status_filter = c.get("status_filter")
    to_memory = c.get("to_memory")

    if action == "add":
        task = tm.add_task(memory, description)
        return (
            f"Task added to {memory} memory\n\n"
            f"ID: {task['id']}\n"
            f"Task: {task['description']}\n"
            f"Status: pending\n\n"
            f"Use ID {task['id']} to edit, complete, cancel or move this task."
        )

    elif action in ("list", "list_all"):
        if action == "list_all":
            all_tasks = tm.get_all_tasks()
            if not all_tasks:
                return "📋 No tasks found across all memories."
            lines = ["📋 *All Tasks:*\n"]
            for mem, tasks in all_tasks.items():
                lines.append(f"*{mem.upper()}*\n{_fmt_tasks(tasks)}")
            return "\n\n".join(lines)
        else:
            tasks = tm.list_tasks(memory, status_filter)
            if not tasks:
                label = f" with status `{status_filter}`" if status_filter else ""
                return f"📋 No tasks in `{memory}`{label}."
            return f"📋 *Tasks in `{memory}`:*\n\n{_fmt_tasks(tasks)}"

    elif action in ("complete", "cancel", "in_progress"):
        status_map = {"complete": "complete", "cancel": "cancelled", "in_progress": "in_progress"}
        new_status = status_map[action]
        result = tm.update_task_status(memory, task_id, new_status)
        if result["status"] == "updated":
            icons = {"complete": "✅", "cancelled": "❌", "in_progress": "🟡"}
            icon = icons.get(new_status, "•")
            return (
                f"{icon} *Task #{task_id} updated in `{memory}`*\n\n"
                f"Status → `{new_status}`\n"
                f"{result['task']['description']}"
            )
        return f"❌ Task #{task_id} not found in `{memory}`."

    elif action == "edit":
        result = tm.edit_task(memory, task_id, description)
        if result["status"] == "edited":
            return f"✏️ *Task #{task_id} updated in `{memory}`*\n\n{description}"
        return f"❌ Task #{task_id} not found in `{memory}`."

    elif action == "delete":
        result = tm.delete_task(memory, task_id)
        if result["status"] == "deleted":
            return f"🗑️ Task #{task_id} deleted from `{memory}`."
        return f"❌ Task #{task_id} not found in `{memory}`."

    elif action == "move":
        result = tm.move_task(memory, task_id, to_memory)
        if result["status"] == "moved":
            return (
                f"🔄 *Task #{task_id} moved*\n\n"
                f"`{memory}` → `{to_memory}`\n"
                f"{result['task']['description']}"
            )
        return f"❌ Task #{task_id} not found in `{memory}`."

    return "❓ Unknown task action."


# ── reminder ───────────────────────────────────────────────────────────────────

def _handle_reminder(c: dict, raw: str) -> str:
    action = c.get("action", "add")
    text = c.get("text", "")
    due_str = c.get("due_datetime")
    reminder_id = c.get("reminder_id")

    if action == "add":
        if c.get("reminder_type") == "recurring":
            interval = c.get("interval_minutes")
            start_time = c.get("start_time")
            end_time = c.get("end_time")
            active_days = c.get("active_days", ["mon","tue","wed","thu","fri","sat","sun"])
            if not interval or not start_time or not end_time:
                return "❌ Please specify interval, start time and end time.\nExample: 'Remind me every hour from 8am to 11pm to drink water'"
            reminder = rm.add_recurring_reminder(text, interval, start_time, end_time, active_days)
            interval_str = f"every {interval // 60} hour(s)" if interval >= 60 else f"every {interval} minutes"
            
            days_display = ", ".join(active_days) if len(active_days) < 7 else "Every day"
            
            return (
                f"Recurring Reminder Set!\n\n"
                f"What: {text}\n"
                f"Fires: {interval_str}\n"
                f"Window: {start_time} to {end_time}\n"
                f"Days: {days_display}\n"
                f"Next fire: {reminder['next_fire'][:16].replace('T', ' ')}\n"
                f"ID: {reminder['id']}"
            )

        else:
            if not due_str:
                return "❌ I couldn't figure out when to remind you. Please specify a time."
            try:
                due = datetime.fromisoformat(due_str)
            except Exception:
                return f"❌ Invalid datetime format: {due_str}"
            if due < datetime.now():
                return "❌ That time is in the past!"
            reminder = rm.add_reminder(text, due)
            due_display = due.strftime("%d %b %Y at %I:%M %p")
            return (
                f"⏰ Reminder set!\n\n"
                f"📝 {text}\n"
                f"🕐 I'll call you on {due_display}\n"
                f"ID: #{reminder['id']}"
            )

    elif action == "list":
        reminders = rm.list_reminders()
        if not reminders:
            return "⏰ No upcoming reminders."
        lines = ["⏰ Your Reminders:\n"]
        for r in reminders:
            if r.get("type") == "recurring":
                paused = " (paused)" if r.get("paused") else ""
                lines.append(f"  🔁 [{r['id']}] {r['text']} — every {r['interval_minutes']}min | {r['start_time']}–{r['end_time']}{paused}")
            else:
                due = datetime.fromisoformat(r["due"]).strftime("%d %b %Y %I:%M %p")
                lines.append(f"  ⏰ [{r['id']}] {r['text']} — {due}")
        return "\n".join(lines)

    elif action == "pause":
        result = rm.pause_reminder(reminder_id)
        if result["status"] == "paused":
            return f"⏸ Reminder #{reminder_id} paused. Say 'resume reminder {reminder_id}' to restart."
        return f"❌ Reminder #{reminder_id} not found."

    elif action == "resume":
        result = rm.resume_reminder(reminder_id)
        if result["status"] == "resumed":
            return f"▶️ Reminder #{reminder_id} resumed!"
        return f"❌ Reminder #{reminder_id} not found."

    elif action == "edit":
        if not due_str:
            return "❌ Please specify the new time."
        try:
            new_due = datetime.fromisoformat(due_str)
        except Exception:
            return f"❌ Invalid datetime: {due_str}"
        if new_due < datetime.now():
            return "❌ That time is in the past!"
        result = rm.edit_reminder(reminder_id, new_due)
        if result["status"] == "updated":
            return f"✏️ Reminder #{reminder_id} updated to {new_due.strftime('%d %b %Y at %I:%M %p')}"
        return f"❌ Reminder #{reminder_id} not found."

    elif action == "delete":
        result = rm.delete_reminder(reminder_id)
        if result["status"] == "deleted":
            return f"🗑️ Reminder #{reminder_id} deleted."
        return f"❌ Reminder #{reminder_id} not found."

    return "❓ Unknown reminder action."


# ── management ─────────────────────────────────────────────────────────────────

def _handle_management(c: dict, raw: str) -> str:
    action = c.get("action")
    memory = c.get("memory", "personal")
    to_memory = c.get("to_memory")
    entry_id = c.get("entry_id")
    new_content = c.get("new_content", "")

    if action == "create":
        mm.create_memory(memory)
        return f"🗂️ Memory `{memory}` created successfully!"

    elif action == "delete":
        result = mm.delete_memory(memory)
        if result["status"] == "deleted":
            return f"🗑️ Memory `{memory}` and all its data has been deleted."
        return f"❌ Memory `{memory}` not found."

    elif action == "list":
        mems = mm.list_memories()
        if not mems:
            return "🗂️ No memories yet."
        lines = ["🗂️ *Your Memories:*\n"]
        for name in mems:
            data = mm.get_memory(name)
            entry_count = len(data.get("entries", []))
            task_count = len(data.get("tasks", []))
            lines.append(f"  • `{name}` — {entry_count} entries, {task_count} tasks")
        return "\n".join(lines)

    elif action == "move_entry":
        result = mm.move_entry(memory, entry_id, to_memory)
        if result["status"] == "moved":
            return (
                f"🔄 *Entry #{entry_id} moved*\n\n"
                f"`{memory}` → `{to_memory}`\n"
                f"New ID: #{result['new_entry']['id']}"
            )
        return f"❌ Entry #{entry_id} not found in `{memory}`."

    elif action == "edit_entry":
        result = mm.edit_entry(memory, entry_id, new_content)
        if result["status"] == "edited":
            return f"✏️ Entry #{entry_id} in `{memory}` updated.\n\n{new_content}"
        return f"❌ Entry #{entry_id} not found in `{memory}`."

    elif action == "delete_entry":
        result = mm.delete_entry(memory, entry_id)
        if result["status"] == "deleted":
            return f"🗑️ Entry #{entry_id} deleted from `{memory}`."
        return f"❌ Entry #{entry_id} not found in `{memory}`."

    return "❓ Unknown management action."
