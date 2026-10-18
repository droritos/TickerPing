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
