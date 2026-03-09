"""
test_local.py
Tests all local logic (memory, task, reminder managers) without needing API keys.
Run: python test_local.py
"""

import os
import sys
import json
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch

# Point to test dirs BEFORE any imports touch the real dirs
TEST_MEMORIES_DIR = "test_memories"
TEST_REMINDERS_FILE = "test_reminders.json"

# Fake out config entirely
import types
fake_config = types.ModuleType("config")
fake_config.MEMORIES_DIR    = TEST_MEMORIES_DIR
fake_config.REMINDERS_FILE  = TEST_REMINDERS_FILE
fake_config.ANTHROPIC_API_KEY = "test"
fake_config.CATEGORIZER_MODEL = "test"
fake_config.BRAIN_MODEL = "test"
fake_config.TWILIO_ACCOUNT_SID  = "test"
fake_config.TWILIO_AUTH_TOKEN   = "test"
fake_config.TWILIO_FROM_NUMBER  = "+10000000000"
fake_config.YOUR_PHONE_NUMBER   = "+10000000001"
fake_config.YOUR_TELEGRAM_CHAT_ID = "12345"
fake_config.REMINDER_POLL_INTERVAL = 30
sys.modules["config"] = fake_config

import memory_manager as mm
import task_manager as tm
import reminder_manager as rm

mm.MEMORIES_DIR = TEST_MEMORIES_DIR
rm.REMINDERS_FILE = TEST_REMINDERS_FILE

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def test(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    mark = "✅" if condition else "❌"
    print(f"    {mark}  {name}")
    if detail and not condition:
        print(f"         → {detail}")

def section(title):
    print(f"\n{'═'*64}")
    print(f"  {title}")
    print(f"{'═'*64}")

def cleanup():
    if os.path.exists(TEST_MEMORIES_DIR):
        shutil.rmtree(TEST_MEMORIES_DIR)
    if os.path.exists(TEST_REMINDERS_FILE):
        os.remove(TEST_REMINDERS_FILE)


# ══════════════════════════════════════════════════════════════════════════════
# 1. MEMORY MANAGER
# ══════════════════════════════════════════════════════════════════════════════

def run_memory_tests():
    section("1. MEMORY MANAGER")
    cleanup()

    # 1.1 Create memory
    mm.create_memory("work")
    test("1.1  Create work memory", os.path.exists(f"{TEST_MEMORIES_DIR}/work.json"))

    # 1.2 Add entries
    e1 = mm.add_entry("work", "Had a meeting about server migration")
    e2 = mm.add_entry("work", "Submitted server access request to admin")
    test("1.2  Add entry 1 gets id=1", e1["id"] == 1)
    test("1.3  Add entry 2 gets id=2", e2["id"] == 2)

    # 1.4 Verify contents
    data = mm.get_memory("work")
    test("1.4  Memory has 2 entries", len(data["entries"]) == 2)

    # 1.5 Edit entry
    result = mm.edit_entry("work", 1, "Had a meeting about network upgrade")
    test("1.5  Edit returns edited", result["status"] == "edited")
    data = mm.get_memory("work")
    test("1.6  Entry content updated", data["entries"][0]["content"] == "Had a meeting about network upgrade")
    test("1.7  edited_at timestamp set", "edited_at" in data["entries"][0])

    # 1.8 Move entry to another memory
    mm.create_memory("personal")
    move = mm.move_entry("work", 2, "personal")
    test("1.8  Move returns moved", move["status"] == "moved")
    work_after  = mm.get_memory("work")
    pers_after  = mm.get_memory("personal")
    test("1.9  Entry removed from work", len(work_after["entries"]) == 1)
    test("1.10 Entry exists in personal", len(pers_after["entries"]) == 1)
    test("1.11 Moved content matches original",
         pers_after["entries"][0]["content"] == "Submitted server access request to admin")

    # 1.12 Delete entry
    del_e = mm.delete_entry("work", 1)
    test("1.12 Delete entry returns deleted", del_e["status"] == "deleted")
    work_empty = mm.get_memory("work")
    test("1.13 Work memory now has 0 entries", len(work_empty["entries"]) == 0)

    # 1.14 Dynamic memory creation (just by adding an entry)
    mm.add_entry("finance", "Paid electricity bill ₹2500")
    test("1.14 Dynamic finance memory created on first add",
         os.path.exists(f"{TEST_MEMORIES_DIR}/finance.json"))
    finance = mm.get_memory("finance")
    test("1.15 Finance entry saved correctly",
         "₹2500" in finance["entries"][0]["content"])

    # 1.16 List memories
    mems = mm.list_memories()
    test("1.16 All 3 memories listed",
         set(mems) >= {"work", "personal", "finance"},
         f"Got: {mems}")

    # 1.17 Add more and verify IDs are sequential per memory
    mm.add_entry("finance", "Mutual fund SIP ₹5000 deducted")
    mm.add_entry("finance", "Received salary ₹65000")
    fin = mm.get_memory("finance")
    ids = [e["id"] for e in fin["entries"]]
    test("1.17 Finance entry IDs sequential", ids == [1, 2, 3])

    # 1.18 Cross-memory search
    mm.add_entry("work", "Completed database migration to PostgreSQL")
    mm.add_entry("work", "Database backup completed successfully")
    results_search = mm.search_memory("work", "database")
    test("1.18 Search within memory returns 2 results", len(results_search) == 2)
    results_none = mm.search_memory("work", "pizza")
    test("1.19 Search with no match returns empty", len(results_none) == 0)

    # 1.20 Get all entries across memories
    all_data = mm.get_all_entries_across_memories()
    test("1.20 Cross-memory fetch has all 3 memories",
         set(all_data.keys()) >= {"work", "personal", "finance"})

    # 1.21 Delete entire memory
    del_mem = mm.delete_memory("finance")
    test("1.21 Delete memory returns deleted", del_mem["status"] == "deleted")
    test("1.22 Finance file removed", not os.path.exists(f"{TEST_MEMORIES_DIR}/finance.json"))
    mems_after = mm.list_memories()
    test("1.23 Finance no longer in memory list", "finance" not in mems_after)

    # 1.24 Delete non-existent memory
    bad = mm.delete_memory("doesnotexist")
    test("1.24 Delete nonexistent memory returns not_found", bad["status"] == "not_found")

    # 1.25 Edit non-existent entry
    bad_edit = mm.edit_entry("work", 999, "ghost")
    test("1.25 Edit nonexistent entry returns not_found", bad_edit["status"] == "not_found")

    # 1.26 Move non-existent entry
    bad_move = mm.move_entry("work", 999, "personal")
    test("1.26 Move nonexistent entry returns not_found", bad_move["status"] == "not_found")

    # 1.27 Memory name normalisation (spaces → underscores)
    mm.add_entry("Post Office", "Collected registered letter")
    test("1.27 Space in name normalized to underscore",
         os.path.exists(f"{TEST_MEMORIES_DIR}/post_office.json"))

    # 1.28 Memory name normalisation (uppercase → lowercase)
    mm.add_entry("Finance", "Test uppercase")
    test("1.28 Uppercase normalized to lowercase",
         os.path.exists(f"{TEST_MEMORIES_DIR}/finance.json"))


# ══════════════════════════════════════════════════════════════════════════════
# 2. TASK MANAGER
# ══════════════════════════════════════════════════════════════════════════════

def run_task_tests():
    section("2. TASK MANAGER")
    cleanup()

    # 2.1 Add tasks
    t1 = tm.add_task("work", "Submit server migration report by Friday")
    t2 = tm.add_task("work", "Review IT security policy")
    t3 = tm.add_task("work", "Schedule DevOps team meeting")
    t4 = tm.add_task("personal", "Buy groceries and medicines")
    t5 = tm.add_task("personal", "Book flight ticket", due="2025-02-15")

    test("2.1  Work task 1 created pending", t1["status"] == "pending" and t1["id"] == 1)
    test("2.2  Work task 2 created", t2["id"] == 2)
    test("2.3  Work task 3 created", t3["id"] == 3)
    test("2.4  Personal task 1 id=1 (separate per memory)", t4["id"] == 1)
    test("2.5  Task with due date saved", t5["due"] == "2025-02-15")

    # 2.6 List tasks
    work_tasks = tm.list_tasks("work")
    test("2.6  List 3 work tasks", len(work_tasks) == 3)
    pers_tasks = tm.list_tasks("personal")
    test("2.7  List 2 personal tasks", len(pers_tasks) == 2)

    # 2.8 Status update: pending → complete
    result = tm.update_task_status("work", 1, "complete")
    test("2.8  Mark task 1 complete", result["status"] == "updated")
    test("2.9  Task status is complete", result["task"]["status"] == "complete")
    test("2.10 updated_at timestamp set", result["task"]["updated_at"] is not None)

    # 2.11 Status: pending → in_progress
    result = tm.update_task_status("work", 2, "in_progress")
    test("2.11 Mark task 2 in_progress", result["task"]["status"] == "in_progress")

    # 2.12 Status: pending → cancelled
    result = tm.update_task_status("work", 3, "cancelled")
    test("2.12 Mark task 3 cancelled", result["task"]["status"] == "cancelled")

    # 2.13 Filter by status
    pending_tasks   = tm.list_tasks("work", "pending")
    complete_tasks  = tm.list_tasks("work", "complete")
    inprog_tasks    = tm.list_tasks("work", "in_progress")
    cancelled_tasks = tm.list_tasks("work", "cancelled")

    test("2.13 No pending work tasks", len(pending_tasks) == 0)
    test("2.14 1 complete work task", len(complete_tasks) == 1)
    test("2.15 1 in_progress work task", len(inprog_tasks) == 1)
    test("2.16 1 cancelled work task", len(cancelled_tasks) == 1)

    # 2.17 Edit task description
    result = tm.edit_task("personal", 1, "Buy groceries, medicines and vitamins")
    test("2.17 Edit task description", result["status"] == "edited")
    test("2.18 Task description updated",
         result["task"]["description"] == "Buy groceries, medicines and vitamins")

    # 2.19 Move task between memories
    move = tm.move_task("personal", 2, "work")
    test("2.19 Move task personal→work", move["status"] == "moved")
    pers_after = tm.list_tasks("personal")
    work_after = tm.list_tasks("work")
    test("2.20 Personal task count decremented", len(pers_after) == 1)
    test("2.21 Work task count incremented", any(
        t["description"] == "Book flight ticket" for t in work_after
    ))

    # 2.22 moved_from metadata
    moved_task = next(t for t in work_after if t.get("moved_from") == "personal")
    test("2.22 Moved task has moved_from field", moved_task["moved_from"] == "personal")

    # 2.23 Delete task
    del_result = tm.delete_task("personal", 1)
    test("2.23 Delete task returns deleted", del_result["status"] == "deleted")
    pers_final = tm.list_tasks("personal")
    test("2.24 Personal tasks now empty", len(pers_final) == 0)

    # 2.25 Error: invalid status
    bad = tm.update_task_status("work", 1, "flying")
    test("2.25 Invalid status returns error", bad["status"] == "error")

    # 2.26 Error: nonexistent task
    bad2 = tm.update_task_status("work", 9999, "complete")
    test("2.26 Update nonexistent task returns not_found", bad2["status"] == "not_found")

    # 2.27 Get all tasks across all memories
    all_tasks = tm.get_all_tasks()
    test("2.27 get_all_tasks returns dict with work key", "work" in all_tasks)

    # 2.28 Task complete lifecycle: pending → in_progress → complete
    t_new = tm.add_task("work", "Deploy hotfix to production")
    tm.update_task_status("work", t_new["id"], "in_progress")
    final_result = tm.update_task_status("work", t_new["id"], "complete")
    test("2.28 Full lifecycle pending→in_progress→complete works",
         final_result["task"]["status"] == "complete")


# ══════════════════════════════════════════════════════════════════════════════
# 3. REMINDER MANAGER
# ══════════════════════════════════════════════════════════════════════════════

def run_reminder_tests():
    section("3. REMINDER MANAGER")
    cleanup()

    now = datetime.now()

    # 3.1 Add reminders
    future1 = now + timedelta(hours=2)
    future2 = now + timedelta(days=1)
    future3 = now + timedelta(minutes=30)

    r1 = rm.add_reminder("Call the bank", future1)
    r2 = rm.add_reminder("Doctor appointment", future2)
    r3 = rm.add_reminder("Take medication", future3)

    test("3.1  Reminder 1 created with id=1", r1["id"] == 1)
    test("3.2  Reminder 2 has correct text", r2["text"] == "Doctor appointment")
    test("3.3  Reminder 3 not fired by default", not r3["fired"])
    test("3.4  Reminders file created", os.path.exists(TEST_REMINDERS_FILE))

    # 3.5 List
    active = rm.list_reminders()
    test("3.5  List shows 3 active reminders", len(active) == 3)

    # 3.6 Mark fired
    rm._mark_fired(r1["id"])
    active_after = rm.list_reminders()
    test("3.6  After firing r1, 2 active remain", len(active_after) == 2)
    test("3.7  Fired reminder excluded from active list",
         all(r["id"] != r1["id"] for r in active_after))

    # 3.8 List including fired
    all_r = rm.list_reminders(include_fired=True)
    test("3.8  Include fired shows all 3", len(all_r) == 3)
    fired_r = next(r for r in all_r if r["id"] == r1["id"])
    test("3.9  Fired reminder has fired=True", fired_r["fired"] is True)
    test("3.10 Fired reminder has fired_at timestamp", "fired_at" in fired_r)

    # 3.11 Delete reminder
    del_r = rm.delete_reminder(r2["id"])
    test("3.11 Delete returns deleted", del_r["status"] == "deleted")
    active_final = rm.list_reminders()
    test("3.12 Only 1 active reminder remains after delete", len(active_final) == 1)
    test("3.13 Remaining is medication reminder",
         active_final[0]["text"] == "Take medication")

    # 3.14 Delete non-existent
    bad = rm.delete_reminder(9999)
    test("3.14 Delete nonexistent returns not_found", bad["status"] == "not_found")

    # 3.15 Polling: past reminder fires via Twilio mock
    past = now - timedelta(seconds=30)
    r_past = rm.add_reminder("Drink water", past)
    test("3.15 Past reminder added with id=4", r_past["id"] == 4)

    twilio_calls = []
    telegram_notifs = []

    def mock_twilio(text):
        twilio_calls.append(text)
        return True

    def mock_telegram(bot, chat_id, reminder):
        telegram_notifs.append(reminder["text"])

    with patch.object(rm, '_make_twilio_call', side_effect=mock_twilio):
        with patch.object(rm, '_send_telegram_reminder', side_effect=mock_telegram):
            # Simulate poll loop iteration
            data = rm._load()
            check_now = datetime.now()
            for reminder in data["reminders"]:
                if not reminder["fired"]:
                    due = datetime.fromisoformat(reminder["due"])
                    if check_now >= due:
                        rm._make_twilio_call(reminder["text"])
                        rm._send_telegram_reminder(None, "12345", reminder)
                        rm._mark_fired(reminder["id"])

    test("3.16 Polling fires past reminder via Twilio",
         "Drink water" in twilio_calls, f"Calls: {twilio_calls}")
    test("3.17 Telegram notified for same reminder",
         "Drink water" in telegram_notifs)
    test("3.18 Future reminders NOT fired",
         "Take medication" not in twilio_calls)

    final_active = rm.list_reminders()
    test("3.19 Past reminder marked fired after poll",
         all(r["text"] != "Drink water" for r in final_active))
    test("3.20 Future reminder still active after poll",
         any(r["text"] == "Take medication" for r in final_active))

    # 3.21 Multiple reminders: only expired ones fire
    r_exp1 = rm.add_reminder("Morning pills", now - timedelta(minutes=2))
    r_exp2 = rm.add_reminder("Evening pills", now - timedelta(minutes=1))
    r_fut  = rm.add_reminder("Night pills", now + timedelta(hours=8))

    twilio_calls2 = []
    with patch.object(rm, '_make_twilio_call', side_effect=lambda t: twilio_calls2.append(t) or True):
        with patch.object(rm, '_send_telegram_reminder'):
            data = rm._load()
            check_now = datetime.now()
            for reminder in data["reminders"]:
                if not reminder["fired"]:
                    due = datetime.fromisoformat(reminder["due"])
                    if check_now >= due:
                        rm._make_twilio_call(reminder["text"])
                        rm._mark_fired(reminder["id"])

    test("3.21 Both expired reminders fired",
         "Morning pills" in twilio_calls2 and "Evening pills" in twilio_calls2,
         f"Fired: {twilio_calls2}")
    test("3.22 Future reminder NOT fired",
         "Night pills" not in twilio_calls2)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "🧪 " * 32)
    print("  AI MEMORY ASSISTANT — LOCAL LOGIC TESTS (no API key needed)")
    print("🧪 " * 32)
    print(f"\n  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    run_memory_tests()
    run_task_tests()
    run_reminder_tests()

    cleanup()

    # Summary
    print(f"\n{'═'*64}")
    print("  FINAL SUMMARY")
    print(f"{'═'*64}")

    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    total  = len(results)

    if failed:
        print("\n  FAILURES:")
        for status, name, detail in results:
            if status == FAIL:
                print(f"    ❌  {name}")
                if detail:
                    print(f"         → {detail}")

    print(f"\n  Total   : {total}")
    print(f"  ✅ Passed : {passed}")
    print(f"  ❌ Failed : {failed}")
    print(f"  Score   : {passed/total*100:.1f}%\n")

    sys.exit(0 if failed == 0 else 1)
