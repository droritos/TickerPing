from datetime import datetime, timedelta
import pytest
from reminders_manager import parse_reminder_input, ReminderManager


def test_parse_reminder_input_relative_minutes():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("25m Check oven", now=base_time)
    assert due_at == datetime(2026, 10, 18, 14, 25, 0)
    assert text == "Check oven"

    due_at2, text2 = parse_reminder_input("in 10 min take out trash", now=base_time)
    assert due_at2 == datetime(2026, 10, 18, 14, 10, 0)
    assert text2 == "take out trash"


def test_parse_reminder_input_relative_hours():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("2h Laundry", now=base_time)
    assert due_at == datetime(2026, 10, 18, 16, 0, 0)
    assert text == "Laundry"

    due_at2, text2 = parse_reminder_input("1.5h Call mom", now=base_time)
    assert due_at2 == datetime(2026, 10, 18, 15, 30, 0)
    assert text2 == "Call mom"


def test_parse_reminder_input_time_today_and_tomorrow():
    # If time is later today
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("18:30 Call doctor", now=base_time)
    assert due_at == datetime(2026, 10, 18, 18, 30, 0)
    assert text == "Call doctor"

    # If time has already passed today -> schedule for tomorrow
    due_at_past, text_past = parse_reminder_input("09:00 Morning standup", now=base_time)
    assert due_at_past == datetime(2026, 10, 19, 9, 0, 0)
    assert text_past == "Morning standup"


def test_parse_reminder_input_tomorrow():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("tomorrow 09:00 Buy groceries", now=base_time)
    assert due_at == datetime(2026, 10, 19, 9, 0, 0)
    assert text == "Buy groceries"

    due_at2, text2 = parse_reminder_input("tomorrow Clean desk", now=base_time)
    assert due_at2 == datetime(2026, 10, 19, 9, 0, 0)
    assert text2 == "Clean desk"


def test_parse_reminder_input_calendar_date():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    # Day/Month with time
    due_at, text = parse_reminder_input("18/11 19:30 Wedding anniversary", now=base_time)
    assert due_at == datetime(2026, 11, 18, 19, 30, 0)
    assert text == "Wedding anniversary"

    # Day/Month without time -> default to 09:00
    due_at2, text2 = parse_reminder_input("18/11 Wedding", now=base_time)
    assert due_at2 == datetime(2026, 11, 18, 9, 0, 0)
    assert text2 == "Wedding"


def test_parse_reminder_input_untimed_todo():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("Buy almond milk and coffee", now=base_time)
    assert due_at is None
    assert text == "Buy almond milk and coffee"


def test_reminder_manager_crud(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)

    # 1. Add timed reminder
    due = datetime(2026, 10, 18, 18, 0, 0)
    r1 = mgr.add_reminder("Call accountant", due_at=due, note="Tax docs")
    assert r1["title"] == "Call accountant"
    assert r1["due_at"] == due.isoformat()
    assert r1["completed"] is False
    assert r1["triggered"] is False

    # 2. Add untimed task
    r2 = mgr.add_reminder("Buy notebook")
    assert r2["title"] == "Buy notebook"
    assert r2["due_at"] is None

    # 3. Retrieve active
    active = mgr.get_reminders()
    assert len(active) == 2

    # 4. Mark completed
    assert mgr.mark_completed(r2["id"]) is True
    assert len(mgr.get_reminders(include_completed=False)) == 1
    assert len(mgr.get_reminders(include_completed=True)) == 2

    # 5. Delete reminder
    assert mgr.delete_reminder(r1["id"]) is True
    assert len(mgr.get_reminders(include_completed=True)) == 1


def test_reminder_manager_get_due_reminders(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)

    base = datetime(2026, 10, 18, 15, 0, 0)
    past = base - timedelta(minutes=5)
    future = base + timedelta(minutes=10)

    r_due = mgr.add_reminder("Past task", due_at=past)
    r_future = mgr.add_reminder("Future task", due_at=future)
    mgr.add_reminder("Untimed task")

    due_list = mgr.get_due_reminders(now=base)
    assert len(due_list) == 1
    assert due_list[0]["id"] == r_due["id"]

    # Mark triggered
    mgr.mark_triggered(r_due["id"])
    assert len(mgr.get_due_reminders(now=base)) == 0


def test_reminder_manager_snooze(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)

    base = datetime(2026, 10, 18, 15, 0, 0)
    past = base - timedelta(minutes=5)
    r = mgr.add_reminder("Oven alert", due_at=past)
    mgr.mark_triggered(r["id"])

    # Snooze for 10 minutes from base
    snoozed = mgr.snooze_reminder(r["id"], minutes=10, now=base)
    assert snoozed is not None
    assert snoozed["triggered"] is False
    assert snoozed["due_at"] == (base + timedelta(minutes=10)).isoformat()


def test_parse_reminder_input_invalid_time_fallback():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at1, text1 = parse_reminder_input("25:00 Call doctor", now=base_time)
    assert due_at1 is None
    assert text1 == "25:00 Call doctor"

    due_at2, text2 = parse_reminder_input("tomorrow 99:99 Meeting", now=base_time)
    assert due_at2 is None
    assert text2 == "tomorrow 99:99 Meeting"


def test_reminder_manager_concurrent_adds(tmp_path):
    import concurrent.futures

    storage = str(tmp_path / "concurrent_reminders.json")
    mgr = ReminderManager(storage_path=storage)

    num_threads = 10
    items_per_thread = 5

    def worker(thread_idx):
        for i in range(items_per_thread):
            mgr.add_reminder(f"Task from thread {thread_idx} item {i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, t) for t in range(num_threads)]
        concurrent.futures.wait(futures)

    reminders = mgr.get_reminders(include_completed=True)
    assert len(reminders) == num_threads * items_per_thread
    titles = {r["title"] for r in reminders}
    assert len(titles) == num_threads * items_per_thread


def test_parse_reminder_input_singular_units():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("in 1 hour call mom", now=base_time)
    assert due_at == datetime(2026, 10, 18, 15, 0, 0)
    assert text == "call mom"

    due_at2, text2 = parse_reminder_input("1 minute check oven", now=base_time)
    assert due_at2 == datetime(2026, 10, 18, 14, 1, 0)
    assert text2 == "check oven"


def test_parse_reminder_input_non_calendar_fallthrough():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    for text_input in ["3.5 star review", "5-6 apples to buy", "1/2 cup sugar"]:
        due_at, text = parse_reminder_input(text_input, now=base_time)
        assert due_at is None
        assert text == text_input


def test_parse_reminder_input_ampm():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("8:30pm dinner", now=base_time)
    assert due_at == datetime(2026, 10, 18, 20, 30, 0)
    assert text == "dinner"

    due_at2, text2 = parse_reminder_input("10:15am meeting", now=base_time)
    # 10:15am has passed today at 14:00, so tomorrow 10:15
    assert due_at2 == datetime(2026, 10, 19, 10, 15, 0)
    assert text2 == "meeting"


def test_reminder_manager_get_reminder(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)
    r = mgr.add_reminder("Buy milk")
    found = mgr.get_reminder(r["id"])
    assert found is not None
    assert found["title"] == "Buy milk"

    # Case insensitive lookup
    assert mgr.get_reminder(r["id"].upper()) is not None

    # Not found
    assert mgr.get_reminder("nonexistent") is None


def test_reminder_manager_snooze_resets_completed(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)
    base = datetime(2026, 10, 18, 15, 0, 0)
    r = mgr.add_reminder("Task", due_at=base)
    mgr.mark_completed(r["id"])
    assert mgr.get_reminder(r["id"])["completed"] is True

    snoozed = mgr.snooze_reminder(r["id"], minutes=15, now=base)
    assert snoozed["completed"] is False
    assert snoozed["completed_at"] is None


def test_reminder_manager_mark_triggered_timestamp(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)
    base = datetime(2026, 10, 18, 15, 0, 0)
    r = mgr.add_reminder("Alert", due_at=base)
    assert r["last_triggered_at"] is None

    mgr.mark_triggered(r["id"])
    updated = mgr.get_reminder(r["id"])
    assert updated["triggered"] is True
    assert updated["last_triggered_at"] is not None


def test_reminder_manager_title_fallback(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)
    r = mgr.add_reminder("   ")
    assert r["title"] == "Reminder"


def test_reminder_manager_data_loss_prevention(tmp_path):
    import os
    storage = str(tmp_path / "corrupted_reminders.json")
    with open(storage, "w", encoding="utf-8") as f:
        f.write("{this is not valid json")

    mgr = ReminderManager(storage_path=storage)
    with pytest.raises(IOError):
        mgr.get_reminders()

    # Backup file should have been created
    bak_path = f"{storage}.bak"
    assert os.path.exists(bak_path)
    with open(bak_path, "r", encoding="utf-8") as f:
        assert f.read() == "{this is not valid json"

    # Mutating operation must also raise IOError and NOT wipe file
    with pytest.raises(IOError):
        mgr.add_reminder("New item")

    with open(storage, "r", encoding="utf-8") as f:
        assert f.read() == "{this is not valid json"


def test_parse_reminder_input_time_at_end():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Jerusalem")
    base_time = datetime(2026, 10, 19, 10, 0, 0, tzinfo=tz)

    due, text = parse_reminder_input("take cake 17:45", now=base_time)
    assert due == datetime(2026, 10, 19, 17, 45, 0, tzinfo=tz)
    assert text == "take cake"

    due2, text2 = parse_reminder_input("take cake at 17:45", now=base_time)
    assert due2 == datetime(2026, 10, 19, 17, 45, 0, tzinfo=tz)
    assert text2 == "take cake"

    due3, text3 = parse_reminder_input("take cake 17:00", now=base_time)
    assert due3 == datetime(2026, 10, 19, 17, 0, 0, tzinfo=tz)
    assert text3 == "take cake"

    due4, text4 = parse_reminder_input("take cake 17", now=base_time)
    assert due4 == datetime(2026, 10, 19, 17, 0, 0, tzinfo=tz)
    assert text4 == "take cake"

    due5, text5 = parse_reminder_input("take cake at 17", now=base_time)
    assert due5 == datetime(2026, 10, 19, 17, 0, 0, tzinfo=tz)
    assert text5 == "take cake"


def test_parse_reminder_input_relative_at_end():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Jerusalem")
    base_time = datetime(2026, 10, 19, 10, 0, 0, tzinfo=tz)

    due, text = parse_reminder_input("Check oven in 25m", now=base_time)
    assert due == datetime(2026, 10, 19, 10, 25, 0, tzinfo=tz)
    assert text == "Check oven"

    due2, text2 = parse_reminder_input("Check oven 25m", now=base_time)
    assert due2 == datetime(2026, 10, 19, 10, 25, 0, tzinfo=tz)
    assert text2 == "Check oven"

    due3, text3 = parse_reminder_input("Laundry in 2h", now=base_time)
    assert due3 == datetime(2026, 10, 19, 12, 0, 0, tzinfo=tz)
    assert text3 == "Laundry"


def test_parse_reminder_input_tomorrow_at_end():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Jerusalem")
    base_time = datetime(2026, 10, 19, 10, 0, 0, tzinfo=tz)

    due, text = parse_reminder_input("Meeting tomorrow 09:00", now=base_time)
    assert due == datetime(2026, 10, 20, 9, 0, 0, tzinfo=tz)
    assert text == "Meeting"

    due2, text2 = parse_reminder_input("Meeting tomorrow at 9:00", now=base_time)
    assert due2 == datetime(2026, 10, 20, 9, 0, 0, tzinfo=tz)
    assert text2 == "Meeting"

    due3, text3 = parse_reminder_input("Buy milk tomorrow", now=base_time)
    assert due3 == datetime(2026, 10, 20, 9, 0, 0, tzinfo=tz)
    assert text3 == "Buy milk"


def test_parse_reminder_input_calendar_at_end():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Jerusalem")
    base_time = datetime(2026, 10, 19, 10, 0, 0, tzinfo=tz)

    due, text = parse_reminder_input("Wedding 18/11 19:30", now=base_time)
    # November in Israel is UTC+2 (standard winter time)
    assert due.day == 18 and due.month == 11 and due.hour == 19 and due.minute == 30
    assert text == "Wedding"

    due2, text2 = parse_reminder_input("Wedding on 18/11 at 19:30", now=base_time)
    assert due2.day == 18 and due2.month == 11 and due2.hour == 19 and due2.minute == 30
    assert text2 == "Wedding"

    due3, text3 = parse_reminder_input("Wedding 18/11", now=base_time)
    assert due3.day == 18 and due3.month == 11 and due3.hour == 9 and due3.minute == 0
    assert text3 == "Wedding"


def test_get_bot_timezone(monkeypatch):
    from reminders_manager import get_bot_timezone
    monkeypatch.delenv("BOT_TIMEZONE", raising=False)
    monkeypatch.delenv("TZ", raising=False)
    assert str(get_bot_timezone()) == "Asia/Jerusalem"

    monkeypatch.setenv("BOT_TIMEZONE", "America/New_York")
    assert str(get_bot_timezone()) == "America/New_York"

