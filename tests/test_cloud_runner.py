import pytest
from unittest.mock import MagicMock, patch
from cloud_runner import CloudRunner

def test_cloud_runner_initialization(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    
    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        max_runtime_seconds=10,
        loop_interval_seconds=2
    )
    assert runner.token == "test_token"
    assert runner.chat_id == "12345"
    assert runner.max_runtime_seconds == 10
    assert runner.loop_interval_seconds == 2

def test_cloud_runner_poll_telegram_updates(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        max_runtime_seconds=1,
        loop_interval_seconds=1
    )

    runner.cmd_handler = MagicMock()
    runner.state_manager = MagicMock()
    runner.state_manager.get_last_offset.return_value = 50

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": [
            {"update_id": 51, "message": {"chat": {"id": 12345}, "text": "/price AAPL"}}
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        runner.poll_telegram_updates()
        runner.cmd_handler.handle_update.assert_called_once()
        runner.state_manager.set_last_offset.assert_called_with(51)

def test_cloud_runner_run_exits_within_budget(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        max_runtime_seconds=1,
        loop_interval_seconds=1
    )

    with patch.object(runner, "poll_telegram_updates"), patch.object(runner, "evaluate_active_alarms"):
        cycles = runner.run()
        assert cycles >= 1
