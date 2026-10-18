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

def test_cloud_runner_poll_callback_query(tmp_path):
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
            {
                "update_id": 52,
                "callback_query": {
                    "id": "cb_1",
                    "data": "del:123",
                    "message": {"chat": {"id": 12345}}
                }
            }
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        had_updates = runner.poll_telegram_updates()
        assert had_updates is True
        runner.cmd_handler.handle_callback_query.assert_called_once()
        runner.state_manager.set_last_offset.assert_called_with(52)


def test_git_sync_changes_skipped_when_not_github_actions(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    runner = CloudRunner("tok", "123", alarms_file, state_file)

    with patch("subprocess.run") as mock_run:
        runner.git_sync_changes()
        mock_run.assert_not_called()


def test_git_sync_changes_executes_when_github_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    runner = CloudRunner("tok", "123", alarms_file, state_file)

    mock_diff = MagicMock()
    mock_diff.returncode = 1  # Indicates diff exists

    with patch("subprocess.run", return_value=mock_diff) as mock_run:
        runner.git_sync_changes()
        assert mock_run.call_count >= 3


def test_cloud_runner_evaluates_due_reminders(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        reminders_path=reminders_file
    )

    runner.send_telegram_msg = MagicMock()
    runner.git_sync_changes = MagicMock()
    runner.reminder_manager = MagicMock()
    runner.reminder_manager.get_due_reminders.return_value = [
        {"id": "rem_1", "title": "Check the oven", "due_at": "2026-10-18T14:30:00"}
    ]

    runner.evaluate_due_reminders()

    runner.send_telegram_msg.assert_called_once()
    call_args = runner.send_telegram_msg.call_args
    assert "Check the oven" in call_args[0][1]
    assert "reply_markup" in call_args[1]
    markup = call_args[1]["reply_markup"]
    assert "inline_keyboard" in markup
    # Check buttons
    buttons = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
    assert "task_done:rem_1" in buttons
    assert "task_snooze:rem_1:10" in buttons
    assert "task_snooze:rem_1:60" in buttons

    runner.reminder_manager.mark_triggered.assert_called_with("rem_1")
    runner.git_sync_changes.assert_called_once()


def test_git_sync_changes_includes_reminders(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")
    runner = CloudRunner("tok", "123", alarms_file, state_file, reminders_path=reminders_file)

    mock_diff = MagicMock()
    mock_diff.returncode = 1

    with patch("subprocess.run", return_value=mock_diff) as mock_run:
        runner.git_sync_changes()
        # Verify git add call includes reminders_file
        add_call = [call for call in mock_run.call_args_list if call[0][0][:2] == ["git", "add"]][0]
        assert reminders_file in add_call[0][0]


def test_cloud_runner_run_calls_evaluate_due_reminders(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        reminders_path=reminders_file,
        max_runtime_seconds=1,
        loop_interval_seconds=1
    )

    with patch.object(runner, "poll_telegram_updates"), \
         patch.object(runner, "evaluate_active_alarms"), \
         patch.object(runner, "evaluate_due_reminders") as mock_eval:
        runner.run()
        assert mock_eval.call_count >= 1


def test_cloud_runner_reminders_html_escaping_and_notes(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        reminders_path=reminders_file
    )

    runner.send_telegram_msg = MagicMock(return_value=True)
    runner.git_sync_changes = MagicMock()
    runner.reminder_manager = MagicMock()
    runner.reminder_manager.get_due_reminders.return_value = [
        {
            "id": "rem_special",
            "title": "Buy milk & bread <organic>",
            "due_at": "2026-10-18T14:30:00",
            "note": "Don't forget & check <expiry>"
        }
    ]

    runner.evaluate_due_reminders()

    runner.send_telegram_msg.assert_called_once()
    msg_text = runner.send_telegram_msg.call_args[0][1]
    assert "Buy milk &amp; bread &lt;organic&gt;" in msg_text
    assert "&amp; check &lt;expiry&gt;" in msg_text


def test_cloud_runner_reminders_batched_git_sync(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        reminders_path=reminders_file
    )

    runner.send_telegram_msg = MagicMock(return_value=True)
    runner.git_sync_changes = MagicMock()
    runner.reminder_manager = MagicMock()
    runner.reminder_manager.get_due_reminders.return_value = [
        {"id": "r1", "title": "Task 1", "due_at": "2026-10-18T14:30:00"},
        {"id": "r2", "title": "Task 2", "due_at": "2026-10-18T14:35:00"}
    ]

    runner.evaluate_due_reminders()

    assert runner.send_telegram_msg.call_count == 2
    assert runner.reminder_manager.mark_triggered.call_count == 2
    runner.git_sync_changes.assert_called_once()


def test_cloud_runner_send_telegram_msg_failure_does_not_mark_triggered(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        reminders_path=reminders_file
    )

    runner.send_telegram_msg = MagicMock(return_value=False)
    runner.git_sync_changes = MagicMock()
    runner.reminder_manager = MagicMock()
    runner.reminder_manager.get_due_reminders.return_value = [
        {"id": "r_fail", "title": "Task Fail", "due_at": "2026-10-18T14:30:00"}
    ]

    runner.evaluate_due_reminders()

    runner.send_telegram_msg.assert_called_once()
    runner.reminder_manager.mark_triggered.assert_not_called()
    runner.git_sync_changes.assert_not_called()


def test_cloud_runner_runtime_seconds_cast_to_int(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    runner = CloudRunner("tok", "123", alarms_file, state_file, max_runtime_seconds="120", loop_interval_seconds="30")
    assert isinstance(runner.max_runtime_seconds, int)
    assert runner.max_runtime_seconds == 120
    assert isinstance(runner.loop_interval_seconds, int)
    assert runner.loop_interval_seconds == 30


def test_send_telegram_msg_checks_status_code_and_ok(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    runner = CloudRunner("tok", "123", alarms_file, state_file)

    mock_ok = MagicMock()
    mock_ok.status_code = 200
    mock_ok.json.return_value = {"ok": True}

    with patch("requests.post", return_value=mock_ok):
        assert runner.send_telegram_msg("123", "test") is True

    mock_fail = MagicMock()
    mock_fail.status_code = 400
    mock_fail.json.return_value = {"ok": False, "description": "Bad Request"}
    mock_fail.text = "Bad Request"

    with patch("requests.post", return_value=mock_fail):
        assert runner.send_telegram_msg("123", "test") is False


def test_cloud_runner_reminders_item_exception_resilience(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        reminders_path=reminders_file
    )

    runner.git_sync_changes = MagicMock()
    runner.reminder_manager = MagicMock()
    runner.reminder_manager.get_due_reminders.return_value = [
        {"id": "r_bad", "title": None, "due_at": "2026-10-18T14:30:00"},
        {"id": "r_good", "title": "Good Task", "due_at": "2026-10-18T14:35:00"}
    ]

    # Make send_telegram_msg raise on r_bad, succeed on r_good
    def fake_send(chat_id, text, reply_markup=None):
        if "None" in text or "r_bad" in str(reply_markup):
            raise RuntimeError("Telegram network glitch")
        return True

    runner.send_telegram_msg = MagicMock(side_effect=fake_send)
    runner.evaluate_due_reminders()

    # r_good should still have succeeded and marked triggered
    runner.reminder_manager.mark_triggered.assert_called_once_with("r_good")
    runner.git_sync_changes.assert_called_once()






