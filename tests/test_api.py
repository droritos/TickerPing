import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app import app

client = TestClient(app)

def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"

def test_get_alarms_empty():
    with patch("app.alarm_manager.get_alarms", return_value=[]):
        response = client.get("/api/alarms")
        assert response.status_code == 200
        assert response.json() == []

def test_add_and_delete_alarm():
    mock_alarm = {
        "id": "test1234",
        "ticker": "AAPL",
        "target_price": 250.0,
        "direction": "ABOVE",
        "note": "Test",
        "active": True,
        "triggered": False
    }
    with patch("app.alarm_manager.add_alarm", return_value=mock_alarm):
        response = client.post("/api/alarms", json={
            "ticker": "AAPL",
            "target_price": 250.0,
            "direction": "ABOVE",
            "note": "Test"
        })
        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"

    with patch("app.alarm_manager.delete_alarm", return_value=True):
        response = client.delete("/api/alarms/test1234")
        assert response.status_code == 200
        assert response.json()["success"] is True

def test_test_whatsapp_endpoint():
    with patch("app.CallMeBotWhatsAppNotifier.send_raw_message", return_value=True):
        response = client.post("/api/test-whatsapp", json={
            "phone": "+1234567890",
            "apikey": "testkey"
        })
        assert response.status_code == 200
        assert response.json()["success"] is True

def test_test_telegram_endpoint():
    with patch("app.TelegramNotifier.send_raw_message", return_value=True):
        response = client.post("/api/test-telegram", json={
            "bot_token": "fake_token",
            "chat_id": "123456"
        })
        assert response.status_code == 200
        assert response.json()["success"] is True
