import os
import tempfile
import pytest
from alarms_manager import AlarmManager

@pytest.fixture
def temp_storage():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_alarm_manager_crud(temp_storage):
    mgr = AlarmManager(storage_path=temp_storage)
    assert mgr.get_alarms() == []

    # Add alarm
    alarm = mgr.add_alarm(ticker="aapl", target_price=250.50, direction="ABOVE", note="Test alarm")
    assert alarm["ticker"] == "AAPL"
    assert alarm["target_price"] == 250.50
    assert alarm["direction"] == "ABOVE"
    assert alarm["active"] is True
    assert alarm["triggered"] is False
    assert alarm["note"] == "Test alarm"

    # Get alarms
    alarms = mgr.get_alarms()
    assert len(alarms) == 1
    assert alarms[0]["id"] == alarm["id"]

    # Mark triggered
    assert mgr.mark_triggered(alarm["id"], trigger_price=251.00) is True
    updated = mgr.get_alarm(alarm["id"])
    assert updated["triggered"] is True
    assert updated["trigger_price"] == 251.00
    assert updated["last_triggered_at"] is not None

    # Reset alarm
    assert mgr.reset_alarm(alarm["id"]) is True
    reset_item = mgr.get_alarm(alarm["id"])
    assert reset_item["triggered"] is False
    assert reset_item["trigger_price"] is None

    # Toggle active
    assert mgr.toggle_active(alarm["id"]) is True
    toggled = mgr.get_alarm(alarm["id"])
    assert toggled["active"] is False

    # Delete alarm
    assert mgr.delete_alarm(alarm["id"]) is True
    assert mgr.get_alarms() == []

def test_delete_by_ticker(temp_storage):
    mgr = AlarmManager(storage_path=temp_storage)
    mgr.add_alarm("URA", 50.0, "BELOW")
    mgr.add_alarm("ura", 56.0, "BELOW")
    mgr.add_alarm("AAPL", 250.0, "ABOVE")

    assert len(mgr.get_alarms()) == 3
    deleted = mgr.delete_by_ticker("uRa")
    assert deleted == 2
    remaining = mgr.get_alarms()
    assert len(remaining) == 1
    assert remaining[0]["ticker"] == "AAPL"

def test_clear_triggered(temp_storage):
    mgr = AlarmManager(storage_path=temp_storage)
    a1 = mgr.add_alarm("URA", 50.0, "BELOW")
    a2 = mgr.add_alarm("TSLA", 200.0, "BELOW")
    mgr.mark_triggered(a1["id"], 49.0)

    assert len(mgr.get_alarms()) == 2
    cleared = mgr.clear_triggered()
    assert cleared == 1
    remaining = mgr.get_alarms()
    assert len(remaining) == 1
    assert remaining[0]["id"] == a2["id"]

def test_case_insensitive_ids(temp_storage):
    mgr = AlarmManager(storage_path=temp_storage)
    a = mgr.add_alarm("NVDA", 120.0, "ABOVE")
    alarm_id = a["id"]
    upper_id = alarm_id.upper()

    assert mgr.get_alarm(upper_id) is not None
    assert mgr.get_alarm(upper_id)["id"] == alarm_id

    assert mgr.toggle_active(upper_id) is True
    assert mgr.get_alarm(alarm_id)["active"] is False

    assert mgr.delete_alarm(upper_id) is True
    assert mgr.get_alarm(alarm_id) is None

