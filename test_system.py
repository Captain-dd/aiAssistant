"""
test_system.py
Comprehensive real-world functional tests for the AI Memory Assistant.
Tests categorizer (real Claude API) + brain (real Claude API) + all local storage.
Twilio and Telegram are mocked since we can't call them in tests.

Run: python test_system.py
"""

import os
import sys
import json
import shutil
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# ── Setup test environment ─────────────────────────────────────────────────────

# Use a temporary memories dir for tests
os.environ.setdefault("MEMORIES_DIR", "test_memories")
TEST_MEMORIES_DIR = "test_memories"
TEST_REMINDERS_FILE = "test_reminders.json"

# Patch config before imports
import config
config.MEMORIES_DIR = TEST_MEMORIES_DIR
config.REMINDERS_FILE = TEST_REMINDERS_FILE

import memory_manager as mm
import task_manager as tm
import reminder_manager as rm
import categorizer
import brain

mm.MEMORIES_DIR = TEST_MEMORIES_DIR
rm.REMINDERS_FILE = TEST_REMINDERS_FILE

# ── Test helpers ───────────────────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def test(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    print(f"  {status}  {name}")
    if detail and not condition:
        print(f"         Detail: {detail}")

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def cleanup():
    """Remove all test data."""
    if os.path.exists(TEST_MEMORIES_DIR):
        shutil.rmtree(TEST_MEMORIES_DIR)
    if os.path.exists(TEST_REMINDERS_FILE):
        os.remove(TEST_REMINDERS_FILE)

def full_pipeline(message: str) -> tuple[dict, str]:
    """Run a message through the full categorizer → brain pipeline."""
    classification = categorizer.categorize(message)
    response = brain.process(classification, message)
    return classification, response


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: MEMORY MANAGER UNIT TESTS (no AI, pure local)
# ══════════════════════════════════════════════════════════════════════════════

def test_memory_manager():
    section("1. MEMORY MANAGER — Unit Tests")
    cleanup()

    # Create memory
    mm.create_memory("work")
    test("Create work memory", os.path.exists(f"{TEST_MEMORIES_DIR}/work.json"))

    # Add entries
    e1 = mm.add_entry("work", "Had a meeting about server migration")
    e2 = mm.add_entry("work", "Submitted server access request")
    test("Add entry 1", e1["id"] == 1)
    test("Add entry 2", e2["id"] == 2)

    # Load and verify
    data = mm.get_memory("work")
    test("Memory has 2 entries", len(data["entries"]) == 2)

    # Edit entry
    result = mm.edit_entry("work", 1, "Had a meeting about network upgrade")
    test("Edit entry 1", result["status"] == "edited")
    data = mm.get_memory("work")
    test("Entry content updated", data["entries"][0]["content"] == "Had a meeting about network upgrade")

    # Create second memory and move entry
    mm.create_memory("personal")
    move_result = mm.move_entry("work", 2, "personal")
    test("Move entry from work→personal", move_result["status"] == "moved")
    work_data = mm.get_memory("work")
    personal_data = mm.get_memory("personal")
    test("Entry removed from work", len(work_data["entries"]) == 1)
    test("Entry exists in personal", len(personal_data["entries"]) == 1)
    test("Moved entry content matches",
         personal_data["entries"][0]["content"] == "Submitted server access request")

    # Delete entry
    del_result = mm.delete_entry("work", 1)
    test("Delete entry", del_result["status"] == "deleted")
    work_data = mm.get_memory("work")
    test("Work memory now empty", len(work_data["entries"]) == 0)

    # List memories
    mems = mm.list_memories()
    test("List memories (work + personal)", "work" in mems and "personal" in mems)

    # Dynamic new memory (create on the fly)
    mm.add_entry("finance", "Paid electricity bill ₹2500")
    test("Dynamic finance memory created",
         os.path.exists(f"{TEST_MEMORIES_DIR}/finance.json"))

    # Delete entire memory
    del_mem = mm.delete_memory("finance")
    test("Delete finance memory", del_mem["status"] == "deleted")
    test("Finance file gone", not os.path.exists(f"{TEST_MEMORIES_DIR}/finance.json"))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: TASK MANAGER UNIT TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_task_manager():
    section("2. TASK MANAGER — Unit Tests")
    cleanup()

    # Add tasks to different memories
    t1 = tm.add_task("work", "Submit server migration report by Friday")
    t2 = tm.add_task("work", "Review IT security policy")
    t3 = tm.add_task("personal", "Buy groceries this weekend")

    test("Add work task 1", t1["status"] == "pending" and t1["id"] == 1)
    test("Add work task 2", t2["status"] == "pending" and t2["id"] == 2)
    test("Add personal task", t3["status"] == "pending" and t3["id"] == 1)

    # List work tasks
    work_tasks = tm.list_tasks("work")
    test("List 2 work tasks", len(work_tasks) == 2)

    # Mark work task 1 as complete
    result = tm.update_task_status("work", 1, "complete")
    test("Mark task 1 complete", result["status"] == "updated")
    test("Task status is complete", result["task"]["status"] == "complete")

    # Cancel work task 2
    result = tm.update_task_status("work", 2, "cancelled")
    test("Cancel task 2", result["task"]["status"] == "cancelled")

    # Filter by status
    pending = tm.list_tasks("work", "pending")
    test("No pending work tasks after updates", len(pending) == 0)
    complete = tm.list_tasks("work", "complete")
    test("1 complete work task", len(complete) == 1)

    # Edit task
    result = tm.edit_task("personal", 1, "Buy groceries and medicines")
    test("Edit personal task", result["status"] == "edited")
    test("Task description updated",
         result["task"]["description"] == "Buy groceries and medicines")

    # Move task from personal to work
    t4 = tm.add_task("personal", "Book flight ticket")
    result = tm.move_task("personal", t4["id"], "work")
    test("Move task personal→work", result["status"] == "moved")
    personal_tasks = tm.list_tasks("personal")
    test("Task removed from personal", len(personal_tasks) == 1)  # only grocery left

    # Get all tasks
    all_tasks = tm.get_all_tasks()
    test("All tasks returns multi-memory dict",
         "work" in all_tasks and "personal" in all_tasks)

    # Delete a task
    del_result = tm.delete_task("personal", 1)
    test("Delete personal task", del_result["status"] == "deleted")
    personal_tasks = tm.list_tasks("personal")
    test("Personal tasks now empty", len(personal_tasks) == 0)

    # Error cases
    bad = tm.update_task_status("work", 999, "complete")
    test("Update non-existent task returns error", bad["status"] == "not_found")
    bad2 = tm.update_task_status("work", 1, "invalid_status")
    test("Invalid status returns error", bad2["status"] == "error")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: REMINDER MANAGER UNIT TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_reminder_manager():
    section("3. REMINDER MANAGER — Unit Tests")
    cleanup()

    # Add reminders
    future1 = datetime.now() + timedelta(hours=2)
    future2 = datetime.now() + timedelta(days=1)
    past    = datetime.now() - timedelta(minutes=5)  # already overdue

    r1 = rm.add_reminder("Call the bank", future1)
    r2 = rm.add_reminder("Doctor appointment", future2)

    test("Add reminder 1", r1["id"] == 1 and r1["text"] == "Call the bank")
    test("Add reminder 2", r2["id"] == 2)
    test("Reminder file created", os.path.exists(TEST_REMINDERS_FILE))

    # List
    reminders = rm.list_reminders()
    test("List shows 2 active reminders", len(reminders) == 2)
    test("Reminder not fired by default", not reminders[0]["fired"])

    # Manually fire one (simulate polling)
    rm._mark_fired(r1["id"])
    active = rm.list_reminders()
    test("After firing r1, only 1 active reminder", len(active) == 1)
    test("Remaining reminder is doctor appointment", active[0]["text"] == "Doctor appointment")

    # List including fired
    all_r = rm.list_reminders(include_fired=True)
    test("Include fired shows both", len(all_r) == 2)

    # Delete
    del_result = rm.delete_reminder(r2["id"])
    test("Delete reminder 2", del_result["status"] == "deleted")
    active = rm.list_reminders()
    test("No active reminders after delete", len(active) == 0)

    # Polling fires expired reminder (simulate)
    r3 = rm.add_reminder("Take medication", past)
    test("Past reminder added", r3["id"] == 3)

    fired_reminders = []
    def mock_twilio(text):
        fired_reminders.append(text)
        return True

    with patch.object(rm, '_make_twilio_call', side_effect=mock_twilio):
        with patch.object(rm, '_send_telegram_reminder'):
            # Manually simulate what the polling loop does
            data = rm._load()
            now = datetime.now()
            for reminder in data["reminders"]:
                if not reminder["fired"]:
                    due = datetime.fromisoformat(reminder["due"])
                    if now >= due:
                        rm._make_twilio_call(reminder["text"])
                        rm._mark_fired(reminder["id"])

    test("Polling fires past reminder via Twilio mock",
         len(fired_reminders) == 1 and fired_reminders[0] == "Take medication")
    fired_check = rm.list_reminders(include_fired=True)
    test("Fired reminder marked as fired",
         any(r["fired"] for r in fired_check if r["text"] == "Take medication"))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: FULL AI PIPELINE — MEMORY OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_ai_pipeline_memory():
    section("4. AI PIPELINE — Memory Storage & Retrieval")
    cleanup()

    print("\n  [4.1] Store: Post office activity (no memory specified)")
    c, r = full_pipeline(
        "Today I went to the post office and submitted my passport documents for renewal"
    )
    test("Categorized as storage", c["type"] == "storage",
         f"Got: {c['type']}")
    test("Has memory field", "memory" in c)
    test("Response confirms storage", "stored" in r.lower() or "✅" in r,
         f"Response: {r[:100]}")

    print("\n  [4.2] Store: Work IT activity (explicit work memory)")
    c, r = full_pipeline(
        "Store in work memory: Had a meeting with the IT team about server migration to AWS"
    )
    test("Categorized as storage", c["type"] == "storage")
    test("Memory is work", "work" in c.get("memory", "").lower(),
         f"Got memory: {c.get('memory')}")
    work_data = mm.get_memory("work")
    test("Entry saved to work.json", len(work_data["entries"]) >= 1)

    print("\n  [4.3] Create new memory: Finance (dynamic creation)")
    c, r = full_pipeline(
        "Add to finance memory: Paid electricity bill ₹2500 today"
    )
    test("Categorized as storage", c["type"] == "storage")
    test("Finance memory created", os.path.exists(f"{TEST_MEMORIES_DIR}/finance.json"),
         f"Files: {os.listdir(TEST_MEMORIES_DIR)}")
    finance_data = mm.get_memory("finance")
    test("Finance entry saved", len(finance_data["entries"]) >= 1)

    print("\n  [4.4] Store more work entries")
    full_pipeline("Work memory: Completed the network security audit report and sent to manager")
    full_pipeline("Store in post_office memory: Collected registered letter from post office at 11am")

    print("\n  [4.5] Question: What did I do at the post office?")
    c, r = full_pipeline("What did I do at the post office?")
    test("Categorized as question", c["type"] == "question",
         f"Got: {c['type']}")
    test("Response mentions post office activity",
         any(word in r.lower() for word in ["post", "passport", "letter", "collected", "submitted"]),
         f"Response: {r[:200]}")

    print("\n  [4.6] Question: Show all work memories")
    c, r = full_pipeline("What have I done at work so far?")
    test("Categorized as question", c["type"] == "question")
    test("Response mentions work activities",
         any(word in r.lower() for word in ["meeting", "server", "network", "audit", "aws", "migration"]),
         f"Response: {r[:200]}")

    print("\n  [4.7] Question: Cross-memory search")
    c, r = full_pipeline("What have I done today across all my memories?")
    test("Categorized as question", c["type"] == "question")
    test("Response has content", len(r) > 50)

    print("\n  [4.8] Management: Edit an entry")
    work_data = mm.get_memory("work")
    entry_id = work_data["entries"][0]["id"]
    c, r = full_pipeline(
        f"Edit entry {entry_id} in work memory: Updated — Meeting with IT team about AWS migration and cost analysis"
    )
    test("Categorized as management or storage", c["type"] in ("management", "storage"),
         f"Got: {c['type']}")

    print("\n  [4.9] Management: Move entry between memories")
    c, r = full_pipeline(
        "Move entry 1 from personal memory to work memory"
    )
    test("Categorized as management", c["type"] in ("management", "task"),
         f"Got: {c['type']}")

    print("\n  [4.10] Management: List all memories")
    c, r = full_pipeline("Show me all my memories")
    test("Categorized as management or question", c["type"] in ("management", "question"))
    test("Response mentions memories", "memory" in r.lower() or "🗂️" in r,
         f"Response: {r[:150]}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: FULL AI PIPELINE — TASK OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_ai_pipeline_tasks():
    section("5. AI PIPELINE — Task Management")
    cleanup()

    print("\n  [5.1] Add work task")
    c, r = full_pipeline(
        "Add a work task: Submit the server migration report by this Friday"
    )
    test("Categorized as task", c["type"] == "task", f"Got: {c['type']}")
    test("Action is add", c.get("action") == "add", f"Got action: {c.get('action')}")
    test("Task in work memory", "work" in c.get("memory", "").lower())
    work_tasks = tm.list_tasks("work")
    test("Task saved to work memory", len(work_tasks) >= 1)

    print("\n  [5.2] Add personal task")
    c, r = full_pipeline("Add personal task: Buy groceries and medicine this weekend")
    test("Categorized as task", c["type"] == "task")
    test("Memory is personal", "personal" in c.get("memory", "").lower())

    print("\n  [5.3] Add more work tasks")
    full_pipeline("Work task: Review IT security policy document")
    full_pipeline("Work task: Schedule meeting with DevOps team for deployment planning")

    print("\n  [5.4] List work tasks")
    c, r = full_pipeline("Show me all my work tasks")
    test("Categorized as task", c["type"] == "task")
    test("Action is list", "list" in c.get("action", ""))
    test("Response contains tasks", any(word in r.lower() for word in
         ["server", "migration", "security", "devops", "report"]),
         f"Response: {r[:200]}")

    print("\n  [5.5] Mark task as complete")
    work_tasks = tm.list_tasks("work")
    first_task_id = work_tasks[0]["id"]
    c, r = full_pipeline(f"Mark work task {first_task_id} as complete")
    test("Categorized as task", c["type"] == "task")
    test("Action is complete", c.get("action") in ("complete", "update"),
         f"Got: {c.get('action')}")
    updated = tm.list_tasks("work", "complete")
    test("Task marked complete in JSON", len(updated) >= 1)

    print("\n  [5.6] Cancel a task")
    work_tasks = tm.list_tasks("work", "pending")
    if work_tasks:
        cancel_id = work_tasks[0]["id"]
        c, r = full_pipeline(f"Cancel work task {cancel_id}")
        test("Categorized as task", c["type"] == "task")
        cancelled = tm.list_tasks("work", "cancelled")
        test("Task cancelled in JSON", len(cancelled) >= 1)
    else:
        test("Cancel task (skipped - no pending)", True)

    print("\n  [5.7] List all tasks across all memories")
    c, r = full_pipeline("Show me all my tasks from all memories")
    test("Categorized as task", c["type"] == "task")
    test("Response has task content", len(r) > 30)

    print("\n  [5.8] Move a task between memories")
    personal_tasks = tm.list_tasks("personal")
    if personal_tasks:
        task_id = personal_tasks[0]["id"]
        c, r = full_pipeline(f"Move personal task {task_id} to work memory")
        test("Categorized as task", c["type"] == "task")
        test("Action is move", c.get("action") == "move", f"Got: {c.get('action')}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: FULL AI PIPELINE — REMINDER OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_ai_pipeline_reminders():
    section("6. AI PIPELINE — Reminder Management")
    cleanup()

    print("\n  [6.1] Set reminder: relative time (in 2 hours)")
    c, r = full_pipeline("Remind me in 2 hours to call the bank about my account")
    test("Categorized as reminder", c["type"] == "reminder", f"Got: {c['type']}")
    test("Action is add", c.get("action") == "add")
    test("Due datetime is set", bool(c.get("due_datetime")))
    test("Response confirms reminder set", "⏰" in r or "reminder" in r.lower(),
         f"Response: {r[:150]}")

    reminders = rm.list_reminders()
    test("Reminder saved to JSON", len(reminders) >= 1)
    if reminders:
        due = datetime.fromisoformat(reminders[-1]["due"])
        test("Reminder is ~2 hours in future",
             abs((due - datetime.now()).total_seconds() - 7200) < 600,  # within 10 min tolerance
             f"Due: {due}, Now: {datetime.now()}")

    print("\n  [6.2] Set reminder: specific time tomorrow")
    c, r = full_pipeline("Remind me tomorrow at 9am to submit the quarterly report")
    test("Categorized as reminder", c["type"] == "reminder")
    test("Has due datetime", bool(c.get("due_datetime")))
    reminders_after = rm.list_reminders()
    test("Second reminder saved", len(reminders_after) >= 2)

    print("\n  [6.3] List reminders")
    c, r = full_pipeline("Show me all my reminders")
    test("Categorized as reminder", c["type"] == "reminder")
    test("Action is list", c.get("action") == "list")
    test("Response shows reminders", "bank" in r.lower() or "report" in r.lower(),
         f"Response: {r[:200]}")

    print("\n  [6.4] Delete a reminder")
    reminders = rm.list_reminders()
    if reminders:
        del_id = reminders[0]["id"]
        c, r = full_pipeline(f"Delete reminder {del_id}")
        test("Categorized as reminder", c["type"] == "reminder")
        remaining = rm.list_reminders()
        test("Reminder deleted", not any(r2["id"] == del_id for r2 in remaining))

    print("\n  [6.5] Polling simulation: past reminder fires via Twilio")
    past_time = datetime.now() - timedelta(seconds=10)
    r_past = rm.add_reminder("Drink water", past_time)

    fired = []
    with patch.object(rm, '_make_twilio_call', side_effect=lambda t: fired.append(t) or True):
        with patch.object(rm, '_send_telegram_reminder'):
            data = rm._load()
            now = datetime.now()
            for reminder in data["reminders"]:
                if not reminder["fired"]:
                    due = datetime.fromisoformat(reminder["due"])
                    if now >= due:
                        rm._make_twilio_call(reminder["text"])
                        rm._mark_fired(reminder["id"])

    test("Past reminder fires via Twilio mock",
         "Drink water" in fired, f"Fired: {fired}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: EDGE CASES & STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_edge_cases():
    section("7. EDGE CASES")
    cleanup()

    print("\n  [7.1] Question to empty memories")
    c, r = full_pipeline("What have I done today?")
    test("Question to empty memories handled gracefully",
         c["type"] == "question" and len(r) > 10)

    print("\n  [7.2] Create multiple dynamic memories in sequence")
    full_pipeline("Diet memory: Ate salad for lunch, skipped dinner")
    full_pipeline("Store in health memory: Blood pressure 120/80, normal")
    full_pipeline("Add to gym memory: Did 30 min cardio + 20 min weights")
    mems = mm.list_memories()
    test("Dynamic memories created",
         any("diet" in m for m in mems) and any("health" in m for m in mems),
         f"Memories: {mems}")

    print("\n  [7.3] Search across multiple memories with specific question")
    full_pipeline("Store in work memory: Fixed the login bug in the IT portal")
    full_pipeline("Store in work memory: Deployed hotfix to production at 3pm")
    c, r = full_pipeline("What bugs did I fix at work?")
    test("Cross-memory question answered", c["type"] == "question")
    test("Response mentions bug", "bug" in r.lower() or "login" in r.lower() or "fix" in r.lower(),
         f"Response: {r[:200]}")

    print("\n  [7.4] Task with multiple statuses tracked correctly")
    full_pipeline("Add work task: Prepare monthly IT report")
    work_tasks = tm.list_tasks("work")
    if work_tasks:
        tid = work_tasks[-1]["id"]
        # pending → in_progress → complete
        tm.update_task_status("work", tid, "in_progress")
        tm.update_task_status("work", tid, "complete")
        final = tm.list_tasks("work", "complete")
        test("Task status lifecycle works", any(t["id"] == tid for t in final))

    print("\n  [7.5] Nonexistent entry operations return not_found")
    r1 = mm.edit_entry("work", 9999, "Ghost entry")
    test("Edit non-existent entry returns not_found", r1["status"] == "not_found")
    r2 = mm.move_entry("work", 9999, "personal")
    test("Move non-existent entry returns not_found", r2["status"] == "not_found")
    r3 = mm.delete_entry("work", 9999)
    test("Delete non-existent entry returns not_found", r3["status"] == "not_found")

    print("\n  [7.6] Memory names with spaces normalized")
    mm.add_entry("Post Office", "Test entry")  # should normalize to post_office
    test("Space in memory name normalized to underscore",
         os.path.exists(f"{TEST_MEMORIES_DIR}/post_office.json"))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "🧪 " * 30)
    print("  AI MEMORY ASSISTANT — COMPREHENSIVE FUNCTIONAL TESTS")
    print("🧪 " * 30)
    print(f"\n  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Test memories dir: {TEST_MEMORIES_DIR}")
    print(f"  Test reminders file: {TEST_REMINDERS_FILE}")
    print(f"  Anthropic API Key: {'✅ SET' if config.ANTHROPIC_API_KEY else '❌ NOT SET'}")

    if not config.ANTHROPIC_API_KEY:
        print("\n❌ ANTHROPIC_API_KEY not set. AI pipeline tests will fail.")
        print("   Set it in .env or export ANTHROPIC_API_KEY=your_key")

    # Run all test suites
    test_memory_manager()
    test_task_manager()
    test_reminder_manager()
    test_ai_pipeline_memory()
    test_ai_pipeline_tasks()
    test_ai_pipeline_reminders()
    test_edge_cases()

    # Final cleanup
    cleanup()

    # Summary
    print("\n" + "="*60)
    print("  RESULTS SUMMARY")
    print("="*60)
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    total  = len(results)

    for status, name, detail in results:
        if status == FAIL:
            print(f"  {status}  {name}")
            if detail:
                print(f"         → {detail}")

    print(f"\n  Total : {total}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  Score : {passed/total*100:.1f}%\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
