"""
task_manager.py
Tasks are stored inside each memory's JSON file under the "tasks" key.
Status lifecycle: pending → in_progress → complete | cancelled
"""

import json
import os
from datetime import datetime
from config import MEMORIES_DIR
import memory_manager as mm


VALID_STATUSES = {"pending", "in_progress", "complete", "cancelled"}


# ── helpers ────────────────────────────────────────────────────────────────────

def _next_task_id(tasks: list) -> int:
    return max((t["id"] for t in tasks), default=0) + 1


# ── task CRUD ──────────────────────────────────────────────────────────────────

def add_task(memory_name: str, description: str, due: str = None) -> dict:
    """Add a task to a specific memory context."""
    data = mm._load(memory_name)
    task = {
        "id": _next_task_id(data["tasks"]),
        "description": description,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "due": due,
        "updated_at": None
    }
    data["tasks"].append(task)
    mm._save(memory_name, data)
    return task

def list_tasks(memory_name: str, status_filter: str = None) -> list[dict]:
    """List tasks in a memory, optionally filtered by status."""
    data = mm._load(memory_name)
    tasks = data.get("tasks", [])
    if status_filter:
        tasks = [t for t in tasks if t["status"] == status_filter]
    return tasks

def update_task_status(memory_name: str, task_id: int, new_status: str) -> dict:
    """Update a task's status."""
    if new_status not in VALID_STATUSES:
        return {"status": "error", "message": f"Invalid status. Choose from: {VALID_STATUSES}"}
    data = mm._load(memory_name)
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["status"] = new_status
            task["updated_at"] = datetime.now().isoformat()
            mm._save(memory_name, data)
            return {"status": "updated", "task": task}
    return {"status": "not_found", "task_id": task_id}

def edit_task(memory_name: str, task_id: int, new_description: str) -> dict:
    """Edit a task's description."""
    data = mm._load(memory_name)
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["description"] = new_description
            task["updated_at"] = datetime.now().isoformat()
            mm._save(memory_name, data)
            return {"status": "edited", "task": task}
    return {"status": "not_found", "task_id": task_id}

def delete_task(memory_name: str, task_id: int) -> dict:
    """Permanently delete a task."""
    data = mm._load(memory_name)
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    if len(data["tasks"]) == before:
        return {"status": "not_found", "task_id": task_id}
    mm._save(memory_name, data)
    return {"status": "deleted", "task_id": task_id}

def move_task(from_memory: str, task_id: int, to_memory: str) -> dict:
    """Move a task from one memory to another."""
    from_data = mm._load(from_memory)
    task = next((t for t in from_data["tasks"] if t["id"] == task_id), None)
    if not task:
        return {"status": "not_found", "task_id": task_id, "from": from_memory}
    # remove from source
    from_data["tasks"] = [t for t in from_data["tasks"] if t["id"] != task_id]
    mm._save(from_memory, from_data)
    # add to destination
    to_data = mm._load(to_memory)
    task["id"] = _next_task_id(to_data["tasks"])
    task["moved_at"] = datetime.now().isoformat()
    task["moved_from"] = from_memory
    to_data["tasks"].append(task)
    mm._save(to_memory, to_data)
    return {"status": "moved", "from": from_memory, "to": to_memory, "task": task}

def get_all_tasks() -> dict:
    """Return all tasks across all memories."""
    result = {}
    for name in mm.list_memories():
        tasks = list_tasks(name)
        if tasks:
            result[name] = tasks
    return result
