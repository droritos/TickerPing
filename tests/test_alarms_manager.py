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
