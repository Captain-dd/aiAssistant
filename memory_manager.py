"""
memory_manager.py
Handles all read/write/move/edit operations on local JSON memory files.
Each memory is a file: memories/<name>.json
"""

import json
import os
from datetime import datetime
from config import MEMORIES_DIR


# ── helpers ────────────────────────────────────────────────────────────────────

def _ensure_dir():
    os.makedirs(MEMORIES_DIR, exist_ok=True)

def _path(name: str) -> str:
    name = name.lower().strip().replace(" ", "_")
    return os.path.join(MEMORIES_DIR, f"{name}.json")

def _blank(name: str) -> dict:
    return {
        "name": name,
        "created_at": datetime.now().isoformat(),
        "entries": [],
        "tasks": []
    }

def _load(name: str) -> dict:
    _ensure_dir()
    p = _path(name)
    if not os.path.exists(p):
        return _blank(name)
    with open(p, "r") as f:
        return json.load(f)

def _save(name: str, data: dict):
    _ensure_dir()
    with open(_path(name), "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── memory-level operations ────────────────────────────────────────────────────

def list_memories() -> list[str]:
    """Return all memory names (without .json extension)."""
    _ensure_dir()
    return [
        f.replace(".json", "")
        for f in os.listdir(MEMORIES_DIR)
        if f.endswith(".json")
    ]

def create_memory(name: str) -> dict:
    """Create a new memory file (idempotent)."""
    name = name.lower().strip().replace(" ", "_")
    data = _load(name)   # returns blank if new
    _save(name, data)
    return {"status": "created", "memory": name}

def delete_memory(name: str) -> dict:
    """Delete an entire memory file."""
    p = _path(name)
    if not os.path.exists(p):
        return {"status": "not_found", "memory": name}
    os.remove(p)
    return {"status": "deleted", "memory": name}

def get_memory(name: str) -> dict:
    """Return full memory dict."""
    return _load(name)


# ── entry-level operations ─────────────────────────────────────────────────────

def add_entry(memory_name: str, content: str) -> dict:
    """Append a new entry to a memory. Creates memory if needed."""
    data = _load(memory_name)
    entry_id = (max((e["id"] for e in data["entries"]), default=0) + 1)
    entry = {
        "id": entry_id,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    data["entries"].append(entry)
    _save(memory_name, data)
    return entry

def edit_entry(memory_name: str, entry_id: int, new_content: str) -> dict:
    """Edit an existing entry by ID."""
    data = _load(memory_name)
    for entry in data["entries"]:
        if entry["id"] == entry_id:
            entry["content"] = new_content
            entry["edited_at"] = datetime.now().isoformat()
            _save(memory_name, data)
            return {"status": "edited", "entry": entry}
    return {"status": "not_found", "entry_id": entry_id}

def delete_entry(memory_name: str, entry_id: int) -> dict:
    """Delete a single entry from a memory."""
    data = _load(memory_name)
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    if len(data["entries"]) == before:
        return {"status": "not_found", "entry_id": entry_id}
    _save(memory_name, data)
    return {"status": "deleted", "entry_id": entry_id}

def move_entry(from_memory: str, entry_id: int, to_memory: str) -> dict:
    """Move an entry from one memory to another."""
    from_data = _load(from_memory)
    entry = next((e for e in from_data["entries"] if e["id"] == entry_id), None)
    if not entry:
        return {"status": "not_found", "entry_id": entry_id, "from": from_memory}
    # remove from source
    from_data["entries"] = [e for e in from_data["entries"] if e["id"] != entry_id]
    _save(from_memory, from_data)
    # add to destination
    new_entry = add_entry(to_memory, entry["content"])
    return {
        "status": "moved",
        "from": from_memory,
        "to": to_memory,
        "original_id": entry_id,
        "new_entry": new_entry
    }

def search_memory(memory_name: str, query: str) -> list[dict]:
    """Simple substring search within a memory."""
    data = _load(memory_name)
    q = query.lower()
    return [e for e in data["entries"] if q in e["content"].lower()]

def get_all_entries_across_memories() -> dict:
    """Return all entries from all memories — used for cross-memory questions."""
    result = {}
    for name in list_memories():
        data = _load(name)
        result[name] = {
            "entries": data.get("entries", []),
            "tasks": data.get("tasks", [])
        }
    return result
