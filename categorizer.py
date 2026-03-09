"""
categorizer.py  ── Model 1
Reads the raw user message and returns a structured JSON classification.
Uses Claude Haiku (fast + cheap) since this runs on every single message.
"""

import json
import anthropic
from datetime import datetime
from config import ANTHROPIC_API_KEY, CATEGORIZER_MODEL
import memory_manager as mm

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """You are a message classifier for a personal AI memory assistant.
Analyze the user's message and classify it into one of these types.
You MUST respond with ONLY valid JSON — no explanation, no markdown, no extra text.

Types and their JSON schemas:

1. STORAGE — user wants to save/record something
{
  "type": "storage",
  "memory": "<memory_name>",        // which memory to store in (default = "personal")
  "create_new_memory": true/false,  // true if this memory doesn't exist yet
  "content": "<cleaned content to store>"
}

2. QUESTION — user is asking something from their memories
{
  "type": "question",
  "memories_to_search": ["<mem1>", "<mem2>"],  // specific memories, or ["all"] for everything
  "query": "<the actual question>"
}

3. TASK — user wants to manage tasks
{
  "type": "task",
  "action": "add|list|complete|cancel|in_progress|edit|delete|move|list_all",
  "memory": "<context, e.g. work, personal>",
  "to_memory": "<destination memory, only for move action>",
  "description": "<task description, for add/edit>",
  "task_id": <integer or null>,
  "status_filter": "<pending|in_progress|complete|cancelled|null>"
}

4. REMINDER — user wants to manage a reminder
For one-shot: { "type": "reminder", "action": "add", "reminder_type": "one_shot",
  "text": "...", "due_datetime": "2025-01-15T14:30:00", "reminder_id": null,
  "interval_minutes": null, "start_time": null, "end_time": null, "active_days": null }
For recurring: { "type": "reminder", "action": "add", "reminder_type": "recurring",
  "text": "...", "due_datetime": null, "reminder_id": null,
  "interval_minutes": 60, "start_time": "08:00", "end_time": "23:00",
  "active_days": ["mon","tue","wed","thu","fri","sat","sun"] }
For other actions: { "type": "reminder", "action": "list|delete|edit|pause|resume",
  "reminder_type": null, "text": null, "due_datetime": null,
  "interval_minutes": null, "start_time": null, "end_time": null,
  "active_days": null, "reminder_id": <integer> }
Rules: "every hour from 8am to 11pm" -> interval_minutes=60, start=08:00, end=23:00
"every 30 min" -> interval_minutes=30. "every weekday" -> active_days mon-fri only.
"pause reminder X" -> action=pause. "resume reminder X" -> action=resume.

5. MANAGEMENT — user wants to manage memories themselves (not entries)
{
  "type": "management",
  "action": "create|delete|list|move_entry|edit_entry|delete_entry",
  "memory": "<source memory name>",
  "to_memory": "<destination memory, only for move_entry>",
  "entry_id": <integer or null>,
  "new_content": "<new content for edit_entry>"
}

Rules:
- Memory names must be lowercase with underscores (e.g. post_office, it_work, finance)
- If user says "store this" or just states a fact, classify as storage
- If user says "remind me in X minutes/hours", compute the absolute datetime from current time
- Default memory for vague statements is "personal"
- Today's datetime for computing relative times: {NOW}
- Available memories: {MEMORIES}
"""


def categorize(user_message: str) -> dict:
    """
    Call Model 1 (Haiku) to classify the user message.
    Returns a parsed dict.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memories = mm.list_memories() or ["personal"]

    prompt = SYSTEM_PROMPT.replace("{NOW}", now).replace("{MEMORIES}", str(memories))

    response = client.messages.create(
        model=CATEGORIZER_MODEL,
        max_tokens=512,
        system=prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        result = json.loads(raw)
        print(f"[Categorizer] '{user_message[:60]}...' → {result['type']}")
        return result
    except json.JSONDecodeError as e:
        print(f"[Categorizer] JSON parse error: {e}\nRaw: {raw}")
        # Fallback: treat as question
        return {
            "type": "question",
            "memories_to_search": ["all"],
            "query": user_message
        }
